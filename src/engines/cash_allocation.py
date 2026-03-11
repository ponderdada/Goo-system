"""模組一：現金 vs 投資配置決策引擎（逆向加碼策略）。

核心邏輯：
  1. VIX 恐慌訊號 — 恐慌越高，投入越多（別人恐懼我貪婪）
  2. 回檔深度訊號 — 大盤從近期高點跌越深，投入越多（買在回檔）
  3. 兩個訊號加權合成，並設最低現金底線（永遠保留至少 5% 現金）

參考：
  - 倒金字塔建倉法（越跌越加重部位）
  - J.P. Morgan 分批投入研究（回檔 10-20% 時分批投入勝率最高）
  - Alpha Architect 趨勢保護模型（規則觸發式現金調度）
"""

from __future__ import annotations

from dataclasses import dataclass

from src.data.market_data import (
    compute_drawdown_from_recent_high,
    get_index_history,
    get_vix,
)


@dataclass
class CashDecision:
    vix: float
    vix_level: str               # calm / normal / fear / panic
    vix_cash_ratio: float        # VIX 訊號建議的現金比例
    drawdown_pct: float          # 大盤從近期高點回檔幅度 (0~1)
    drawdown_level: str          # near_high / pullback / correction / bear
    drawdown_cash_ratio: float   # 回檔訊號建議的現金比例
    recent_high: float           # 近期高點價位
    current_price: float         # 目前價位
    cash_ratio: float            # 最終建議現金比例 0~1
    invest_ratio: float          # 最終建議投資比例 0~1
    reasoning: str


def _vix_to_cash(vix: float, cfg: dict) -> tuple[float, str]:
    """VIX 恐慌訊號 → 現金比例（逆向：越恐慌 → 現金越少）。

    邏輯：
      VIX < 15  (calm)    → 市場過於安逸，可能見頂，保留較多現金
      VIX 15~25 (normal)  → 正常波動，維持中等現金
      VIX 25~35 (fear)    → 恐慌升溫，開始積極投入
      VIX ≥ 35  (panic)   → 極度恐慌，大幅投入（保留最少現金）
    """
    thresholds = cfg["vix_thresholds"]
    ratios = cfg["vix_cash_ratios"]

    if vix < thresholds["calm"]:
        return ratios["calm"], "calm"
    elif vix < thresholds["normal"]:
        # 在 calm~normal 之間線性插值
        t = (vix - thresholds["calm"]) / (thresholds["normal"] - thresholds["calm"])
        cash = ratios["calm"] + t * (ratios["normal"] - ratios["calm"])
        return round(cash, 4), "normal"
    elif vix < thresholds["fear"]:
        t = (vix - thresholds["normal"]) / (thresholds["fear"] - thresholds["normal"])
        cash = ratios["normal"] + t * (ratios["fear"] - ratios["normal"])
        return round(cash, 4), "fear"
    else:
        # VIX ≥ fear threshold，線性遞減到 panic 值（上限 VIX=50）
        cap_vix = min(vix, 50.0)
        t = (cap_vix - thresholds["fear"]) / max(50.0 - thresholds["fear"], 1)
        cash = ratios["fear"] + t * (ratios["panic"] - ratios["fear"])
        return round(max(cash, ratios["panic"]), 4), "panic"


def _drawdown_to_cash(drawdown_pct: float, cfg: dict) -> tuple[float, str]:
    """回檔深度訊號 → 現金比例（越跌 → 現金越少）。

    邏輯：
      回檔 < 3%          (near_high)   → 接近高點，保留較多現金
      回檔 3%~10%        (pullback)    → 小回檔，開始減少現金
      回檔 10%~20%       (correction)  → 修正，積極投入
      回檔 ≥ 20%         (bear)        → 熊市區域，大幅投入
    """
    levels = cfg["drawdown_levels"]
    ratios = cfg["drawdown_cash_ratios"]

    if drawdown_pct < levels["pullback"]:
        return ratios["near_high"], "near_high"
    elif drawdown_pct < levels["correction"]:
        # pullback ~ correction 之間線性插值
        t = (drawdown_pct - levels["pullback"]) / (levels["correction"] - levels["pullback"])
        cash = ratios["pullback"] + t * (ratios["correction"] - ratios["pullback"])
        return round(cash, 4), "pullback"
    elif drawdown_pct < levels["bear"]:
        t = (drawdown_pct - levels["correction"]) / (levels["bear"] - levels["correction"])
        cash = ratios["correction"] + t * (ratios["bear"] - ratios["correction"])
        return round(cash, 4), "correction"
    else:
        return ratios["bear"], "bear"


def decide(config: dict) -> CashDecision:
    """根據 VIX + 回檔深度雙訊號，決定現金 vs 投資配置。"""
    cfg = config["cash_allocation"]
    mkt = config["market"]

    # ── 訊號一：VIX 恐慌指標 ──
    vix = get_vix()
    vix_cash, vix_level = _vix_to_cash(vix, cfg)

    # ── 訊號二：大盤回檔深度 ──
    index_hist = get_index_history(mkt["index_symbol"])
    lookback = cfg.get("drawdown_lookback_days", 40)
    dd_pct, recent_high, current_price = compute_drawdown_from_recent_high(
        index_hist, lookback_days=lookback
    )
    dd_cash, dd_level = _drawdown_to_cash(dd_pct, cfg)

    # ── 加權合成 ──
    w_vix = cfg.get("weight_vix", 0.5)
    w_dd = cfg.get("weight_drawdown", 0.5)
    raw_cash = w_vix * vix_cash + w_dd * dd_cash

    # 最低現金底線
    floor = cfg.get("min_cash_floor", 0.05)
    final_cash = round(max(raw_cash, floor), 2)
    invest_ratio = round(1.0 - final_cash, 2)

    # ── 產生推理說明 ──
    vix_labels = {"calm": "平靜", "normal": "正常", "fear": "恐慌", "panic": "極度恐慌"}
    dd_labels = {"near_high": "接近高點", "pullback": "小幅回檔", "correction": "修正回檔", "bear": "熊市回檔"}

    reasoning = (
        f"【VIX 恐慌訊號】VIX = {vix:.1f}（{vix_labels.get(vix_level, vix_level)}），"
        f"建議現金 {vix_cash:.0%}。"
        f"【回檔深度訊號】大盤從近 {lookback} 日高點 {recent_high:,.0f} "
        f"回檔 {dd_pct:.1%} 至 {current_price:,.0f}（{dd_labels.get(dd_level, dd_level)}），"
        f"建議現金 {dd_cash:.0%}。"
        f"【綜合決策】加權後建議：現金 {final_cash:.0%} / 投資 {invest_ratio:.0%}。"
    )

    return CashDecision(
        vix=round(vix, 2),
        vix_level=vix_level,
        vix_cash_ratio=round(vix_cash, 4),
        drawdown_pct=round(dd_pct, 4),
        drawdown_level=dd_level,
        drawdown_cash_ratio=round(dd_cash, 4),
        recent_high=recent_high,
        current_price=current_price,
        cash_ratio=final_cash,
        invest_ratio=invest_ratio,
        reasoning=reasoning,
    )
