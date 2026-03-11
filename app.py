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
from flask import Flask, jsonify, render_template_string, request

from src.engines import cash_allocation, industry_report, stock_picker
from src.data import watchlist as wl

app = Flask(__name__)

# --- 快取機制 ---
_cache: dict = {
    "cash": None,
    "picks": None,
    "report": None,
    "updated_at": None,
    "error": None,
}
_cache_lock = threading.Lock()


_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_config(path: str | None = None) -> dict:
    if path is None:
        path = os.path.join(_BASE_DIR, "config", "settings.yaml")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_analysis() -> None:
    """執行三大模組分析並寫入快取。"""
    try:
        config = load_config()
        cash = cash_allocation.decide(config)
        picks = stock_picker.decide(config)
        # 為排名第一的個股生成產業分析報告
        report = None
        if picks.candidates:
            top = picks.candidates[0]
            report = industry_report.generate(
                top.symbol, top.news_score, top.momentum_score
            )
        with _cache_lock:
            _cache["cash"] = cash
            _cache["picks"] = picks
            _cache["report"] = report
            _cache["updated_at"] = dt.datetime.now()
            _cache["error"] = None
    except Exception as e:
        # 只記錄簡潔的錯誤訊息，不顯示完整 traceback
        err_str = str(e)
        if "rate limit" in err_str.lower() or "too many requests" in err_str.lower():
            friendly = "Yahoo Finance 暫時限制了請求次數，系統將在幾分鐘後自動重試。"
        else:
            friendly = f"分析時發生錯誤：{err_str}"
        with _cache_lock:
            _cache["error"] = friendly
            _cache["updated_at"] = dt.datetime.now()


_RETRY_INTERVALS = [60, 180, 300]  # 失敗後的重試等待秒數（1分、3分、5分）


def background_scheduler(interval_seconds: int = 3600) -> None:
    """背景排程：每隔指定秒數自動更新分析，失敗時自動重試。"""
    while True:
        run_analysis()
        with _cache_lock:
            has_error = _cache["error"] is not None
            has_data = _cache["cash"] is not None
        if has_error and not has_data:
            # 還沒成功取得過資料，短間隔重試
            for wait in _RETRY_INTERVALS:
                time.sleep(wait)
                run_analysis()
                with _cache_lock:
                    if _cache["cash"] is not None:
                        break  # 成功了
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

  /* 刪除按鈕 */
  .del-btn {
    background: rgba(248,113,113,0.15);
    border: none;
    color: var(--red);
    font-size: 1rem;
    width: 28px; height: 28px;
    border-radius: 8px;
    cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
    margin-left: 0.5rem;
  }
  .del-btn:active { background: rgba(248,113,113,0.35); }

  /* 新增個股輸入列 */
  .add-row {
    display: flex;
    gap: 0.5rem;
    margin-top: 0.8rem;
    padding-top: 0.8rem;
    border-top: 1px solid rgba(255,255,255,0.08);
  }
  .add-input {
    flex: 1;
    background: rgba(255,255,255,0.05);
    border: 1px solid var(--card-border);
    border-radius: 10px;
    padding: 0.6rem 0.8rem;
    color: var(--text);
    font-size: 0.85rem;
    outline: none;
  }
  .add-input::placeholder { color: var(--muted); }
  .add-input:focus { border-color: var(--accent); }
  .add-btn {
    background: rgba(74,222,128,0.15);
    border: 1px solid rgba(74,222,128,0.3);
    color: var(--green);
    font-size: 0.85rem;
    font-weight: 600;
    padding: 0.6rem 1rem;
    border-radius: 10px;
    cursor: pointer;
    white-space: nowrap;
  }
  .add-btn:active { background: rgba(74,222,128,0.3); }
  .stock-name { font-size: 0.72rem; color: var(--muted); }
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
    <span class="summary-label">建議現金保留</span>
    <span class="summary-value" style="color: var(--muted)">{{ (cash.cash_ratio * 100)|round }}%</span>
  </div>
  <div class="summary-row">
    <span class="summary-label">建議投資比例</span>
    <span class="summary-value" style="color: var(--accent)">{{ (cash.invest_ratio * 100)|round }}%</span>
  </div>
</div>

<!-- ===== 模組一：VIX 恐慌訊號 ===== -->
<div class="card">
  <div class="card-header">
    <div class="card-icon" style="background: rgba(56,189,248,0.15);">💰</div>
    <span class="card-title">VIX 恐慌訊號</span>
  </div>
  <div class="metrics">
    <div class="pill">
      <div class="pill-label">VIX</div>
      <div class="pill-value" style="color: {% if cash.vix > 35 %}var(--green){% elif cash.vix > 25 %}var(--accent){% elif cash.vix < 15 %}var(--red){% else %}var(--orange){% endif %}">
        {{ cash.vix }}</div>
    </div>
    <div class="pill">
      <div class="pill-label">恐慌等級</div>
      <div class="pill-value">{{ {'calm':'平靜','normal':'正常','fear':'恐慌','panic':'極度恐慌'}.get(cash.vix_level, cash.vix_level) }}</div>
    </div>
    <div class="pill">
      <div class="pill-label">VIX 建議現金</div>
      <div class="pill-value">{{ (cash.vix_cash_ratio * 100)|round }}%</div>
    </div>
  </div>
  <div class="note" style="font-size: 0.72rem; color: var(--muted);">恐慌越高 → 投入越多（別人恐懼我貪婪）</div>
