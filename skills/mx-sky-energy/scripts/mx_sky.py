#!/usr/bin/env python3
"""
mx-sky 能源管理查询工具
支持：站点列表、实时数据、BESS状态、收益查询、功率图表、图表生成
认证：用户名 + 密码（自动登录获取 token）
"""
import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone

CREDENTIALS_FILE = os.path.expanduser("~/.sunergy/credentials")
TOKEN_CACHE_FILE = os.path.expanduser("~/.sunergy/token")
BASE_URL = "http://web.aws.aiminis.com/api"
CHART_SCRIPT = "/root/.openclaw/workspace/skills/mx-sky-energy/scripts/gen_energy_chart.py"
OUTPUT_DIR = "/root/.openclaw/workspace/memory/chart/output"

# ─── 凭证管理 ────────────────────────────────────────────────

def load_credentials():
    """加载用户名/密码（支持 phone 或 username 字段）"""
    if not os.path.exists(CREDENTIALS_FILE):
        return None
    creds = {}
    with open(CREDENTIALS_FILE) as f:
        for line in f:
            line = line.strip()
            if "=" in line:
                k, v = line.split("=", 1)
                creds[k.strip()] = v.strip()
    # 支持 phone（手机号）或 username 字段
    username = creds.get("phone") or creds.get("username") or ""
    password = creds.get("password", "")
    if username and password:
        return username, password
    return None


def save_token(token):
    """缓存登录 token"""
    with open(TOKEN_CACHE_FILE, "w") as f:
        f.write(token)


def load_cached_token():
    """加载缓存的 token"""
    if os.path.exists(TOKEN_CACHE_FILE):
        with open(TOKEN_CACHE_FILE) as f:
            return f.read().strip()
    return None


