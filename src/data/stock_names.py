"""台股代號 → 中文名稱對照表。

優先使用本地對照表，若查無則嘗試從 yfinance 取得。
"""

from __future__ import annotations

import yfinance as yf

# 常見台股對照表
_NAMES: dict[str, str] = {
    "0050.TW": "元大台灣50",
    "0056.TW": "元大高股息",
    "2330.TW": "台積電",
    "2317.TW": "鴻海",
    "2454.TW": "聯發科",
    "2881.TW": "富邦金",
    "2882.TW": "國泰金",
    "2303.TW": "聯電",
    "3711.TW": "日月光投控",
    "2412.TW": "中華電",
    "2308.TW": "台達電",
    "2886.TW": "兆豐金",
    "2891.TW": "中信金",
    "2884.TW": "玉山金",
    "2357.TW": "華碩",
    "2382.TW": "廣達",
    "2345.TW": "智邦",
    "3037.TW": "欣興",
    "2379.TW": "瑞昱",
    "6669.TW": "緯穎",
    "3443.TW": "創意",
    "5274.TW": "信驊",
    "2603.TW": "長榮",
    "2615.TW": "萬海",
    "2609.TW": "陽明",
    "3231.TW": "緯創",
    "2301.TW": "光寶科",
    "2395.TW": "研華",
    "3008.TW": "大立光",
    "2327.TW": "國巨",
    "6505.TW": "台塑化",
    "1301.TW": "台塑",
    "1303.TW": "南亞",
    "2002.TW": "中鋼",
    "1216.TW": "統一",
    "2912.TW": "統一超",
}

# 動態快取（避免重複查詢 yfinance）
_cache: dict[str, str] = {}


def get_name(symbol: str) -> str:
    """取得股票中文名稱。"""
    sym = symbol.strip().upper()
    if sym in _NAMES:
        return _NAMES[sym]
    if sym in _cache:
        return _cache[sym]
    # 嘗試 yfinance
    try:
        info = yf.Ticker(sym).info or {}
        name = info.get("shortName") or info.get("longName") or sym
        _cache[sym] = name
        return name
    except Exception:
        _cache[sym] = sym
        return sym
