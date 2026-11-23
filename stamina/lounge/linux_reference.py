"""Учебник Linux для тренажёра: темы, команды, примеры, теория.

Данные отдельно от интерфейса — их читает панель `docker_ref_panel`
(переиспользуется под любой терминальный учебник) и по ним же строится
подсказка автодополнения.

Поле ``sim`` — команда отвечает в учебном симуляторе (`terminal_sim`).
Поле ``theory`` у темы — короткие тезисы, которые панель показывает над
списком команд: это и есть «теория» раздела, без прокрутки в объяснение.
"""

from __future__ import annotations

from stamina.i18n import t as _t

#: Заголовок панели учебника (в интерфейсе — на языке пилота).
PANEL_TITLE = _t("УЧЕБНИК LINUX · КОМАНДЫ")
SIM_HINT = _t("✓ выполняется в тренажёре")
REAL_HINT = _t("· только в настоящем Linux")

# fmt: off
TOPICS = [
    {
        "id": "basics",
        "title": "Основы Linux",
        "blurb": "Bash-терминал: команда — это программа из PATH, опции идут через дефис.",
        "commands": [
            {
                "cmd": "pwd",
                "desc": "Текущий рабочий каталог. То же, что «где я сейчас».",
                "example": "pwd",
                "sim": True,
            },
            {
                "cmd": "whoami",
                "desc": "Кто я? Пользователь, от чьего имени идёт работа.",
                "example": "whoami",
                "sim": True,
            },
            {
                "cmd": "id",
                "desc": "uid, gid и группы. По группам видно, есть ли права на docker и sudo.",
                "example": "id",
                "sim": True,
            },
            {
                "cmd": "uname -a",
                "desc": "Ядро, архитектура, версия сборки.",
                "example": "uname -a",
                "sim": True,
            },
            {
                "cmd": "cat /etc/os-release",
                "desc": "Имя дистрибутива и версия — из файла, а не из памяти.",
                "example": "cat /etc/os-release",
                "sim": True,
            },
            {
                "cmd": "hostname",
                "desc": "Имя машины в сети. На борту — ship.",
                "example": "hostname",
                "sim": True,
            },
        ],
        "theory": [
            "Команда — это файл-программа; оболочка ищет её по списку путей PATH.",
            "Пробел разделяет команду и аргументы: ls -la /var/log — команда, флаг, путь.",
            "Регистр важен: LS и ls — разные вещи; в Linux почти всё в нижнем регистре.",
        ],
    },
    {
        "id": "files",
        "title": "Файлы и поиск",
        "blurb": "Навигация и чтение: ls, cd, cat, find, grep. Путь / — корень, ~ — домашний каталог.",
        "commands": [
            {
                "cmd": "ls -la",
                "desc": "Список файлов: права, владелец, размер, дата. Флаг -a показывает скрытые.",
                "example": "ls -la /var/log",
                "sim": True,
            },
            {
                "cmd": "cd /var/log",
                "desc": "Сменить каталог. cd без аргументов — домой, cd - — назад.",
                "example": "cd /var/log",
                "sim": True,
            },
            {
                "cmd": "cat /var/log/syslog",
                "desc": "Прочитать файл целиком. Для длинных — head, tail или less.",
                "example": "cat /var/log/syslog",
                "sim": True,
            },
            {
                "cmd": "head -n 5 /var/log/syslog",
                "desc": "Первые строки файла: быстро понять формат.",
                "example": "head -n 5 /var/log/syslog",
                "sim": True,
            },
            {
                "cmd": "tail -n 20 /var/log/syslog",
                "desc": "Последние строки — то, что случилось только что.",
                "example": "tail -n 20 /var/log/syslog",
                "sim": True,
            },
            {
                "cmd": "find /var/log -name '*.log'",
                "desc": "Найти файлы по имени, возрасту (-mtime), размеру (-size).",
                "example": "find /var/log -name '*.log'",
                "sim": True,
            },
            {
                "cmd": "grep -i error /var/log/syslog",
                "desc": "Поиск строк по образцу. -i — без учёта регистра, -n — с номером строки.",
                "example": "grep -i error /var/log/syslog",
                "sim": True,
            },
        ],
        "theory": [
            "Путь начинается с / — абсолютный; без / — относительно текущего каталога.",
            "find ищет файлы по имени и времени, grep ищет текст внутри файлов.",
            "Две команды через && выполнятся подряд, если первая не упала.",
        ],
    },
    {
        "id": "processes",
        "title": "Процессы",
        "blurb": "Что запущено и кто ест процессор: ps, top, kill, nice. У каждого процесса есть PID.",
        "commands": [
            {
                "cmd": "ps aux",
                "desc": "Все процессы: USER, PID, %CPU, %MEM, STAT, COMMAND.",
                "example": "ps aux",
                "sim": True,
            },
            {
                "cmd": "top",
                "desc": "Живой мониторинг: обновляется сам, q — выход.",
                "example": "top",
                "sim": True,
            },
            {
                "cmd": "kill -9 1234",
                "desc": "Завершить процесс по PID. -15 (по умолчанию) — вежливо, -9 — жёстко.",
                "example": "kill -9 1234",
                "sim": True,
            },
            {
                "cmd": "nice -n 10 tail -f /var/log/syslog",
                "desc": "Запустить с низким приоритетом, чтобы не мешать остальным.",
                "example": "nice -n 10 tail -f /var/log/syslog",
                "sim": False,
            },
        ],
        "theory": [
            "PID — номер процесса, по нему работают kill и systemctl.",
            "STAT: S — спит, R — работает, Z — зомби, s — лидер сессии.",
            "%CPU выше 100% значит, что процесс занял несколько ядер.",
        ],
    },
    {
        "id": "network",
        "title": "Сеть",
        "blurb": "Порты, адреса и HTTP: ss, ping, curl. Сначала — кто слушает порт, потом — доступен ли он.",
        "commands": [
            {
                "cmd": "ss -tulpn",
                "desc": "Слушающие TCP/UDP сокеты: адрес, порт, процесс.",
                "example": "ss -tulpn",
                "sim": True,
            },
            {
                "cmd": "netstat -tulpn",
                "desc": "То же самое, классический вариант из net-tools.",
                "example": "netstat -tulpn",
                "sim": True,
            },
            {
                "cmd": "ping -c 4 8.8.8.8",
                "desc": "4 пакета до адреса — есть ли связь и какая задержка.",
                "example": "ping -c 4 8.8.8.8",
                "sim": True,
            },
            {
                "cmd": "curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/health",
                "desc": "HTTP-запрос, в вывод — только код ответа (200, 502 …).",
                "example": "curl -s http://localhost:8080/health",
                "sim": True,
            },
            {
                "cmd": "ip a",
                "desc": "Адреса интерфейсов: какой у машины IP в этой сети.",
                "example": "ip a",
                "sim": True,
            },
        ],
        "theory": [
            "0.0.0.0:8080 — порт открыт на всех интерфейсах; 127.0.0.1:8080 — только локально.",
            "Порт занят — новая служба не стартует; ищите владельца через ss -tulpn.",
            "ping проверяет ICMP, curl — настоящий HTTP; это разные проверки.",
        ],
    },
    {
        "id": "services",
        "title": "Службы и сервисы",
        "blurb": "systemctl управляет службами systemd: status, start, stop, restart, enable.",
        "commands": [
            {
                "cmd": "systemctl status orion",
                "desc": "Состояние службы: loaded, active (running), PID, память.",
                "example": "systemctl status orion",
                "sim": True,
            },
            {
                "cmd": "systemctl list-units --type=service",
                "desc": "Все службы: имя, статус, описание.",
                "example": "systemctl list-units --type=service",
                "sim": True,
            },
            {
                "cmd": "systemctl restart orion",
                "desc": "Перезапуск: stop + start одной командой.",
                "example": "systemctl restart orion",
                "sim": True,
            },
            {
                "cmd": "systemctl enable orion",
                "desc": "Включить автозапуск при загрузке. disable — выключить.",
                "example": "systemctl enable orion",
                "sim": True,
            },
        ],
        "theory": [
            "active (running) — работает; inactive (dead) — остановлена; failed — упала.",
            "enable — про автозапуск, start — про «сейчас»; это разные вещи.",
            "Службу удобно проверять парой: status + journalctl -u.",
        ],
    },
    {
        "id": "permissions",
        "title": "Права и владельцы",
        "blurb": "У файла есть владелец, группа и три тройки прав: владелец, группа, остальные.",
        "commands": [
            {
                "cmd": "ls -la /var/log/syslog",
                "desc": "Первая колонка — права: -rw-r----- это 640.",
                "example": "ls -la /var/log/syslog",
                "sim": True,
            },
            {
                "cmd": "chmod 640 /var/log/syslog",
                "desc": "Права числом: 6 = rw-, 4 = r--, 0 = ---.",
                "example": "chmod 640 /var/log/syslog",
                "sim": True,
            },
            {
                "cmd": "chmod +x deploy.sh",
                "desc": "Добавить бит выполнения — без него скрипт не запустится.",
                "example": "chmod +x deploy.sh",
                "sim": False,
            },
            {
                "cmd": "chown orion:ship /var/log/syslog",
                "desc": "Сменить владельца и группу: user:group.",
                "example": "chown orion:ship /var/log/syslog",
                "sim": True,
            },
            {
                "cmd": "sudo systemctl restart orion",
                "desc": "Выполнить команду с правами root. Просит пароль.",
                "example": "sudo systemctl restart orion",
                "sim": True,
            },
        ],
        "theory": [
            "Три тройки: владелец, группа, остальные. r=4, w=2, x=1 — складываются в цифру.",
            "644 — читают все, пишет владелец; 600 — только владелец; 755 — программа.",
            "Менять владельца может только root, поэтому chown идёт через sudo.",
        ],
    },
    {
        "id": "archives",
        "title": "Архивы и пакеты",
        "blurb": "Сжать, распаковать, посмотреть место и поставить пакет: tar, df, du, apt.",
        "commands": [
            {
                "cmd": "tar -czf /tmp/logs.tar.gz /var/log",
                "desc": "Создать gzip-архив: c — создать, z — gzip, f — файл.",
                "example": "tar -czf /tmp/logs.tar.gz /var/log",
                "sim": True,
            },
            {
                "cmd": "tar -xzf /tmp/logs.tar.gz -C /tmp",
                "desc": "Распаковать: x вместо c, -C — куда распаковывать.",
                "example": "tar -xzf /tmp/logs.tar.gz -C /tmp",
                "sim": True,
            },
            {
                "cmd": "df -h",
                "desc": "Сколько места на дисках в человекочитаемом виде.",
                "example": "df -h",
                "sim": True,
            },
            {
                "cmd": "du -sh /var/lib/docker",
                "desc": "Сколько занимает каталог: -s — итог, -h — с единицами.",
                "example": "du -sh /var/lib/docker",
                "sim": True,
            },
            {
                "cmd": "sudo apt update && sudo apt install htop",
                "desc": "Debian/Ubuntu: обновить список пакетов и поставить программу.",
                "example": "sudo apt install htop",
                "sim": True,
            },
        ],
        "theory": [
            "tar сам не сжимает — z (gzip) или J (xz) делают архив компактным.",
            "Буквы флагов tar: c — создать, x — распаковать, t — посмотреть, f — файл архива.",
            "df показывает диски, du — каталоги; «место кончилось» ищут этой парой.",
        ],
    },
    {
        "id": "logs",
        "title": "Журналы и планировщик",
        "blurb": "Что случилось и что случится по расписанию: journalctl, tail -f, crontab.",
        "commands": [
            {
                "cmd": "journalctl -u orion -n 20 --no-pager",
                "desc": "Журнал службы: последние 20 строк без интерактивного просмотрщика.",
                "example": "journalctl -u orion -n 20 --no-pager",
                "sim": True,
            },
            {
                "cmd": "journalctl -u orion -f",
                "desc": "Следить за журналом в реальном времени, как tail -f.",
                "example": "journalctl -u orion -f",
                "sim": False,
            },
            {
                "cmd": "tail -f /var/log/syslog",
                "desc": "Живой хвост файла журнала. Ctrl+C — выход.",
                "example": "tail -f /var/log/syslog",
                "sim": False,
            },
            {
                "cmd": "crontab -l",
                "desc": "Показать свои задания планировщика.",
                "example": "crontab -l",
                "sim": True,
            },
            {
                "cmd": "echo '0 3 * * * /usr/local/bin/backup.sh' | crontab -",
                "desc": "Поставить задание: минута, час, день, месяц, день недели, команда.",
                "example": "echo '0 3 * * * /usr/local/bin/backup.sh' | crontab -",
                "sim": True,
            },
        ],
        "theory": [
            "Пять полей cron: минута 0-59, час 0-23, день, месяц, день недели.",
            "0 3 * * * — каждый день в 03:00; */15 * * * * — каждые 15 минут.",
            "Журнал службы (journalctl -u) точнее файла: там видно и причину падения.",
        ],
    },
    {
        "id": "pipelines",
        "title": "Конвейеры и текст",
        "blurb": "Главная сила оболочки: вывод одной команды идёт на вход другой через |.",
        "commands": [
            {
                "cmd": "grep -i error /var/log/syslog | wc -l",
                "desc": "Сколько строк с ошибками: wc -l считает строки.",
                "example": "grep -i error /var/log/syslog | wc -l",
                "sim": True,
            },
            {
                "cmd": "grep -i error /var/log/syslog | sort -u",
                "desc": "Убрать повторы: sort -u сортирует и склеивает одинаковые строки.",
                "example": "grep -i error /var/log/syslog | sort -u",
                "sim": True,
            },
            {
                "cmd": "cat /var/log/syslog | head -n 3",
                "desc": "Первые строки после фильтра — удобно для проверки.",
                "example": "cat /var/log/syslog | head -n 3",
                "sim": True,
            },
            {
                "cmd": "ps aux | grep python",
                "desc": "Найти процесс по имени среди всего списка.",
                "example": "ps aux | grep python",
                "sim": True,
            },
            {
                "cmd": "ls -la /var/log | tee /tmp/listing.txt",
                "desc": "Показать на экране и одновременно записать в файл.",
                "example": "ls -la /var/log | tee /tmp/listing.txt",
                "sim": True,
            },
        ],
        "theory": [
            "| соединяет команды: stdout левой становится stdin правой.",
            "> перезаписывает файл, >> дописывает, 2> отправляет туда ошибки.",
            "Конвейер читается слева направо: сначала источник, потом фильтры.",
        ],
    },
    {
        "id": "remote",
        "title": "Удалённый доступ",
        "blurb": "ssh, ключи и передача файлов: как попасть на соседний узел без пароля.",
        "commands": [
            {
                "cmd": "ssh orion@10.0.0.5",
                "desc": "Войти на удалённую машину. Первый раз спросит про отпечаток ключа.",
                "example": "ssh orion@10.0.0.5",
                "sim": True,
            },
            {
                "cmd": "ssh orion@10.0.0.5 uptime",
                "desc": "Выполнить одну команду удалённо и выйти — без интерактивной сессии.",
                "example": "ssh orion@10.0.0.5 uptime",
                "sim": True,
            },
            {
                "cmd": "ssh-keygen -t ed25519 -C 'orion@ship'",
                "desc": "Создать пару ключей: приватный остаётся, публичный копируют на сервер.",
                "example": "ssh-keygen -t ed25519 -C 'orion@ship'",
                "sim": True,
            },
            {
                "cmd": "scp /tmp/logs.tar.gz orion@10.0.0.5:/tmp/",
                "desc": "Скопировать файл по ssh. Обратный порядок аргументов — забрать файл.",
                "example": "scp /tmp/logs.tar.gz orion@10.0.0.5:/tmp/",
                "sim": True,
            },
        ],
        "theory": [
            "Ключ ed25519 короче и надёжнее RSA; пароль после настройки не нужен.",
            "Публичный ключ кладут в ~/.ssh/authorized_keys на удалённой машине.",
            "scp и rsync идут поверх ssh, поэтому работают с теми же ключами.",
        ],
    },
]


def topics() -> list[dict]:
    return TOPICS


def topic(topic_id: str) -> dict | None:
    for t in TOPICS:
        if t["id"] == topic_id:
            return t
    return None


def commands(topic_id: str | None = None) -> list[dict]:
    if topic_id is None:
        return [c for t in TOPICS for c in t["commands"]]
    t = topic(topic_id)
    return list(t["commands"]) if t else []


def total() -> int:
    return sum(len(t["commands"]) for t in TOPICS)


def supported() -> list[dict]:
    return [c for c in commands() if c.get("sim")]


def completions() -> list[str]:
    out: list[str] = []
    for c in commands():
        head = " ".join(c["cmd"].split()[:2])
        if head and not head.startswith("-") and head not in out:
            out.append(head)
    return out


def search(query: str, topic_id: str | None = None) -> list[dict]:
    q = (query or "").strip().lower()
    items = commands(topic_id)
    if not q:
        return items
    words = q.split()
    return [c for c in items if all(w in (c["cmd"] + " " + c["desc"]).lower() for w in words)]
# fmt: on
