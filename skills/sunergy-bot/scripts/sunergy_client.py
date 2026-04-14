#!/usr/bin/env python3
"""
Sunergy API 客户端
支持完整的登录认证、站点管理、实时监控、图表查询能力
"""

import urllib.request
import urllib.error
import json
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

# ============ 配置 ============
TOKEN_FILE = Path(__file__).parent.parent / ".sunergy-bot" / "token"
BASE_URL = "http://web.nsw.aiminis.com/api"
TENANT_ID = "3"
TIMEZONE = "Asia/Shanghai"

# 默认 Token（硬编码，不再提示用户输入）
DEFAULT_TOKEN = "f7792b679a924991a6f6ec89fe887093"

# ============ Token 管理 ============
def load_token() -> str:
    if TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text().strip()
        if token:
            return token
    return DEFAULT_TOKEN


def save_token(token: str):
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(token)


# ============ HTTP 请求基础 ============
class SunergyClient:
    def __init__(self, token: Optional[str] = None):
        self.token = token or load_token()
        self._headers = {
            "Host": "web.nsw.aiminis.com",
            "User-Agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
            "Accept-Encoding": "gzip, deflate",
            "tenantId": TENANT_ID,
            "timeZone": TIMEZONE,
            "Connection": "keep-alive",
            "Referer": "http://web.nsw.aiminis.com/",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache"
        }

    def _auth_headers(self) -> Dict[str, str]:
        h = self._headers.copy()
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _get(self, path: str, query: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = BASE_URL + path
        if query:
            qs = "&".join(f"{k}={v}" for k, v in query.items())
            url = f"{url}?{qs}"
        req = urllib.request.Request(url, headers=self._auth_headers())
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return {"code": e.code, "success": False, "msg": str(e), "data": None}

    def _post(self, path: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = BASE_URL + path
        data = json.dumps(body or {}).encode("utf-8") if body else b""
        req = urllib.request.Request(url, data=data, headers=self._auth_headers(), method="POST")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return {"code": e.code, "success": False, "msg": str(e), "data": None}

    # ============ 认证接口 ============

    def login_phone(self, phone: str, password: str) -> Dict[str, Any]:
        """手机号密码登录"""
        h = self._headers.copy()
        h.pop("Authorization", None)
        client_token = load_token()
        if client_token:
            h["clientToken"] = client_token
        body = {"phone": phone, "password": password}
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(BASE_URL + "/auth/getToken/byPhonePassword", data=data, headers=h, method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        if result.get("success") and result.get("data", {}).get("access_token"):
            self.token = result["data"]["access_token"]
            save_token(self.token)
        return result

    def login_email(self, email: str, password: str) -> Dict[str, Any]:
        """邮箱密码登录"""
        h = self._headers.copy()
        h.pop("Authorization", None)
        client_token = load_token()
        if client_token:
            h["clientToken"] = client_token
        body = {"email": email, "password": password}
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(BASE_URL + "/auth/getToken/byEmailPassword", data=data, headers=h, method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        if result.get("success") and result.get("data", {}).get("access_token"):
            self.token = result["data"]["access_token"]
            save_token(self.token)
        return result

    def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """刷新令牌"""
        body = {"refreshToken": refresh_token}
        return self._post("/auth/refreshToken", body)

    # ============ 站点接口 ============

    def get_sites(self) -> Dict[str, Any]:
        """获取当前用户关联的Site实时数据列表"""
        return self._get("/app/sites/")

    def get_site_detail(self, site_id: str) -> Dict[str, Any]:
        """获取站点实时数据详情"""
        return self._get(f"/app/sites/{site_id}")

    def get_site_power_today(self, site_id: str) -> Dict[str, Any]:
        """获取站点今日功率数据（逆变器/光伏）"""
        return self._get(f"/app/sites/{site_id}/power/today")

    def get_site_bess_today(self, site_id: str) -> Dict[str, Any]:
        """获取站点今日Bess数据"""
        return self._get(f"/app/sites/{site_id}/bess/today")

    def get_site_solar_today(self, site_id: str) -> Dict[str, Any]:
        """获取站点今日光伏数据"""
        return self._get(f"/app/sites/{site_id}/solars/today")

    # ============ 图表接口 ============

    def get_power_day(self, site_id: str, timestamp: int) -> Dict[str, Any]:
        """
        获取站点功率日统计5分钟图表数据
        timestamp: 毫秒时间戳
        """
        return self._get(f"/app/sites/{site_id}/power/day", {"timestamp": timestamp})

    def get_charts_day(self, site_id: str, timestamp: int) -> Dict[str, Any]:
        """获取站点日统计图表数据"""
        return self._get(f"/app/sites/{site_id}/charts/day", {"timestamp": timestamp})

    def get_charts_month(self, site_id: str, timestamp: int) -> Dict[str, Any]:
        """获取站点月统计图表数据"""
        return self._get(f"/app/sites/{site_id}/charts/month", {"timestamp": timestamp})

    def get_charts_year(self, site_id: str, timestamp: int) -> Dict[str, Any]:
        """获取站点年统计图表数据"""
        return self._get(f"/app/sites/{site_id}/charts/year", {"timestamp": timestamp})

    # ============ 收益/电量接口 ============

    def get_earnings_week(self, site_id: str, timestamp: int) -> Dict[str, Any]:
        """获取站点收益周统计日图表数据"""
        return self._get(f"/app/sites/{site_id}/earnings/week", {"timestamp": timestamp})

    def get_earnings_year(self, site_id: str, timestamp: int) -> Dict[str, Any]:
        """获取站点收益年统计月图表数据"""
        return self._get(f"/app/sites/{site_id}/earnings/year", {"timestamp": timestamp})

    def get_energy_week(self, site_id: str, timestamp: int) -> Dict[str, Any]:
        """获取站点电量周统计日图表数据"""
        return self._get(f"/app/sites/{site_id}/energy/week", {"timestamp": timestamp})


# ============ 工具函数 ============

def ts_of_date(date_str: str) -> int:
    """日期字符串 -> 毫秒时间戳（Asia/Shanghai 00:00:00）"""
    tz = timezone(timedelta(hours=8))
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=tz)
    return int(dt.timestamp() * 1000)


def ts_of_month(year_month: str) -> int:
    """年月字符串 -> 毫秒时间戳（该月1日 00:00:00）"""
    tz = timezone(timedelta(hours=8))
    dt = datetime.strptime(year_month + "-01", "%Y-%m-%d").replace(tzinfo=tz)
    return int(dt.timestamp() * 1000)


def ts_of_year(year: str) -> int:
    """年字符串 -> 毫秒时间戳（该年1月1日 00:00:00）"""
    tz = timezone(timedelta(hours=8))
    dt = datetime.strptime(year + "-01-01", "%Y-%m-%d").replace(tzinfo=tz)
    return int(dt.timestamp() * 1000)


def now_ts() -> int:
    return int(datetime.now(timezone(timedelta(hours=8))).timestamp() * 1000)


def parse_series(data: Dict[str, Any]) -> Dict[str, List]:
    """将 series 数组转为 dict {code: [values]}"""
    if not data or "data" not in data or "series" not in data.get("data", {}):
        return {}
    result = {}
    for s in data["data"]["series"]:
        result[s["code"]] = s.get("value", [])
    return result


# ============ 主函数 ============

if __name__ == "__main__":
    client = SunergyClient()
    
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "sites"
    
    if cmd == "sites":
        print("=== 站点列表 ===")
        result = client.get_sites()
        if result.get("success"):
            for site in result.get("data", []):
                print(f"  [{site['id']}] {site['name']}  "
                      f"SOC={site.get('totalSoc')}%  "
                      f"BESS={site.get('bessTotalPower')}kW  "
                      f"Solar={site.get('solarTotalPower')}kW")
        else:
            print(f"失败: {result}")
    
    elif cmd == "detail" and len(sys.argv) > 2:
        site_id = sys.argv[2]
        print(f"=== 站点详情 {site_id} ===")
        result = client.get_site_detail(site_id)
        if result.get("success"):
            d = result["data"]
            print(f"  名称: {d.get('name')}")
            print(f"  总功率: {d.get('totalPower')}kW")
            print(f"  负载: {d.get('consumption')}kW")
            print(f"  光伏: {d.get('solarTotalPower')}kW")
            print(f"  储能: {d.get('bessTotalPower')}kW")
            print(f"  SOC: {d.get('totalSoc')}%")
            print(f"  今日收益: {d.get('todayRevenue')}")
            print(f"  更新时间: {datetime.fromtimestamp(d.get('lastUpdateTime', 0)/1000, tz=timezone(timedelta(hours=8)))}")
        else:
            print(f"失败: {result}")
    
    elif cmd == "bess" and len(sys.argv) > 2:
        site_id = sys.argv[2]
        print(f"=== 今日BESS {site_id} ===")
        result = client.get_site_bess_today(site_id)
        if result.get("success"):
            d = result["data"]
            status_map = {0: "离线", 1: "待机", 2: "放电", 3: "充电", 4: "故障"}
            print(f"  SOC: {d.get('soc')}%")
            print(f"  当前功率: {d.get('currentPower')}kW")
            print(f"  今日充电量: {d.get('chg')}Wh")
            print(f"  今日放电量: {d.get('dischg')}Wh")
            print(f"  额定容量: {d.get('ratedCapacity')}kWh")
            print(f"  状态: {status_map.get(d.get('status'), '未知')}")
        else:
            print(f"失败: {result}")
    
    elif cmd == "solar" and len(sys.argv) > 2:
        site_id = sys.argv[2]
        print(f"=== 今日光伏 {site_id} ===")
        result = client.get_site_solar_today(site_id)
        if result.get("success"):
            d = result["data"]
            print(f"  当前功率: {d.get('currentPower')}kW")
            print(f"  今日发电量: {d.get('powerGeneration')}Wh")
            print(f"  额定功率: {d.get('ratedPower')}kW")
        else:
            print(f"失败: {result}")
    
    elif cmd == "power_day" and len(sys.argv) > 3:
        site_id = sys.argv[2]
        date_str = sys.argv[3]
        ts = ts_of_date(date_str)
        print(f"=== 日功率曲线 {site_id} @ {date_str} ===")
        result = client.get_power_day(site_id, ts)
        if result.get("success"):
            import pprint
            pprint.pprint(result["data"])
        else:
            print(f"失败: {result}")
    
    elif cmd == "charts_month" and len(sys.argv) > 3:
        site_id = sys.argv[2]
        ym = sys.argv[3]
        ts = ts_of_month(ym)
        print(f"=== 月统计 {site_id} @ {ym} ===")
        result = client.get_charts_month(site_id, ts)
        if result.get("success"):
            import pprint
            pprint.pprint(result["data"])
        else:
            print(f"失败: {result}")
    
    elif cmd == "earnings_week" and len(sys.argv) > 3:
        site_id = sys.argv[2]
        date_str = sys.argv[3]
        ts = ts_of_date(date_str)
        print(f"=== 收益周报 {site_id} @ {date_str} ===")
        result = client.get_earnings_week(site_id, ts)
        if result.get("success"):
            import pprint
            pprint.pprint(result["data"])
        else:
            print(f"失败: {result}")
    
    else:
        print("用法:")
        print("  python3 sunergy_client.py sites")
        print("  python3 sunergy_client.py detail <site_id>")
        print("  python3 sunergy_client.py bess <site_id>")
        print("  python3 sunergy_client.py solar <site_id>")
        print("  python3 sunergy_client.py power_day <site_id> <YYYY-MM-DD>")
        print("  python3 sunergy_client.py charts_month <site_id> <YYYY-MM>")
        print("  python3 sunergy_client.py earnings_week <site_id> <YYYY-MM-DD>")
