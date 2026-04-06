#!/usr/bin/env python3
"""
mx-sky 能源管理查询工具
支持：站点列表、实时数据、BESS状态、收益查询、功率图表、图表生成
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime

TOKEN_FILE = os.path.expanduser("~/.mx-sky/token")
BASE_URL = "http://web.aws.aiminis.com/api"
CHART_SCRIPT = "/root/.openclaw/workspace/skills/mx-sky-energy/scripts/gen_energy_chart.py"
OUTPUT_DIR = "/root/.openclaw/workspace/memory/chart/output"

def get_token():
    token = os.environ.get("MX_SKY_TOKEN")
    if token:
        return token
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            return f.read().strip()
    return None

def api_get(path, params=None, tz="Australia/Sydney"):
    token = get_token()
    if not token:
        print("❌ 未配置 Token！请运行: echo '你的BearerToken' > ~/.mx-sky/token")
        sys.exit(1)

    url = f"{BASE_URL}{path}"
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())

    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("tenantId", "3")
    req.add_header("timeZone", tz)

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP错误 {e.code}: {e.read().decode()}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        sys.exit(1)

def ts_to_bj(ts_ms):
    """毫秒时间戳转北京时间"""
    if not ts_ms:
        return "-"
    dt = datetime.fromtimestamp(ts_ms / 1000)
    return dt.strftime("%Y-%m-%d %H:%M")

def fmt_power(v):
    """格式化功率"""
    if v is None:
        return "N/A"
    return f"{v:.2f} kW"

def cmd_list():
    """站点列表"""
    data = api_get("/app/sites/")
    sites = data.get("data", [])
    if not sites:
        print("暂无站点数据")
        return

    print(f"\n{'='*60}")
    print(f"{'站点列表':^50} (共 {len(sites)} 个)")
    print(f"{'='*60}")
    for s in sites:
        print(f"\n📍 {s.get('name','-')}  [{s.get('id')}]")
        print(f"   位置: {s.get('city','-')}, {s.get('province','-')}")
        print(f"   ⚡ 光伏: {fmt_power(s.get('solarTotalPower'))}  "
              f"| 🔋 SOC: {s.get('totalSoc','-')}%  "
              f"| 🔌 电池: {fmt_power(s.get('bessTotalPower'))}")
        last = ts_to_bj(s.get("lastUpdateTime"))
        print(f"   ⏰ 更新: {last}")

def cmd_realtime(site_id):
    """实时数据"""
    data = api_get(f"/app/sites/{site_id}")
    d = data.get("data", {})
    if not d:
        print("未获取到数据，请检查 site_id")
        return

    print(f"\n{'='*60}")
    print(f" 实时数据 — {d.get('name','-')}  [{site_id}]")
    print(f"{'='*60}")
    print(f" 位置: {d.get('city','-')}, {d.get('province','-')}, {d.get('locale','-')}")
    print(f" ⚡ 光伏功率: {fmt_power(d.get('solarTotalPower'))}")
    print(f" 🔋 电池SOC: {d.get('totalSoc','-')}%  | 电池功率: {fmt_power(d.get('bessTotalPower'))}")
    print(f" 🔌 电网功率: {fmt_power(d.get('totalPower'))}  | 消耗: {fmt_power(d.get('consumption'))}")
    print(f" 💰 今日收益: ${d.get('todayRevenue', 0):.4f}")
    print(f" ⏰ 最后更新: {ts_to_bj(d.get('lastUpdateTime'))}")

def cmd_bess(site_id):
    """BESS今日数据"""
    data = api_get(f"/app/sites/{site_id}/bess/today")
    d = data.get("data", {})
    status_map = {1: "离线", 2: "告警", 3: "正常"}
    print(f"\n{'='*60}")
    print(f" 今日 BESS — [{site_id}]")
    print(f"{'='*60}")
    print(f" 状态: {status_map.get(d.get('status'), '-')}  | 额定容量: {d.get('ratedCapacity','-')} kWh")
    print(f" 当前SOC: {d.get('soc','-')}%  | 当前功率: {fmt_power(d.get('currentPower'))}")
    print(f" 今日充电: {d.get('chg',0)/1000:.2f} kWh  | 放电: {d.get('dischg',0)/1000:.2f} kWh")

def cmd_power_day(site_id, date_str=None):
    """日功率图表数据"""
    if date_str:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    else:
        dt = datetime.utcnow()
    ts = int(dt.timestamp() * 1000)

    data = api_get(f"/app/sites/{site_id}/power/day", {"timestamp": ts})
    resp = data.get("data", {})
    marks = resp.get("marks", [])
    series_map = {s["code"]: s["value"] for s in resp.get("series", [])}

    # 生成图表
    labels = [datetime.fromtimestamp(m / 1000).strftime("%H:%M") for m in marks]
    grid = series_map.get("gridPower", [])
    solar = series_map.get("solarTotalPower", [])
    consumption = series_map.get("consumption", [])
    bess = series_map.get("bessTotalPower", [])

    print(f"\n{'='*60}")
    print(f" 日功率 — [{site_id}]  {date_str or datetime.now().strftime('%Y-%m-%d')}")
    print(f"{'='*60}")
    print(f" 数据点数: {len(labels)}")
    if grid and grid[0] is not None:
        print(f" 电网功率范围: {min(g for g in grid if g):.2f} ~ {max(g for g in grid if g):.2f} kW")
    if solar and solar[0] is not None:
        print(f" 光伏功率范围: {min(s for s in solar if s):.2f} ~ {max(s for s in solar if s):.2f} kW")

    # 生成图表
    _gen_chart(labels, grid, "电网功率", "line", f"power_day_{site_id}_{date_str or 'today'}")
    _gen_bar_chart(labels[:24], [round((c or 0), 2) for c in consumption[:24]] if consumption else [],
                   "消耗功率(kW)", f"consumption_day_{site_id}")

    print(f"\n📊 图表已生成！")

def cmd_earnings_week(site_id):
    """周收益"""
    ts = int(datetime.utcnow().timestamp() * 1000)
    data = api_get(f"/app/sites/{site_id}/earnings/week", {"timestamp": ts})
    resp = data.get("data", {})
    marks = resp.get("marks", [])
    values = resp.get("series", [{}])[0].get("value", [])

    labels = [datetime.fromtimestamp(m / 1000).strftime("%m-%d") for m in marks]
    earnings = [round(v or 0, 2) for v in values]

    total = sum(earnings)
    print(f"\n{'='*60}")
    print(f" 周收益 — [{site_id}]")
    print(f"{'='*60}")
    for lb, ev in zip(labels, earnings):
        bar = "█" * int(abs(ev) / max(earnings) * 30) if max(earnings) > 0 else ""
        print(f"  {lb}  ${ev:>10.2f}  {bar}")
    print(f"  {'-'*30}")
    print(f"  合计  ${total:>10.2f}")

    # 生成图表
    _gen_chart(labels, earnings, "周收益(AU$)", "bar", f"earnings_week_{site_id}")
    print(f"\n📊 图表已生成！")

def cmd_earnings_year(site_id):
    """年收益"""
    ts = int(datetime.utcnow().timestamp() * 1000)
    data = api_get(f"/app/sites/{site_id}/earnings/year", {"timestamp": ts})
    resp = data.get("data", {})
    marks = resp.get("marks", [])
    values = resp.get("series", [{}])[0].get("value", [])

    labels = [datetime.fromtimestamp(m / 1000).strftime("%Y-%m") for m in marks]
    earnings = [round(v or 0, 2) for v in values]

    total = sum(earnings)
    print(f"\n{'='*60}")
    print(f" 年收益 — [{site_id}]")
    print(f"{'='*60}")
    for lb, ev in zip(labels, earnings):
        if abs(ev) > 0.01:
            bar = "█" * int(abs(ev) / max(earnings) * 30) if max(earnings) > 0 else ""
            print(f"  {lb}  ${ev:>12.2f}  {bar}")
    print(f"  {'-'*35}")
    print(f"  合计  ${total:>12.2f}")

    # 生成图表
    _gen_chart(labels, earnings, "月收益(AU$)", "bar", f"earnings_year_{site_id}")
    print(f"\n📊 图表已生成！")

def cmd_chart_month(site_id, year_month=None):
    """月统计图表"""
    if year_month:
        dt = datetime.strptime(year_month, "%Y-%m")
    else:
        dt = datetime.utcnow()
    ts = int(dt.timestamp() * 1000)

    data = api_get(f"/app/sites/{site_id}/charts/month", {"timestamp": ts})
    resp = data.get("data", {})
    marks = resp.get("marks", [])
    series_map = {s["code"]: s["value"] for s in resp.get("series", [])}

    labels = [datetime.fromtimestamp(m / 1000).strftime("%m-%d") for m in marks]
    solar_chg = [round((v or 0) / 1000, 2) for v in series_map.get("solarChg", [])]
    bess_chg = [round((v or 0) / 1000, 2) for v in series_map.get("bessChg", [])]
    bess_dischg = [round((v or 0) / 1000, 2) for v in series_map.get("bessDischg", [])]

    print(f"\n{'='*60}")
    print(f" 月统计 — [{site_id}]  {year_month or datetime.now().strftime('%Y-%m')}")
    print(f"{'='*60}")
    total_solar = sum(solar_chg)
    total_bess_chg = sum(bess_chg)
    total_bess_dischg = sum(bess_dischg)
    print(f" 光伏充电量: {total_solar:.2f} kWh")
    print(f" 电池充电量: {total_bess_chg:.2f} kWh  | 放电量: {total_bess_dischg:.2f} kWh")
    print(f" 净收益: {(total_bess_dischg - total_bess_chg):.2f} kWh")

    # 生成充放电对比图
    _gen_multi_bar(labels, {
        "光伏充电": solar_chg,
        "电池充电": bess_chg,
        "电池放电": bess_dischg,
    }, "月充放电统计(kWh)", f"monthly_{site_id}")
    print(f"\n📊 图表已生成！")

def cmd_report(site_id):
    """综合分析报告"""
    print(f"\n{'='*60}")
    print(f"  ⚡ 能源站点综合分析报告  [{site_id}]")
    print(f"{'='*60}")

    # 实时数据
    data = api_get(f"/app/sites/{site_id}")
    d = data.get("data", {})
    name = d.get("name", "-")

    # BESS数据
    bess_data = api_get(f"/app/sites/{site_id}/bess/today")
    bess = bess_data.get("data", {})

    print(f"\n📍 基本信息: {name}")
    print(f"   今日收益: ${d.get('todayRevenue', 0):.4f}")
    print(f"   光伏功率: {fmt_power(d.get('solarTotalPower'))}")
    print(f"   电池SOC: {d.get('totalSoc','-')}% | 电池功率: {fmt_power(d.get('bessTotalPower'))}")

    chg = bess.get("chg", 0) / 1000
    dischg = bess.get("dischg", 0) / 1000
    print(f"\n🔋 今日BESS: 充电 {chg:.2f}kWh | 放电 {dischg:.2f}kWh | 净 {dischg-chg:.2f}kWh")

    # 周收益
    ts = int(datetime.utcnow().timestamp() * 1000)
    ew = api_get(f"/app/sites/{site_id}/earnings/week", {"timestamp": ts})
    ew_vals = [v or 0 for v in ew.get("data", {}).get("series", [{}])[0].get("value", [])]
    ew_total = sum(ew_vals)
    print(f"\n💰 周收益: AU${ew_total:.2f}")

    # 年收益
    ey = api_get(f"/app/sites/{site_id}/earnings/year", {"timestamp": ts})
    ey_vals = [v or 0 for v in ey.get("data", {}).get("series", [{}])[0].get("value", [])]
    ey_total = sum(ey_vals)
    print(f"💰 年收益: AU${ey_total:.2f}")

    print(f"\n{'='*60}")
    print(f" 报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    # 生成图表
    ew_marks = ew.get("data", {}).get("marks", [])
    ew_labels = [datetime.fromtimestamp(m / 1000).strftime("%m-%d") for m in ew_marks]
    if ew_vals:
        _gen_chart(ew_labels, ew_vals, "周收益(AU$)", "bar", f"report_week_{site_id}")

    ey_marks = ey.get("data", {}).get("marks", [])
    ey_labels = [datetime.fromtimestamp(m / 1000).strftime("%Y-%m") for m in ey_marks]
    if ey_vals:
        _gen_chart(ey_labels, ey_vals, "月收益(AU$)", "bar", f"report_year_{site_id}")

    print(f"\n📊 分析图表已生成！")

def _gen_chart(labels, values, ylabel, kind, filename):
    """生成单系列图表"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output = f"{OUTPUT_DIR}/{filename}.png"

    # 过滤无效值
    valid_labels, valid_values = [], []
    for lb, val in zip(labels, values):
        if val is not None and val != "":
            valid_labels.append(lb)
            valid_values.append(float(val))

    if not valid_values:
        print(f"  (无有效数据，跳过图表)")
        return

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm

    # 设置中文字体
    font_paths = [
        '/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc',
        '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
        '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            plt.rcParams['font.sans-serif'] = [fp, 'WenQuanYi Micro Hei', 'DejaVu Sans']
            break
    plt.rcParams['axes.unicode_minus'] = False

    plt.figure(figsize=(10, 5))
    if kind == "bar":
        plt.bar(valid_labels, valid_values, color="#4A90D9")
        plt.ylabel(ylabel)
    else:
        plt.plot(valid_labels, valid_values, marker="o", color="#4A90D9", linewidth=2)
        plt.ylabel(ylabel)

    plt.title(filename.replace("_", " ").title())
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(output)
    plt.close()
    print(f"  ✅ 图表已保存: {output}")

def _gen_bar_chart(labels, values, ylabel, filename):
    """生成柱状图"""
    _gen_chart(labels, values, ylabel, "bar", filename)

def _gen_multi_bar(labels, series_dict, ylabel, filename):
    """生成多系列柱状图"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output = f"{OUTPUT_DIR}/{filename}.png"

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    plt.figure(figsize=(12, 5))
    x = range(len(labels))
    width = 0.25
    colors = ["#4A90D9", "#50C878", "#FF6B6B"]
    for i, (name, vals) in enumerate(series_dict.items()):
        plt.bar([xi + i * width for xi in x], vals, width, label=name, color=colors[i % len(colors)])

    plt.xlabel("日期")
    plt.ylabel(ylabel)
    plt.title(filename.replace("_", " ").title())
    plt.xticks([xi + width for xi in x], labels, rotation=45, ha="right")
    plt.legend()
    plt.tight_layout()
    plt.savefig(output)
    plt.close()
    print(f"  ✅ 图表已保存: {output}")

def main():
    parser = argparse.ArgumentParser(description="mx-sky 能源管理查询工具")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("list", help="查看所有站点")
    sub.add_parser("realtime", help="实时数据").add_argument("site_id", help="站点ID")
    sub.add_parser("bess", help="今日BESS数据").add_argument("site_id", help="站点ID")
    sub.add_parser("earnings-week", help="周收益").add_argument("site_id", help="站点ID")
    sub.add_parser("earnings-year", help="年收益").add_argument("site_id", help="站点ID")
    sub.add_parser("report", help="综合分析报告").add_argument("site_id", help="站点ID")

    pd = sub.add_parser("power-day", help="日功率图表")
    pd.add_argument("site_id", help="站点ID")
    pd.add_argument("date", nargs="?", help="日期 YYYY-MM-DD")

    cm = sub.add_parser("chart-month", help="月统计图表")
    cm.add_argument("site_id", help="站点ID")
    cm.add_argument("year_month", nargs="?", help="年月 YYYY-MM")

    args = parser.parse_args()

    if args.cmd == "list":
        cmd_list()
    elif args.cmd == "realtime":
        cmd_realtime(args.site_id)
    elif args.cmd == "bess":
        cmd_bess(args.site_id)
    elif args.cmd == "power-day":
        cmd_power_day(args.site_id, args.date)
    elif args.cmd == "chart-month":
        cmd_chart_month(args.site_id, args.year_month)
    elif args.cmd == "earnings-week":
        cmd_earnings_week(args.site_id)
    elif args.cmd == "earnings-year":
        cmd_earnings_year(args.site_id)
    elif args.cmd == "report":
        cmd_report(args.site_id)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
