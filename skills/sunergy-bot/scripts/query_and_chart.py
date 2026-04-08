#!/usr/bin/env python3
"""
Sunergy API 查询与图表生成脚本
用法: python3 query_and_chart.py <site_id> [start_ts] [end_ts]
示例: python3 query_and_chart.py 1872845402077761538 1775577600280 1775663999999
"""

import sys
import urllib.request
import json
import os
from datetime import datetime
from pathlib import Path

# 读取 token
TOKEN_FILE = Path.home() / ".mx-sky" / "token"
TOKEN = "a6b085941d6a48da83aa66636fd68f87"  # 默认 token

if TOKEN_FILE.exists():
    TOKEN = TOKEN_FILE.read_text().strip()

def query_power_data(site_id, start_ts, end_ts, time_span=5):
    """查询日功率图表数据"""
    url = f"http://web.aws.aiminis.com/api/mobile/chart/site/{site_id}/power/day"
    url += f"?siteId={site_id}&start={start_ts}&end={end_ts}&timeSpan={time_span}"
    
    headers = {
        "Host": "web.aws.aiminis.com",
        "User-Agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
        "Accept-Encoding": "gzip, deflate",
        "tenantId": "3",
        "timeZone": "Asia/Shanghai",
        "Authorization": f"Bearer {TOKEN}",
        "Connection": "keep-alive",
        "Referer": f"http://web.aws.aiminis.com/siteDetail?id={site_id}",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache"
    }
    
    req = urllib.request.Request(url, headers=headers)
    
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode('utf-8'))


def generate_charts(data, output_dir="/tmp"):
    """生成图表"""
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import numpy as np
    
    marks = data['data']['marks']
    times = [datetime.fromtimestamp(m/1000) for m in marks]
    
    series_dict = {}
    for s in data['data']['series']:
        series_dict[s['code']] = s['value']
    
    # Create figure with 4 subplots
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle(f'电站功率数据 ({times[0].strftime("%Y-%m-%d")})', fontsize=14, fontweight='bold')
    
    # 1. totalPower
    ax1 = axes[0, 0]
    power = series_dict.get('totalPower', [])
    valid_power = [v if v >= 0 else np.nan for v in power]
    ax1.plot(times[:len(valid_power)], valid_power, 'b-', linewidth=0.8, label='总有功功率')
    ax1.fill_between(times[:len(valid_power)], valid_power, alpha=0.3)
    ax1.set_title('总有功功率 (kW)')
    ax1.set_ylabel('功率 (kW)')
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    
    # 2. consumption
    ax2 = axes[0, 1]
    cons = series_dict.get('consumption', [])
    ax2.plot(times[:len(cons)], cons, 'r-', linewidth=0.8, label='消耗电量')
    ax2.set_title('消耗电量 (kWh)')
    ax2.set_ylabel('电量 (kWh)')
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax2.grid(True, alpha=0.3)
    ax2.legend()
    
    # 3. totalBessPower
    ax3 = axes[1, 0]
    bess_power = series_dict.get('totalBessPower', [])
    valid_bp = [v if v >= 0 else np.nan for v in bess_power]
    ax3.plot(times[:len(valid_bp)], valid_bp, 'g-', linewidth=0.8, label='储能功率')
    ax3.fill_between(times[:len(valid_bp)], valid_bp, alpha=0.3, color='green')
    ax3.set_title('储能功率 (kW)')
    ax3.set_ylabel('功率 (kW)')
    ax3.set_xlabel('时间')
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax3.grid(True, alpha=0.3)
    ax3.legend()
    
    # 4. totalBessSoc
    ax4 = axes[1, 1]
    soc = series_dict.get('totalBessSoc', [])
    ax4.plot(times[:len(soc)], soc, 'purple', linewidth=1.5, label='储能SOC')
    ax4.fill_between(times[:len(soc)], soc, alpha=0.3, color='purple')
    ax4.set_title('储能 SOC (%)')
    ax4.set_ylabel('SOC (%)')
    ax4.set_xlabel('时间')
    ax4.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax4.set_ylim(0, 100)
    ax4.grid(True, alpha=0.3)
    ax4.legend()
    
    plt.tight_layout()
    path1 = os.path.join(output_dir, 'power_day_chart.png')
    plt.savefig(path1, dpi=150, bbox_inches='tight')
    print(f"图表已保存: {path1}")
    
    # Combined chart
    fig2, ax = plt.subplots(figsize=(16, 6))
    ax.plot(times[:len(power)], power, 'b-', linewidth=0.8, label='总有功功率 (kW)', alpha=0.8)
    ax.plot(times[:len(bess_power)], bess_power, 'g-', linewidth=0.8, label='储能功率 (kW)', alpha=0.8)
    ax2_twin = ax.twinx()
    ax2_twin.plot(times[:len(soc)], soc, 'purple', linewidth=2, label='储能SOC (%)', alpha=0.8)
    ax.set_title(f'电站综合功率数据 ({times[0].strftime("%Y-%m-%d")})', fontsize=14, fontweight='bold')
    ax.set_ylabel('功率 (kW)', color='blue')
    ax2_twin.set_ylabel('SOC (%)', color='purple')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.grid(True, alpha=0.3)
    ax.legend(loc='upper left')
    ax2_twin.legend(loc='upper right')
    plt.tight_layout()
    path2 = os.path.join(output_dir, 'power_combined_chart.png')
    plt.savefig(path2, dpi=150, bbox_inches='tight')
    print(f"综合图表已保存: {path2}")
    
    return path1, path2


def print_stats(data):
    """打印数据统计"""
    series_dict = {}
    for s in data['data']['series']:
        code = s['code']
        values = s['value']
        valid = [v for v in values if v >= 0]
        
        print(f"\n{code}:")
        print(f"  有效值: {len(valid)}/{len(values)}")
        if valid:
            print(f"  最大值: {max(valid):.2f}")
            print(f"  最小值: {min(valid):.2f}")
            print(f"  平均值: {sum(valid)/len(valid):.2f}")


def main():
    if len(sys.argv) < 2:
        # 默认查询 2026-04-08 数据
        site_id = "1872845402077761538"
        start_ts = "1775577600280"
        end_ts = "1775663999999"
    else:
        site_id = sys.argv[1]
        start_ts = sys.argv[2] if len(sys.argv) > 2 else str(int(datetime.now().timestamp() * 1000) - 86400000)
        end_ts = sys.argv[3] if len(sys.argv) > 3 else str(int(datetime.now().timestamp() * 1000))
    
    print(f"查询站点: {site_id}")
    print(f"时间范围: {datetime.fromtimestamp(int(start_ts)/1000)} ~ {datetime.fromtimestamp(int(end_ts)/1000)}")
    
    data = query_power_data(site_id, start_ts, end_ts)
    
    if data.get('code') == 200:
        print("\n✅ 查询成功!")
        print_stats(data)
        generate_charts(data)
    else:
        print(f"❌ 查询失败: {data}")


if __name__ == "__main__":
    main()
