"""市場資料擷取模組 — 透過 yfinance 取得股價、VIX、技術指標。"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import yfinance as yf


def get_vix(period: str = "5d") -> float:
    """取得最新 VIX 收盤值。"""
    vix = yf.Ticker("^VIX")
    hist = vix.history(period=period)
    if hist.empty:
        raise RuntimeError("無法取得 VIX 資料")
    return float(hist["Close"].iloc[-1])


def get_index_history(symbol: str = "^TWII", period: str = "1y") -> pd.DataFrame:
    """取得大盤指數歷史資料。"""
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period=period)
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
    hist = ticker.history(period=period)
    return hist


def get_batch_history(symbols: list[str], period: str = "3mo") -> dict[str, pd.DataFrame]:
    """批次取得多檔股票歷史資料。"""
    result: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        try:
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
