#!/usr/bin/env python3
"""
BESS 状态分析图表
1. 今日BESS概览（饼图+状态卡片）
2. 从 power/day 数据生成 SOC + 充放电功率 组合图
用法: python3 chart_bess.py <site_id> [date_str]
示例: python3 chart_bess.py 1872845402077761538 2026-04-08
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


def chart_bess_today_overview(site_id: str, date_str: str):
    """今日BESS数据卡片 + 饼图"""
    import matplotlib.pyplot as plt
    import numpy as np

    set_chinese_font()
    client = SunergyClient()

    if date_str == datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d"):
        ts = now_ts()
    else:
        ts = ts_of_date(date_str)

    result = client.get_site_bess_today(site_id)
    if not result.get("success"):
        print(f"❌ 查询失败: {result.get('msg')}")
        return

    d = result["data"]
    soc = d.get("soc", 0)
    chg = d.get("chg", 0) / 1000  # Wh -> kWh
    dischg = d.get("dischg", 0) / 1000
    current_power = d.get("currentPower", 0)
    rated_capacity = d.get("ratedCapacity", 0)
    status = d.get("status", 0)

    status_map = {0: "Offline", 1: "Standby", 2: "Discharging", 3: "Charging", 4: "Fault"}
    status_text = status_map.get(status, "Unknown")

    # ===== 图1: BESS 概览仪表盘 =====
    fig = plt.figure(figsize=(12, 6))

    # SOC 仪表
    ax1 = fig.add_subplot(131, projection="polar")
    theta = np.linspace(0, np.pi, 100)
    r = np.ones_like(theta)
    colors = plt.cm.RdYlGn_r(theta / np.pi)
    ax1.pcolormesh([theta], [[1] * len(theta)], cmap="RdYlGn_r", shading="auto", vmin=0, vmax=100)
    ax1.set_theta_direction(-1)
    ax1.set_theta_zero_location("W")
    ax1.set_thetamin(0)
    ax1.set_thetamax(90)
    # 指针
    needle_theta = np.radians(90 - soc * 90 / 100)
    ax1.annotate("", xy=(needle_theta, 0.8), xytext=(0, 0),
                 arrowprops=dict(arrowstyle="->", color="black", lw=2))
    ax1.text(0, 0, f"{soc:.0f}%", ha="center", va="center", fontsize=20, fontweight="bold")
    ax1.set_title(f"SOC  {soc:.0f}%", fontsize=12, pad=20)
    ax1.set_yticklabels([])
    ax1.set_xticklabels([])
    ax1.grid(False)

    # 充放电量对比
    ax2 = fig.add_subplot(132)
    categories = ["Charge", "Discharge"]
    values = [chg, dischg]
    bar_colors = ["green", "red"]
    bars = ax2.bar(categories, values, color=bar_colors, alpha=0.7, width=0.5)
    for bar, val in zip(bars, values):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                 f"{val:.2f} kWh", ha="center", fontsize=10)
    ax2.set_ylabel("Energy (kWh)")
    ax2.set_title("Today's Charge / Discharge")
    ax2.grid(True, alpha=0.3, axis="y")

    # 当前功率
    ax3 = fig.add_subplot(233)
    ax3.axis("off")
    info = [
        f"Site ID: {site_id}",
        f"Date: {date_str}",
        f"Status: {status_text}",
        f"Current Power: {current_power:.2f} kW",
        f"Rated Capacity: {rated_capacity:.1f} kWh",
        f"SOC: {soc:.1f}%",
        f"Charge: {chg:.2f} kWh",
        f"Discharge: {dischg:.2f} kWh",
    ]
    ax3.text(0.1, 0.9, "\n".join(info), transform=ax3.transAxes,
             fontsize=11, verticalalignment="top",
             bbox=dict(boxstyle="round", facecolor="lightblue", alpha=0.5))
    ax3.set_title("BESS Overview")

    fig.suptitle(f"BESS Status Overview ({site_id} - {date_str})", fontsize=14, fontweight="bold")
    plt.tight_layout()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, f"{site_id}_bess_overview_{date_str}.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    print(f"✅ BESS概览已保存: {path}")
    plt.close()


def chart_bess_power_curve(site_id: str, date_str: str):
    """从 power/day 数据生成 BESS 功率 + SOC 组合图"""
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
    bess_power = np.array([series.get("bessTotalPower", [])[i] if i < len(series.get("bessTotalPower", [])) else np.nan for i in range(n)], dtype=float)
    bess_soc = np.array([series.get("bessTotalSoc", [])[i] if i < len(series.get("bessTotalSoc", [])) else np.nan for i in range(n)], dtype=float)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 8), sharex=True)

    # 充电（正）/ 放电（负）着色
    chg_mask = bess_power > 0
    dischg_mask = bess_power < 0

    ax1.fill_between(times, 0, bess_power, where=chg_mask, color="green", alpha=0.5, label="Charging (+)")
    ax1.fill_between(times, 0, bess_power, where=dischg_mask, color="red", alpha=0.5, label="Discharging (-)")
    ax1.plot(times, bess_power, "k-", linewidth=0.5)
    ax1.axhline(0, color="gray", linewidth=0.8)
    ax1.set_ylabel("BESS Power (kW)")
    ax1.set_title(f"BESS Power & SOC ({date_str})")
    ax1.legend(loc="upper right")
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

    ax2.plot(times, bess_soc, "purple", linewidth=1.5, label="SOC")
    ax2.fill_between(times, bess_soc, alpha=0.2, color="purple")
    ax2.set_ylim(0, 100)
    ax2.set_ylabel("SOC (%)")
    ax2.set_xlabel("Time")
    ax2.legend(loc="upper right")
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

    plt.tight_layout()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, f"{site_id}_bess_power_soc_{date_str}.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    print(f"✅ BESS功率+SOC图表已保存: {path}")
    plt.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 chart_bess.py <site_id> [date_str]")
        sys.exit(1)
    site_id = sys.argv[1]
    date_str = sys.argv[2] if len(sys.argv) > 2 else datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
    chart_bess_today_overview(site_id, date_str)
    chart_bess_power_curve(site_id, date_str)
