"""模組：個股排名引擎。

根據消息面驅動（價量異常）排序個股，主要排序依據：
  1. 消息面分數 — 最近一季最容易因消息帶動上漲的個股
  2. 預估投報率 — 動能分數作為投報代理指標
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.data.market_data import (
    compute_momentum,
    compute_rsi,
    compute_volatility,
    get_batch_history,
)
from src.data.news_sentiment import compute_news_proxy_score


@dataclass
class StockCandidate:
    symbol: str
    news_score: float       # 消息面驅動分數 0~1（主排序）
    momentum_score: float   # 動能分數（近季報酬率，次排序）
    rsi: float
    volatility: float
    composite_score: float  # 綜合得分
    reason: str


@dataclass
class StockPickResult:
    candidates: list[StockCandidate] = field(default_factory=list)
    picks: list[StockCandidate] = field(default_factory=list)
    reasoning: str = ""


def decide(config: dict) -> StockPickResult:
    """執行個股排名：消息面為主、預估投報為次。"""
    cfg = config["news_stock_picker"]
    watch_list = cfg["watch_list"]
    lookback = cfg["lookback_days"]

    all_hist = get_batch_history(watch_list, period="6mo")

    candidates: list[StockCandidate] = []

    for symbol, hist in all_hist.items():
        if hist.empty or len(hist) < 20:
            continue

        news_score = compute_news_proxy_score(hist, lookback)
        momentum = compute_momentum(hist, lookback)
        rsi = compute_rsi(hist)
        vol = compute_volatility(hist)

        # 動能正規化到 0~1
        momentum_norm = max(min((momentum + 0.3) / 0.6, 1.0), 0.0)

        # RSI 適中加分（40~70 為佳）
        if 40 <= rsi <= 70:
            rsi_bonus = 0.05
        elif rsi > 80 or rsi < 20:
            rsi_bonus = -0.10
        else:
            rsi_bonus = 0.0

        # 綜合分數：消息面 55% + 動能 30% + 低波動 15%
        composite = (
            news_score * 0.55
            + momentum_norm * 0.30
            + 0.15 * (1.0 - min(vol, 1.0))
            + rsi_bonus
        )
        composite = round(max(min(composite, 1.0), 0.0), 4)

        reason_parts = []
        if news_score >= 0.4:
            reason_parts.append(f"消息面活躍({news_score:.2f})")
        if momentum > 0:
            reason_parts.append(f"動能 {momentum:+.1%}")
        if 40 <= rsi <= 70:
            reason_parts.append(f"RSI {rsi:.0f}")

        candidates.append(StockCandidate(
            symbol=symbol,
            news_score=news_score,
            momentum_score=round(momentum, 4),
            rsi=round(rsi, 1),
            volatility=round(vol, 4) if vol == vol else 0.0,
            composite_score=composite,
            reason="、".join(reason_parts) if reason_parts else "消息面平淡",
        ))

    # 排序：主要依消息面分數，次要依動能分數
    candidates.sort(key=lambda c: (c.news_score, c.momentum_score), reverse=True)

    # 前 5 名為推薦
    picks = candidates[:cfg.get("selection", {}).get("max_picks", 5)]

    reasoning = (
        f"從 {len(watch_list)} 檔觀察清單中分析 {len(candidates)} 檔，"
        f"以消息面驅動為主要排序、預估投報為次要排序。"
    )

    return StockPickResult(
        candidates=candidates,
        picks=picks,
        reasoning=reasoning,
    )
