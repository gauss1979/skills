#!/usr/bin/env python3
"""
收益走势图生成
支持: earnings_week (周收益按日) / earnings_year (年收益按月)
用法: python3 chart_earnings.py <site_id> week <YYYY-MM-DD>
       python3 chart_earnings.py <site_id> year <YYYY-MM-DD>
示例: python3 chart_earnings.py 1872845402077761538 week 2026-04-01
      python3 chart_earnings.py 1872845402077761538 year 2026-01-01
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent))
from sunergy_client import SunergyClient, ts_of_date, parse_series

OUTPUT_DIR = "/tmp/sunergy_charts"


def set_chinese_font():
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "SimHei", "WenQuanYi Micro Hei", "Noto Sans CJK SC"]
    plt.rcParams["axes.unicode_minus"] = False


def chart_earnings_week(site_id: str, date_str: str):
    """收益周报（按日）"""
    import matplotlib.pyplot as plt
    import numpy as np

    set_chinese_font()
    client = SunergyClient()
    ts = ts_of_date(date_str)
    result = client.get_earnings_week(site_id, ts)

    if not result.get("success"):
        print(f"❌ 查询失败: {result.get('msg')}")
        return

    data = result["data"]
    marks = data.get("marks", [])
    series = parse_series(result)

    if not marks:
        print("⚠️ 无数据")
        return

    times = [datetime.fromtimestamp(m / 1000, tz=timezone(timedelta(hours=8))) for m in marks]
    earnings = series.get("earnings", [])

    labels = [t.strftime("%m-%d %a") for t in times]
    values = [v if v is not None else 0 for v in earnings]

    fig, ax = plt.subplots(figsize=(max(10, len(labels) * 1.2), 5))
    colors = ["green" if v >= 0 else "red" for v in values]
    bars = ax.bar(labels, values, color=colors, alpha=0.7)

    for bar, val in zip(bars, values):
        ypos = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, ypos + (0.5 if ypos >= 0 else -1.5),
                f"{val:.1f}", ha="center", va="bottom" if ypos >= 0 else "top", fontsize=8)

    ax.axhline(0, color="gray", linewidth=0.8)
    ax.set_title(f"{site_id} 周收益 ({date_str})")
    ax.set_ylabel("Earnings ($)")
    ax.set_xlabel("Date")
    ax.grid(True, alpha=0.3, axis="y")
    plt.xticks(rotation=45, fontsize=8)
    plt.tight_layout()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, f"{site_id}_earnings_week_{date_str}.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    print(f"✅ 周收益图表已保存: {path}")
    plt.close()


def chart_earnings_year(site_id: str, date_str: str):
    """收益年报（按月）"""
    import matplotlib.pyplot as plt
    import numpy as np

    set_chinese_font()
    client = SunergyClient()
    ts = ts_of_date(date_str)
    result = client.get_earnings_year(site_id, ts)

    if not result.get("success"):
        print(f"❌ 查询失败: {result.get('msg')}")
        return

    data = result["data"]
    marks = data.get("marks", [])
    series = parse_series(result)

    if not marks:
        print("⚠️ 无数据")
        return

    months = [datetime.fromtimestamp(m / 1000, tz=timezone(timedelta(hours=8))).strftime("%Y-%m") for m in marks]
    earnings = series.get("earnings", [])
    values = [v if v is not None else 0 for v in earnings]

    fig, ax = plt.subplots(figsize=(12, 5))
    colors = ["green" if v >= 0 else "red" for v in values]
    bars = ax.bar(months, values, color=colors, alpha=0.7)

    for bar, val in zip(bars, values):
        ypos = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, ypos + (50 if ypos >= 0 else -200),
                f"{val:.0f}", ha="center", va="bottom" if ypos >= 0 else "top", fontsize=8)

    ax.axhline(0, color="gray", linewidth=0.8)
    ax.set_title(f"{site_id} 年收益 ({date_str[:4]})")
    ax.set_ylabel("Earnings ($)")
    ax.set_xlabel("Month")
    ax.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, f"{site_id}_earnings_year_{date_str[:4]}.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    print(f"✅ 年收益图表已保存: {path}")
    plt.close()


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("用法:")
        print("  python3 chart_earnings.py <site_id> week <YYYY-MM-DD>")
        print("  python3 chart_earnings.py <site_id> year <YYYY-MM-DD>")
        sys.exit(1)

    site_id = sys.argv[1]
    period = sys.argv[2]
    date_str = sys.argv[3]

    if period == "week":
        chart_earnings_week(site_id, date_str)
    elif period == "year":
        chart_earnings_year(site_id, date_str)
    else:
        print("period 必须是 week 或 year")
