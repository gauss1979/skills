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
    """日功率图表数据 — 输出顺序：图表 → 表格 → 总结"""
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

    # ── ① 图表（第一条输出）──────────────────────────────
    chart1 = _gen_chart(labels, grid, "电网功率(kW)", "line", f"power_day_{site_id}_{date_str or 'today'}")
    chart2 = _gen_bar_chart(labels[:24], [round((c or 0), 2) for c in consumption[:24]] if consumption else [],
                              "消耗功率(kW)", f"consumption_day_{site_id}")
    print(f"\n📊 图表路径: {chart1} / {chart2}")

    # ── ② 文字表格（第二条输出）──────────────────────────
    print(f"\n{'='*60}")
    print(f" 日功率 — [{site_id}]  {date_str or datetime.now().strftime('%Y-%m-%d')}")
    print(f"{'='*60}")
    print(f" 数据点数: {len(labels)}")
    valid_grid = [g for g in grid if g is not None and g != 0]
    valid_solar = [s for s in solar if s is not None and s != 0]
    if valid_grid:
        print(f" 电网功率范围: {min(valid_grid):.2f} ~ {max(valid_grid):.2f} kW")
    if valid_solar:
        print(f" 光伏功率范围: {min(valid_solar):.2f} ~ {max(valid_solar):.2f} kW")
    if bess and any(b for b in bess if b):
        valid_bess = [b for b in bess if b]
        print(f" 电池功率范围: {min(valid_bess):.2f} ~ {max(valid_bess):.2f} kW")

    # ── ③ 总结（第三条输出）──────────────────────────────
    net_import = sum(g for g in grid if g and g > 0) if grid else 0
    net_export = abs(sum(g for g in grid if g and g < 0)) if grid else 0
    print(f"\n电网净输入: {net_import:.2f} kW | 净输出: {net_export:.2f} kW")


def cmd_earnings_week(site_id):
    """周收益 — 输出顺序：图表 → 表格 → 总结"""
    ts = int(datetime.now(timezone.utc).timestamp() * 1000)
    data = api_get(f"/app/sites/{site_id}/earnings/week", {"timestamp": ts})
    resp = data.get("data", {})
    marks = resp.get("marks", [])
    values = resp.get("series", [{}])[0].get("value", [])

    labels = [datetime.fromtimestamp(m / 1000).strftime("%m-%d") for m in marks]
    earnings = [round(v or 0, 2) for v in values]

    # ── ① 图表（第一条输出）──────────────────────────────
    chart_path = _gen_chart(labels, earnings, "周收益(AU$)", "bar", f"earnings_week_{site_id}")
    print(f"\n📊 图表路径: {chart_path}")

    # ── ② 文字表格（第二条输出）──────────────────────────
    total = sum(earnings)
    print(f"\n{'='*60}")
    print(f" 周收益 — [{site_id}]  ({labels[0]} ~ {labels[-1]})")
    print(f"{'='*60}")
    max_val = max(abs(e) for e in earnings) if earnings else 1
    for lb, ev in zip(labels, earnings):
        bar = "█" * int(abs(ev) / max_val * 25)
        sign = "+" if ev >= 0 else "-"
        print(f"  {lb}  {sign}${abs(ev):>9.2f}  {bar}")
    print(f"  {'-'*32}")
    print(f"  合计  ${total:>10.2f}")

    # ── ③ 总结信息（第三条输出）──────────────────────────
    positive_days = [e for e in earnings if e > 0]
    negative_days = [e for e in earnings if e < 0]
    best_day = max(earnings) if earnings else 0
    worst_day = min(earnings) if earnings else 0
    best_label = labels[earnings.index(best_day)] if earnings and best_day in earnings else "-"
    worst_label = labels[earnings.index(worst_day)] if earnings and worst_day in earnings else "-"

    trend = "全周正收益" if not negative_days else f"{len(negative_days)}天负收益"
    status = "✅" if total > 0 else "⚠️"

    print(f"\n{trend}，周{'总收益' if total > 0 else '总亏损' if total < 0 else '持平'}")
    print(f"最高: ${best_day:.2f}（{best_label}） | 最低: ${worst_day:.2f}（{worst_label}）")
    print(f"合计: ${total:.2f} {status}")

    if negative_days and total > 0:
        avg_positive = sum(positive_days) / len(positive_days) if positive_days else 0
        print(f"正收益日均: ${avg_positive:.2f}，负收益日均: ${sum(negative_days)/len(negative_days):.2f}")


