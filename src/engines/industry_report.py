"""產業分析報告引擎。

針對排名第一的個股，自動生成：
  - 產業概況分析
  - 三情境預估投資報酬率（樂觀、中性、悲觀）

資料來源：yfinance 公司資訊 + 技術指標計算。
"""

from __future__ import annotations

from dataclasses import dataclass

import yfinance as yf

from src.data.market_data import (
    compute_momentum,
    compute_rsi,
    compute_volatility,
    get_stock_history,
)


# 台股代號 → 公司名稱 / 產業 對照表
_TW_STOCK_INFO: dict[str, dict] = {
    "0050.TW": {"name": "元大台灣50", "industry": "ETF 指數型基金", "sector": "金融"},
    "2330.TW": {"name": "台積電", "industry": "晶圓代工", "sector": "半導體"},
    "2317.TW": {"name": "鴻海", "industry": "電子代工/伺服器", "sector": "電子"},
    "2454.TW": {"name": "聯發科", "industry": "IC 設計", "sector": "半導體"},
    "2881.TW": {"name": "富邦金", "industry": "金融控股", "sector": "金融"},
    "2882.TW": {"name": "國泰金", "industry": "金融控股", "sector": "金融"},
    "2303.TW": {"name": "聯電", "industry": "晶圓代工", "sector": "半導體"},
    "3711.TW": {"name": "日月光投控", "industry": "封裝測試", "sector": "半導體"},
    "2412.TW": {"name": "中華電", "industry": "電信服務", "sector": "電信"},
    "2308.TW": {"name": "台達電", "industry": "電源/散熱/自動化", "sector": "電子"},
}

# 產業趨勢描述
_INDUSTRY_TRENDS: dict[str, str] = {
    "晶圓代工": "受惠 AI 晶片需求爆發，先進製程產能持續滿載，產業展望正面。",
    "IC 設計": "AI 邊緣運算與手機 AP 需求回溫，天璣系列市佔穩健成長。",
    "電子代工/伺服器": "AI 伺服器訂單持續湧入，雲端資本支出維持高檔。",
    "金融控股": "升息環境有利利差擴大，但需關注信用風險與房市曝險。",
    "封裝測試": "先進封裝（CoWoS）需求爆發，產能擴張帶動營收成長。",
    "電信服務": "5G 用戶穩定成長，企業專網與雲端服務為新成長動能。",
    "電源/散熱/自動化": "AI 伺服器高功耗帶動電源與散熱需求，電動車充電樁市場擴大。",
    "ETF 指數型基金": "追蹤台灣前 50 大市值股票，反映整體市場表現。",
}


@dataclass
class IndustryReport:
    symbol: str
    company_name: str
    industry: str
    sector: str
    current_price: float
    analysis: str           # 產業分析文字
    # 樂觀劇本
    bull_return: float      # 預估報酬率 %
    bull_target: float      # 目標價
    bull_reason: str
    # 中性劇本
    base_return: float
    base_target: float
    base_reason: str
    # 悲觀劇本
    bear_return: float
    bear_target: float
    bear_reason: str


def _get_stock_info(symbol: str) -> dict:
    """取得個股公司資訊（優先用本地對照表，再嘗試 yfinance）。"""
    if symbol in _TW_STOCK_INFO:
        return _TW_STOCK_INFO[symbol]
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}
        return {
            "name": info.get("shortName", symbol),
            "industry": info.get("industry", "未知產業"),
            "sector": info.get("sector", "未知"),
        }
    except Exception:
        return {"name": symbol, "industry": "未知產業", "sector": "未知"}


