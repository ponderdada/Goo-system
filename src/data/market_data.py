"""市場資料擷取模組 — 透過 yfinance 取得股價、VIX、技術指標。"""

from __future__ import annotations

import datetime as dt
import time

import numpy as np
import pandas as pd
import yfinance as yf


_TIMEOUT = 30  # 每次 yfinance 請求的最長等待秒數
_MAX_RETRIES = 3  # 遇到 rate limit 時最多重試次數
_CALL_DELAY = 2  # 每次 API 呼叫之間的延遲秒數


def _retry_on_rate_limit(func):
    """裝飾器：遇到 rate limit 時自動重試（指數退避）。"""
    def wrapper(*args, **kwargs):
        for attempt in range(_MAX_RETRIES):
            try:
                result = func(*args, **kwargs)
                time.sleep(_CALL_DELAY)  # 成功後也加延遲，避免下一個呼叫被限流
                return result
            except Exception as e:
                err_msg = str(e).lower()
                if "rate limit" in err_msg or "too many requests" in err_msg:
                    wait = (2 ** attempt) * 5  # 5s, 10s, 20s
                    time.sleep(wait)
                    if attempt == _MAX_RETRIES - 1:
                        raise RuntimeError(
                            f"Yahoo Finance 速率限制，已重試 {_MAX_RETRIES} 次仍失敗，請稍後再試"
                        ) from e
                else:
                    raise
        return None  # unreachable
    return wrapper


@_retry_on_rate_limit
def get_vix(period: str = "5d") -> float:
    """取得最新 VIX 收盤值。"""
    vix = yf.Ticker("^VIX")
    hist = vix.history(period=period, timeout=_TIMEOUT)
    if hist.empty:
        raise RuntimeError("無法取得 VIX 資料")
    return float(hist["Close"].iloc[-1])


@_retry_on_rate_limit
def get_index_history(symbol: str = "^TWII", period: str = "1y") -> pd.DataFrame:
    """取得大盤指數歷史資料。"""
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period=period, timeout=_TIMEOUT)
    if hist.empty:
        raise RuntimeError(f"無法取得 {symbol} 資料")
    return hist


def is_above_ma(hist: pd.DataFrame, window: int = 200) -> bool:
    """判斷最新收盤價是否高於 N 日均線。"""
    if len(hist) < window:
        window = len(hist)
    ma = hist["Close"].rolling(window=window).mean().iloc[-1]
    return float(hist["Close"].iloc[-1]) > ma


def get_stock_history(symbol: str, period: str = "6mo") -> pd.DataFrame:
    """取得個股歷史資料。"""
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period=period, timeout=_TIMEOUT)
    return hist


@_retry_on_rate_limit
def get_batch_history(symbols: list[str], period: str = "3mo") -> dict[str, pd.DataFrame]:
    """批次取得多檔股票歷史資料（使用 yfinance 批次下載加速）。"""
    result: dict[str, pd.DataFrame] = {}
    try:
        data = yf.download(symbols, period=period, group_by="ticker", threads=False, timeout=_TIMEOUT)
        if len(symbols) == 1:
            result[symbols[0]] = data if not data.empty else pd.DataFrame()
        else:
            for sym in symbols:
                try:
                    df = data[sym].dropna(how="all")
                    if not df.empty:
                        result[sym] = df
                except (KeyError, Exception):
                    continue
    except Exception as e:
        err_msg = str(e).lower()
        if "rate limit" in err_msg or "too many requests" in err_msg:
            raise  # 讓 _retry_on_rate_limit 處理
        # 其他錯誤：退回逐一下載（每次間隔延遲）
        for sym in symbols:
            try:
                time.sleep(_CALL_DELAY)
                result[sym] = get_stock_history(sym, period)
            except Exception:
                continue
    return result


def compute_volatility(hist: pd.DataFrame, window: int = 20) -> float:
    """計算年化波動率。"""
    if hist.empty or len(hist) < window:
        return float("nan")
    returns = hist["Close"].pct_change().dropna()
    return float(returns.tail(window).std() * np.sqrt(252))


def compute_momentum(hist: pd.DataFrame, lookback: int = 60) -> float:
    """計算動能分數（近 N 日報酬率）。"""
    if hist.empty or len(hist) < lookback:
        lookback = len(hist)
    if lookback < 2:
        return 0.0
    start = float(hist["Close"].iloc[-lookback])
    end = float(hist["Close"].iloc[-1])
    if start == 0:
        return 0.0
    return (end - start) / start


def compute_rsi(hist: pd.DataFrame, window: int = 14) -> float:
    """計算 RSI 指標。"""
    if hist.empty or len(hist) < window + 1:
        return 50.0
    delta = hist["Close"].diff()
    gain = delta.where(delta > 0, 0.0).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=window).mean()
    rs = gain.iloc[-1] / loss.iloc[-1] if loss.iloc[-1] != 0 else float("inf")
    return float(100 - (100 / (1 + rs)))


def compute_drawdown_from_recent_high(hist: pd.DataFrame, lookback_days: int = 40) -> tuple[float, float, float]:
    """計算從近期高點的回檔幅度。

    Args:
        hist: 包含 Close 欄位的歷史資料
        lookback_days: 往回看幾個交易日找高點（40日 ≈ 2個月）

    Returns:
        (drawdown_pct, recent_high, current_price)
        drawdown_pct: 回檔幅度（0~1，0 表示在高點，0.15 表示跌了 15%）
    """
    if hist.empty or len(hist) < 5:
        return 0.0, 0.0, 0.0
    window = min(lookback_days, len(hist))
    recent = hist["Close"].tail(window)
    recent_high = float(recent.max())
    current = float(hist["Close"].iloc[-1])
    if recent_high <= 0:
        return 0.0, 0.0, current
    drawdown = (recent_high - current) / recent_high
    return round(max(drawdown, 0.0), 4), round(recent_high, 2), round(current, 2)
