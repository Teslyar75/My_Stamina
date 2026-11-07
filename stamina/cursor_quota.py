"""Утилиты контроля usage/quota для отдельного Cursor-виджета."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

CONFIG_PATH = Path.home() / ".cursor-token-widget.json"


def _intish(value) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value) if value >= 0 else None
    if isinstance(value, str):
        raw = value.strip().replace(" ", "").replace("_", "").replace(",", ".")
        if not raw:
            return None
        try:
            num = float(raw)
        except ValueError:
            return None
        return int(num) if num >= 0 else None
    return None


def _lc_map(data: dict) -> dict:
    return {str(key).lower(): val for key, val in data.items()}


def _pick_value(data: dict, keys: tuple[str, ...]):
    low = _lc_map(data)
    for key in keys:
        if key in low:
            return low[key]
    return None


def _quota_candidates(payload: dict) -> list[dict]:
    rows = [payload]
    for key in ("data", "result", "usage", "quota", "totals", "stats"):
        val = payload.get(key)
        if isinstance(val, dict):
            rows.append(val)
    return rows


def parse_models(payload: dict) -> list[dict]:
    """Собрать расход по моделям из типовых JSON-схем usage/quota."""
    out: list[dict] = []
    buckets = []
    for base in _quota_candidates(payload):
        low = _lc_map(base)
        for key in ("models", "by_model", "model_usage", "per_model"):
            val = low.get(key)
            if val:
                buckets.append(val)
    for bucket in buckets:
        if isinstance(bucket, dict):
            items = bucket.items()
        elif isinstance(bucket, list):
            items = []
            for row in bucket:
                if isinstance(row, dict):
                    name = str(row.get("model") or row.get("name") or row.get("id") or "").strip()
                    items.append((name, row))
        else:
            continue
        for name, row in items:
            if not isinstance(row, dict):
                continue
            title = str(name or row.get("model") or row.get("name") or row.get("id") or "").strip()
            if not title:
                continue
            used = _intish(
                _pick_value(row, ("used_tokens", "tokens_used", "used", "consumed", "current", "usage"))
            )
            limit = _intish(
                _pick_value(row, ("limit_tokens", "tokens_limit", "limit", "quota", "total", "max"))
            )
            if used is None and limit is None:
                continue
            item = {"model": title, "used": used, "limit": limit}
            if item not in out:
                out.append(item)
    return out


def parse_usage_payload(payload: dict, *, limit: int = 0, period: str = "") -> dict:
    """Преобразовать произвольный usage/quota JSON в унифицированный снимок."""
    if not isinstance(payload, dict):
        return {"ok": False, "error": "format", "message": "JSON-формат не поддержан"}
    used = None
    total = None
    period_val = str(period or "").strip()
    for block in _quota_candidates(payload):
        used = used if used is not None else _intish(
            _pick_value(
                block,
                ("used_tokens", "tokens_used", "used", "consumed", "usage", "current_usage", "current"),
            )
        )
        total = total if total is not None else _intish(
            _pick_value(block, ("limit_tokens", "tokens_limit", "limit", "quota", "total", "max"))
        )
        if not period_val:
            found = _pick_value(block, ("period", "window", "cycle", "billing_period", "reset_at"))
            if found is not None:
                period_val = str(found)
    if total is None and limit > 0:
        total = max(0, int(limit))
    if used is None and total is None:
        return {"ok": False, "error": "format", "message": "В ответе нет usage/quota полей"}
    remaining = max(0, total - used) if (total is not None and used is not None) else None
    percent = (
        max(0.0, min(100.0, (used / total) * 100.0))
        if (used is not None and total is not None and total > 0)
        else None
    )
    return {
        "ok": True,
        "used": used,
        "limit": total,
        "remaining": remaining,
        "percent": percent,
        "period": period_val,
        "models": parse_models(payload),
        "updated": time.time(),
    }


def fetch_usage(*, url: str, token: str = "", limit: int = 0, period: str = "", timeout: float = 20.0) -> dict:
    """Получить usage/quota по API и вернуть нормализованный снимок."""
    url = str(url or "").strip()
    token = str(token or "").strip()
    if not url:
        return {"ok": False, "error": "no_url", "message": "URL API не задан"}
    if not token:
        return {"ok": False, "error": "no_token", "message": "Токен API не задан"}
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "Cursor-Token-Widget",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return {"ok": False, "error": "http", "message": f"HTTP {exc.code}"}
    except urllib.error.URLError:
        return {"ok": False, "error": "network", "message": "Сеть недоступна"}
    except OSError as exc:
        return {"ok": False, "error": "io", "message": str(exc)}
    try:
        payload = json.loads(body)
    except ValueError:
        return {"ok": False, "error": "json", "message": "Ответ не JSON"}
    return parse_usage_payload(payload, limit=max(0, int(limit or 0)), period=period)


def load_settings(path: Path = CONFIG_PATH) -> dict:
    """Прочитать сохранённые настройки виджета."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"url": "", "token": "", "period": "", "limit": 0, "refresh": 60}
    if not isinstance(data, dict):
        return {"url": "", "token": "", "period": "", "limit": 0, "refresh": 60}
    out = {
        "url": str(data.get("url") or "").strip(),
        "token": str(data.get("token") or "").strip(),
        "period": str(data.get("period") or "").strip(),
        "limit": max(0, int(_intish(data.get("limit")) or 0)),
        "refresh": max(10, int(_intish(data.get("refresh")) or 60)),
    }
    return out


def save_settings(
    *,
    url: str = "",
    token: str = "",
    period: str = "",
    limit: int = 0,
    refresh: int = 60,
    path: Path = CONFIG_PATH,
) -> dict:
    """Сохранить настройки виджета."""
    data = {
        "url": str(url or "").strip(),
        "token": str(token or "").strip(),
        "period": str(period or "").strip(),
        "limit": max(0, int(limit or 0)),
        "refresh": max(10, int(refresh or 60)),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data
