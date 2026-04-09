#!/usr/bin/env python3
"""
综合对比图 - 多站点功率+SOC对比
用法: python3 chart_comparison.py <site_id> <date_str>
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent))
from sunergy_client import SunergyClient, ts_of_date, parse_series, now_ts

OUTPUT_DIR = "/tmp/sunergy_charts"


def set_chinese_font():
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "SimHei", "Noto Sans CJK SC"]
    plt.rcParams["axes.unicode_minus"] = False


def chart_comparison(site_id: str, date_str: str):
    """综合对比图: 电网/光伏/负载/储能/SOC"""
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import numpy as np

    set_chinese_font()
    client = SunergyClient()
    ts = ts_of_date(date_str) if date_str != datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d") else now_ts()

    result = client.get_power_day(site_id, ts)
    if not result.get("success"):
        print(f"❌ 查询失败: {result.get('msg')}")
        return

    marks = result["data"].get("marks", [])
    series = parse_series(result)
    if not marks:
        print("⚠️ 无数据")
        return

    times = [datetime.fromtimestamp(m / 1000, tz=timezone(timedelta(hours=8))) for m in marks]
    n = len(times)

    def safe(code, i, default=np.nan):
        arr = series.get(code, [])
        v = arr[i] if i < len(arr) else default
        return v if v is not None else default

    grid = np.array([safe("gridPower", i) for i in range(n)], dtype=float)
    solar = np.array([safe("solarTotalPower", i) for i in range(n)], dtype=float)
    cons = np.array([safe("consumption", i) for i in range(n)], dtype=float)
    bess = np.array([safe("bessTotalPower", i) for i in range(n)], dtype=float)
    soc = np.array([safe("bessTotalSoc", i) for i in range(n)], dtype=float)

    solar_clean = np.where(solar < 0, np.nan, solar)
    cons_clean = np.where(cons < 0, np.nan, cons)

    fig, (ax_main, ax_soc) = plt.subplots(2, 1, figsize=(18, 10), gridspec_kw={"height_ratios": [3, 1]})
    fig.suptitle(f"{site_id} 综合功率分析 ({date_str})", fontsize=14, fontweight="bold")

    # 上半: 功率
    ax_main.plot(times, grid, "b-", linewidth=0.8, label="Grid (kW)", alpha=0.9)
    ax_main.plot(times, solar_clean, color="orange", linewidth=0.8, label="Solar (kW)", alpha=0.9)
    ax_main.plot(times, cons_clean, "r-", linewidth=0.8, label="Consumption (kW)", alpha=0.9)
    ax_main.plot(times, bess, "g-", linewidth=0.8, label="BESS (kW)", alpha=0.9)
    ax_main.axhline(0, color="gray", linewidth=0.5)
    ax_main.fill_between(times, grid, 0, where=grid > 0, alpha=0.1, color="blue")
    ax_main.set_ylabel("Power (kW)")
    ax_main.legend(loc="upper right", ncol=4, fontsize=8)
    ax_main.grid(True, alpha=0.3)
    ax_main.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

    # 下半: SOC
    ax_soc.fill_between(times, soc, alpha=0.3, color="purple")
    ax_soc.plot(times, soc, "purple", linewidth=1.5, label="BESS SOC (%)")
    ax_soc.set_ylim(0, 100)
    ax_soc.set_ylabel("SOC (%)")
    ax_soc.set_xlabel("Time")
    ax_soc.legend(loc="upper right")
    ax_soc.grid(True, alpha=0.3)
    ax_soc.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

    plt.tight_layout()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, f"{site_id}_comparison_{date_str}.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    print(f"✅ 综合对比图已保存: {path}")
    plt.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 chart_comparison.py <site_id> [date_str]")
        sys.exit(1)
    site_id = sys.argv[1]
    date_str = sys.argv[2] if len(sys.argv) > 2 else datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
    chart_comparison(site_id, date_str)
