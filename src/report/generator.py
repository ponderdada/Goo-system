"""每日投資決策報告產生器。"""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

from jinja2 import Template

HTML_TEMPLATE = Template("""\
<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>投資決策日報 — {{ date }}</title>
<style>
  :root { --bg: #0f172a; --card: #1e293b; --accent: #38bdf8; --green: #4ade80;
           --red: #f87171; --text: #e2e8f0; --muted: #94a3b8; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif;
         padding: 2rem; max-width: 960px; margin: 0 auto; }
  h1 { color: var(--accent); margin-bottom: 0.5rem; font-size: 1.8rem; }
  .date { color: var(--muted); margin-bottom: 2rem; }
  .card { background: var(--card); border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; }
  .card h2 { color: var(--accent); font-size: 1.2rem; margin-bottom: 1rem;
             border-bottom: 1px solid #334155; padding-bottom: 0.5rem; }
  .metric { display: inline-block; background: #334155; border-radius: 8px;
            padding: 0.8rem 1.2rem; margin: 0.3rem; text-align: center; min-width: 120px; }
  .metric .label { font-size: 0.75rem; color: var(--muted); }
  .metric .value { font-size: 1.4rem; font-weight: bold; }
  .metric .value.green { color: var(--green); }
  .metric .value.red { color: var(--red); }
  .bar-container { display: flex; height: 28px; border-radius: 6px; overflow: hidden; margin: 0.8rem 0; }
  .bar-cash { background: var(--muted); display: flex; align-items: center; justify-content: center;
              font-size: 0.8rem; font-weight: bold; }
  .bar-invest { background: var(--accent); display: flex; align-items: center; justify-content: center;
                font-size: 0.8rem; font-weight: bold; color: #0f172a; }
  .bar-index { background: #818cf8; display: flex; align-items: center; justify-content: center;
               font-size: 0.8rem; font-weight: bold; color: #0f172a; }
  .bar-stock { background: var(--green); display: flex; align-items: center; justify-content: center;
               font-size: 0.8rem; font-weight: bold; color: #0f172a; }
  table { width: 100%; border-collapse: collapse; margin-top: 0.8rem; }
  th, td { padding: 0.6rem 0.8rem; text-align: left; border-bottom: 1px solid #334155; }
  th { color: var(--muted); font-size: 0.8rem; text-transform: uppercase; }
  .pick-row { background: #1a3a2a; }
  .reasoning { color: var(--muted); font-size: 0.9rem; margin-top: 0.8rem; line-height: 1.6; }
  .footer { text-align: center; color: var(--muted); font-size: 0.8rem; margin-top: 2rem; }
</style>
</head>
<body>
<h1>投資決策日報</h1>
<p class="date">{{ date }} 分析報告</p>

<!-- 模組一：現金配置 -->
<div class="card">
  <h2>一、現金 vs 投資配置</h2>
  <div>
    <div class="metric">
      <div class="label">VIX 恐慌指數</div>
      <div class="value {% if cash.vix > 25 %}red{% elif cash.vix < 15 %}green{% endif %}">
        {{ cash.vix }}</div>
    </div>
    <div class="metric">
      <div class="label">VIX 級別</div>
      <div class="value">{{ cash.vix_level }}</div>
    </div>
    <div class="metric">
      <div class="label">大盤趨勢</div>
      <div class="value {% if cash.is_uptrend %}green{% else %}red{% endif %}">
        {{ '多頭 ▲' if cash.is_uptrend else '空頭 ▼' }}</div>
    </div>
  </div>
  <div class="bar-container">
    <div class="bar-cash" style="width: {{ (cash.cash_ratio * 100)|round }}%">
      現金 {{ (cash.cash_ratio * 100)|round }}%</div>
    <div class="bar-invest" style="width: {{ (cash.invest_ratio * 100)|round }}%">
      投資 {{ (cash.invest_ratio * 100)|round }}%</div>
  </div>
  <p class="reasoning">{{ cash.reasoning }}</p>
</div>

<!-- 模組二：指數 vs 個股 -->
<div class="card">
  <h2>二、指數 vs 個股配置</h2>
  <div>
    <div class="metric">
      <div class="label">市場寬度</div>
      <div class="value">{{ idx.market_breadth if idx.market_breadth is not none else 'N/A' }}</div>
    </div>
    <div class="metric">
      <div class="label">寬度評級</div>
      <div class="value">{{ idx.breadth_level }}</div>
    </div>
    <div class="metric">
      <div class="label">個股均波動率</div>
      <div class="value">{{ (idx.avg_stock_volatility * 100)|round(1) }}%</div>
    </div>
  </div>
  <p style="color: var(--muted); font-size: 0.85rem; margin-top: 0.5rem;">
    以下比例為「投資部位」內的分配：</p>
  <div class="bar-container">
    <div class="bar-index" style="width: {{ (idx.index_ratio * 100)|round }}%">
      指數 {{ (idx.index_ratio * 100)|round }}%</div>
    <div class="bar-stock" style="width: {{ (idx.stock_ratio * 100)|round }}%">
      個股 {{ (idx.stock_ratio * 100)|round }}%</div>
  </div>
  <p class="reasoning">{{ idx.reasoning }}</p>
</div>

<!-- 模組三：個股推薦 -->
<div class="card">
  <h2>三、新聞驅動個股推薦</h2>
  <p class="reasoning" style="margin-bottom: 0.8rem;">{{ picks.reasoning }}</p>
  <table>
    <thead>
      <tr>
        <th>代碼</th>
        <th>消息分數</th>
        <th>動能</th>
        <th>RSI</th>
        <th>波動率</th>
        <th>綜合得分</th>
        <th>理由</th>
      </tr>
    </thead>
    <tbody>
    {% for c in picks.candidates %}
      <tr {% if c in picks.picks %}class="pick-row"{% endif %}>
        <td><strong>{{ c.symbol }}</strong></td>
        <td>{{ c.news_score }}</td>
        <td class="{% if c.momentum_score > 0 %}green{% else %}red{% endif %}">
          {{ (c.momentum_score * 100)|round(1) }}%</td>
        <td>{{ c.rsi }}</td>
        <td>{{ (c.volatility * 100)|round(1) }}%</td>
        <td><strong>{{ c.composite_score }}</strong></td>
        <td style="font-size: 0.85rem;">{{ c.reason }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
  {% if picks.picks %}
  <p style="margin-top: 1rem; color: var(--green); font-weight: bold;">
    推薦標的：{{ picks.picks | map(attribute='symbol') | join(', ') }}
  </p>
  {% endif %}
</div>

<!-- 總結 -->
<div class="card">
  <h2>投資配置總結</h2>
  <table>
    <tr><td>現金保留</td><td><strong>{{ (cash.cash_ratio * 100)|round }}%</strong></td></tr>
    <tr><td>指數型 ETF</td>
        <td><strong>{{ (cash.invest_ratio * idx.index_ratio * 100)|round(1) }}%</strong></td></tr>
    <tr><td>個股</td>
        <td><strong>{{ (cash.invest_ratio * idx.stock_ratio * 100)|round(1) }}%</strong></td></tr>
  </table>
</div>

<p class="footer">此報告由投資決策系統自動產生，僅供參考，不構成投資建議。</p>
</body>
</html>
""")