def do_login(username, password):
    """执行登录，获取 token（Bearer）"""
    url = f"{BASE_URL}/auth/getToken/byPhonePassword"
    payload = json.dumps({
        "phone": username,
        "password": password,
        "type": False,
        "tenantId": "3",
        "isNew": 0
    }).encode()
    headers = {
        "Content-Type": "application/json",
        "tenantId": "3",
        "timeZone": "Asia/Shanghai",
        "Authorization": "Basic c3VuOk5jdlJmL2EyZFBPTjU3Nm9HZkMvUXc9PQ==",
        "Origin": "http://web.aws.aiminis.com",
        "Referer": "http://web.aws.aiminis.com/login",
        "User-Agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
    }
    req = urllib.request.Request(url, data=payload, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            if data.get("success") and data.get("data", {}).get("access_token"):
                token = data["data"]["access_token"]
                save_token(token)
                return token
            print(f"❌ 登录失败: {data.get('msg', '未知错误')}")
            sys.exit(1)
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        try:
            err_obj = json.loads(err)
            print(f"❌ 登录失败 ({e.code}): {err_obj.get('msg', err)}")
        except Exception:
            print(f"❌ 登录失败 ({e.code}): {err}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 登录请求失败: {e}")
        sys.exit(1)


def ensure_token():
    """确保有可用 token：优先缓存，其次登录"""
    token = load_cached_token()
    if token:
        return token

    creds = load_credentials()
    if not creds:
        print("❌ 未配置 Sunergy 凭证！")
        print("请提供你的 Sunergy 登录信息，格式：")
        print('  echo "phone=你的手机号" > ~/.sunergy/credentials')
        print('  echo "password=你的密码" >> ~/.sunergy/credentials')
        print('  chmod 600 ~/.sunergy/credentials')
        print("\n示例：")
        print('  echo "phone=13301313667" > ~/.sunergy/credentials')
        print('  echo "password=231456" >> ~/.sunergy/credentials')
        sys.exit(1)

    print("🔐 正在登录 Sunergy...")
    return do_login(creds[0], creds[1])


# ─── API 请求 ────────────────────────────────────────────────

def api_get(path, params=None, tz="Australia/Sydney"):
    token = ensure_token()

    url = f"{BASE_URL}{path}"
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())

    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("tenantId", "3")
    req.add_header("timeZone", tz)
    req.add_header("Origin", "http://web.aws.aiminis.com")
    req.add_header("Referer", "http://web.aws.aiminis.com/")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 401:
            # Token 过期，尝试重新登录
            creds = load_credentials()
            if creds:
                print("🔐 Token 过期，重新登录...")
                token = do_login(creds[0], creds[1])
                req.add_header("Authorization", f"Bearer {token}")
                try:
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        return json.loads(resp.read().decode())
                except Exception:
                    pass
        print(f"❌ HTTP错误 {e.code}: {e.read().decode()}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        sys.exit(1)


# ─── 工具函数 ────────────────────────────────────────────────

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


# ─── 命令实现 ────────────────────────────────────────────────

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
        dt = datetime.now(timezone.utc)
    ts = int(dt.timestamp() * 1000)

    data = api_get(f"/app/sites/{site_id}/power/day", {"timestamp": ts})
    resp = data.get("data", {})
    marks = resp.get("marks", [])
    series_map = {s["code"]: s["value"] for s in resp.get("series", [])}

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

    _gen_chart(labels, grid, "电网功率", "line", f"power_day_{site_id}_{date_str or 'today'}")
    _gen_bar_chart(labels[:24], [round((c or 0), 2) for c in consumption[:24]] if consumption else [],
                   "消耗功率(kW)", f"consumption_day_{site_id}")
    print(f"\n📊 图表已生成！")


def cmd_earnings_week(site_id):
    """周收益"""
    ts = int(datetime.now(timezone.utc).timestamp() * 1000)
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

    _gen_chart(labels, earnings, "周收益(AU$)", "bar", f"earnings_week_{site_id}")
    print(f"\n📊 图表已生成！")


def cmd_earnings_year(site_id):
    """年收益"""
    ts = int(datetime.now(timezone.utc).timestamp() * 1000)
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

    _gen_chart(labels, earnings, "月收益(AU$)", "bar", f"earnings_year_{site_id}")
    print(f"\n📊 图表已生成！")


def cmd_chart_month(site_id, year_month=None):
    """月统计图表（使用 /charts/month，日聚合数据）"""
    if year_month:
        dt = datetime.strptime(year_month, "%Y-%m")
    else:
        dt = datetime.now(timezone.utc)
    ts = int(dt.timestamp() * 1000)

    data = api_get(f"/app/sites/{site_id}/charts/month", {"timestamp": ts})
    resp = data.get("data", {})
    marks = resp.get("marks", [])
    series_map = {s["code"]: s["value"] for s in resp.get("series", [])}

    labels = [datetime.fromtimestamp(m / 1000).strftime("%m-%d") for m in marks]
    solar_chg = [round((v or 0) / 3_600_000, 2) for v in series_map.get("solarChg", [])]
    bess_chg = [round((v or 0) / 3_600_000, 2) for v in series_map.get("bessChg", [])]
    bess_dischg = [round((v or 0) / 3_600_000, 2) for v in series_map.get("bessDischg", [])]

    print(f"\n{'='*60}")
    print(f" 月统计 — [{site_id}]  {year_month or datetime.now().strftime('%Y-%m')}")
    print(f"{'='*60}")
    total_solar = sum(solar_chg)
    total_bess_chg = sum(bess_chg)
    total_bess_dischg = sum(bess_dischg)
    print(f" 光伏充电量: {total_solar:.2f} kWh")
    print(f" 电池充电量: {total_bess_chg:.2f} kWh  | 放电量: {total_bess_dischg:.2f} kWh")
    print(f" 净收益: {(total_bess_dischg - total_bess_chg):.2f} kWh")

    _gen_multi_bar(labels, {
        "光伏充电": solar_chg,
        "电池充电": bess_chg,
        "电池放电": bess_dischg,
    }, "月充放电统计(kWh)", f"monthly_{site_id}")
    print(f"\n📊 图表已生成！")


def cmd_solar(site_id, days=7):
    """查询站点近N天发电量（使用 /charts/month 接口）"""
    now = datetime.now(timezone.utc)
    months = []
    for offset in range(2):
        d = datetime(now.year, now.month, 1)
        if offset > 0:
            d = (d - timedelta(days=1)).replace(day=1)
        months.append((d.year, d.month, int(d.timestamp() * 1000)))

    daily_data = {}
    for year, month, ts in months:
        data = api_get(f"/app/sites/{site_id}/charts/month", {"timestamp": ts})
        resp = data.get("data", {})
        marks = resp.get("marks", [])
        series_map = {s["code"]: s["value"] for s in resp.get("series", [])}
        for m, val in zip(marks, series_map.get("solarChg", [])):
            if val is not None and val > 0:
                syd_ts = m / 1000 + 10 * 3600
                dt = datetime.fromtimestamp(syd_ts)
                date_str = dt.strftime("%Y-%m-%d")
                daily_data[date_str] = round(val / 1000, 2)

    sorted_dates = sorted(daily_data.keys(), reverse=True)[:days]
    sorted_dates.reverse()

    print(f"\n{'='*60}")
    print(f"  近 {days} 天光伏日发电量 — [{site_id}]")
    print(f"{'='*60}")
    total = 0
    max_val = max(daily_data.values()) if daily_data else 1
    for date_str in sorted_dates:
        val = daily_data[date_str]
        total += val
        bar = "█" * int(val / max_val * 25)
        weekday = datetime.strptime(date_str, "%Y-%m-%d").strftime("%a")
        print(f"  {date_str} ({weekday})  {val:>8.2f} kWh  {bar}")
    print(f"  {'-'*40}")
    print(f"  合计: {total:.2f} kWh")

    labels = [datetime.strptime(d, "%Y-%m-%d").strftime("%m-%d") for d in sorted_dates]
    values = [daily_data[d] for d in sorted_dates]
    _gen_chart(labels, values, "Solar Generation (kWh)", "bar", f"solar_{site_id}_{days}days")
    print(f"\n  图表已生成!")


def cmd_report(site_id):
    """综合分析报告"""
    print(f"\n{'='*60}")
    print(f"  ⚡ 能源站点综合分析报告  [{site_id}]")
    print(f"{'='*60}")

    data = api_get(f"/app/sites/{site_id}")
    d = data.get("data", {})
    name = d.get("name", "-")

    bess_data = api_get(f"/app/sites/{site_id}/bess/today")
    bess = bess_data.get("data", {})

    print(f"\n📍 基本信息: {name}")
    print(f"   今日收益: ${d.get('todayRevenue', 0):.4f}")
    print(f"   光伏功率: {fmt_power(d.get('solarTotalPower'))}")
    print(f"   电池SOC: {d.get('totalSoc','-')}% | 电池功率: {fmt_power(d.get('bessTotalPower'))}")

    chg = bess.get("chg", 0) / 1000
    dischg = bess.get("dischg", 0) / 1000
    print(f"\n🔋 今日BESS: 充电 {chg:.2f}kWh | 放电 {dischg:.2f}kWh | 净 {dischg-chg:.2f}kWh")

    ts = int(datetime.now(timezone.utc).timestamp() * 1000)
    ew = api_get(f"/app/sites/{site_id}/earnings/week", {"timestamp": ts})
    ew_vals = [v or 0 for v in ew.get("data", {}).get("series", [{}])[0].get("value", [])]
    ew_total = sum(ew_vals)
    print(f"\n💰 周收益: AU${ew_total:.2f}")

    ey = api_get(f"/app/sites/{site_id}/earnings/year", {"timestamp": ts})
    ey_vals = [v or 0 for v in ey.get("data", {}).get("series", [{}])[0].get("value", [])]
    ey_total = sum(ey_vals)
    print(f"💰 年收益: AU${ey_total:.2f}")

    print(f"\n{'='*60}")
    print(f" 报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    ew_marks = ew.get("data", {}).get("marks", [])
    ew_labels = [datetime.fromtimestamp(m / 1000).strftime("%m-%d") for m in ew_marks]
    if ew_vals:
        _gen_chart(ew_labels, ew_vals, "周收益(AU$)", "bar", f"report_week_{site_id}")

    ey_marks = ey.get("data", {}).get("marks", [])
    ey_labels = [datetime.fromtimestamp(m / 1000).strftime("%Y-%m") for m in ey_marks]
    if ey_vals:
        _gen_chart(ey_labels, ey_vals, "月收益(AU$)", "bar", f"report_year_{site_id}")

    print(f"\n📊 分析图表已生成！")


# ─── 图表生成 ────────────────────────────────────────────────

def _gen_chart(labels, values, ylabel, kind, filename):
    """生成单系列图表"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output = f"{OUTPUT_DIR}/{filename}.png"

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


# ─── 主入口 ───────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="mx-sky 能源管理查询工具")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("list", help="查看所有站点")
    sub.add_parser("realtime", help="实时数据").add_argument("site_id", help="站点ID")
    sub.add_parser("bess", help="今日BESS数据").add_argument("site_id", help="站点ID")
    sub.add_parser("earnings-week", help="周收益").add_argument("site_id", help="站点ID")
    sub.add_parser("earnings-year", help="年收益").add_argument("site_id", help="站点ID")
    sub.add_parser("report", help="综合分析报告").add_argument("site_id", help="站点ID")
    solar_p = sub.add_parser("solar", help="近N天光伏日发电量")
    solar_p.add_argument("site_id", help="站点ID")
    solar_p.add_argument("days", nargs="?", type=int, default=7, help="天数，默认7天")

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
    elif args.cmd == "solar":
        cmd_solar(args.site_id, args.days)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