def cmd_earnings_year(site_id):
    """年收益 — 输出顺序：图表 → 表格 → 总结"""
    ts = int(datetime.now(timezone.utc).timestamp() * 1000)
    data = api_get(f"/app/sites/{site_id}/earnings/year", {"timestamp": ts})
    resp = data.get("data", {})
    marks = resp.get("marks", [])
    values = resp.get("series", [{}])[0].get("value", [])

    labels = [datetime.fromtimestamp(m / 1000).strftime("%Y-%m") for m in marks]
    earnings = [round(v or 0, 2) for v in values]

    # ── ① 图表（第一条输出）──────────────────────────────
    chart_path = _gen_chart(labels, earnings, "月收益(AU$)", "bar", f"earnings_year_{site_id}")
    print(f"\n📊 图表路径: {chart_path}")

    # ── ② 文字表格（第二条输出）──────────────────────────
    total = sum(earnings)
    print(f"\n{'='*60}")
    print(f" 年收益 — [{site_id}]")
    print(f"{'='*60}")
    non_zero = [(lb, ev) for lb, ev in zip(labels, earnings) if abs(ev) > 0.01]
    max_val = max(abs(ev) for _, ev in non_zero) if non_zero else 1
    for lb, ev in non_zero:
        bar = "█" * int(abs(ev) / max_val * 25)
        sign = "+" if ev >= 0 else "-"
        print(f"  {lb}  {sign}${abs(ev):>11.2f}  {bar}")
    print(f"  {'-'*35}")
    print(f"  合计  ${total:>12.2f}")

    # ── ③ 总结信息（第三条输出）──────────────────────────
    months_positive = [e for e in earnings if e > 0]
    months_negative = [e for e in earnings if e < 0]
    best_month_val = max(earnings) if earnings else 0
    worst_month_val = min(earnings) if earnings else 0
    best_label = labels[earnings.index(best_month_val)] if earnings and best_month_val in earnings else "-"
    worst_label = labels[earnings.index(worst_month_val)] if earnings and worst_month_val in earnings else "-"

    trend = f"{len(months_negative)}个月负收益" if months_negative else "全年正收益"
    status = "✅" if total > 0 else "⚠️"

    print(f"\n{trend}，年{'总收益' if total > 0 else '总亏损' if total < 0 else '持平'}")
    print(f"最高月: ${best_month_val:.2f}（{best_label}） | 最低月: ${worst_month_val:.2f}（{worst_label}）")
    print(f"合计: ${total:.2f} {status}")
    if months_positive:
        print(f"月均收益: ${total/len(months_positive):.2f}")


def cmd_chart_month(site_id, year_month=None):
    """月统计图表 — 输出顺序：图表 → 表格 → 总结"""
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

    # ── ① 图表（第一条输出）──────────────────────────────
    chart_path = _gen_multi_bar(labels, {
        "光伏充电": solar_chg,
        "电池充电": bess_chg,
        "电池放电": bess_dischg,
    }, "月充放电统计(kWh)", f"monthly_{site_id}")
    print(f"\n📊 图表路径: {chart_path}")

    # ── ② 文字表格（第二条输出）──────────────────────────
    total_solar = sum(solar_chg)
    total_bess_chg = sum(bess_chg)
    total_bess_dischg = sum(bess_dischg)
    net = total_bess_dischg - total_bess_chg
    print(f"\n{'='*60}")
    print(f" 月统计 — [{site_id}]  {year_month or datetime.now().strftime('%Y-%m')}")
    print(f"{'='*60}")
    print(f" 光伏充电量: {total_solar:.2f} kWh")
    print(f" 电池充电量: {total_bess_chg:.2f} kWh  | 放电量: {total_bess_dischg:.2f} kWh")
    print(f" 净充放电: {net:+.2f} kWh")

    # ── ③ 总结（第三条输出）──────────────────────────────
    chg_ratio = (total_bess_chg / total_solar * 100) if total_solar > 0 else 0
    dischg_ratio = (total_bess_dischg / total_bess_chg * 100) if total_bess_chg > 0 else 0
    print(f"\n光伏自用率: {chg_ratio:.1f}% | 放电率: {dischg_ratio:.1f}%")
    status = "✅" if net >= 0 else "⚠️"
    print(f"电池净{'获利' if net >= 0 else '损耗'}: {abs(net):.2f} kWh {status}")


def cmd_solar(site_id, days=7):
    """查询站点近N天发电量 — 输出顺序：图表 → 表格 → 总结"""
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
    labels = [datetime.strptime(d, "%Y-%m-%d").strftime("%m-%d") for d in sorted_dates]
    values = [daily_data[d] for d in sorted_dates]

    # ── ① 图表（第一条输出）──────────────────────────────
    chart_path = _gen_chart(labels, values, "Solar Generation (kWh)", "bar", f"solar_{site_id}_{days}days")
    print(f"\n📊 图表路径: {chart_path}")

    # ── ② 文字表格（第二条输出）──────────────────────────
    print(f"\n{'='*60}")
    print(f"  近 {days} 天光伏日发电量 — [{site_id}]")
    print(f"{'='*60}")
    total = 0
    max_val = max(values) if values else 1
    for date_str, val in zip(sorted_dates, values):
        total += val
        bar = "█" * int(val / max_val * 25)
        weekday = datetime.strptime(date_str, "%Y-%m-%d").strftime("%a")
        print(f"  {date_str} ({weekday})  {val:>8.2f} kWh  {bar}")
    print(f"  {'-'*40}")
    print(f"  合计: {total:.2f} kWh")

    # ── ③ 总结信息（第三条输出）──────────────────────────
    if values:
        avg = total / len(values)
        max_v = max(values)
        min_v = min(values)
        best_date = sorted_dates[values.index(max_v)]
        worst_date = sorted_dates[values.index(min_v)]
        print(f"\n日均发电: {avg:.2f} kWh，最高 {max_v:.2f} kWh（{best_date}），最低 {min_v:.2f} kWh（{worst_date}）")
        print(f"总发电量: {total:.2f} kWh ✅")