def generate(symbol: str, news_score: float, momentum: float) -> IndustryReport | None:
    """為指定個股生成產業分析報告。"""
    try:
        info = _get_stock_info(symbol)
        hist = get_stock_history(symbol, period="6mo")
        if hist.empty:
            return None

        current_price = float(hist["Close"].iloc[-1])
        rsi = compute_rsi(hist)
        vol = compute_volatility(hist)
        mom_3m = compute_momentum(hist, lookback=60)

        industry = info["industry"]
        name = info["name"]
        sector = info["sector"]
        trend = _INDUSTRY_TRENDS.get(industry, f"{industry}產業近期動態需持續關注。")

        # ── 生成分析報告 ──
        # 根據指標動態生成文字
        if mom_3m > 0.10:
            momentum_desc = f"近一季漲幅達 {mom_3m:.1%}，動能強勁"
        elif mom_3m > 0:
            momentum_desc = f"近一季小幅上漲 {mom_3m:.1%}，走勢穩健"
        elif mom_3m > -0.10:
            momentum_desc = f"近一季小幅回檔 {mom_3m:.1%}，但跌幅有限"
        else:
            momentum_desc = f"近一季回檔 {mom_3m:.1%}，短線承壓"

        if rsi > 70:
            rsi_desc = f"RSI 達 {rsi:.0f}，短線偏超買，留意回檔風險"
        elif rsi < 30:
            rsi_desc = f"RSI 僅 {rsi:.0f}，短線超賣，可能出現反彈"
        else:
            rsi_desc = f"RSI {rsi:.0f}，技術面中性健康"

        if news_score >= 0.6:
            news_desc = "消息面活躍，近期放量明顯，市場關注度高"
        elif news_score >= 0.4:
            news_desc = "消息面溫和，量能尚可"
        else:
            news_desc = "消息面偏淡，近期缺乏明顯催化劑"

        analysis = (
            f"【{name}（{symbol}）】屬於{sector}產業 — {industry}。"
            f"{trend}"
            f"{momentum_desc}。{rsi_desc}。{news_desc}。"
            f"年化波動率 {vol:.1%}。"
        )

        # ── 三情境投報率 ──
        # 基於動能、波動率、RSI 動態計算
        if vol != vol:  # NaN check
            vol = 0.3

        # 樂觀：動能延續 + 產業利多
        bull_pct = round(max(mom_3m * 2 + vol * 0.5, 0.08) * 100, 1)
        bull_pct = min(bull_pct, 60.0)  # 上限 60%
        bull_target = round(current_price * (1 + bull_pct / 100), 1)

        # 中性：溫和成長
        base_pct = round(max(mom_3m * 0.8 + 0.03, 0.02) * 100, 1)
        base_pct = min(base_pct, 30.0)
        base_target = round(current_price * (1 + base_pct / 100), 1)

        # 悲觀：回檔修正
        bear_pct = round(min(-vol * 0.8, -0.05) * 100, 1)
        bear_pct = max(bear_pct, -40.0)  # 下限 -40%
        bear_target = round(current_price * (1 + bear_pct / 100), 1)

        # 情境理由
        if industry in ("晶圓代工", "IC 設計", "封裝測試"):
            bull_reason = "AI 需求超預期，先進製程漲價，營收大幅成長"
            base_reason = "AI 需求穩健，產能利用率維持高檔"
            bear_reason = "全球景氣放緩，終端需求不振，庫存調整"
        elif industry in ("電子代工/伺服器",):
            bull_reason = "AI 伺服器出貨量超預期，毛利率提升"
            base_reason = "伺服器訂單穩健，營收溫和成長"
            bear_reason = "雲端資本支出縮減，訂單放緩"
        elif industry in ("金融控股",):
            bull_reason = "利差持續擴大，投資收益回升"
            base_reason = "獲利持平，股利配發穩定"
            bear_reason = "信用風險升高，投資部位虧損"
        elif industry in ("電信服務",):
            bull_reason = "5G 滲透率加速，企業服務營收躍升"
            base_reason = "用戶數穩定成長，ARPU 持平"
            bear_reason = "價格戰壓縮毛利，資本支出沉重"
        elif industry in ("電源/散熱/自動化",):
            bull_reason = "AI 伺服器電源需求暴增，新品放量"
            base_reason = "電動車與 AI 雙軌成長，營收穩健"
            bear_reason = "終端需求放緩，庫存去化壓力"
        else:
            bull_reason = "產業利多催化，營收優於預期"
            base_reason = "產業穩健發展，獲利持平"
            bear_reason = "市場逆風，需求下滑"

        return IndustryReport(
            symbol=symbol,
            company_name=name,
            industry=industry,
            sector=sector,
            current_price=current_price,
            analysis=analysis,
            bull_return=bull_pct,
            bull_target=bull_target,
            bull_reason=bull_reason,
            base_return=base_pct,
            base_target=base_target,
            base_reason=base_reason,
            bear_return=bear_pct,
            bear_target=bear_target,
            bear_reason=bear_reason,
        )
    except Exception:
        return None
