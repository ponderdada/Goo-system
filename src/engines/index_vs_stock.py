"""模組二：指數 vs 個股配置決策引擎。

在決定投資比例後，進一步決定應分配多少到指數型 ETF、
多少到個股。主要根據市場寬度（漲跌家數比）與個股波動度。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.data.market_data import (
    compute_volatility,
    get_batch_history,
    get_index_history,
)


@dataclass
class IndexStockDecision:
    market_breadth: float | None   # 漲跌比（若可取得）
    breadth_level: str             # healthy / neutral / narrow
    avg_stock_volatility: float
    index_ratio: float             # 指數佔投資部位比例
    stock_ratio: float             # 個股佔投資部位比例
    reasoning: str


def _estimate_breadth(index_hist) -> float | None:
    """用大盤近 20 日上漲天數比例來粗估市場寬度。"""
    if index_hist.empty or len(index_hist) < 20:
        return None
    recent = index_hist["Close"].pct_change().dropna().tail(20)
    up_ratio = float((recent > 0).sum()) / len(recent)
    return round(up_ratio, 2)


def decide(config: dict) -> IndexStockDecision:
    """執行指數 vs 個股配置決策。"""
    cfg = config["index_vs_stock"]
    mkt = config["market"]
    watch = config["news_stock_picker"]["watch_list"]

    base_index = cfg["base_index_ratio"]

    # 1. 市場寬度
    index_hist = get_index_history(mkt["index_symbol"])
    breadth = _estimate_breadth(index_hist)

    thresholds = cfg["breadth_thresholds"]
    adjustments = cfg["breadth_adjustments"]

    if breadth is not None and breadth > thresholds["healthy"]:
        breadth_adj = adjustments["healthy"]
        breadth_level = "healthy"
    elif breadth is not None and breadth < thresholds["narrow"]:
        breadth_adj = adjustments["narrow"]
        breadth_level = "narrow"
    else:
        breadth_adj = 0.0
        breadth_level = "neutral"

    # 2. 個股波動度
    stock_data = get_batch_history(watch, period="3mo")
    vols = [compute_volatility(h) for h in stock_data.values() if not h.empty]
    vols = [v for v in vols if not np.isnan(v)]
    avg_vol = float(np.mean(vols)) if vols else 0.3

    # 高波動 => 多配指數
    vol_adj = 0.0
    if avg_vol > 0.40:
        vol_adj = 0.10
    elif avg_vol < 0.20:
        vol_adj = -0.05

    # 3. 合成
    index_ratio = base_index + breadth_adj + vol_adj
    index_ratio = max(0.30, min(index_ratio, 0.85))
    index_ratio = round(index_ratio, 2)
    stock_ratio = round(1.0 - index_ratio, 2)

    # 個股上限
    cap = cfg["stock_volatility_cap"]
    if stock_ratio > cap:
        stock_ratio = cap
        index_ratio = round(1.0 - cap, 2)

    reasoning = (
        f"市場寬度 {breadth if breadth is not None else 'N/A'}（{breadth_level}），"
        f"寬度調整 {breadth_adj:+.0%}。"
        f"個股平均波動率 {avg_vol:.1%}，波動調整 {vol_adj:+.0%}。"
        f"建議配置：指數 {index_ratio:.0%} / 個股 {stock_ratio:.0%}。"
    )

    return IndexStockDecision(
        market_breadth=breadth,
        breadth_level=breadth_level,
        avg_stock_volatility=round(avg_vol, 4),
        index_ratio=index_ratio,
        stock_ratio=stock_ratio,
        reasoning=reasoning,
    )
