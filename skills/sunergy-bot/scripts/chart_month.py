#!/usr/bin/env python3
"""
月/年统计柱状图生成
支持: solarChg / bessChg / bessDischg
用法: python3 chart_month.py <site_id> <YYYY-MM>  # 月统计
      python3 chart_year.py <site_id> <YYYY>      # 年统计（调用同一个，月内自动）
示例: python3 chart_month.py 1872845402077761538 2026-04
      python3 chart_year.py 1872845402077761538 2026
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent))
from sunergy_client import SunergyClient, ts_of_date, ts_of_month, ts_of_year, parse_series

OUTPUT_DIR = "/tmp/sunergy_charts"


def set_chinese_font():
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "SimHei", "WenQuanYi Micro Hei", "Noto Sans CJK SC"]
    plt.rcParams["axes.unicode_minus"] = False


def chart_month(site_id: str, year_month: str):
    """月统计柱状图"""
    import matplotlib.pyplot as plt
    import numpy as np

    set_chinese_font()
    client = SunergyClient()
    ts = ts_of_month(year_month)
    result = client.get_charts_month(site_id, ts)

    if not result.get("success"):
        print(f"❌ 查询失败: {result.get('msg')}")
        return

    data = result["data"]
    marks = data.get("marks", [])
    series = parse_series(result)

    if not marks:
        print("⚠️ 无数据")
        return

    labels = [datetime.fromtimestamp(m / 1000, tz=timezone(timedelta(hours=8))).strftime("%m-%d") for m in marks]
    solar_chg = series.get("solarChg", [])
    bess_chg = series.get("bessChg", [])
    bess_dischg = series.get("bessDischg", [])

    # 转换 None -> 0
    def clean(arr):
        return [v if v is not None else 0 for v in arr]

    solar_chg = clean(solar_chg)
    bess_chg = clean(bess_chg)
    bess_dischg = clean(bess_dischg)

    x = np.arange(len(labels))
    width = 0.25

    fig, ax = plt.subplots(figsize=(max(14, len(labels) * 0.6), 6))
    ax.bar(x - width, solar_chg, width, label="Solar Charge (Wh)", color="orange", alpha=0.8)
    ax.bar(x, bess_chg, width, label="BESS Charge (Wh)", color="green", alpha=0.8)
    ax.bar(x + width, bess_dischg, width, label="BESS Discharge (Wh)", color="red", alpha=0.8)

    ax.set_xlabel("Date")
    ax.set_ylabel("Energy (Wh)")
    ax.set_title(f"{site_id} 月统计 ({year_month})")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, fontsize=8)
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, f"{site_id}_charts_month_{year_month}.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    print(f"✅ 月统计图表已保存: {path}")
    plt.close()


def chart_year(site_id: str, year: str):
    """年统计柱状图"""
    import matplotlib.pyplot as plt
    import numpy as np

    set_chinese_font()
    client = SunergyClient()
    ts = ts_of_year(year)
    result = client.get_charts_year(site_id, ts)

    if not result.get("success"):
        print(f"❌ 查询失败: {result.get('msg')}")
        return

    data = result["data"]
    marks = data.get("marks", [])
    series = parse_series(result)

    if not marks:
        print("⚠️ 无数据")
        return

    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    # marks 是毫秒时间戳，取月份
    months = [datetime.fromtimestamp(m / 1000, tz=timezone(timedelta(hours=8))).month - 1 for m in marks]
    labels = [month_labels[m] for m in months]

    solar_chg = series.get("solarChg", [])
    bess_chg = series.get("bessChg", [])
    bess_dischg = series.get("bessDischg", [])

    def clean(arr):
        return [v if v is not None else 0 for v in arr]

    solar_chg = clean(solar_chg)
    bess_chg = clean(bess_chg)
    bess_dischg = clean(bess_dischg)

    x = np.arange(len(labels))
    width = 0.25

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.bar(x - width, solar_chg, width, label="Solar Charge (Wh)", color="orange", alpha=0.8)
    ax.bar(x, bess_chg, width, label="BESS Charge (Wh)", color="green", alpha=0.8)
    ax.bar(x + width, bess_dischg, width, label="BESS Discharge (Wh)", color="red", alpha=0.8)

    ax.set_xlabel("Month")
    ax.set_ylabel("Energy (Wh)")
    ax.set_title(f"{site_id} 年统计 ({year})")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, f"{site_id}_charts_year_{year}.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    print(f"✅ 年统计图表已保存: {path}")
    plt.close()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法:")
        print("  python3 chart_month.py <site_id> <YYYY-MM>  # 月统计")
        print("  python3 chart_year.py <site_id> <YYYY>       # 年统计")
        sys.exit(1)

    script = Path(sys.argv[0]).name
    site_id = sys.argv[1]

    if "month" in script:
        ym = sys.argv[2]
        chart_month(site_id, ym)
    elif "year" in script:
        year = sys.argv[2]
        chart_year(site_id, year)
