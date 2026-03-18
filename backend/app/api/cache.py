"""簡易 TTL 快取"""
import time
from typing import Any

_cache: dict[str, tuple[float, Any]] = {}

def get_cache(key: str, ttl: int = 60) -> Any | None:
    """取得快取，若超過 TTL 秒則回傳 None"""
    if key in _cache:
        ts, val = _cache[key]
        if time.time() - ts < ttl:
            return val
        del _cache[key]
    return None

def set_cache(key: str, value: Any) -> None:
    """設定快取"""
    _cache[key] = (time.time(), value)

def clear_cache(prefix: str = "") -> None:
    """清除指定前綴的快取"""
    if not prefix:
        _cache.clear()
    else:
        keys = [k for k in _cache if k.startswith(prefix)]
        for k in keys:
            del _cache[k]