</div>

<!-- ===== 模組一-B：回檔深度訊號 ===== -->
<div class="card">
  <div class="card-header">
    <div class="card-icon" style="background: rgba(248,113,113,0.15);">📉</div>
    <span class="card-title">回檔深度訊號</span>
  </div>
  <div class="metrics">
    <div class="pill">
      <div class="pill-label">回檔幅度</div>
      <div class="pill-value" style="color: {% if cash.drawdown_pct > 0.10 %}var(--green){% elif cash.drawdown_pct > 0.05 %}var(--accent){% else %}var(--orange){% endif %}">
        -{{ (cash.drawdown_pct * 100)|round(1) }}%</div>
    </div>
    <div class="pill">
      <div class="pill-label">回檔等級</div>
      <div class="pill-value">{{ {'near_high':'接近高點','pullback':'小回檔','correction':'修正','bear':'熊市'}.get(cash.drawdown_level, cash.drawdown_level) }}</div>
    </div>
    <div class="pill">
      <div class="pill-label">回檔建議現金</div>
      <div class="pill-value">{{ (cash.drawdown_cash_ratio * 100)|round }}%</div>
    </div>
  </div>
  <div class="metrics">
    <div class="pill">
      <div class="pill-label">近期高點</div>
      <div class="pill-value" style="font-size: 0.9rem;">{{ '{:,.0f}'.format(cash.recent_high) }}</div>
    </div>
    <div class="pill">
      <div class="pill-label">目前價位</div>
      <div class="pill-value" style="font-size: 0.9rem;">{{ '{:,.0f}'.format(cash.current_price) }}</div>
    </div>
  </div>
  <div class="note" style="font-size: 0.72rem; color: var(--muted);">跌越深 → 投入越多（買在回檔）</div>
</div>

<!-- ===== 個股排名 ===== -->
<div class="card">
  <div class="card-header">
    <div class="card-icon" style="background: rgba(74,222,128,0.15);">🏆</div>
    <span class="card-title">個股排名</span>
  </div>
  <div class="note" style="margin-bottom: 0.8rem;">{{ picks.reasoning }}</div>
  <div class="stock-list">
    {% for c in picks.candidates %}
    <div class="stock-item" id="stock-{{ c.symbol }}">
      <div class="stock-left">
        <div class="stock-rank {% if loop.index <= 3 %}top{% else %}normal{% endif %}">
          {{ loop.index }}</div>
        <div>
          <div class="stock-symbol">{{ c.company_name }} <span class="stock-name">{{ c.symbol }}</span></div>
          <div class="stock-reason">{{ c.reason }}</div>
        </div>
      </div>
      <div style="display:flex;align-items:center;">
        <div class="stock-right">
          <div class="stock-score" style="color: {% if loop.index <= 3 %}var(--green){% else %}var(--text){% endif %}">
            {{ c.composite_score }}</div>
          <div class="stock-momentum" style="color: {% if c.momentum_score > 0 %}var(--green){% else %}var(--red){% endif %}">
            {{ (c.momentum_score * 100)|round(1) }}%</div>
        </div>
        <button class="del-btn" onclick="removeStock('{{ c.symbol }}')" title="移除">x</button>
      </div>
    </div>
    {% endfor %}
  </div>
  <div class="add-row">
    <input class="add-input" id="add-symbol" type="text" placeholder="輸入股票代號，例如 2330" />
    <button class="add-btn" onclick="addStock()">新增</button>
  </div>
</div>

