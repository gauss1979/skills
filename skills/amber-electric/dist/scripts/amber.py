#!/usr/bin/env python3
"""
Amber Electric API 查询工具 v3
支持：站点列表、实时电价、电价预测、用量查询（Python预处理）、电价分析报告

认证方式：用户名 + 密码（OAuth 2.0 Password Grant）
"""
import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone, timedelta
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

CRED_FILE = os.path.expanduser("~/.amber/credentials.json")
CONFIG_FILE = os.path.expanduser("~/.amber/config.json")

AUTH_URL = "https://auth.amber.com.au/connect/token"
BASE_URL = "https://api.amber.com.au/v1"


def load_config():
    """加载站点配置，无配置时返回空字典。"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


def save_config(cfg):
    """保存站点配置到 ~/.amber/config.json。"""
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)



def get_site_id_from_config():
    """从配置文件中读取站点ID，无配置时返回 None。"""
    return load_config().get("site_id")
BASE_URL = "https://api.amber.com.au/v1"
# NEM 时区 (UTC+10, AEST, 无夏令时)
NEM_TZ = timezone(timedelta(hours=10))

# ============ 认证（用户名+密码） ============
# 友好的错误提示，供 api_get 等函数在认证失败时引用
_AUTH_FAIL_MSG = (
    "❌ 认证失败或未配置 Amber 用户名/密码！\n"
    "请提供你的 Amber 用户名和密码，格式：\n"
    "  amber.py login <用户名> <密码>\n"
    "输入后技能会自动保存，后续查询无需再输入。"
)


class AuthMissingError(Exception):
    """用户名/密码未配置或无效，提示用户输入。"""
    USER_MSG = (
        "为了完成您的要求，我需要您提供 Amber 的用户名和密码。\n\n"
        "请将用户名和密码告诉我（格式：amber.py login <用户名> <密码>），"
        "技能会自动完成认证并保存凭证，后续无需再输入。\n\n"
        "示例：amber.py login myemail@example.com mypassword123"
    )


def _load_credentials():
    """从 ~/.amber/credentials.json 加载用户名和密码。"""
    if os.path.exists(CRED_FILE):
        try:
            with open(CRED_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_credentials(username, password):
    """保存用户名和密码到 ~/.amber/credentials.json。"""
    os.makedirs(os.path.dirname(CRED_FILE), exist_ok=True)
    with open(CRED_FILE, 'w') as f:
        json.dump({"username": username, "password": password}, f)
    os.chmod(CRED_FILE, 0o600)


def _get_access_token():
    """使用用户名+密码获取 Access Token。"""
    creds = _load_credentials()
    username = creds.get("username")
    password = creds.get("password")
    if not username or not password:
        return None

    data = urllib.parse.urlencode({
        "grant_type": "password",
        "username": username,
        "password": password,
        "scope": "openid profile email address phone",
    }).encode()

    req = urllib.request.Request(AUTH_URL, data=data)
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            token_data = json.loads(resp.read().decode())
            return token_data.get("access_token")
    except urllib.error.HTTPError as e:
        if e.code in (400, 401):
            return None
        raise
    except Exception:
        return None


def test_auth():
    """测试用户名+密码认证是否有效，返回 (成功bool, 站点数或错误信息)。"""
    token = _get_access_token()
    if not token:
        return False, "用户名或密码错误，请检查后重新输入。"

    req = urllib.request.Request(f"{BASE_URL}/sites")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return True, len(data) if isinstance(data, list) else 0
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False, "Token 已失效（401），请重新登录。"
        return False, f"HTTP {e.code}: {e.read().decode()[:200]}"
    except Exception as e:
        return False, f"请求失败: {e}"


def api_get(path, params=None):
    """带认证的 GET 请求，自动换取 Token。"""
    token = _get_access_token()
    if not token:
        raise AuthMissingError(_AUTH_FAIL_MSG)

    url = f"{BASE_URL}{path}"
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise AuthMissingError(
                "❌ 认证失败（401 Unauthorized）！\n"
                "请重新提供正确的用户名和密码：\n"
                "  amber.py login <用户名> <密码>"
            )
        raise AuthMissingError(f"❌ HTTP {e.code}: {e.read().decode()[:200]}")
    except Exception as e:
        raise AuthMissingError(f"❌ 请求失败: {e}")

# ============ 时间工具 ============
def nem_now():
    return datetime.now(NEM_TZ)

def to_nem(iso_str):
    """ISO字符串 → NEM时区"""
    if not iso_str:
        return None
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    return dt.astimezone(NEM_TZ)

def date_to_api(date_str):
    """将 YYYY-MM-DD 或 YYYY-M-D 转为 API 格式"""
    # 自动补全 YYYY-MM-DD
    parts = re.split(r'[-\/]', date_str.strip())
    if len(parts) == 3:
        return f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"
    return date_str

def parse_natural_date(text, ref_date=None):
    """
    将自然语言日期转换为 (start_date, end_date) API格式字符串
    ref_date: 参考日期（nem_now）
    返回: (start_YYYY_MM_DD, end_YYYY_MM_DD)
    """
    if ref_date is None:
        ref_date = nem_now()

    text = text.strip().lower()

    # 今天/昨天/前天
    today = ref_date.date()
    if text in ["今天", "今日", "today"]:
        return (today.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))
    if text in ["昨天", "yesterday"]:
        d = today - timedelta(days=1)
        return (d.strftime("%Y-%m-%d"), d.strftime("%Y-%m-%d"))
    if text in ["前天"]:
        d = today - timedelta(days=2)
        return (d.strftime("%Y-%m-%d"), d.strftime("%Y-%m-%d"))

    # 近N天
    m = re.match(r'(?:近|过去|最近)(?:.*?)?(\d+)天', text)
    if m:
        n = int(m.group(1))
        start = today - timedelta(days=n - 1)
        return (start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))

    # 前N天
    m = re.match(r'前(\d+)天', text)
    if m:
        n = int(m.group(1))
        start = today - timedelta(days=n)
        end = today - timedelta(days=1)
        return (start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))

    # 自然周 (周一~周日)
    # 本周：从本周一开始到今天
    if text in ["本周", "这周", "本周至今"]:
        monday = today - timedelta(days=today.weekday())
        return (monday.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))
    # 上周：从上周一开始到上周日
    if text in ["上周", "上周整周"]:
        this_monday = today - timedelta(days=today.weekday())
        last_monday = this_monday - timedelta(days=7)
        last_sunday = last_monday + timedelta(days=6)
        return (last_monday.strftime("%Y-%m-%d"), last_sunday.strftime("%Y-%m-%d"))
    # 上上周
    if text in ["上上周"]:
        this_monday = today - timedelta(days=today.weekday())
        last_monday = this_monday - timedelta(days=7)
        last_sunday = last_monday + timedelta(days=6)
        prev_monday = last_monday - timedelta(days=7)
        prev_sunday = prev_monday + timedelta(days=6)
        return (prev_monday.strftime("%Y-%m-%d"), prev_sunday.strftime("%Y-%m-%d"))

    # 指定日期 YYYY-MM-DD 或 YYYY-M-D
    m = re.match(r'^(\d{4})[-/]?(\d{1,2})[-/]?(\d{1,2})$', text)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return (f"{y:04d}-{mo:02d}-{d:02d}", f"{y:04d}-{mo:02d}-{d:02d}")

    # 区间格式: "2026-03-01 到 2026-03-07" 或 "2026-03-01~2026-03-07"
    for sep in ['到', '~', '-', '--', '  ']:
        if sep in text:
            parts = text.split(sep)
            if len(parts) == 2:
                s = date_to_api(parts[0].strip())
                e = date_to_api(parts[1].strip())
                return (s, e)

    # 月份格式 "2026年3月" -> 全月
    m = re.match(r'(\d{4})[年]?\s*(\d{1,2})[月]?', text)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        return None, None  # 月份暂不支持

    return None, None

def format_nem_datetime(iso_str):
    """NEM时间显示格式"""
    dt = to_nem(iso_str)
    if not dt:
        return "-"
    return dt.strftime("%m-%d %H:%M")

# ============ 站点命令 ============
def cmd_list():
    data = api_get("/sites")
    if not data:
        print("暂无站点数据")
        return
    print(f"\n{'='*65}")
    print(f"  Amber Electric 站点列表  (共 {len(data)} 个)")
    print(f"{'='*65}")
    for i, site in enumerate(data, 1):
        channels = site.get("channels", [])
        e1 = next((c for c in channels if c.get("identifier") == "E1"), {})
        b1 = next((c for c in channels if c.get("identifier") == "B1"), {})
        print(f"\n  {i}. {site.get('id')}")
        print(f"     NMI: {site.get('nmi','-')}  |  电网: {site.get('network','-')}")
        print(f"     状态: {site.get('status','-')}  |  激活: {site.get('activeFrom','-')}  |  粒度: {site.get('intervalLength','-')}min")
        if e1:
            print(f"     购电(E1) tariff: {e1.get('tariff','-')}  |  类型: {e1.get('type','-')}")
        if b1:
            print(f"     售电(B1) tariff: {b1.get('tariff','-')}  |  类型: {b1.get('type','-')}")
    print()

# ============ 当前电价命令 ============
def cmd_price(site_id):
    # 查过去6个+未来12个 30分钟价格
    data = api_get(f"/sites/{site_id}/prices/current", {
        "previous": 6, "next": 12, "resolution": 30
    })
    if not data:
        print("无电价数据")
        return

    general = [d for d in data if d.get("channelType") == "general"]
    feedin  = [d for d in data if d.get("channelType") == "feedIn"]
    now = nem_now()

    print(f"\n{'='*65}")
    print(f"  当前电价  {site_id}")
    print(f"  NEM时间: {now.strftime('%Y-%m-%d %H:%M')}  ({now.strftime('%A')})")
    print(f"{'='*65}")

    # 购电
    print(f"\n  🔌 购电 (general / E1)")
    print(f"  {'时间(NEM)':<18} {'类型':<6} {'电价':>10} {'市场':>10} {'信号':<12} {'区间'}")
    print(f"  {'-'*70}")
    for d in general:
        dt = to_nem(d.get("startTime"))
        tp = "实际" if d.get("type") in ("ActualInterval","CurrentInterval") else "预测"
        per = d.get("perKwh", 0)
        spot = d.get("spotPerKwh", 0)
        desc = d.get("descriptor", "-")
        period = d.get("tariffInformation", {}).get("period", "-") or "-"
        time_str = dt.strftime("%m-%d %H:%M") if dt else "-"
        print(f"  {time_str:<18} {tp:<6} {per:>10.2f} {spot:>10.2f} {desc:<12} {period}")

    # 售电
    if feedin:
        print(f"\n  📤 售电 (feedIn / B1)")
        print(f"  {'时间(NEM)':<18} {'类型':<6} {'电价':>10} {'市场':>10} {'信号'}")
        print(f"  {'-'*60}")
        for d in feedin:
            dt = to_nem(d.get("startTime"))
            tp = "实际" if d.get("type") in ("ActualInterval","CurrentInterval") else "预测"
            per = d.get("perKwh", 0)
            spot = d.get("spotPerKwh", 0)
            desc = d.get("descriptor", "-")
            time_str = dt.strftime("%m-%d %H:%M") if dt else "-"
            print(f"  {time_str:<18} {tp:<6} {per:>10.2f} {spot:>10.2f} {desc}")

    # 摘要
    actual_g = [d for d in general if d.get("type") in ("ActualInterval", "CurrentInterval")]
    actual_f = [d for d in feedin if d.get("type") in ("ActualInterval", "CurrentInterval")]
    if actual_g:
        avg = sum(d.get("perKwh",0) for d in actual_g) / len(actual_g)
        print(f"\n  当前购电均价: {avg:.2f} c/kWh = AU${avg/100:.4f}/kWh")
    if actual_f:
        avg = sum(d.get("perKwh",0) for d in actual_f) / len(actual_f)
        sign = "+" if avg > 0 else ""
        print(f"  当前售电均价: {sign}{avg:.2f} c/kWh = AU${avg/100:.4f}/kWh")

# ============ 电价预测图表生成 ============

def _gen_forecast_chart(time_prices, hours):
    """生成电价预测折线图，返回图片路径。"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    sorted_keys = sorted(time_prices.keys())
    gen = [time_prices[k].get("general", 0) for k in sorted_keys]
    feed = [time_prices[k].get("feedIn", 0) for k in sorted_keys]

    chart_file = f"{OUTPUT_DIR}/amber_forecast_{hours}h.png"

    plt.figure(figsize=(12, 5.5))
    plt.plot(sorted_keys, gen, 'o-', color='#FF6B6B', linewidth=2.5, markersize=7,
             label='Buy Price (Gen)')
    plt.plot(sorted_keys, feed, 's-', color='#4ECDC4', linewidth=2.5, markersize=7,
             label='Sell Price (Feed-in)')

    # 标注最高最低购电点
    for i, (g, f) in enumerate(zip(gen, feed)):
        if g == max(gen):
            plt.annotate(f'{g:.1f}', (sorted_keys[i], g),
                         textcoords='offset points', xytext=(0, 8),
                         ha='center', fontsize=8, color='#FF6B6B', fontweight='bold')
        if g == min(gen):
            plt.annotate(f'{g:.1f}', (sorted_keys[i], g),
                         textcoords='offset points', xytext=(0, -12),
                         ha='center', fontsize=8, color='#FF6B6B', fontweight='bold')

    plt.axhline(y=0, color='gray', linewidth=1, linestyle='--')
    plt.xlabel('Time (NEM)', fontsize=11)
    plt.ylabel('Price (c/kWh)', fontsize=11)
    plt.title(f'Amber — Next {hours} Hours Price Forecast (Buy vs Sell)',
              fontsize=13, fontweight='bold', pad=12)
    plt.legend(fontsize=10)
    plt.grid(alpha=0.3, linestyle='--')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.savefig(chart_file, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\n  📊 图表已生成: {chart_file}")
    return chart_file


# ============ 电价预测命令 ============
def cmd_forecast(site_id, hours=4):
    n = hours * 2  # 30min intervals
    data = api_get(f"/sites/{site_id}/prices/current", {
        "previous": 2, "next": n, "resolution": 30
    })
    if not data:
        print("无预测数据")
        return

    forecast = [d for d in data if d.get("type") == "ForecastInterval"]
    now = nem_now()

    print(f"\n{'='*65}")
    print(f"  电价预测  {site_id}  (未来 {hours} 小时, NEM时间)")
    print(f"  查询时间: {now.strftime('%Y-%m-%d %H:%M')}  ({now.strftime('%A')})")
    print(f"{'='*65}")
    print(f"  {'时间(NEM)':<18} {'购电(c/kWh)':>14} {'售电(c/kWh)':>14} {'购电信号':<10} {'售电信号'}")
    print(f"  {'-'*65}")

    # 按时间聚合
    time_prices = {}
    for d in forecast:
        dt = to_nem(d.get("startTime"))
        if not dt:
            continue
        key = dt.strftime("%Y-%m-%d %H:%M")
        if key not in time_prices:
            time_prices[key] = {}
        ch = d.get("channelType")
        time_prices[key][ch] = d.get("perKwh", 0)

    signals = {0: "general", 1: "feedIn"}
    for key in sorted(time_prices)[:hours * 2]:
        vals = time_prices[key]
        gen = vals.get("general", 0)
        feed = vals.get("feedIn", 0)
        # 信号判断
        gen_sig = ""
        if gen > 30: gen_sig = "⚠️高价"
        elif gen > 20: gen_sig = "较高"
        elif gen < 10: gen_sig = "✅低价"
        feed_sig = "✅收益" if feed > 0 else "⚠️倒贴"
        print(f"  {key:<18} {gen:>14.2f} {feed:>14.2f} {gen_sig:<10} {feed_sig}")

    # 生成图表
    chart_path = _gen_forecast_chart(time_prices, hours)
    print(f"\n{'='*65}")
    print(f"  🖼️ CHART_PATH={chart_path}")

# ============ 用量图表生成 ============
OUTPUT_DIR = "/root/.openclaw/workspace/memory/chart/output"

def _gen_usage_chart(daily, start_str, end_str):
    """生成用量/收益图表，返回图片路径。"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    sorted_dates = sorted(daily.keys())
    labels = []
    net_cents, gen_cents, feed_cents = [], [], []
    for dk in sorted_dates:
        v = daily[dk]
        wd = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][
            datetime.strptime(dk, "%Y-%m-%d").weekday()]
        labels.append(f"{dk[5:]}\n{wd}")
        net_cents.append(v["gen_cost"] + v["feed_cost"])
        gen_cents.append(v["gen_cost"])
        feed_cents.append(v["feed_cost"])

    net_aud = [n / 100 for n in net_cents]
    gen_aud = [g / 100 for g in gen_cents]
    feed_aud = [f / 100 for f in feed_cents]

    chart_file = f"{OUTPUT_DIR}/amber_usage_{start_str}_{end_str}.png"

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))

    # 左图：每日净收益
    ax1 = axes[0]
    colors = ['#50C878' if n >= 0 else '#FF6B6B' for n in net_aud]
    bars = ax1.bar(labels, net_aud, color=colors, edgecolor='#2c3e50', linewidth=0.5, width=0.6)
    ax1.axhline(y=0, color='black', linewidth=0.8)
    for bar, val in zip(bars, net_aud):
        y_pos = val + 0.05 if val >= 0 else val - 0.15
        ax1.text(bar.get_x() + bar.get_width()/2, y_pos,
                  f'{val:+.2f}', ha='center', va='bottom' if val >= 0 else 'top',
                  fontsize=9, fontweight='bold', color='#333')
    ax1.set_ylabel('Net Earnings (AU$)', fontsize=11)
    ax1.set_title('Daily Net Earnings', fontsize=13, fontweight='bold', pad=10)
    ax1.set_ylim(min(net_aud) - 0.5 if net_aud else -3.5, max(net_aud) + 0.5 if net_aud else 0.5)
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    ax1.grid(axis='y', alpha=0.3, linestyle='--')
    total_net = sum(net_aud)
    ax1.text(0.98, 0.05, f'Total:\nAU${total_net:.2f}',
             transform=ax1.transAxes, ha='right', va='bottom',
             fontsize=11, fontweight='bold',
             bbox=dict(boxstyle='round,pad=0.5', facecolor='#2C3E50', alpha=0.85), color='white')

    # 右图：堆叠费用分解
    ax2 = axes[1]
    x = range(len(labels))
    width = 0.45
    ax2.bar(x, gen_aud, width, label='Gen Cost', color='#FF6B6B', alpha=0.85)
    ax2.bar(x, feed_aud, width, label='Feed-in Cost', color='#4ECDC4', alpha=0.85)
    ax2.axhline(y=0, color='black', linewidth=0.8)
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels)
    ax2.set_ylabel('Cost (AU$)', fontsize=11)
    ax2.set_title('Cost Breakdown', fontsize=13, fontweight='bold', pad=10)
    ax2.legend(loc='upper right', fontsize=9)
    ax2.spines['top'].set_visible(False)
    ax2.grid(axis='y', alpha=0.3, linestyle='--')
    total_gen = sum(gen_aud)
    total_feed = sum(feed_aud)
    ax2.text(0.98, 0.05,
             f'Total Gen: AU${total_gen:.2f}\nTotal Feed: AU${total_feed:.2f}',
             transform=ax2.transAxes, ha='right', va='bottom',
             fontsize=10, fontweight='bold',
             bbox=dict(boxstyle='round,pad=0.5', facecolor='#555', alpha=0.85), color='white')

    fig.suptitle(f'Amber — Usage & Earnings ({start_str} ~ {end_str})',
                 fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(chart_file, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\n  📊 图表已生成: {chart_file}")
    return chart_file


# ============ 用量查询命令（Python预处理） ============
def cmd_usage(site_id, start_date, end_date):
    """
    1. 解析自然语言日期
    2. 调用API（API格式: YYYY-MM-DD）
    3. Python预处理数据
    4. 打印分析结果
    """
    ref = nem_now()
    start_str, end_str = parse_natural_date(start_date, ref)
    if start_str is None and end_str is None:
        # 月份不支持
        print("非常抱歉，由于Amber的限制，目前暂不支持按月查询。")
        return

    if end_date:
        end_str2, _ = parse_natural_date(end_date, ref)
        if end_str2:
            end_str = end_str2

    print(f"\n  📊 用量查询: {start_str} → {end_str}  (NEM时间)")

    # 调用API
    raw = api_get(f"/sites/{site_id}/usage", {
        "startDate": start_str,
        "endDate": end_str
    })
    if not raw:
        print("  无数据")
        return

    # ============ Python预处理 ============
    # 5分钟一条数据，按 channelType 分类
    general = [d for d in raw if d.get("channelType") == "general"]
    feedin  = [d for d in raw if d.get("channelType") == "feedIn"]

    # 按天汇总
    daily = {}
    for rec in general + feedin:
        nem_dt = to_nem(rec.get("startTime"))
        if not nem_dt:
            continue
        date_key = nem_dt.strftime("%Y-%m-%d")
        ch = rec.get("channelType", "")

        if date_key not in daily:
            daily[date_key] = {
                "gen_kwh": 0.0, "gen_cost": 0.0,
                "feed_kwh": 0.0, "feed_cost": 0.0,
                "spike_count": 0, "high_count": 0, "low_count": 0
            }

        kwh = rec.get("kwh", 0) or 0.0
        cost = rec.get("cost", 0) or 0.0  # cost直接是cents

        if ch == "general":
            daily[date_key]["gen_kwh"] += kwh
            daily[date_key]["gen_cost"] += cost
        elif ch == "feedIn":
            daily[date_key]["feed_kwh"] += kwh
            daily[date_key]["feed_cost"] += cost

        # 统计信号
        desc = rec.get("descriptor", "")
        if desc == "high":
            daily[date_key]["high_count"] += 1
        elif desc in ("veryLow", "low"):
            daily[date_key]["low_count"] += 1

        if rec.get("spikeStatus") == "spike":
            daily[date_key]["spike_count"] += 1

    # 输出
    print(f"\n{'='*75}")
    print(f"  📊 用量详情  {site_id}  ({start_str} → {end_str})")
    print(f"{'='*75}")
    print(f"  {'日期':<12} {'购kWh':>10} {'购费(c)':>12} {'售kWh':>10} {'售收支(c)':>12} {'净(c)':>12} {'高峰':>6} {'低价':>6}")
    print(f"  {'-'*80}")

    # 逐日打印
    for date_key in sorted(daily.keys()):
        v = daily[date_key]
        net = v["gen_cost"] + v["feed_cost"]  # 总费用（feed负则抵销）
        from datetime import date as date_class
        d_obj = datetime.strptime(date_key, "%Y-%m-%d").date()
        wd = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][d_obj.weekday()]
        feed_label = f"{v['feed_cost']:+.2f}"  # 正=收益，负=被收费
        net_label = f"{net:+.2f}"
        print(f"  {date_key}({wd}) {v['gen_kwh']:>10.2f} {v['gen_cost']:>12.2f} "
              f"{v['feed_kwh']:>10.2f} {feed_label:>12} {net_label:>12} "
              f"{v['spike_count']:>6} {v['low_count']:>6}")

    print(f"  {'-'*80}")

    # feed_cost为负表示被收费（售电倒贴），为正表示售电赚钱
    # 分别统计：购电总费用、售电总收费（正负都有意义）
    totals_gen_cost = sum(v["gen_cost"] for v in daily.values())
    totals_feed_cost = sum(v["feed_cost"] for v in daily.values())  # 负数=被收费
    totals_gen_kwh = sum(v["gen_kwh"] for v in daily.values())
    totals_feed_kwh = sum(v["feed_kwh"] for v in daily.values())
    totals_spike = sum(v["spike_count"] for v in daily.values())
    totals_low = sum(v["low_count"] for v in daily.values())

    print(f"  {'合计':<12} {totals_gen_kwh:>10.2f} {totals_gen_cost:>12.2f} "
          f"{totals_feed_kwh:>10.2f} {totals_feed_cost:>12.2f}")
    print()
    print(f"  💰 费用汇总（单位：cents → ÷100 = AUD）")
    print(f"    购电费用:     {totals_gen_cost:>10.2f} c  = AU${totals_gen_cost/100:.2f}")
    if totals_feed_cost > 0:
        print(f"    售电收入:    {totals_feed_cost:>10.2f} c  = AU${totals_feed_cost/100:.2f}  ✅")
    elif totals_feed_cost < 0:
        print(f"    售电倒贴:    {totals_feed_cost:>10.2f} c  = AU${totals_feed_cost/100:.2f}  ⚠️")
    else:
        print(f"    售电收支:      0.00 c  = AU$0.00")
    net = totals_gen_cost + totals_feed_cost  # 总费用（feed_cost为负则减少费用）
    print(f"    {'─'*30}")
    print(f"    净费用:      {net:>10.2f} c  = AU${net/100:.2f}  ({'支出' if net>0 else '净收入'})")
    print()
    if totals_spike > 0:
        print(f"  ⚠️ 高峰(feed-in收费)时段次数: {totals_spike} 次")
    if totals_low > 0:
        print(f"  ✅ 低价(推荐充放电)时段次数: {totals_low} 次")

    # 自动生成图表
    chart_path = _gen_usage_chart(daily, start_str, end_str)
    print(f"\n{'='*65}")
    print(f"  🖼️ CHART_PATH={chart_path}")


# ============ 主入口 ============
def cmd_login(username=None, password=None):
    """使用用户名+密码认证，成功后保存凭证。"""
    # 如无参数，尝试加载已有凭证并测试
    if not username or not password:
        creds = _load_credentials()
        if creds.get("username") and creds.get("password"):
            username = creds["username"]
            password = creds["password"]
            print(f"当前已保存用户: {username}")
            print("正在验证...")
            ok, msg = test_auth()
            if ok:
                print(f"✅ 认证有效，站点数: {msg}，无需重新登录。")
                return
            else:
                print(f"❌ 当前凭证已失效: {msg}")
        print(AuthMissingError.USER_MSG)
        return

    # 保存并测试新凭证
    _save_credentials(username, password)
    print(f"正在验证 {username}...")
    ok, msg = test_auth()
    if ok:
        print(f"✅ 认证成功（站点数: {msg}），凭证已保存到 ~/.amber/credentials.json")
        print(f"\n🎉 配置完成！后续查询无需再输入用户名和密码。")
    else:
        print(f"❌ 认证失败: {msg}")
        print(f"请检查用户名和密码是否正确。")


def main():
    parser = argparse.ArgumentParser(
        description="Amber Electric 查询工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  amber.py login <用户名> <密码>      # 设置/测试认证（首次）
  amber.py login                       # 验证已有凭证
  amber.py list                         # 查看所有站点
  amber.py price <id>                  # 当前电价
  amber.py forecast <id> 4            # 未来4小时电价预测
  amber.py usage <id> 昨天             # 昨天用量
  amber.py usage <id> 上周             # 上周完整用电
  amber.py usage <id> 2026-03-01 2026-03-07  # 指定日期区间
  amber.py usage <id> 近30天          # 近30天用量
  amber.py report <id>                # 综合分析报告
        """
    )
    sub = parser.add_subparsers(dest="cmd")

    lp = sub.add_parser("login", help="设置/测试用户名+密码认证")
    lp.add_argument("username", nargs="?", help="Amber 用户名（邮箱）")
    lp.add_argument("password", nargs="?", help="Amber 密码")

    sub.add_parser("list", help="查看所有站点")
    sub.add_parser("price", help="当前电价").add_argument("site_id", nargs="?", help="Amber站点ID（可选）")

    fp = sub.add_parser("forecast", help="电价预测")
    fp.add_argument("site_id", nargs="?", help="Amber站点ID（可选）")
    fp.add_argument("hours", nargs="?", type=int, default=4, help="预测小时数")

    up = sub.add_parser("usage", help="用量查询")
    up.add_argument("site_id", nargs="?", help="Amber站点ID（可选）")
    up.add_argument("start", help="开始日期（支持自然语言：昨天/上周/近7天/YYYY-MM-DD）")
    up.add_argument("end", nargs="?", help="结束日期（可选）")

    sub.add_parser("report", help="综合分析报告").add_argument("site_id", nargs="?", help="Amber站点ID（可选）")

    def resolve_site_id(site_id_arg):
        """从参数或配置文件中获取 site_id。"""
        if site_id_arg:
            return site_id_arg
        saved = get_site_id_from_config()
        if saved:
            return saved
        raise AuthMissingError(
            "未指定站点ID，也未找到已保存的站点配置。\n\n"
            + AuthMissingError.USER_MSG
        )

    args = parser.parse_args()

    try:
        if args.cmd == "login":
            cmd_login(args.username, args.password)
        elif args.cmd == "list":
            cmd_list()
        elif args.cmd == "price":
            cmd_price(resolve_site_id(args.site_id))
        elif args.cmd == "forecast":
            cmd_forecast(resolve_site_id(args.site_id), args.hours)
        elif args.cmd == "usage":
            cmd_usage(resolve_site_id(args.site_id), args.start, args.end)
        elif args.cmd == "report":
            sid = resolve_site_id(args.site_id)
            cmd_price(sid)
            print()
            cmd_usage(sid, "昨天", None)
        else:
            parser.print_help()
    except AuthMissingError as e:
        print(AuthMissingError.USER_MSG)

if __name__ == "__main__":
    main()
