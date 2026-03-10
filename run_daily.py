#!/usr/bin/env python3
"""投資決策系統 — 每日執行入口。

使用方式：
    python run_daily.py              # 產生 HTML 報告
    python run_daily.py --text       # 產生純文字報告
    python run_daily.py --no-open    # 不自動開啟瀏覽器
"""

from __future__ import annotations

import argparse
import platform
import subprocess
import sys
from pathlib import Path

import yaml

from src.engines import cash_allocation, index_vs_stock, stock_picker
from src.report.generator import generate_report


def load_config(path: str = "config/settings.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def open_file(filepath: str) -> None:
    """跨平台開啟檔案。"""
    system = platform.system()
    if system == "Darwin":
        subprocess.run(["open", filepath])
    elif system == "Windows":
        subprocess.run(["start", filepath], shell=True)
    else:
        subprocess.run(["xdg-open", filepath])


def main() -> None:
    parser = argparse.ArgumentParser(description="投資決策系統每日分析")
    parser.add_argument("--text", action="store_true", help="產生純文字報告")
    parser.add_argument("--no-open", action="store_true", help="不自動開啟報告")
    parser.add_argument("--config", default="config/settings.yaml", help="設定檔路徑")
    args = parser.parse_args()

    config = load_config(args.config)

    if args.text:
        config["report"]["format"] = "text"

    print("=" * 50)
    print("  投資決策系統 — 開始每日分析")
    print("=" * 50)

    # 模組一：現金配置
    print("\n[1/3] 分析現金 vs 投資配置...")
    try:
        cash_result = cash_allocation.decide(config)
        print(f"  ✓ VIX={cash_result.vix} → 現金 {cash_result.cash_ratio:.0%} / 投資 {cash_result.invest_ratio:.0%}")
    except Exception as e:
        print(f"  ✗ 現金配置分析失敗: {e}", file=sys.stderr)
        sys.exit(1)

    # 模組二：指數 vs 個股
    print("\n[2/3] 分析指數 vs 個股配置...")
    try:
        idx_result = index_vs_stock.decide(config)
        print(f"  ✓ 指數 {idx_result.index_ratio:.0%} / 個股 {idx_result.stock_ratio:.0%}")
    except Exception as e:
        print(f"  ✗ 指數個股配置分析失敗: {e}", file=sys.stderr)
        sys.exit(1)

    # 模組三：個股篩選
    print("\n[3/3] 篩選新聞驅動個股...")
    try:
        pick_result = stock_picker.decide(config)
        if pick_result.picks:
            symbols = ", ".join(p.symbol for p in pick_result.picks)
            print(f"  ✓ 推薦標的: {symbols}")
        else:
            print("  ✓ 無符合條件的推薦標的")
    except Exception as e:
        print(f"  ✗ 個股篩選失敗: {e}", file=sys.stderr)
        sys.exit(1)

    # 產生報告
    print("\n正在產生報告...")
    filepath = generate_report(cash_result, idx_result, pick_result, config)
    print(f"  ✓ 報告已儲存: {filepath}")

    if not args.no_open and config.get("report", {}).get("auto_open", True):
        open_file(filepath)
        print("  ✓ 已開啟報告")

    print("\n" + "=" * 50)
    print("  分析完成！")
    print("=" * 50)


if __name__ == "__main__":
    main()