<!-- ===== 產業分析報告 ===== -->
{% if report %}
<div class="card">
  <div class="card-header">
    <div class="card-icon" style="background: rgba(167,139,250,0.15);">📋</div>
    <span class="card-title">{{ report.symbol }} 產業分析報告</span>
  </div>

  <div class="metrics">
    <div class="pill">
      <div class="pill-label">產業</div>
      <div class="pill-value" style="font-size: 0.85rem;">{{ report.industry }}</div>
    </div>
    <div class="pill">
      <div class="pill-label">目前股價</div>
      <div class="pill-value" style="font-size: 0.85rem;">{{ '{:,.1f}'.format(report.current_price) }}</div>
    </div>
  </div>

  <div style="margin-bottom: 1rem;">
    <div class="note" style="font-size: 0.82rem; color: var(--text); line-height: 1.7;">{{ report.analysis }}</div>
  </div>

  <div style="font-size: 0.82rem; font-weight: 600; color: var(--accent); margin-bottom: 0.6rem;">預估投資報酬率</div>

  <div class="stock-list">
    <div class="stock-item">
      <div class="stock-left">
        <div class="stock-rank" style="background: var(--green);">+</div>
        <div>
          <div class="stock-symbol" style="font-size: 0.85rem;">樂觀劇本</div>
          <div class="stock-reason">{{ report.bull_reason }}</div>
        </div>
      </div>
      <div class="stock-right">
        <div class="stock-score" style="color: var(--green);">+{{ report.bull_return }}%</div>
        <div class="stock-momentum" style="color: var(--muted);">目標 {{ '{:,.0f}'.format(report.bull_target) }}</div>
      </div>
    </div>
    <div class="stock-item">
      <div class="stock-left">
        <div class="stock-rank" style="background: var(--orange);">=</div>
        <div>
          <div class="stock-symbol" style="font-size: 0.85rem;">中性劇本</div>
          <div class="stock-reason">{{ report.base_reason }}</div>
        </div>
      </div>
      <div class="stock-right">
        <div class="stock-score" style="color: var(--orange);">+{{ report.base_return }}%</div>
        <div class="stock-momentum" style="color: var(--muted);">目標 {{ '{:,.0f}'.format(report.base_target) }}</div>
      </div>
    </div>
    <div class="stock-item">
      <div class="stock-left">
        <div class="stock-rank" style="background: var(--red);">-</div>
        <div>
          <div class="stock-symbol" style="font-size: 0.85rem;">悲觀劇本</div>
          <div class="stock-reason">{{ report.bear_reason }}</div>
        </div>
      </div>
      <div class="stock-right">
        <div class="stock-score" style="color: var(--red);">{{ report.bear_return }}%</div>
        <div class="stock-momentum" style="color: var(--muted);">目標 {{ '{:,.0f}'.format(report.bear_target) }}</div>
      </div>
    </div>
  </div>
</div>
{% endif %}

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

<script>
function removeStock(symbol) {
  if (!confirm('確定移除 ' + symbol + '？')) return;
  fetch('/api/watchlist/remove', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({symbol: symbol})
  }).then(r => r.json()).then(() => {
    var el = document.getElementById('stock-' + symbol);
    if (el) el.style.display = 'none';
  });
}

function addStock() {
  var input = document.getElementById('add-symbol');
  var sym = input.value.trim();
  if (!sym) return;
  input.disabled = true;
  fetch('/api/watchlist/add', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({symbol: sym})
  }).then(r => r.json()).then(data => {
    input.value = '';
    input.disabled = false;
    alert(data.added + ' 已新增，下次分析更新時將納入排名。');
  }).catch(() => {
    input.disabled = false;
    alert('新增失敗，請稍後再試');
  });
}

document.getElementById('add-symbol')?.addEventListener('keydown', function(e) {
  if (e.key === 'Enter') addStock();
});
</script>
</body>
</html>
"""


@app.route("/")
def dashboard():
    with _cache_lock:
        return render_template_string(
            MOBILE_TEMPLATE,
            cash=_cache["cash"],
            picks=_cache["picks"],
            report=_cache["report"],
            updated_at=_cache["updated_at"],
            error=_cache["error"],
        )


@app.route("/healthz")
def healthz():
    """Render 健康檢查端點 — 立即回應，不等分析完成。"""
    return {"status": "ok"}, 200


@app.route("/api/status")
def api_status():
    with _cache_lock:
        return {
            "has_data": _cache["cash"] is not None,
            "updated_at": _cache["updated_at"].isoformat() if _cache["updated_at"] else None,
            "error": _cache["error"],
        }


@app.route("/api/watchlist", methods=["GET"])
def api_watchlist_get():
    """取得目前觀察清單。"""
    return jsonify(wl.load())


@app.route("/api/watchlist/add", methods=["POST"])
def api_watchlist_add():
    """新增個股到觀察清單。"""
    data = request.get_json(silent=True) or {}
    symbol = data.get("symbol", "").strip()
    if not symbol:
        return jsonify({"error": "請輸入股票代號"}), 400
    symbols = wl.add(symbol)
    return jsonify({"symbols": symbols, "added": symbol.upper()})


@app.route("/api/watchlist/remove", methods=["POST"])
def api_watchlist_remove():
    """從觀察清單移除個股。"""
    data = request.get_json(silent=True) or {}
    symbol = data.get("symbol", "").strip()
    if not symbol:
        return jsonify({"error": "請輸入股票代號"}), 400
    symbols = wl.remove(symbol)
    return jsonify({"symbols": symbols, "removed": symbol})


_scheduler_started = False


@app.before_request
def _ensure_scheduler():
    """第一個 HTTP 請求到來時才啟動背景排程（避免 import 時崩潰）。"""
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler_started = True
    try:
        config = load_config()
        interval = config.get("web", {}).get("refresh_interval_seconds", 3600)
    except Exception:
        interval = 3600
    t = threading.Thread(target=background_scheduler, args=(interval,), daemon=True)
    t.start()


if __name__ == "__main__":
    config = load_config()
    web_cfg = config.get("web", {})
    port = web_cfg.get("port", 5000)

    _scheduler_started = True
    threading.Thread(
        target=background_scheduler,
        args=(web_cfg.get("refresh_interval_seconds", 3600),),
        daemon=True,
    ).start()

    print(f"\n  投資決策儀表板已啟動：http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
