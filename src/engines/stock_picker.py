"""模組三：新聞驅動個股篩選引擎。

從觀察清單中，挑選出近一季因消息面（以價量異常為代理指標）
帶動上漲機率最大的個股。
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
    news_score: float       # 新聞/消息驅動分數 0~1
    momentum_score: float   # 動能分數（近季報酬率）
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
    """執行個股篩選。"""
    cfg = config["news_stock_picker"]
    watch_list = cfg["watch_list"]
    lookback = cfg["lookback_days"]
    sel = cfg["selection"]

    # 取得所有股票歷史
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

        # RSI 適中加分（40~70 為佳），過高或過低扣分
        if 40 <= rsi <= 70:
            rsi_bonus = 0.1
        elif rsi > 80 or rsi < 20:
            rsi_bonus = -0.15
        else:
            rsi_bonus = 0.0

        composite = (
            news_score * 0.40
            + momentum_norm * 0.40
            + 0.20 * (1.0 - min(vol, 1.0))  # 低波動加分
            + rsi_bonus
        )
        composite = round(max(min(composite, 1.0), 0.0), 4)

        reason_parts = []
        if news_score >= sel["min_news_score"]:
            reason_parts.append(f"消息面活躍({news_score:.2f})")
        if momentum > 0:
            reason_parts.append(f"正向動能({momentum:+.1%})")
        if 40 <= rsi <= 70:
            reason_parts.append(f"RSI 健康({rsi:.0f})")

        candidates.append(StockCandidate(
            symbol=symbol,
            news_score=news_score,
            momentum_score=round(momentum, 4),
            rsi=round(rsi, 1),
            volatility=round(vol, 4) if vol == vol else 0.0,
            composite_score=composite,
            reason="、".join(reason_parts) if reason_parts else "未達篩選門檻",
        ))

    # 排序
    candidates.sort(key=lambda c: c.composite_score, reverse=True)

    # 篩選
    picks = [
        c for c in candidates
        if c.news_score >= sel["min_news_score"]
        and c.momentum_score >= sel["min_momentum_score"]
    ][:sel["max_picks"]]

    # 若篩選後不足，取綜合分數最高的幾檔
    if not picks:
        picks = candidates[:sel["max_picks"]]

    reasoning = (
        f"從 {len(watch_list)} 檔觀察清單中分析 {len(candidates)} 檔，"
        f"篩選出 {len(picks)} 檔推薦個股。"
    )

    return StockPickResult(
        candidates=candidates,
        picks=picks,
        reasoning=reasoning,
    )
