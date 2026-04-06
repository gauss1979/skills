#!/usr/bin/env python3
"""
Amber Electric API 查询工具
支持：站点列表、实时电价、电价预测、用量查询、电价分析报告
"""
import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

TOKEN_FILE = os.path.expanduser("~/.amber/token")
BASE_URL = "https://api.amber.com.au/v1"
# NEM 时区 (UTC+10)
NEM_TZ = timezone(timedelta(hours=10))

def get_token():
    token = os.environ.get("AMBER_TOKEN")
    if token:
        return token
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            return f.read().strip()
    return None

def api_get(path, params=None):
    token = get_token()
    if not token:
        print("❌ 未配置 Token！请运行: echo '你的Token' > ~/.amber/token")
        sys.exit(1)

    url = f"{BASE_URL}{path}"
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())

    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP错误 {e.code}: {e.read().decode()}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        sys.exit(1)

def to_nem_time(iso_str):
    """ISO 时间字符串 → NEM 时区时间"""
    if not iso_str:
        return None
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    return dt.astimezone(NEM_TZ)

def nem_now():
    return datetime.now(NEM_TZ)

def cmd_list():
    """站点列表"""
    data = api_get("/sites")
    if not data:
        print("暂无站点数据")
        return

    print(f"\n{'='*70}")
    print(f"{'Amber Electric 站点列表':^50} (共 {len(data)} 个)")
    print(f"{'='*70}")
    for i, site in enumerate(data, 1):
        channels = site.get("channels", [])
        e1 = next((c for c in channels if c.get("identifier") == "E1"), {})
        b1 = next((c for c in channels if c.get("identifier") == "B1"), {})
        print(f"\n{i}. {site.get('id')} [{site.get('status','').upper()}]")
        print(f"   NMI: {site.get('nmi', '-')}")
        print(f"   电网: {site.get('network', '-')}")
        print(f"   状态: {site.get('status', '-')} | 激活: {site.get('activeFrom', '-')}")
        print(f"   通道数: {len(channels)} | 粒度: {site.get('intervalLength', '-')}min")
        if e1:
            print(f"   购电(E1) tariff: {e1.get('tariff','-')} | 类型: {e1.get('type','-')}")
        if b1:
            print(f"   售电(B1) tariff: {b1.get('tariff','-')} | 类型: {b1.get('type','-')}")

def cmd_price(site_id):
    """当前电价（购电+售电）"""
    # 查询过去6个+未来12个30分钟价格
    data = api_get(f"/sites/{site_id}/prices/current", {
        "previous": 6,
        "next": 12,
        "resolution": 30
    })
    if not data:
        print("无电价数据")
        return

    # 分类
    general = [d for d in data if d.get("channelType") == "general"]
    feedin = [d for d in data if d.get("channelType") == "feedIn"]

    now = nem_now()
    print(f"\n{'='*70}")
    print(f" 当前电价 — {site_id}  ({now.strftime('%Y-%m-%d %H:%M')} NEM)")
    print(f"{'='*70}")

    # 购电
    print(f"\n{'🔌 购电 (general)':}")
    print(f"  {'时间':<22} {'类型':<6} {'电价(c/kWh)':>12} {'批发市场':>12} {'信号':<10}")
    print(f"  {'-'*65}")
    for d in general[:12]:
        dt = to_nem_time(d.get("startTime"))
        tp = "实际" if d.get("type") == "ActualInterval" else "预测"
        per = d.get("perKwh", 0)
        spot = d.get("spotPerKwh", 0)
        desc = d.get("descriptor", "-")
        label = f"{dt.strftime('%m-%d %H:%M')}" if dt else "-"
        print(f"  {label:<22} {tp:<6} {per:>12.2f} {spot:>12.2f} {desc:<10}")

    # 售电
    if feedin:
        print(f"\n{'📤 售电 (feedIn)':}")
        print(f"  {'时间':<22} {'类型':<6} {'电价(c/kWh)':>12} {'批发市场':>12} {'信号':<10}")
        print(f"  {'-'*65}")
        for d in feedin[:12]:
            dt = to_nem_time(d.get("startTime"))
            tp = "实际" if d.get("type") == "ActualInterval" else "预测"
            per = d.get("perKwh", 0)
            spot = d.get("spotPerKwh", 0)
            desc = d.get("descriptor", "-")
            label = f"{dt.strftime('%m-%d %H:%M')}" if dt else "-"
            print(f"  {label:<22} {tp:<6} {per:>12.2f} {spot:>12.2f} {desc:<10}")

    # 摘要
    actual_g = [d for d in general if d.get("type") == "ActualInterval"]
    actual_f = [d for d in feedin if d.get("type") == "ActualInterval"]
    if actual_g:
        avg_buy = sum(d.get("perKwh",0) for d in actual_g) / len(actual_g)
        print(f"\n  当前购电均价: {avg_buy:.2f} c/kWh = AU${avg_buy/100:.4f}/kWh")
    if actual_f:
        avg_sell = sum(d.get("perKwh",0) for d in actual_f) / len(actual_f)
        print(f"  当前售电均价: {avg_sell:.2f} c/kWh = AU${avg_sell/100:.4f}/kWh")

