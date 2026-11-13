"""Роли пилота: капитан — разработчик с доступом к GitHub-репозиторию проекта.

Капитан и разработчик — одна роль: пилот, у которого подтверждён доступ к
репозиторию Teslyar75/My_Stamina (GitHub API). Ему открыты все уровни и отсеки.
Остальные пилоты открывают уровни строго по порядку: первый уровень линейки
открыт, следующий — после прохождения предыдущего на unlock_pct %.

Признак role в pilots.json и migrated_from сами по себе капитана не дают.
Токен GitHub не пишется в pilots.json: сначала хранилище ОС (agent_connect),
иначе файл github_token в папке пилота. Токен нигде не логируется.
Проверка сети ленивая, с таймаутом, не выполняется при импорте модуля
и не блокирует запуск Tk: is_captain читает кэш (24 ч); обновление в фоне.
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

CAPTAIN = "captain"
DEVELOPER = "developer"
PILOT = "pilot"

REPO_OWNER = "Teslyar75"
REPO_NAME = "My_Stamina"
REPO = f"{REPO_OWNER}/{REPO_NAME}"
API_REPO = f"https://api.github.com/repos/{REPO}"
API_USER = "https://api.github.com/user"
CACHE_TTL_SEC = 24 * 3600
HTTP_TIMEOUT = 5.0
CRED_PREFIX = "StarTyping/github/"
TOKEN_FILE = "github_token"
CACHE_FILE = "github_access.json"

# Тесты и STAR_TYPING_SAFE: не трогать системное хранилище учётных данных.
_FORCE_FILE_STORE = False
_refreshing: set[str] = set()
_refresh_lock = threading.Lock()


def _pilot(p=None) -> dict | None:
    from stamina import pilots
    if p is not None:
        return p
    return pilots.active()


def _pid_of(p) -> str:
    return str((p or {}).get("id") or "")


def _login_of(p) -> str:
    if not p:
        return ""
    login = str(p.get("github_login") or "").strip().lstrip("@")
    if login:
        return login
    try:
        from stamina import pilots
        pid = _pid_of(p)
        if pid:
            prof = pilots.profile(pid)
            return str(prof.get("github_login") or "").strip().lstrip("@")
    except Exception:  # noqa: BLE001
        pass
    return ""


def cred_ref(pid: str) -> str:
    return CRED_PREFIX + str(pid)


def token_path(pid: str) -> Path:
    from stamina import pilots
    return pilots.pilot_dir(pid) / TOKEN_FILE


def cache_path(pid: str) -> Path:
    from stamina import pilots
    return pilots.pilot_dir(pid) / CACHE_FILE


def _use_file_store() -> bool:
    return bool(_FORCE_FILE_STORE or os.environ.get("STAR_TYPING_SAFE"))


def _store_token(pid: str, token: str) -> None:
    """Сохранить токен: хранилище ОС, иначе файл в папке пилота. Не логировать."""
    token = (token or "").strip()
    path = token_path(pid)
    if not token:
        _delete_token(pid)
        return
    if not _use_file_store():
        try:
            from stamina import agent_connect
            ref = agent_connect.store_key(pid, token, ref=cred_ref(pid))
            if ref:
                _set_pilot_fields(pid, github_cred_ref=ref)
                if path.is_file():
                    path.unlink()
                return
        except Exception:  # noqa: BLE001
            pass
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _delete_token(pid: str) -> None:
    if not _use_file_store():
        try:
            from stamina import agent_connect
            from stamina import pilots
            p = pilots.get(pid) or {}
            ref = p.get("github_cred_ref") or cred_ref(pid)
            agent_connect.delete_key(ref)
        except Exception:  # noqa: BLE001
            pass
    path = token_path(pid)
    try:
        if path.is_file():
            path.unlink()
    except OSError:
        pass


def _read_token(pid: str) -> str:
    if not pid:
        return ""
    if not _use_file_store():
        try:
            from stamina import agent_connect
            from stamina import pilots
            p = pilots.get(pid) or {}
            ref = p.get("github_cred_ref") or cred_ref(pid)
            tok = (agent_connect.read_key(ref) or "").strip()
            if tok:
                return tok
        except Exception:  # noqa: BLE001
            pass
    path = token_path(pid)
    try:
        if path.is_file():
            return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    return ""


def _set_pilot_fields(pid: str, **fields) -> None:
    try:
        from stamina import pilots
        pilots.update_pilot(pid, **fields)
    except Exception:  # noqa: BLE001
        pass


def write_access_cache(pid: str, *, ok: bool, login: str = "") -> None:
    """Записать кэш проверки GitHub (результат verify или подготовка теста)."""
    if not pid:
        return
    path = cache_path(pid)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "ok": bool(ok),
        "checked_at": time.time(),
        "login": (login or "").strip().lstrip("@"),
        "repo": REPO,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def _read_cache(pid: str) -> dict | None:
    try:
        data = json.loads(cache_path(pid).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _cache_fresh(cache: dict | None) -> bool:
    if not cache or "ok" not in cache:
        return False
    try:
        checked = float(cache.get("checked_at") or 0)
    except (TypeError, ValueError):
        return False
    return (time.time() - checked) < CACHE_TTL_SEC


def _http_json(url: str, token: str, timeout: float) -> tuple[int, dict]:
    """GET JSON с токеном. Тело/заголовки с токеном не пробрасываются наружу."""
    req = urllib.request.Request(url, method="GET", headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "StarTyping",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read() or b""
            code = int(getattr(resp, "status", 200) or 200)
            if not raw:
                return code, {}
            data = json.loads(raw.decode("utf-8"))
            return code, data if isinstance(data, dict) else {}
    except urllib.error.HTTPError as exc:
        try:
            exc.read()
        except Exception:  # noqa: BLE001
            pass
        try:
            exc.close()
        except Exception:  # noqa: BLE001
            pass
        return int(exc.code), {}


def _permissions_ok(data: dict) -> bool:
    """Write-доступ, либо pull у закрытого репозитория (для публичного pull есть у всех)."""
    perms = data.get("permissions") or {}
    if not isinstance(perms, dict):
        return False
    if perms.get("admin") or perms.get("maintain") or perms.get("push"):
        return True
    if data.get("private") and perms.get("pull"):
        return True
    return False


def _is_collaborator(token: str, login: str, timeout: float) -> bool:
    if not login:
        return False
    url = f"{API_REPO}/collaborators/{login}"
    try:
        code, _ = _http_json(url, token, timeout)
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        raise
    return code == 204


def verify_github(p=None, *, timeout: float = HTTP_TIMEOUT, force: bool = False) -> bool:
    """Синхронная проверка доступа к репозиторию. При сбое сети — кэш, иначе False."""
    p = _pilot(p)
    pid = _pid_of(p)
    if not pid:
        return False
    if not force:
        cache = _read_cache(pid)
        if _cache_fresh(cache):
            return bool(cache.get("ok"))
    token = _read_token(pid)
    expected = _login_of(p)
    if not token:
        write_access_cache(pid, ok=False, login=expected)
        return False
    try:
        code, data = _http_json(API_REPO, token, timeout)
        user_login = ""
        try:
            ucode, udata = _http_json(API_USER, token, timeout)
            if ucode == 200:
                user_login = str(udata.get("login") or "").strip()
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
            user_login = expected
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        cache = _read_cache(pid)
        return bool(cache and cache.get("ok"))
    if expected and user_login and expected.casefold() != user_login.casefold():
        ok = False
    elif code != 200:
        ok = False
    else:
        ok = _permissions_ok(data)
        if not ok:
            try:
                ok = _is_collaborator(token, user_login or expected, timeout)
            except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
                cache = _read_cache(pid)
                return bool(cache and cache.get("ok"))
    login = user_login or expected
    if ok and user_login and not expected:
        _set_pilot_fields(pid, github_login=user_login)
    write_access_cache(pid, ok=ok, login=login)
    return ok


def _schedule_refresh(pid: str) -> None:
    with _refresh_lock:
        if pid in _refreshing:
            return
        _refreshing.add(pid)

    def run() -> None:
        try:
            from stamina import pilots
            p = pilots.get(pid)
            if p:
                verify_github(p, timeout=HTTP_TIMEOUT, force=True)
        except Exception:  # noqa: BLE001
            pass
        finally:
            with _refresh_lock:
                _refreshing.discard(pid)

    threading.Thread(target=run, name=f"github-access-{pid}", daemon=True).start()


def is_developer(p=None) -> bool:
    """Подтверждённый доступ к Teslyar75/My_Stamina. Сеть при проверке не ждём."""
    p = _pilot(p)
    pid = _pid_of(p)
    if not pid:
        return False
    cache = _read_cache(pid)
    if _cache_fresh(cache):
        return bool(cache.get("ok"))
    if _read_token(pid):
        _schedule_refresh(pid)
    if cache is not None and "ok" in cache:
        return bool(cache.get("ok"))
    return False


def is_captain(p=None) -> bool:
    """Капитан = разработчик с подтверждённым доступом к GitHub."""
    return is_developer(p)


def role_of(p=None) -> str:
    """Высшая роль: капитан (он же разработчик) либо обычный пилот."""
    return CAPTAIN if is_developer(p) else PILOT


def _dedupe_paste(token: str) -> str:
    """Токен, случайно вставленный несколько раз подряд, -> одна копия."""
    for n in range(2, 6):
        if len(token) % n == 0:
            one = token[: len(token) // n]
            if one and one * n == token:
                return one
    return token


def link_github(pid: str, login: str, token: str, *,
                verify: bool = True, timeout: float = HTTP_TIMEOUT) -> tuple[bool, str]:
    """Сохранить логин и токен пилота; по умолчанию сразу проверить доступ.

    Токен не попадает в возвращаемое сообщение и не пишется в pilots.json.
    """
    from stamina import pilots
    pid = str(pid or "").strip()
    if not pid or pilots.get(pid) is None:
        return False, "pilot not found"
    login = (login or "").strip().lstrip("@")
    token = _dedupe_paste((token or "").strip())
    if not token:
        return False, "empty token"
    if login:
        _set_pilot_fields(pid, github_login=login)
    _store_token(pid, token)
    if not verify:
        return True, "saved"
    p = pilots.get(pid)
    ok = verify_github(p, timeout=timeout, force=True)
    return ok, ("ok" if ok else "github access not confirmed")


def _clipboard_text() -> str:
    """Текст из буфера обмена через Tk (без печати в консоль)."""
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            return str(root.clipboard_get() or "")
        finally:
            root.destroy()
    except Exception:  # noqa: BLE001
        return ""


def main(argv: list[str] | None = None) -> int:
    """python -m stamina.roles link LOGIN [--pilot ID]  — токен спрашивается скрытно."""
    import argparse
    import getpass
    import sys

    parser = argparse.ArgumentParser(prog="stamina.roles")
    sub = parser.add_subparsers(dest="cmd", required=True)
    link = sub.add_parser("link", help="привязать GitHub и проверить доступ к репозиторию")
    link.add_argument("login", help="логин GitHub")
    link.add_argument("--pilot", default="", help="id пилота; по умолчанию активный или last_pilot")
    link.add_argument("--clipboard", action="store_true",
                      help="взять токен из буфера обмена (без вставки в консоль)")
    args = parser.parse_args(argv)
    if args.cmd != "link":
        parser.print_help()
        return 2
    from stamina import pilots
    pid = (args.pilot or "").strip()
    if not pid:
        active = pilots.active()
        if active:
            pid = active["id"]
        else:
            reg = pilots.load_registry() or {}
            pid = str(reg.get("last_pilot") or "")
    if not pid or pilots.get(pid) is None:
        print("pilot not found", file=sys.stderr)
        return 2
    if args.clipboard:
        token = _clipboard_text().strip()
        if not token:
            print("clipboard is empty", file=sys.stderr)
            return 1
    else:
        token = getpass.getpass("GitHub token (символы не видны): ").strip()
    ok, msg = link_github(pid, args.login, token)
    print(msg)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
