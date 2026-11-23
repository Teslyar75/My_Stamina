"""Фейковый симулятор терминальных тренажёров: учебный вывод команд.

Один класс обслуживает Linux- и PowerShell-тренажёр: игрок печатает команду,
симулятор отвечает «боевым» выводом. Состояние небольшое, но живое — права и
владелец файлов, текущий каталог, архивы, crontab, переменные окружения, —
поэтому `ls -la` после `chmod` показывает новые права, а `crontab -l` отдаёт
то, что записали строкой раньше. Конвейеры (`|`) и цепочки (`&&`) считаются
по-настоящему: вывод команды слева уходит в команду справа.

Никаких процессов и файлов на диске симулятор не трогает: это учебный стенд.
"""

from __future__ import annotations

import json
import re
# Готовое содержимое файлов, которые читают миссии.
FILE_CONTENTS: dict[str, list[str]] = {
    "/var/log/syslog": [
        "[2026-11-21 10:00:00] Module boot ok",
        "[2026-11-21 10:00:02] orion.service: started",
        "[2026-11-21 10:00:12] ERROR radio: handshake timeout",
        "[2026-11-21 10:00:15] lab: constellation loaded (1247 entities)",
        "[2026-11-21 10:00:20] WARNING disk: /var/lib/docker 78% used",
        "[2026-11-21 10:01:00] backup: snapshot ship-2026-11-21 taken",
    ],
    "/var/log/auth.log": [
        "Nov 21 10:00:01 ship sshd[812]: Accepted publickey for orion from 10.0.0.5",
        "Nov 21 10:02:11 ship sudo[913]: orion : TTY=pts/0 ; PWD=/home/orion ; COMMAND=/bin/systemctl restart orion",
        "Nov 21 10:05:44 ship sshd[1201]: Failed password for invalid user admin from 10.0.0.9",
    ],
    "/var/log/app.log": [
        "2026-11-21T10:00:00 INFO  app started",
        "2026-11-21T10:00:04 INFO  connected to db: base:5432",
        "2026-11-21T10:00:09 ERROR request /health timeout",
        "2026-11-21T10:00:10 INFO  listening on 0.0.0.0:8080",
    ],
    "/etc/os-release": [
        'PRETTY_NAME="StaminaOS 3.9 (orbital)"',
        'NAME="StaminaOS"',
        "VERSION_ID=3.9",
        'HOME_URL="https://stamina.local"',
    ],
    "/etc/hostname": ["ship"],
    "/home/orion/.bashrc": [
        "# ~/.bashrc — настройки оболочки",
        "export EDITOR=vim",
        "alias ll='ls -la'",
    ],
}

# Каталоги: имя → строки `ls -la` (права, ссылки, владелец, размер, дата, имя).
DIR_CONTENTS: dict[str, list[tuple[str, str, int, str]]] = {
    "/var/log": [
        ("-rw-r-----", "root:adm", 18432, "syslog"),
        ("-rw-r-----", "root:adm", 2048, "auth.log"),
        ("-rw-r--r--", "orion:ship", 8192, "app.log"),
        ("-rw-r--r--", "root:root", 0, "bootstrap.log"),
    ],
    "/home/orion": [
        ("drwxr-xr-x", "orion:ship", 4096, "ship"),
        ("-rw-r--r--", "orion:ship", 256, ".bashrc"),
        ("-rw-r--r--", "orion:ship", 512, "notes.md"),
    ],
    "/tmp": [
        ("-rw-r--r--", "orion:ship", 4096, "logs.tar.gz"),
    ],
    "/etc": [
        ("-rw-r--r--", "root:root", 512, "os-release"),
        ("-rw-r--r--", "root:root", 12, "hostname"),
        ("drwxr-xr-x", "root:root", 4096, "systemd"),
    ],
}


def _split_outside_quotes(line: str, sep: str) -> list[str]:
    """Разбить строку по разделителю, не трогая кавычки: `echo "a|b" | wc -l`."""
    parts: list[str] = []
    buf: list[str] = []
    quote = ""
    i = 0
    while i < len(line):
        ch = line[i]
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = ""
            i += 1
            continue
        if ch in "\"'":
            quote = ch
            buf.append(ch)
            i += 1
            continue
        if line.startswith(sep, i):
            parts.append("".join(buf))
            buf = []
            i += len(sep)
            continue
        buf.append(ch)
        i += 1
    parts.append("".join(buf))
    return [p.strip() for p in parts if p.strip()]