def cmd_forecast(site_id, hours=4):
    """未来电价预测"""
    # resolution=5 查接下来1小时(12个5分钟)，之后resolution=30
    # 先用resolution=30查30分钟粒度
    n_intervals = hours * 2  # 30min intervals
    data = api_get(f"/sites/{site_id}/prices/current", {
        "previous": 2,
        "next": n_intervals,
        "resolution": 30
    })
    if not data:
        print("无预测数据")
        return

    forecast = [d for d in data if d.get("type") == "ForecastInterval"]
    now = nem_now()

    print(f"\n{'='*70}")
    print(f" 电价预测 — {site_id}  (未来 {hours} 小时, NEM时间)")
    print(f"{'='*70}")
    print(f"  {'时间':<22} {'购电(c/kWh)':>14} {'售电(c/kWh)':>14} {'信号':<10}")
    print(f"  {'-'*65}")

    # 按时间分组
    time_prices = {}
    for d in forecast:
        dt = to_nem_time(d.get("startTime"))
        if not dt:
            continue
        key = dt.strftime("%Y-%m-%d %H:%M")
        if key not in time_prices:
            time_prices[key] = {}
        ch = d.get("channelType")
        time_prices[key][ch] = d.get("perKwh", 0)

    for key in sorted(time_prices.keys())[:hours*2]:
        vals = time_prices[key]
        gen = vals.get("general", 0)
        feed = vals.get("feedIn", 0)
        # 确定信号
        desc = ""
        if gen > 30:
            desc = "⚠️ 高价"
        elif gen > 20:
            desc = "较高"
        elif gen < 10:
            desc = "✅ 低价"
        print(f"  {key:<22} {gen:>14.2f} {feed:>14.2f} {desc:<10}")

def cmd_usage(site_id, start_date, end_date):
    """用量查询"""
    # 转换日期为ISO格式
    start_iso = f"{start_date}T00:00:01Z"
    end_iso = f"{end_date}T00:00:01Z"

    print(f"\n  查询: {start_date} → {end_date}")

    data = api_get(f"/sites/{site_id}/usage", {
        "startDate": start_iso,
        "endDate": end_iso
    })
    if not data:
        print("  无用量数据")
        return

    # 按天汇总
    daily = {}
    for d in data:
        dt = to_nem_time(d.get("startTime"))
        if not dt:
            continue
        date_key = dt.strftime("%Y-%m-%d")
        ch = d.get("channelType", "")
        per = d.get("perKwh", 0)
        dur = d.get("duration", 30)
        # kWh = perKwh(c/kWh) * 0.01 * duration(h)
        kwh = per * 0.01 * (dur / 60)
        if date_key not in daily:
            daily[date_key] = {"general_kwh": 0, "feedin_kwh": 0, "general_cost": 0, "feedin_rev": 0}
        if ch == "general":
            daily[date_key]["general_kwh"] += kwh
            daily[date_key]["general_cost"] += kwh * per
        elif ch == "feedIn":
            daily[date_key]["feedin_kwh"] += kwh
            daily[date_key]["feedin_rev"] += kwh * per

    print(f"\n{'='*70}")
    print(f" 用量详情 — {site_id}  ({start_date} → {end_date})")
    print(f"{'='*70}")
    print(f"  {'日期':<14} {'购电(kWh)':>12} {'购电费用(c)':>14} {'售电(kWh)':>12} {'售电收入(c)':>14}")
    print(f"  {'-'*70}")
    total_gen_kwh=total_gen_cost=total_feed_kwh=total_feed_rev=0
    for date_key in sorted(daily.keys()):
        v = daily[date_key]
        wk = v["general_kwh"]
        wc = v["general_cost"]
        sk = v["feedin_kwh"]
        sc = v["feedin_rev"]
        total_gen_kwh+=wk; total_gen_cost+=wc; total_feed_kwh+=sk; total_feed_rev+=sc
        print(f"  {date_key:<14} {wk:>12.2f} {wc:>14.2f} {sk:>12.2f} {sc:>14.2f}")
    print(f"  {'-'*70}")
    print(f"  {'合计':<14} {total_gen_kwh:>12.2f} {total_gen_cost:>14.2f} {total_feed_kwh:>12.2f} {total_feed_rev:>14.2f}")
    net = total_feed_rev - total_gen_cost
    print(f"\n  💰 净费用: {total_gen_cost:.2f}c - {total_feed_rev:.2f}c = {net:.2f}c (AU${abs(net)/100:.2f})")
    if net < 0:
        print(f"  → 净支出 AU${abs(net)/100:.2f}")
    else:
        print(f"  → 净收入 AU${net/100:.2f}")

