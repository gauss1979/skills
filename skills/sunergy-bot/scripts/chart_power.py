#!/usr/bin/env python3
"""
日功率曲线图表生成
支持: gridPower / solarTotalPower / consumption / bessTotalPower / bessTotalSoc
用法: python3 chart_power.py <site_id> [date_str]
  date_str: YYYY-MM-DD，默认今天
示例: python3 chart_power.py 1872845402077761538 2026-04-08
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
    plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "SimHei", "WenQuanYi Micro Hei", "Noto Sans CJK SC"]
    plt.rcParams["axes.unicode_minus"] = False


def chart_power_day(site_id: str, date_str: str, site_name: str = ""):
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import numpy as np

    set_chinese_font()
    client = SunergyClient()

    # 如果查今天，用 now_ts；否则用日期0点
    if date_str == datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d"):
        ts = now_ts()
    else:
        ts = ts_of_date(date_str)

    result = client.get_power_day(site_id, ts)
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

    # 取各字段（可能为null）
    def safe_val(arr, i, default=np.nan):
        v = arr[i] if i < len(arr) else np.nan
        return v if v is not None else default

    n = len(times)
    grid_power = np.array([safe_val(series.get("gridPower", []), i) for i in range(n)], dtype=float)
    solar_power = np.array([safe_val(series.get("solarTotalPower", []), i) for i in range(n)], dtype=float)
    consumption = np.array([safe_val(series.get("consumption", []), i) for i in range(n)], dtype=float)
    bess_power = np.array([safe_val(series.get("bessTotalPower", []), i) for i in range(n)], dtype=float)
    bess_soc = np.array([safe_val(series.get("bessTotalSoc", []), i) for i in range(n)], dtype=float)

    # ========== 图1: 分项子图 ==========
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    title = f"{site_name or site_id} 日功率曲线 ({date_str})"
    fig.suptitle(title, fontsize=14, fontweight="bold")

    # 电网功率
    ax1 = axes[0, 0]
    ax1.plot(times, grid_power, "b-", linewidth=0.8, label="Grid Power")
    ax1.fill_between(times, grid_power, alpha=0.2, color="blue")
    ax1.axhline(0, color="gray", linewidth=0.5)
    ax1.set_title("Grid Power (kW)")
    ax1.set_ylabel("kW")
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax1.grid(True, alpha=0.3)
    ax1.legend()

    # 光伏功率
    ax2 = axes[0, 1]
    solar_clean = np.where(solar_power < 0, np.nan, solar_power)
    ax2.plot(times, solar_clean, "orange", linewidth=0.8, label="Solar Power")
    ax2.fill_between(times, solar_clean, alpha=0.3, color="orange")
    ax2.set_title("Solar Power (kW)")
    ax2.set_ylabel("kW")
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax2.grid(True, alpha=0.3)
    ax2.legend()

    # 负载消耗
    ax3 = axes[1, 0]
    cons_clean = np.where(consumption < 0, np.nan, consumption)
    ax3.plot(times, cons_clean, "red", linewidth=0.8, label="Consumption")
    ax3.fill_between(times, cons_clean, alpha=0.2, color="red")
    ax3.set_title("Consumption (kW)")
    ax3.set_ylabel("kW")
    ax3.set_xlabel("Time")
    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax3.grid(True, alpha=0.3)
    ax3.legend()

    # 储能SOC
    ax4 = axes[1, 1]
    ax4.plot(times, bess_soc, "purple", linewidth=1.2, label="BESS SOC")
    ax4.fill_between(times, bess_soc, alpha=0.2, color="purple")
    ax4.set_ylim(0, 100)
    ax4.set_title("BESS SOC (%)")
    ax4.set_ylabel("SOC %")
    ax4.set_xlabel("Time")
    ax4.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax4.grid(True, alpha=0.3)
    ax4.legend()

    plt.tight_layout()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path1 = os.path.join(OUTPUT_DIR, f"{site_id}_power_day_{date_str}.png")
    plt.savefig(path1, dpi=150, bbox_inches="tight")
    print(f"✅ 分项图表已保存: {path1}")
    plt.close()

    # ========== 图2: 综合对比图（双Y轴）==========
    fig2, ax = plt.subplots(figsize=(16, 6))
    ax.plot(times, grid_power, "b-", linewidth=0.8, label="Grid (kW)", alpha=0.8)
    ax.plot(times, solar_clean, "orange", linewidth=0.8, label="Solar (kW)", alpha=0.8)
    ax.plot(times, cons_clean, "red", linewidth=0.8, label="Consumption (kW)", alpha=0.8)
    ax.plot(times, bess_power, "g-", linewidth=0.8, label="BESS Power (kW)", alpha=0.8)
    ax.axhline(0, color="gray", linewidth=0.5)
    ax.set_ylabel("Power (kW)", color="black")
    ax.set_xlabel("Time")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax.grid(True, alpha=0.3)

    ax2_twin = ax.twinx()
    ax2_twin.plot(times, bess_soc, "purple", linewidth=2, label="SOC (%)", alpha=0.8)
    ax2_twin.set_ylabel("SOC (%)", color="purple")
    ax2_twin.set_ylim(0, 100)

    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2_twin.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc="upper right")

    fig2.suptitle(title, fontsize=14, fontweight="bold")
    plt.tight_layout()
    path2 = os.path.join(OUTPUT_DIR, f"{site_id}_power_combined_{date_str}.png")
    fig2.savefig(path2, dpi=150, bbox_inches="tight")
    print(f"✅ 综合图表已保存: {path2}")
    plt.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 chart_power.py <site_id> [date_str]")
        sys.exit(1)
    site_id = sys.argv[1]
    date_str = sys.argv[2] if len(sys.argv) > 2 else datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
    chart_power_day(site_id, date_str)
