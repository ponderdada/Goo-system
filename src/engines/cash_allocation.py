"""模組一：現金 vs 投資配置決策引擎。

根據 VIX 恐慌指數與大盤均線趨勢，決定應保留多少現金、
多少資金投入市場。
"""

from __future__ import annotations

from dataclasses import dataclass

from src.data.market_data import get_index_history, get_vix, is_above_ma


@dataclass
class CashDecision:
    vix: float
    vix_level: str           # low / medium / high / extreme
    is_uptrend: bool         # 大盤是否處於多頭（高於 200MA）
    cash_ratio: float        # 建議現金比例 0~1
    invest_ratio: float      # 建議投資比例 0~1
    reasoning: str


def decide(config: dict) -> CashDecision:
    """根據設定檔參數執行現金配置決策。"""
    cfg = config["cash_allocation"]
    mkt = config["market"]

    # 1. 取得 VIX
    vix = get_vix()

    # 2. 根據 VIX 決定基礎現金比例
    thresholds = cfg["vix_thresholds"]
    ratios = cfg["cash_ratios"]

    if vix < thresholds["low"]:
        base_cash = ratios["low_vix"]
        vix_level = "low"
    elif vix < thresholds["medium"]:
        base_cash = ratios["medium_vix"]
        vix_level = "medium"
    elif vix < thresholds["high"]:
        base_cash = ratios["high_vix"]
        vix_level = "high"
    else:
        base_cash = ratios["extreme_vix"]
        vix_level = "extreme"

    # 3. 均線趨勢調整
    index_hist = get_index_history(mkt["index_symbol"])
    uptrend = is_above_ma(index_hist, window=200)
    trend_adj = cfg["trend_adjustment"]

    if uptrend:
        adjusted_cash = max(base_cash - trend_adj, 0.05)
        trend_note = "大盤高於 200 日均線（多頭），減少現金保留"
    else:
        adjusted_cash = min(base_cash + trend_adj, 0.90)
        trend_note = "大盤低於 200 日均線（空頭），增加現金保留"

    adjusted_cash = round(adjusted_cash, 2)
    invest_ratio = round(1.0 - adjusted_cash, 2)

    reasoning = (
        f"VIX = {vix:.1f}（{vix_level} 級別），基礎現金比例 {base_cash:.0%}。"
        f"{trend_note}。最終建議：現金 {adjusted_cash:.0%} / 投資 {invest_ratio:.0%}。"
    )

    return CashDecision(
        vix=round(vix, 2),
        vix_level=vix_level,
        is_uptrend=uptrend,
        cash_ratio=adjusted_cash,
        invest_ratio=invest_ratio,
        reasoning=reasoning,
    )