class FakeTerminalSimulator:
    """Отвечает на команды Linux и PowerShell, помнит учебное состояние."""

    HOME = "/home/orion"

    def __init__(self) -> None:
        self.last_output: str = ""
        self.calls: list[str] = []
        self.cwd: str = self.HOME
        # путь → [права, владелец]
        self.meta: dict[str, list[str]] = {
            "/var/log/syslog": ["-rw-r-----", "root:adm"],
            "/var/log/auth.log": ["-rw-r-----", "root:adm"],
            "/var/log/app.log": ["-rw-r--r--", "orion:ship"],
            "/etc/os-release": ["-rw-r--r--", "root:root"],
            "/home/orion/.bashrc": ["-rw-r--r--", "orion:ship"],
        }
        self.archives: dict[str, str] = {}
        self.crontab: list[str] = []
        self.env: dict[str, str] = {"SHIP_MODE": "patrol", "LOG_LEVEL": "info"}
        self.variables: dict[str, str] = {"Pilot": "orion", "Mission": "patrol"}
        self.ps_modules: list[tuple[str, str]] = [
            ("Microsoft.PowerShell.Management", "7.4"),
            ("Microsoft.PowerShell.Utility", "7.4"),
            ("PSReadLine", "2.3"),
        ]

    # ─── точка входа ────────────────────────────────────────────────────
    def execute(self, cmd: str) -> tuple[str, int]:
        cmd_clean = cmd.strip()
        self.calls.append(cmd_clean)
        out = self._run(cmd_clean)
        self.last_output = out
        return out, 0 if not out.startswith("bash: ") else 127

    def _run(self, line: str) -> str:
        """Цепочки `a && b`, `a ; b` и конвейеры `a | b`."""
        if not line:
            return ""
        chunks = _split_outside_quotes(line, "&&")
        if len(chunks) == 1:
            chunks = _split_outside_quotes(line, ";")
        if len(chunks) > 1:
            out = [self._run(part) for part in chunks]
            return "\n".join(piece for piece in out if piece)
        segments = _split_outside_quotes(line, "|")
        text = self._answer(segments[0])
        for segment in segments[1:]:
            text = self._pipe(text, segment)
        return text

    # ─── базовая команда ────────────────────────────────────────────────
    def _answer(self, cmd: str) -> str:
        lowered = cmd.lower().strip()
        if not lowered:
            return ""
        words = cmd.split()
        head = words[0].lower()
        args = words[1:]

        # ── PowerShell (команды с глаголом и дефисом) ───────────────────
        if head.startswith(("get-", "set-", "new-", "remove-", "copy-", "move-",
                            "start-", "stop-", "restart-", "test-", "convertto-",
                            "convertfrom-", "export-", "import-", "select-",
                            "where-", "sort-", "measure-", "foreach-", "out-",
                            "format-", "invoke-", "write-", "resolve-", "clear-")):
            return self._powershell(head, args)
        if lowered.startswith("$psversiontable"):
            return ("Name                           Value\n"
                    "----                           -----\n"
                    "PSVersion                      7.4.1\n"
                    "PSEdition                      Core\n"
                    "OS                             Windows 11\n")
        if lowered.startswith("$env:"):
            return self._ps_env(lowered)

        # ── Linux ───────────────────────────────────────────────────────
        return self._linux(head, args, cmd)

    # ─── Linux ──────────────────────────────────────────────────────────
    def _linux(self, head: str, args: list[str], cmd: str) -> str:
        if head == "pwd":
            return self.cwd + "\n"
        if head == "whoami":
            return "orion\n"
        if head == "hostname":
            return "ship\n"
        if head == "id":
            return "uid=1000(orion) gid=1000(ship) groups=1000(ship),27(sudo),999(docker)\n"
        if head == "groups":
            return "ship sudo docker\n"
        if head == "uname":
            return "Linux ship 6.8.0-orbital #1 SMP PREEMPT_DYNAMIC x86_64 GNU/Linux\n"
        if head == "uptime":
            return " 10:01:12 up 14 days,  3:22,  1 user,  load average: 0.14, 0.09, 0.08\n"
        if head == "date":
            return "Sat Nov 21 10:01:12 UTC 2026\n"
        if head == "ls":
            return self._ls(args)
        if head == "cd":
            return self._cd(args)
        if head in ("cat", "less", "more", "bat"):
            return self._cat(args)
        if head == "head":
            return self._head_tail(args, last=False)
        if head == "tail":
            return self._head_tail(args, last=True)
        if head == "grep":
            return self._grep(args)
        if head == "find":
            return self._find(args)
        if head in ("wc",):
            return self._wc(args)
        if head == "ps":
            return ("USER       PID  %CPU  %MEM  STAT  COMMAND\n"
                    "root         1  0.0   0.1  Ss    /sbin/init\n"
                    "root       412  0.1   0.2  Ssl   /usr/bin/dockerd\n"
                    "orion     1234  0.3   0.4  Ss    bash\n"
                    "orion     2048  1.2   2.1  Sl    python -m stamina\n")
        if head == "top":
            return ("top - 10:01:12 up 14 days,  load average: 0.14, 0.09, 0.08\n"
                    "Tasks: 118 total,   1 running, 117 sleeping\n"
                    "PID USER      %CPU  %MEM  COMMAND\n"
                    "2048 orion      1.2   2.1  python -m stamina\n")
        if head == "kill":
            return self._kill(args)
        if head == "nice":
            return self._answer(" ".join(args)) if args else ""
        if head == "df":
            return ("Filesystem      Size  Used Avail Use% Mounted on\n"
                    "/dev/sda1       120G   78G   32G  71% /\n"
                    "/dev/sdb1       480G  374G   82G  83% /var/lib/docker\n")
        if head == "du":
            return "356M\t/var/lib/docker\n"
        if head == "free":
            return ("               total        used        free\n"
                    "Mem:            15Gi        7,1Gi       4,2Gi\n"
                    "Swap:          2,0Gi          0B       2,0Gi\n")
        if head == "ss":
            return ("State   Recv-Q  Local Address:Port  Peer Address:Port  Process\n"
                    "LISTEN  0       128    0.0.0.0:8080           0.0.0.0:*      users:((\"python\",pid=2048))\n"
                    "LISTEN  0       128    0.0.0.0:22             0.0.0.0:*      users:((\"sshd\",pid=812))\n")
        if head == "netstat":
            return self._linux("ss", args, cmd)
        if head == "ping":
            target = args[-1] if args else "8.8.8.8"
            return (f"PING {target} 56(84) bytes of data.\n"
                    f"64 bytes from {target}: icmp_seq=1 ttl=117 time=12.4 ms\n"
                    f"64 bytes from {target}: icmp_seq=2 ttl=117 time=11.9 ms\n"
                    "--- 4 packets transmitted, 4 received, 0% packet loss ---\n")
        if head in ("curl", "wget"):
            if "-o" in args and "/dev/null" in " ".join(args):
                return "200\n"
            return "hello from ship/lab\n"
        if head in ("systemctl", "service"):
            return self._systemctl(args)
        if head == "journalctl":
            return self._journalctl(args)
        if head == "tar":
            return self._tar(args)
        if head in ("gzip", "gunzip"):
            return ""
        if head == "chmod":
            return self._chmod(args)
        if head == "chown":
            return self._chown(args)
        if head in ("crontab",):
            return self._crontab(args)
        if head == "ssh":
            return self._ssh(args)
        if head in ("scp", "rsync"):
            return "logs.tar.gz               100%  4096     4.0MB/s   00:00\n"
        if head == "ssh-keygen":
            return ("Generating public/private ed25519 key pair.\n"
                    "Your identification has been saved in /home/orion/.ssh/id_ed25519\n"
                    "Your public key has been saved in /home/orion/.ssh/id_ed25519.pub\n")
        if head in ("apt", "apt-get", "dnf", "yum", "pacman"):
            return self._packages(head, args)
        if head == "sudo":
            rest = " ".join(args)
            return self._answer(rest) if rest else "usage: sudo command\n"
        if head == "export":
            return self._export(cmd)
        if head == "env":
            return "".join(f"{k}={v}\n" for k, v in self.env.items())
        if head == "echo":
            return self._echo(cmd)
        if head in ("mkdir", "touch", "rm", "rmdir", "mv", "cp", "ln"):
            return self._fs_change(head, args)
        if head in ("sort", "uniq", "cut", "tr"):
            return ""
        if head in ("nano", "vim", "vi", "less"):
            return "Редактор в тренажёре не запускается — читайте файл через cat.\n"
        if head == "man":
            return f"NAME\n    {args[0] if args else 'command'} — справка в тренажёре не открывается,\n    смотрите учебник F2.\n"
        if head == "history":
            return "".join(f"  {i}  {c}\n" for i, c in enumerate(self.calls[-10:], 1))
        if head == "clear":
            return ""
        if head == "sleep":
            return ""
        if head in ("ip", "ifconfig"):
            return ("2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500\n"
                    "    inet 10.0.0.5/24 brd 10.0.0.255 scope global eth0\n")
        if head in ("dig", "nslookup", "host"):
            return "ship.example.com has address 10.0.0.5\n"
        return "Запрос принят: {0}\n".format(cmd)

    # -- файлы -----------------------------------------------------------
    def _resolve(self, path: str) -> str:
        if not path:
            return self.cwd
        if path.startswith("~"):
            path = self.HOME + path[1:]
        if not path.startswith("/"):
            base = "" if self.cwd == "/" else self.cwd
            path = f"{base}/{path}"
        # схлопнуть `//`, `/./` и `..`
        parts: list[str] = []
        for piece in path.split("/"):
            if piece in ("", "."):
                continue
            if piece == "..":
                if parts:
                    parts.pop()
                continue
            parts.append(piece)
        return "/" + "/".join(parts)

    def _meta(self, path: str, default_dir: bool = False) -> list[str]:
        if path in self.meta:
            return self.meta[path]
        return ["drwxr-xr-x", "root:root"] if default_dir else ["-rw-r--r--", "orion:ship"]

    def _ls(self, args: list[str]) -> str:
        flags = " ".join(a for a in args if a.startswith("-"))
        paths = [a for a in args if not a.startswith("-")]
        target = self._resolve(paths[0]) if paths else self.cwd
        long_form = "l" in flags or "-la" in flags or "-al" in flags
        lines: list[str] = []
        if long_form:
            lines.append("total 48")
        if target in DIR_CONTENTS:
            entries = DIR_CONTENTS[target]
        elif target in FILE_CONTENTS or target in self.meta:
            path_meta = self._meta(target)
            entries = [(path_meta[0], path_meta[1], len("\n".join(FILE_CONTENTS.get(target, [""]))),
                        target.rsplit("/", 1)[-1])]
        else:
            return f"ls: cannot access '{paths[0] if paths else target}': No such file or directory\n"
        show_hidden = "a" in flags.replace("-", "")
        for mode, owner, size, name in entries:
            if name.startswith(".") and not show_hidden:
                continue
            if long_form:
                lines.append(f"{mode} 1 {owner:<11} {size:>6} Nov 21 10:00 {name}")
            else:
                lines.append(name)
        return "\n".join(lines) + "\n"

    def _cd(self, args: list[str]) -> str:
        target = self._resolve(args[0]) if args else self.HOME
        if target in DIR_CONTENTS or target == self.HOME or target == "/":
            self.cwd = target
            return ""
        if target in FILE_CONTENTS:
            return f"bash: cd: {args[0]}: Not a directory\n"
        return f"bash: cd: {args[0]}: No such file or directory\n"

    def _cat(self, args: list[str]) -> str:
        paths = [a for a in args if not a.startswith("-")]
        if not paths:
            return ""
        path = self._resolve(paths[0])
        if path in FILE_CONTENTS:
            return "\n".join(FILE_CONTENTS[path]) + "\n"
        return f"cat: {paths[0]}: No such file or directory\n"

    def _head_tail(self, args: list[str], last: bool) -> str:
        count = 10
        paths: list[str] = []
        i = 0
        while i < len(args):
            arg = args[i]
            if arg in ("-n", "-c") and i + 1 < len(args):
                try:
                    count = int(args[i + 1])
                except ValueError:
                    count = 10
                i += 2
                continue
            if re.fullmatch(r"-\d+", arg):
                count = int(arg[1:])
            elif not arg.startswith("-"):
                paths.append(arg)
            i += 1
        if not paths:
            return ""
        path = self._resolve(paths[0])
        lines = FILE_CONTENTS.get(path)
        if lines is None:
            return f"{'tail' if last else 'head'}: cannot open '{paths[0]}' for reading: No such file\n"
        chunk = lines[-count:] if last else lines[:count]
        return "\n".join(chunk) + "\n"

    def _grep(self, args: list[str]) -> str:
        flags = [a for a in args if a.startswith("-")]
        rest = [a for a in args if not a.startswith("-")]
        if not rest:
            return ""
        pattern = rest[0].strip("\"'")
        paths = rest[1:]
        text_lines: list[str] = []
        if paths:
            for path in paths:
                resolved = self._resolve(path)
                if resolved in FILE_CONTENTS:
                    text_lines.extend(FILE_CONTENTS[resolved])
                elif resolved in self.meta:
                    text_lines.extend(FILE_CONTENTS.get(resolved, []))
                else:
                    return f"grep: {path}: No such file or directory\n"
        else:
            for resolved in FILE_CONTENTS:
                text_lines.extend(FILE_CONTENTS[resolved])
        ignore_case = any("i" in f for f in flags)
        number = any("n" in f for f in flags)
        invert = any("v" in f for f in flags)
        needle = pattern.lower() if ignore_case else pattern
        hits = []
        for line in text_lines:
            haystack = line.lower() if ignore_case else line
            matched = needle in haystack
            if matched != invert:
                hits.append(line)
        if not hits:
            return ""
        if number:
            return "".join(f"{i}:{line}\n" for i, line in enumerate(hits, 1))
        return "\n".join(hits) + "\n"

    def _find(self, args: list[str]) -> str:
        start = self._resolve(args[0]) if args and not args[0].startswith("-") else "."
        name = "*.log"
        if "-name" in args:
            name = args[args.index("-name") + 1].strip("\"'")
        pattern = re.escape(name).replace(r"\*", ".*")
        found: list[str] = []
        for path in list(FILE_CONTENTS) + list(DIR_CONTENTS):
            if start not in ("/", ".") and not path.startswith(start):
                continue
            if re.fullmatch(pattern, path.rsplit("/", 1)[-1]):
                found.append(path)
        return "\n".join(sorted(found)) + "\n" if found else ""

    def _wc(self, args: list[str]) -> str:
        paths = [a for a in args if not a.startswith("-")]
        flags = " ".join(a for a in args if a.startswith("-"))
        if not paths:
            return ""
        path = self._resolve(paths[0])
        lines = FILE_CONTENTS.get(path, [])
        words = sum(len(line.split()) for line in lines)
        if "l" in flags:
            return f"{len(lines)}\n"
        if "w" in flags:
            return f"{words}\n"
        return f"{len(lines):>6} {words:>6} {sum(len(x) for x in lines):>6} {paths[0]}\n"

    # -- процессы --------------------------------------------------------
    def _kill(self, args: list[str]) -> str:
        numbers = [a for a in args if a.isdigit()]
        if not numbers:
            return "kill: usage: kill [-s sigspec | -n signum] pid\n"
        return ""

    # -- службы и журналы ------------------------------------------------
    def _systemctl(self, args: list[str]) -> str:
        if not args:
            return "Usage: systemctl [start|stop|restart|status|enable|list-units]\n"
        verb = args[0]
        unit = args[1] if len(args) > 1 else "orion"
        if not unit.endswith(".service"):
            unit = f"{unit}.service"
        if verb == "status":
            return (f"● {unit} - Stamina {unit.replace('.service', '')} module\n"
                    "     Loaded: loaded (/etc/systemd/system/" + unit + "; enabled)\n"
                    "     Active: active (running) since Sat 2026-11-21 10:00:02 UTC\n"
                    "   Main PID: 2048 (python)\n"
                    "     Memory: 148.2M\n")
        if verb in ("start", "restart", "stop", "enable", "disable", "reload"):
            return ""
        if verb in ("is-active",):
            return "active\n"
        if verb == "list-units":
            return ("UNIT              LOAD   ACTIVE   SUB     DESCRIPTION\n"
                    "orion.service     loaded active   running Stamina orion module\n"
                    "base.service      loaded active   running Postgres base\n"
                    "radio.service     loaded inactive dead    Radio receiver\n"
                    "sshd.service      loaded active   running OpenSSH server\n")
        return ""

    def _journalctl(self, args: list[str]) -> str:
        unit = "orion"
        if "-u" in args:
            unit = args[args.index("-u") + 1]
        count = 10
        if "-n" in args:
            try:
                count = int(args[args.index("-n") + 1])
            except (ValueError, IndexError):
                count = 10
        lines = [
            f"Nov 21 10:00:02 ship systemd[1]: Started {unit}.service.",
            f"Nov 21 10:00:02 ship {unit}[2048]: Neural core initializing...",
            f"Nov 21 10:00:03 ship {unit}[2048]: Agent ready on port 9000",
            f"Nov 21 10:00:12 ship {unit}[2048]: WARNING disk 78% used",
            f"Nov 21 10:01:00 ship {unit}[2048]: heartbeat ok",
        ]
        return "\n".join(lines[-count:]) + "\n"

    # -- архивы и права --------------------------------------------------
    def _tar(self, args: list[str]) -> str:
        flags = ""
        name = ""
        targets: list[str] = []
        i = 0
        while i < len(args):
            arg = args[i]
            if arg.startswith("-") and "f" in arg and not name:
                flags = arg
                if i + 1 < len(args):
                    name = args[i + 1]
                    i += 2
                    continue
            elif arg.startswith("-"):
                flags = arg
            elif arg.endswith(".gz") or arg.endswith(".tar"):
                if not name:
                    name = arg
            else:
                targets.append(arg)
            i += 1
        if "x" in flags:
            return ""
        if "t" in flags:
            return "".join(f"{t.strip('/')}/syslog\n" for t in targets) or "syslog\n"
        if name:
            self.archives[self._resolve(name)] = ", ".join(targets) or "."
        return ""

    def _chmod(self, args: list[str]) -> str:
        values = [a for a in args if not a.startswith("-")]
        if len(values) < 2:
            return "chmod: missing operand\n"
        mode, path = values[0], self._resolve(values[1])
        if not re.fullmatch(r"[0-7]{3,4}", mode):
            return f"chmod: invalid mode: '{mode}'\n"
        digits = mode[-3:]
        def triple(n: int) -> str:
            return ("r" if n & 4 else "-") + ("w" if n & 2 else "-") + ("x" if n & 1 else "-")
        bits = f"-{triple(int(digits[0]))}{triple(int(digits[1]))}{triple(int(digits[2]))}"
        meta = self.meta.setdefault(path, ["-rw-r--r--", "orion:ship"])
        meta[0] = bits
        return ""

    def _chown(self, args: list[str]) -> str:
        values = [a for a in args if not a.startswith("-")]
        if len(values) < 2:
            return "chown: missing operand\n"
        owner, path = values[0], self._resolve(values[1])
        meta = self.meta.setdefault(path, ["-rw-r--r--", "orion:ship"])
        meta[1] = owner
        return ""

    def _crontab(self, args: list[str]) -> str:
        if args and args[0] == "-l":
            if not self.crontab:
                return "no crontab for orion\n"
            return "".join(line + "\n" for line in self.crontab)
        if args and args[0] == "-r":
            self.crontab.clear()
            return ""
        if args and args[0] == "-e":
            return ("Редактор crontab в тренажёре не открывается — "
                    "ставьте задание строкой: echo \"...\" | crontab -\n")
        return ""

    def _ssh(self, args: list[str]) -> str:
        targets = [a for a in args if not a.startswith("-")]
        if not targets:
            return "usage: ssh [user@]host [command]\n"
        host = targets[0]
        command = " ".join(targets[1:]).strip("\"'")
        if command:
            return (f"{command}: up 9 days, 4:11\n"
                    f"{host}: 0.11 0.07 0.05\n")
        return (f"Welcome to StaminaOS 3.9 (orbital) — {host}\n"
                "Last login: Sat Nov 21 09:12:44 from 10.0.0.5\n")

    def _packages(self, head: str, args: list[str]) -> str:
        verb = args[0] if args else "list"
        if verb in ("install", "reinstall"):
            pkg = args[1] if len(args) > 1 else "htop"
            return (f"Reading package lists... Done\n"
                    f"Setting up {pkg} ...\n"
                    f"{pkg} is already the newest version.\n")
        if verb in ("remove", "purge", "erase"):
            return "Removing package ...\n"
        if verb in ("update", "upgrade", "check-update"):
            return "All packages are up to date.\n"
        return "Listing...\nhtop/stable 3.3.0 amd64\n"

    def _export(self, cmd: str) -> str:
        for piece in cmd.split(None)[1:]:
            key, _, value = piece.partition("=")
            if key:
                self.env[key.strip()] = value.strip().strip("\"'")
        return ""

    def _echo(self, cmd: str) -> str:
        text = cmd.split(None, 1)[1] if len(cmd.split(None, 1)) > 1 else ""
        text = text.strip()
        if text.startswith("$"):
            return self.env.get(text[1:].strip(), "") + "\n"
        return text.strip("\"'") + "\n"

    def _fs_change(self, head: str, args: list[str]) -> str:
        values = [a for a in args if not a.startswith("-")]
        if not values:
            return f"{head}: missing operand\n"
        if head in ("mkdir", "touch"):
            path = self._resolve(values[-1])
            if head == "mkdir":
                DIR_CONTENTS.setdefault(path, [])
            else:
                FILE_CONTENTS.setdefault(path, [])
            return ""
        if head in ("rm", "rmdir"):
            path = self._resolve(values[-1])
            FILE_CONTENTS.pop(path, None)
            self.meta.pop(path, None)
            return ""
        return ""

    # ─── PowerShell ─────────────────────────────────────────────────────
    def _powershell(self, head: str, args: list[str]) -> str:
        if head == "get-process":
            return self._ps_get_process(args)
        if head == "get-service":
            return self._ps_get_service(args)
        if head in ("get-content", "gc"):
            return self._ps_get_content(args)
        if head in ("get-childitem", "gci", "dir", "ls"):
            return self._ps_get_childitem(args)
        if head in ("get-location", "gl", "pwd"):
            return ("Path\n----\nC:\\ship\n")
        if head == "set-location":
            return ""
        if head == "get-command":
            return ("CommandType     Name                Version   Source\n"
                    "-----------     ----                -------   ------\n"
                    "Cmdlet          Get-Process         7.4.1     Microsoft.PowerShell.Management\n"
                    "Cmdlet          Get-Service         7.4.1     Microsoft.PowerShell.Management\n"
                    "Application     docker              27.3.1    C:\\Program Files\\Docker\\docker.exe\n")
        if head == "get-help":
            name = args[0] if args else "Get-Process"
            return (f"NAME\n    {name}\n\nSYNOPSIS\n    {name} — справка доступна в учебнике (F2).\n\n"
                    "SYNTAX\n    " + name + " [-Name <string[]>] [-Id <int[]>]\n")
        if head == "get-module":
            return "ModuleType Version  Name\n---------- ------- ----\n" + \
                   "".join(f"Manifest   {v:<8} {n}\n" for n, v in self.ps_modules)
        if head in ("get-psversion", "get-host"):
            return "PSVersion  7.4.1\nPSEdition  Core\nOS         Windows 11\n"
        if head in ("test-netconnection", "tnc"):
            return ("ComputerName           : localhost\n"
                    "RemotePort             : 8080\n"
                    "TcpTestSucceeded       : True\n"
                    "RemoteAddress          : 127.0.0.1\n")
        if head == "get-nettcpconnection":
            return ("LocalAddress  LocalPort  RemoteAddress  RemotePort  State   OwningProcess\n"
                    "------------  ---------  -------------  ----------  ------  -------------\n"
                    "0.0.0.0       8080       0.0.0.0        0           Listen  2048\n")
        if head == "resolve-dnsname":
            name = args[0] if args else "ship.example.com"
            return f"Name              Type   TTL   Section    IPAddress\n----              ----   ---   -------    ---------\n{name}  A      60    Answer     10.0.0.5\n"
        if head in ("start-process", "stop-process", "restart-process"):
            return ""
        if head in ("start-service", "stop-service", "restart-service"):
            name = " ".join(a for a in args if not a.startswith("-")) or "Spooler"
            state = "Stopped" if head == "stop-service" else "Running"
            return f"Status   Name      DisplayName\n------   ----      -----------\n{state:<8} {name:<9} {name}\n"
        if head in ("get-date",):
            return "Saturday, 21 November 2026 10:01:12\n"
        if head in ("get-variable",):
            return ("Name                           Value\n"
                    "----                           -----\n"
                    "Pilot                          orion\n"
                    "Mission                        patrol\n")
        if head in ("set-variable", "new-variable"):
            return ""
        if head in ("set-content", "add-content", "out-file", "clear-content"):
            return ""
        if head in ("copy-item", "move-item", "new-item", "remove-item"):
            return ""
        if head == "select-string":
            pattern = ""
            for arg in args:
                if not arg.startswith("-"):
                    pattern = arg.strip("\"'")
                    break
            return (f"app.log:3:2026-11-21T10:00:09 ERROR request /health timeout\n"
                    if "error" in pattern.lower() else f"app.log:1:2026-11-21T10:00:00 INFO  app started\n")
        if head in ("convertto-json", "convertfrom-json"):
            return ('[\n  {\n    "Name": "orion",\n    "Status": "Running"\n  },\n'
                    '  {\n    "Name": "base",\n    "Status": "Running"\n  }\n]\n')
        if head in ("export-csv", "import-csv"):
            return "Name,Status\norion,Running\nbase,Running\n"
        if head == "write-output" or head == "write-host":
            return " ".join(a for a in args if not a.startswith("-")).strip("\"'") + "\n"
        if head == "out-string" or head == "format-table" or head == "format-list":
            return self._ps_get_process(args)
        if head == "where-object":
            return "  Id Name     CPU(s)\n1234 pwsh     0.03\n"
        if head == "sort-object":
            return "  Id Name     CPU(s)\n5678 svchost 0.11\n1234 pwsh     0.03\n"
        if head == "select-object":
            return "Name     CPU(s)\n----     ------\npwsh     0.03\nsvchost  0.11\n"
        if head == "measure-object":
            return "Count    : 2\nAverage  : 0,07\nSum      : 0,14\nMaximum  : 0,11\nMinimum  : 0,03\n"
        if head == "foreach-object":
            return "pwsh\nsvchost\n"
        return "Запрос принят: {0}\n".format(" ".join([head] + args))

    def _ps_get_process(self, args: list[str]) -> str:
        name = ""
        for i, arg in enumerate(args):
            if arg in ("-Name", "-name") and i + 1 < len(args):
                name = args[i + 1]
            elif not arg.startswith("-") and not name:
                name = arg
        name = name.strip("\"'")
        rows = [("1234", "pwsh", "0.03"), ("5678", "svchost", "0.11"), ("2048", "docker", "0.42")]
        if name:
            rows = [r for r in rows if name.lower() in r[1].lower()] or rows[:1]
        body = "".join(f"{pid:>5} {proc:<8} {cpu:>8}\n" for pid, proc, cpu in rows)
        return "  Id Name     CPU(s)\n" + body

    def _ps_get_service(self, args: list[str]) -> str:
        name = ""
        for i, arg in enumerate(args):
            if arg in ("-Name", "-name") and i + 1 < len(args):
                name = args[i + 1]
            elif not arg.startswith("-") and not name:
                name = arg
        name = name.strip("\"'")
        rows = [("docker", "Running", "docker"), ("Spooler", "Running", "Print Spooler"),
                ("sshd", "Stopped", "OpenSSH SSH Server")]
        if name:
            rows = [r for r in rows if name.lower() in r[0].lower()] or rows[:1]
        body = "".join(f"{status:<10} {svc:<9} {display}\n" for svc, status, display in rows)
        return "Status     Name      DisplayName\n------     ----      -----------\n" + body

    def _ps_get_content(self, args: list[str]) -> str:
        path = ""
        for i, arg in enumerate(args):
            if arg in ("-Path", "-path") and i + 1 < len(args):
                path = args[i + 1]
            elif not arg.startswith("-") and not path:
                path = arg
        tail = 0
        if "-Tail" in args:
            try:
                tail = int(args[args.index("-Tail") + 1])
            except (ValueError, IndexError):
                tail = 10
        path = path.strip("\"'")
        lines = FILE_CONTENTS.get("/var/log/app.log", [])
        if tail:
            lines = lines[-tail:]
        return "\n".join(lines) + "\n"

    def _ps_get_childitem(self, args: list[str]) -> str:
        if "env:" in " ".join(args).lower():
            return "".join(f"{k,-22} {v}\n" for k, v in self.env.items())
        path = ""
        flt = ""
        takes_value = ("-path", "-filter", "-depth", "-name", "-include", "-exclude")
        i = 0
        while i < len(args):
            arg = args[i]
            low = arg.lower()
            if low in takes_value and i + 1 < len(args):
                if low == "-path":
                    path = args[i + 1]
                elif low == "-filter":
                    flt = args[i + 1]
                i += 2
                continue
            if not arg.startswith("-") and not path:
                path = arg
            i += 1
        path = path.strip("\"'") or "C:\\ship"
        rows = [("app.log", "8192"), ("notes.md", "512"), ("docker-compose.yml", "1024")]
        if flt:
            needle = flt.replace("*", "").lower()
            rows = [r for r in rows if needle in r[0].lower()]
        body = "".join(f"{name:<20} {size:>6}\n" for name, size in rows)
        return (f"    Directory: {path}\n\n"
                "Mode    LastWriteTime      Length Name\n"
                "----    -------------      ------ ----\n"
                f"{body}")

    def _ps_env(self, lowered: str) -> str:
        key = lowered[5:].strip()
        if "=" in key:
            name, _, value = key.partition("=")
            self.env[name.upper()] = value.strip("\"'")
            return ""
        return self.env.get(key.upper(), "") + "\n"

    # ─── конвейеры ──────────────────────────────────────────────────────
    def _pipe(self, text: str, segment: str) -> str:
        seg = segment.strip()
        low = seg.lower()
        lines = [line for line in text.split("\n") if line.strip()]

        if low.startswith("wc"):
            if "-l" in low:
                return f"{len(lines)}\n"
            if "-w" in low:
                return f"{sum(len(line.split()) for line in lines)}\n"
            return f"{len(lines)}\n"
        if low.startswith("head"):
            count = self._pipe_count(seg, 10)
            return "\n".join(lines[:count]) + "\n"
        if low.startswith("tail"):
            count = self._pipe_count(seg, 10)
            return "\n".join(lines[-count:]) + "\n"
        if re.match(r"sort(\s|$)", low):
            ordered = sorted(lines)
            if "-u" in low:
                ordered = list(dict.fromkeys(ordered))
            return "\n".join(ordered) + "\n" if ordered else ""
        if low.startswith("uniq"):
            out: list[str] = []
            for line in lines:
                if not out or out[-1].split(" ", 1)[-1] != line:
                    if "-c" in low:
                        out.append(f"      1 {line}")
                    else:
                        out.append(line)
            return "\n".join(out) + "\n" if out else ""
        if low.startswith("grep"):
            pattern = " ".join(seg.split()[1:]).strip("\"'")
            hits = [line for line in lines if pattern.lower() in line.lower()]
            return "\n".join(hits) + "\n" if hits else ""
        if low.startswith("cut"):
            field = 1
            if "-f" in low:
                try:
                    field = int(seg.split("-f")[-1].split()[0])
                except ValueError:
                    field = 1
            out = []
            for line in lines:
                parts = line.split()
                if len(parts) >= field:
                    out.append(parts[field - 1])
            return "\n".join(out) + "\n"
        if low.startswith("tr"):
            return text
        if low.startswith("tee") or low.startswith("xargs"):
            return text
        if low.startswith("crontab"):
            # `echo "…" | crontab -` — записать задание планировщика
            if "-" in seg.split():
                self.crontab = [line for line in lines if line.strip()]
                return ""
            if "-l" in seg.split():
                return "".join(line + "\n" for line in self.crontab)
            return ""
        if low.startswith(("select-object", "select")):
            if "-first" in low:
                count = self._pipe_count(seg, 3)
                return "\n".join(lines[:count]) + "\n"
            if "-property" in low or "-expandproperty" in low:
                key = "-Property" if "-Property" in seg else "-ExpandProperty"
                props = seg.split(key, 1)[1].strip()
                return f"{props}\n{''.join(line.split()[-1] + chr(10) for line in lines)}"
            return "\n".join(lines) + "\n"
        if low.startswith("where-object") or low.startswith("where"):
            numeric = re.search(r"-(?:gt|ge|lt|le)\s+([\d.,]+)", seg)
            if numeric:
                limit = float(numeric.group(1).replace(",", "."))
                greater = "-gt" in low or "-ge" in low
                hits = []
                for line in lines:
                    value = self._row_number(line)
                    if value is None:
                        continue
                    if (value > limit) if greater else (value < limit):
                        hits.append(line)
                return ("\n".join(hits) + "\n") if hits else ""
            words = [w.strip("\"'") for w in re.split(r"\s+", seg) if w.strip("\"'")]
            needle = next((w for w in reversed(words) if not w.startswith("-")), "")
            hits = [line for line in lines if needle.lower() in line.lower()]
            return "\n".join(hits) + "\n" if hits else ""
        if low.startswith("sort-object"):
            descending = "-descending" in low
            words = [w for w in seg.split()[1:] if not w.startswith("-")]
            prop = words[0] if words else "cpu"
            rows = [line for line in lines[1:] if line.strip() and not line.strip().startswith("-")]
            if prop.lower() in ("cpu", "cpu(s)", "ws", "id"):
                key_index = 0 if prop.lower() == "id" else -1
                def sort_key(line: str) -> float:
                    parts = line.split()
                    try:
                        return float(parts[key_index].replace(",", "."))
                    except (ValueError, IndexError):
                        return 0.0
                rows.sort(key=sort_key, reverse=descending)
                header = lines[0] if lines and "Id" in lines[0] else ""
                return (header + "\n" if header else "") + "\n".join(rows) + "\n"
            return text
        if low.startswith("measure-object"):
            rows = [line for line in lines[1:] if line.strip() and not line.strip().startswith("-")]
            total = 0.0
            for line in rows:
                value = self._row_number(line)
                if value is not None:
                    total += value
            return ("Count    : {0}\nAverage  : {1:,.2f}\nSum      : {2:,.2f}\n"
                    "Maximum  : {3:,.2f}\nMinimum  : {4:,.2f}\n").format(
                len(rows), (total / len(rows) if rows else 0.0), total,
                max((self._row_number(r) or 0.0) for r in rows) if rows else 0.0,
                min((self._row_number(r) or 0.0) for r in rows) if rows else 0.0,
            ).replace(",", " ")
        if low.startswith(("convertto-json", "convert-to-json")):
            rows = [line.split() for line in lines[1:]
                    if line.strip() and not line.strip().startswith("-")]
            payload = [{"Name": row[-1], "Status": "Running"} for row in rows if row]
            return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        if low.startswith(("set-content", "add-content", "out-file", "export-csv")):
            return ""
        if low.startswith("select-string"):
            pattern = " ".join(seg.split()[1:]).strip("\"'")
            hits = [line for line in lines if pattern.lower() in line.lower()]
            return "\n".join(hits) + "\n" if hits else ""
        if low.startswith("foreach-object"):
            return "".join(line.split()[-1] + "\n" for line in lines[1:] if line.split())
        if low.startswith(("format-table", "out-string", "format-list")):
            return text
        return text

    @staticmethod
    def _row_number(line: str) -> float | None:
        """Последнее число в строке таблицы — для -gt/-lt и Measure-Object."""
        for token in reversed(line.split()):
            try:
                return float(token.replace(",", "."))
            except ValueError:
                continue
        return None

    @staticmethod
    def _pipe_count(seg: str, default: int) -> int:
        words = seg.split()
        for i, word in enumerate(words):
            if word.lower() in ("-n", "-first") and i + 1 < len(words):
                try:
                    return int(words[i + 1])
                except ValueError:
                    return default
            if re.fullmatch(r"-\d+", word):
                return int(word[1:])
        return default

    # ─── сохранение песочницы ───────────────────────────────────────────
    def to_dict(self) -> dict:
        return {
            "fake": True,
            "cwd": self.cwd,
            "meta": {path: list(meta) for path, meta in self.meta.items()},
            "archives": dict(self.archives),
            "crontab": list(self.crontab),
            "env": dict(self.env),
            "variables": dict(self.variables),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FakeTerminalSimulator":
        sim = cls()
        sim.cwd = data.get("cwd", sim.cwd)
        sim.meta = {path: list(meta) for path, meta in (data.get("meta") or {}).items()} or sim.meta
        sim.archives = dict(data.get("archives") or {})
        sim.crontab = list(data.get("crontab") or [])
        sim.env = dict(data.get("env") or sim.env)
        sim.variables = dict(data.get("variables") or sim.variables)
        return sim
