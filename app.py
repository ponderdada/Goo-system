#!/usr/bin/env python3
"""投資決策系統 — Flask Web 應用。

啟動後在 http://localhost:5000 提供手機友善的投資儀表板。
"""

from __future__ import annotations

import datetime as dt
import json
import os
import threading
import time
import traceback

import yaml
from flask import Flask, render_template_string

from src.engines import cash_allocation, index_vs_stock, stock_picker

app = Flask(__name__)

# --- 快取機制 ---
_cache: dict = {
    "cash": None,
    "idx": None,
    "picks": None,
    "updated_at": None,
    "error": None,
}
_cache_lock = threading.Lock()


def load_config(path: str = "config/settings.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_analysis() -> None:
    """執行三大模組分析並寫入快取。"""
    try:
        config = load_config()
        cash = cash_allocation.decide(config)
        idx = index_vs_stock.decide(config)
        picks = stock_picker.decide(config)
        with _cache_lock:
            _cache["cash"] = cash
            _cache["idx"] = idx
            _cache["picks"] = picks
            _cache["updated_at"] = dt.datetime.now()
            _cache["error"] = None
    except Exception as e:
        with _cache_lock:
            _cache["error"] = f"{e}\n{traceback.format_exc()}"
            _cache["updated_at"] = dt.datetime.now()


def background_scheduler(interval_seconds: int = 3600) -> None:
    """背景排程：每隔指定秒數自動更新分析。"""
    while True:
        run_analysis()
        time.sleep(interval_seconds)


# --- 手機版 HTML 模板 ---
MOBILE_TEMPLATE = """\
<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<title>投資決策儀表板</title>
<style>
  :root {
    --bg: #0a0e1a;
    --card: #141b2d;
    --card-border: #1e2a45;
    --accent: #38bdf8;
    --green: #4ade80;
    --red: #f87171;
    --orange: #fbbf24;
    --purple: #a78bfa;
    --text: #e2e8f0;
    --muted: #8892a8;
    --radius: 16px;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;
    padding: 0;
    min-height: 100vh;
    -webkit-font-smoothing: antialiased;
  }

  /* 頂部狀態列 */
  .header {
    background: linear-gradient(135deg, #141b2d 0%, #1a2540 100%);
    padding: 3rem 1.5rem 1.5rem;
    text-align: center;
    border-bottom: 1px solid var(--card-border);
  }
  .header h1 {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--accent);
    letter-spacing: 0.03em;
  }
  .header .update-time {
    font-size: 0.8rem;
    color: var(--muted);
    margin-top: 0.4rem;
  }

  .container { padding: 1rem; max-width: 480px; margin: 0 auto; }

  /* 總覽卡片 */
  .summary-card {
    background: linear-gradient(135deg, #1a2a4a 0%, #162040 100%);
    border: 1px solid var(--card-border);
    border-radius: var(--radius);
    padding: 1.25rem;
    margin-bottom: 1rem;
  }
  .summary-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.6rem 0;
    border-bottom: 1px solid rgba(255,255,255,0.05);
  }
  .summary-row:last-child { border-bottom: none; }
  .summary-label { font-size: 0.85rem; color: var(--muted); }
  .summary-value { font-size: 1.3rem; font-weight: 700; }

  /* 模組卡片 */
  .card {
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: var(--radius);
    padding: 1.25rem;
    margin-bottom: 1rem;
  }
  .card-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 1rem;
  }
  .card-icon {
    width: 32px; height: 32px;
    border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1rem;
    flex-shrink: 0;
  }
  .card-title { font-size: 1rem; font-weight: 600; }

  /* 指標 pill */
  .metrics {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-bottom: 1rem;
  }
  .pill {
    background: rgba(255,255,255,0.05);
    border-radius: 10px;
    padding: 0.6rem 0.9rem;
    flex: 1;
    min-width: 100px;
    text-align: center;
  }
  .pill-label { font-size: 0.7rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }
  .pill-value { font-size: 1.1rem; font-weight: 700; margin-top: 0.2rem; }

  /* 長條圖 */
  .bar-wrapper { margin: 0.8rem 0; }
  .bar-track {
    height: 36px;
    background: rgba(255,255,255,0.05);
    border-radius: 10px;
    display: flex;
    overflow: hidden;
  }
  .bar-seg {
    display: flex; align-items: center; justify-content: center;
    font-size: 0.75rem; font-weight: 700; color: #0a0e1a;
    transition: width 0.6s ease;
  }

  /* 個股表格 */
  .stock-list { margin-top: 0.5rem; }
  .stock-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.75rem 0;
    border-bottom: 1px solid rgba(255,255,255,0.05);
  }
  .stock-item:last-child { border-bottom: none; }
  .stock-left { display: flex; align-items: center; gap: 0.6rem; }
  .stock-rank {
    width: 24px; height: 24px;
    border-radius: 6px;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.7rem; font-weight: 700;
    color: #0a0e1a;
  }
  .stock-rank.top { background: var(--green); }
  .stock-rank.normal { background: var(--muted); }
  .stock-symbol { font-weight: 600; font-size: 0.95rem; }
  .stock-reason { font-size: 0.72rem; color: var(--muted); margin-top: 0.15rem; max-width: 180px; }
  .stock-right { text-align: right; }
  .stock-score { font-size: 1.1rem; font-weight: 700; }
  .stock-momentum { font-size: 0.75rem; margin-top: 0.15rem; }

  .note {
    font-size: 0.75rem;
    color: var(--muted);
    line-height: 1.5;
    margin-top: 0.5rem;
  }

  .refresh-btn {
    display: block;
    width: 100%;
    padding: 0.9rem;
    background: rgba(56, 189, 248, 0.12);
    border: 1px solid rgba(56, 189, 248, 0.25);
    color: var(--accent);
    font-size: 0.9rem;
    font-weight: 600;
    border-radius: 12px;
    cursor: pointer;
    text-align: center;
    margin-bottom: 1rem;
    text-decoration: none;
  }
  .refresh-btn:active { background: rgba(56, 189, 248, 0.25); }

  .footer {
    text-align: center;
    font-size: 0.7rem;
    color: var(--muted);
    padding: 1.5rem 0 3rem;
  }

  .error-box {
    background: rgba(248, 113, 113, 0.1);
    border: 1px solid var(--red);
    border-radius: 12px;
    padding: 1rem;
    color: var(--red);
    font-size: 0.85rem;
    margin-bottom: 1rem;
    white-space: pre-wrap;
    word-break: break-all;
  }
</style>
</head>
<body>

<div class="header">
  <h1>投資決策儀表板</h1>
  <div class="update-time">
    {% if updated_at %}
      更新時間：{{ updated_at.strftime('%Y-%m-%d %H:%M') }}
    {% else %}
      尚未產生分析
    {% endif %}
  </div>
</div>

<div class="container">

{% if error %}
<div class="error-box">分析錯誤：{{ error }}</div>
{% endif %}

{% if cash %}

<!-- ===== 總覽 ===== -->
<div class="summary-card">
  <div class="summary-row">
    <span class="summary-label">現金保留</span>
    <span class="summary-value" style="color: var(--muted)">{{ (cash.cash_ratio * 100)|round }}%</span>
  </div>
  <div class="summary-row">
    <span class="summary-label">指數 ETF</span>
    <span class="summary-value" style="color: var(--purple)">{{ (cash.invest_ratio * idx.index_ratio * 100)|round(1) }}%</span>
  </div>
  <div class="summary-row">
    <span class="summary-label">個股</span>
    <span class="summary-value" style="color: var(--green)">{{ (cash.invest_ratio * idx.stock_ratio * 100)|round(1) }}%</span>
  </div>
</div>

<!-- ===== 模組一 ===== -->
<div class="card">
  <div class="card-header">
    <div class="card-icon" style="background: rgba(56,189,248,0.15);">💰</div>
    <span class="card-title">現金 vs 投資</span>
  </div>
  <div class="metrics">
    <div class="pill">
      <div class="pill-label">VIX</div>
      <div class="pill-value" style="color: {% if cash.vix > 25 %}var(--red){% elif cash.vix < 15 %}var(--green){% else %}var(--orange){% endif %}">
        {{ cash.vix }}</div>
    </div>
    <div class="pill">
      <div class="pill-label">級別</div>
      <div class="pill-value">{{ cash.vix_level }}</div>
    </div>
    <div class="pill">
      <div class="pill-label">大盤趨勢</div>
      <div class="pill-value" style="color: {% if cash.is_uptrend %}var(--green){% else %}var(--red){% endif %}">
        {{ '多頭 ▲' if cash.is_uptrend else '空頭 ▼' }}</div>
    </div>
  </div>
  <div class="bar-wrapper">
    <div class="bar-track">
      <div class="bar-seg" style="width: {{ (cash.cash_ratio * 100)|round }}%; background: var(--muted);">
        現金 {{ (cash.cash_ratio * 100)|round }}%</div>
      <div class="bar-seg" style="width: {{ (cash.invest_ratio * 100)|round }}%; background: var(--accent);">
        投資 {{ (cash.invest_ratio * 100)|round }}%</div>
    </div>
  </div>
  <div class="note">{{ cash.reasoning }}</div>
</div>

<!-- ===== 模組二 ===== -->
<div class="card">
  <div class="card-header">
    <div class="card-icon" style="background: rgba(167,139,250,0.15);">📊</div>
    <span class="card-title">指數 vs 個股</span>
  </div>
  <div class="metrics">
    <div class="pill">
      <div class="pill-label">市場寬度</div>
      <div class="pill-value">{{ idx.market_breadth if idx.market_breadth is not none else 'N/A' }}</div>
    </div>
    <div class="pill">
      <div class="pill-label">評級</div>
      <div class="pill-value">{{ idx.breadth_level }}</div>
    </div>
    <div class="pill">
      <div class="pill-label">波動率</div>
      <div class="pill-value">{{ (idx.avg_stock_volatility * 100)|round(1) }}%</div>
    </div>
  </div>
  <div class="bar-wrapper">
    <div class="bar-track">
      <div class="bar-seg" style="width: {{ (idx.index_ratio * 100)|round }}%; background: var(--purple);">
        指數 {{ (idx.index_ratio * 100)|round }}%</div>
      <div class="bar-seg" style="width: {{ (idx.stock_ratio * 100)|round }}%; background: var(--green);">
        個股 {{ (idx.stock_ratio * 100)|round }}%</div>
    </div>
  </div>
  <div class="note">{{ idx.reasoning }}</div>
</div>

<!-- ===== 模組三 ===== -->
<div class="card">
  <div class="card-header">
    <div class="card-icon" style="background: rgba(74,222,128,0.15);">🔍</div>
    <span class="card-title">推薦個股</span>
  </div>
  <div class="note" style="margin-bottom: 0.8rem;">{{ picks.reasoning }}</div>
  <div class="stock-list">
    {% for c in picks.candidates %}
    <div class="stock-item">
      <div class="stock-left">
        <div class="stock-rank {% if c in picks.picks %}top{% else %}normal{% endif %}">
          {{ loop.index }}</div>
        <div>
          <div class="stock-symbol">{{ c.symbol }}</div>
          <div class="stock-reason">{{ c.reason }}</div>
        </div>
      </div>
      <div class="stock-right">
        <div class="stock-score" style="color: {% if c in picks.picks %}var(--green){% else %}var(--text){% endif %}">
          {{ c.composite_score }}</div>
        <div class="stock-momentum" style="color: {% if c.momentum_score > 0 %}var(--green){% else %}var(--red){% endif %}">
          {{ (c.momentum_score * 100)|round(1) }}%</div>
      </div>
    </div>
    {% endfor %}
  </div>
</div>

{% else %}

<div class="card" style="text-align: center; padding: 3rem 1rem;">
  <div style="font-size: 2rem; margin-bottom: 1rem;">⏳</div>
  <div style="font-size: 1rem; color: var(--muted);">正在載入分析資料...</div>
  <div style="font-size: 0.8rem; color: var(--muted); margin-top: 0.5rem;">首次啟動需要數分鐘下載市場資料</div>
</div>

{% endif %}

<a href="/" class="refresh-btn">重新整理</a>

<div class="footer">
  僅供參考，不構成投資建議<br>
  投資決策系統 v1.0
</div>

</div>
</body>
</html>
"""


@app.route("/")
def dashboard():
    with _cache_lock:
        return render_template_string(
            MOBILE_TEMPLATE,
            cash=_cache["cash"],
            idx=_cache["idx"],
            picks=_cache["picks"],
            updated_at=_cache["updated_at"],
            error=_cache["error"],
        )


@app.route("/api/status")
def api_status():
    with _cache_lock:
        return {
            "has_data": _cache["cash"] is not None,
            "updated_at": _cache["updated_at"].isoformat() if _cache["updated_at"] else None,
            "error": _cache["error"],
        }


def create_app() -> Flask:
    """建立 Flask app 並啟動背景排程。"""
    config = load_config()
    interval = config.get("web", {}).get("refresh_interval_seconds", 3600)

    scheduler = threading.Thread(
        target=background_scheduler,
        args=(interval,),
        daemon=True,
    )
    scheduler.start()

    return app


def _auto_start() -> None:
    """模組載入時自動啟動背景排程（供 gunicorn 使用）。"""
    config = load_config()
    interval = config.get("web", {}).get("refresh_interval_seconds", 3600)
    scheduler = threading.Thread(target=background_scheduler, args=(interval,), daemon=True)
    scheduler.start()


# gunicorn 透過 app:app 取得此 instance，preload 時自動啟動排程
_auto_start()


if __name__ == "__main__":
    config = load_config()
    web_cfg = config.get("web", {})
    port = web_cfg.get("port", 5000)

    print(f"\n  投資決策儀表板已啟動：http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