def cmd_report(site_id):
    """综合分析报告 — 输出顺序：图表 → 表格 → 总结"""
    ts = int(datetime.now(timezone.utc).timestamp() * 1000)

    # ── 并行拉取所有数据 ────────────────────────────────
    site_data = api_get(f"/app/sites/{site_id}")
    d = site_data.get("data", {})
    name = d.get("name", "-")

    bess_data = api_get(f"/app/sites/{site_id}/bess/today")
    bess = bess_data.get("data", {})

    ew = api_get(f"/app/sites/{site_id}/earnings/week", {"timestamp": ts})
    ew_vals = [v or 0 for v in ew.get("data", {}).get("series", [{}])[0].get("value", [])]
    ew_marks = ew.get("data", {}).get("marks", [])
    ew_labels = [datetime.fromtimestamp(m / 1000).strftime("%m-%d") for m in ew_marks]
    ew_total = sum(ew_vals)

    ey = api_get(f"/app/sites/{site_id}/earnings/year", {"timestamp": ts})
    ey_vals = [v or 0 for v in ey.get("data", {}).get("series", [{}])[0].get("value", [])]
    ey_marks = ey.get("data", {}).get("marks", [])
    ey_labels = [datetime.fromtimestamp(m / 1000).strftime("%Y-%m") for m in ey_marks]
    ey_total = sum(ey_vals)

    # ── ① 图表（第一条输出）──────────────────────────────
    chart_week = _gen_chart(ew_labels, ew_vals, "周收益(AU$)", "bar", f"report_week_{site_id}") if ew_vals else None
    chart_year = _gen_chart(ey_labels, ey_vals, "月收益(AU$)", "bar", f"report_year_{site_id}") if ey_vals else None
    print(f"\n📊 图表路径: 周收益={chart_week} / 年收益={chart_year}")

    # ── ② 文字表格（第二条输出）──────────────────────────
    chg = bess.get("chg", 0) / 1000
    dischg = bess.get("dischg", 0) / 1000
    today_rev = d.get('todayRevenue', 0)
    print(f"\n{'='*60}")
    print(f"  ⚡ 能源站点综合分析报告  [{site_id}]  {name}")
    print(f"{'='*60}")
    print(f"\n📍 今日概况")
    print(f"   收益: ${today_rev:.4f} | 光伏: {fmt_power(d.get('solarTotalPower'))} | SOC: {d.get('totalSoc','-')}%")
    print(f"\n🔋 今日BESS: 充电 {chg:.2f}kWh | 放电 {dischg:.2f}kWh | 净 {dischg-chg:+.2f}kWh")
    print(f"\n💰 周收益: AU${ew_total:.2f} | 年收益: AU${ey_total:.2f}")
    print(f"\n{'='*60}")
    print(f" 报告生成: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    # ── ③ 总结（第三条输出）──────────────────────────────
    ew_best = max(ew_vals) if ew_vals else 0
    ew_worst = min(ew_vals) if ew_vals else 0
    ey_best = max(ey_vals) if ey_vals else 0
    ey_worst = min(ey_vals) if ey_vals else 0

    print(f"\n📊 关键指标")
    print(f"  周收益: AU${ew_total:.2f}（最高 ${ew_best:.2f}，最低 ${ew_worst:.2f}）")
    print(f"  年收益: AU${ey_total:.2f}（最高月 ${ey_best:.2f}，最低月 ${ey_worst:.2f}）")
    print(f"  今日BESS净: {'放电' if dischg > chg else '充电'} {abs(dischg-chg):.2f} kWh")
    overall = "✅ 盈利状态" if ey_total > 0 else "⚠️ 亏损状态"
    print(f"\n整体运营: {overall}")


# ─── 图表生成 ────────────────────────────────────────────────

def _gen_chart(labels, values, ylabel, kind, filename):
    """生成单系列图表，返回图表文件路径"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output = f"{OUTPUT_DIR}/{filename}.png"

    valid_labels, valid_values = [], []
    for lb, val in zip(labels, values):
        if val is not None and val != "":
            valid_labels.append(lb)
            valid_values.append(float(val))

    if not valid_values:
        print(f"  (无有效数据，跳过图表)")
        return None

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
    return output


def _gen_bar_chart(labels, values, ylabel, filename):
    """生成单系列柱状图（兼容封装）"""
    return _gen_chart(labels, values, ylabel, "bar", filename)


def _gen_multi_bar(labels, series_dict, ylabel, filename):
    """生成多系列柱状图，返回图表文件路径"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output = f"{OUTPUT_DIR}/{filename}.png"

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
    return output


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
