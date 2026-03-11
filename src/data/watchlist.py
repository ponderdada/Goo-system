"""觀察清單持久化管理。

觀察清單儲存在 data/watchlist.json，新增或刪除後即時寫入。
首次使用時從 config/settings.yaml 的 watch_list 初始化。
"""

from __future__ import annotations

import json
import os
import threading

_lock = threading.Lock()
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_WATCHLIST_PATH = os.path.join(_BASE_DIR, "data", "watchlist.json")


def _ensure_dir() -> None:
    os.makedirs(os.path.dirname(_WATCHLIST_PATH), exist_ok=True)


def load() -> list[str]:
    """讀取觀察清單。若檔案不存在則回傳空清單。"""
    with _lock:
        if not os.path.exists(_WATCHLIST_PATH):
            return []
        with open(_WATCHLIST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []


def save(symbols: list[str]) -> None:
    """寫入觀察清單。"""
    with _lock:
        _ensure_dir()
        with open(_WATCHLIST_PATH, "w", encoding="utf-8") as f:
            json.dump(symbols, f, ensure_ascii=False, indent=2)


def init_from_config(config_list: list[str]) -> list[str]:
    """若 watchlist.json 不存在，以 settings.yaml 的 watch_list 初始化。"""
    if os.path.exists(_WATCHLIST_PATH):
        return load()
    save(config_list)
    return list(config_list)


def add(symbol: str) -> list[str]:
    """新增一檔股票（自動去重）。回傳更新後的清單。"""
    symbols = load()
    sym = symbol.strip().upper()
    if not sym:
        return symbols
    # 台股自動加 .TW 後綴
    if sym.isdigit() and len(sym) == 4:
        sym = sym + ".TW"
    if sym not in symbols:
        symbols.append(sym)
        save(symbols)
    return symbols


def remove(symbol: str) -> list[str]:
    """移除一檔股票。回傳更新後的清單。"""
    symbols = load()
    sym = symbol.strip().upper()
    if sym in symbols:
        symbols.remove(sym)
        save(symbols)
    return symbols
