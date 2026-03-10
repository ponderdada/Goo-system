"""新聞情緒分析模組 — 基於價量特徵推估消息面影響。

由於免費新聞 API 有諸多限制，本模組採用「價量異常偵測」作為消息面
代理指標：當個股出現放量上漲且偏離均線時，視為正面消息驅動。
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_news_proxy_score(hist: pd.DataFrame, lookback: int = 60) -> float:
    """透過價量異常程度推估新聞正面驅動分數。

    分數範圍 0~1：
    - 成交量相對均量的倍數（量能分數）
    - 近期漲幅偏離度（價格分數）
    - 連續上漲天數比例（趨勢分數）

    三者加權平均得出綜合分數。
    """
    if hist.empty or len(hist) < lookback:
        lookback = max(len(hist), 5)

    recent = hist.tail(lookback).copy()

    # --- 量能分數 ---
    vol_mean = recent["Volume"].mean()
    vol_recent = recent["Volume"].tail(5).mean()
    if vol_mean > 0:
        vol_ratio = vol_recent / vol_mean
        volume_score = min(vol_ratio / 3.0, 1.0)  # 3 倍量以上 = 滿分
    else:
        volume_score = 0.0

    # --- 價格偏離分數 ---
    ma20 = recent["Close"].rolling(20).mean()
    if not ma20.empty and not np.isnan(ma20.iloc[-1]) and ma20.iloc[-1] != 0:
        deviation = (float(recent["Close"].iloc[-1]) - float(ma20.iloc[-1])) / float(ma20.iloc[-1])
        price_score = max(min(deviation / 0.10, 1.0), 0.0)  # 偏離 10% = 滿分
    else:
        price_score = 0.0

    # --- 趨勢分數 ---
    daily_returns = recent["Close"].pct_change().dropna().tail(20)
    if len(daily_returns) > 0:
        up_days = (daily_returns > 0).sum()
        trend_score = float(up_days) / len(daily_returns)
    else:
        trend_score = 0.5

    # 加權合成
    composite = volume_score * 0.35 + price_score * 0.40 + trend_score * 0.25
    return round(float(composite), 4)