def cmd_report(site_id):
    """综合电价分析报告"""
    now = nem_now()
    today = now.strftime("%Y-%m-%d")
    week_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d")

    print(f"\n{'='*70}")
    print(f"  Amber 电价综合分析报告")
    print(f"  站点: {site_id}")
    print(f"{'='*70}")

    # 当前电价
    print(f"\n📌 当前电价（NEM {now.strftime('%Y-%m-%d %H:%M')}）")
    price_data = api_get(f"/sites/{site_id}/prices/current", {
        "previous": 6, "next": 6, "resolution": 30
    })
    actual = [d for d in price_data if d.get("type") == "ActualInterval"]
    forecast = [d for d in price_data if d.get("type") == "ForecastInterval"]

    if actual:
        gen_actual = [d for d in actual if d.get("channelType") == "general"]
        feed_actual = [d for d in actual if d.get("channelType") == "feedIn"]
        if gen_actual:
            avg_gen = sum(d.get("perKwh",0) for d in gen_actual) / len(gen_actual)
            print(f"  购电均价: {avg_gen:.2f} c/kWh = AU${avg_gen/100:.4f}/kWh")
        if feed_actual:
            avg_feed = sum(d.get("perKwh",0) for d in feed_actual) / len(feed_actual)
            print(f"  售电均价: {avg_feed:.2f} c/kWh = AU${avg_feed/100:.4f}/kWh")

    if forecast:
        peak = max(d.get("perKwh",0) for d in forecast if d.get("channelType") == "general")
        low = min(d.get("perKwh",0) for d in forecast if d.get("channelType") == "general")
        print(f"  预测峰值: {peak:.2f} c/kWh | 预测最低: {low:.2f} c/kWh")

    # 近7天用量
    print(f"\n📊 近7天用电（{week_ago} → {today}）")
    usage_data = api_get(f"/sites/{site_id}/usage", {
        "startDate": f"{week_ago}T00:00:01Z",
        "endDate": f"{today}T00:00:01Z"
    })
    if usage_data:
        gen_kwh = sum(
            d.get("perKwh",0) * 0.01 * d.get("duration",30)/60
            for d in usage_data if d.get("channelType") == "general"
        )
        feed_kwh = sum(
            d.get("perKwh",0) * 0.01 * d.get("duration",30)/60
            for d in usage_data if d.get("channelType") == "feedIn"
        )
        print(f"  购电量: {gen_kwh:.2f} kWh")
        print(f"  售电量: {feed_kwh:.2f} kWh")
    else:
        print("  暂无数据")

    print(f"\n{'='*70}")

def main():
    parser = argparse.ArgumentParser(description="Amber Electric 查询工具")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("list", help="查看所有站点")
    sub.add_parser("price", help="当前电价").add_argument("site_id", help="Amber站点ID")
    fp = sub.add_parser("forecast", help="电价预测")
    fp.add_argument("site_id", help="Amber站点ID")
    fp.add_argument("hours", nargs="?", type=int, default=4, help="预测小时数，默认4小时")

    up = sub.add_parser("usage", help="用量查询")
    up.add_argument("site_id", help="Amber站点ID")
    up.add_argument("start_date", help="开始日期 YYYY-MM-DD")
    up.add_argument("end_date", help="结束日期 YYYY-MM-DD")

    sub.add_parser("report", help="综合分析报告").add_argument("site_id", help="Amber站点ID")

    args = parser.parse_args()

    if args.cmd == "list":
        cmd_list()
    elif args.cmd == "price":
        cmd_price(args.site_id)
    elif args.cmd == "forecast":
        cmd_forecast(args.site_id, args.hours)
    elif args.cmd == "usage":
        cmd_usage(args.site_id, args.start_date, args.end_date)
    elif args.cmd == "report":
        cmd_report(args.site_id)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
