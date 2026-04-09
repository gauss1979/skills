#!/usr/bin/env python3
"""
全站概览报告
一次性查询所有站点实时数据并展示
用法: python3 report_all.py
"""

import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent))
from sunergy_client import SunergyClient


def fmt_power(v):
    if v is None:
        return "N/A"
    return f"{v:.2f} kW"


def fmt_ts(ts):
    if not ts:
        return "N/A"
    return datetime.fromtimestamp(ts / 1000, tz=timezone(timedelta(hours=8))).strftime("%H:%M:%S")


def main():
    client = SunergyClient()
    print("=" * 70)
    print(f"  Sunergy 全站概览  ({datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')})")
    print("=" * 70)

    result = client.get_sites()
    if not result.get("success"):
        print(f"❌ 查询失败: {result.get('msg')}")
        return

    sites = result.get("data", [])
    if not sites:
        print("⚠️ 没有找到任何站点")
        return

    for site in sites:
        sid = site["id"]
        name = site.get("name", "未知")
        soc = site.get("totalSoc")
        bess_pwr = site.get("bessTotalPower")
        solar_pwr = site.get("solarTotalPower")
        province = site.get("province", "")
        city = site.get("city", "")
        last_update = fmt_ts(site.get("lastUpdateTime"))

        print(f"\n{'─' * 50}")
        print(f"  🏭 {name} [{sid}]")
        print(f"  位置: {province} {city}")
        print(f"  光伏功率: {fmt_power(solar_pwr)}")
        print(f"  储能功率: {fmt_power(bess_pwr)}")
        print(f"  SOC: {soc}%  " if soc is not None else "  SOC: N/A  ", end="")
        print(f"更新时间: {last_update}")

        # 查询详细数据
        detail = client.get_site_detail(sid)
        if detail.get("success"):
            d = detail["data"]
            total_power = d.get("totalPower")
            consumption = d.get("consumption")
            today_rev = d.get("todayRevenue")
            print(f"  总功率: {fmt_power(total_power)}  负载: {fmt_power(consumption)}")
            if today_rev is not None:
                print(f"  今日收益: {today_rev:.2f}")

        # 查询今日BESS
        bess_today = client.get_site_bess_today(sid)
        if bess_today.get("success"):
            bd = bess_today["data"]
            status_map = {0: "离线", 1: "待机", 2: "放电", 3: "充电", 4: "故障"}
            status = status_map.get(bd.get("status", 0), "未知")
            print(f"  BESS状态: {status}  今日充电: {bd.get('chg', 0)/1000:.2f} kWh  "
                  f"放电: {bd.get('dischg', 0)/1000:.2f} kWh")

        # 查询今日光伏
        solar_today = client.get_site_solar_today(sid)
        if solar_today.get("success"):
            sd = solar_today["data"]
            print(f"  今日发电: {sd.get('powerGeneration', 0)/1000:.2f} kWh  "
                  f"当前功率: {sd.get('currentPower', 0):.2f} kW")

    print(f"\n{'=' * 70}")
    print(f"共 {len(sites)} 个站点")


if __name__ == "__main__":
    main()