TEXT_TEMPLATE = Template("""\
============================================================
  投資決策日報 — {{ date }}
============================================================

【一、現金 vs 投資配置】
  VIX = {{ cash.vix }}（{{ cash.vix_level }}）
  大盤趨勢：{{ '多頭 ▲' if cash.is_uptrend else '空頭 ▼' }}
  建議：現金 {{ (cash.cash_ratio * 100)|round }}% / 投資 {{ (cash.invest_ratio * 100)|round }}%
  {{ cash.reasoning }}

【二、指數 vs 個股配置】（佔投資部位）
  市場寬度：{{ idx.market_breadth if idx.market_breadth is not none else 'N/A' }}（{{ idx.breadth_level }}）
  個股平均波動率：{{ (idx.avg_stock_volatility * 100)|round(1) }}%
  建議：指數 {{ (idx.index_ratio * 100)|round }}% / 個股 {{ (idx.stock_ratio * 100)|round }}%
  {{ idx.reasoning }}

【三、新聞驅動個股推薦】
  {{ picks.reasoning }}
{% for c in picks.picks %}
  ★ {{ c.symbol }}  綜合 {{ c.composite_score }}  消息 {{ c.news_score }}  動能 {{ (c.momentum_score * 100)|round(1) }}%  RSI {{ c.rsi }}
    → {{ c.reason }}
{% endfor %}

【投資配置總結】
  現金保留：{{ (cash.cash_ratio * 100)|round }}%
  指數型 ETF：{{ (cash.invest_ratio * idx.index_ratio * 100)|round(1) }}%
  個股：{{ (cash.invest_ratio * idx.stock_ratio * 100)|round(1) }}%

※ 此報告由投資決策系統自動產生，僅供參考，不構成投資建議。
""")


def generate_report(
    cash_decision,
    index_decision,
    stock_result,
    config: dict,
) -> str:
    """產生報告並儲存，回傳檔案路徑。"""
    report_cfg = config.get("report", {})
    output_dir = report_cfg.get("output_dir", "reports")
    fmt = report_cfg.get("format", "html")

    os.makedirs(output_dir, exist_ok=True)

    today = dt.date.today().isoformat()
    context = {
        "date": today,
        "cash": cash_decision,
        "idx": index_decision,
        "picks": stock_result,
    }

    if fmt == "html":
        content = HTML_TEMPLATE.render(**context)
        filename = f"{output_dir}/report_{today}.html"
    else:
        content = TEXT_TEMPLATE.render(**context)
        filename = f"{output_dir}/report_{today}.txt"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)

    return filename
