---
name: sunergy-bot
description: Sunergy (mx-sky) 能源管理系统 API 查询与图表生成技能。当用户需要查询电站功率数据、BESS状态、发电量、收益统计等，并生成可视化图表时使用。支持直接调用 API 生成折线图、柱状图等。触发场景：查询功率、查看图表、生成功率曲线、BESS 状态分析、收益查询、站点列表。
---

# SunergyBot 技能

基于 Sunergy OpenAPI 文档全面重构，支持完整的登录认证、站点管理、实时监控、图表查询和收益分析能力。

---

## 一、API 配置

| 配置项 | 值 |
|--------|----|
| **Base URL** | `http://web.nsw.aiminis.com/api` |
| **TenantId** | `3` |
| **时区** | `Asia/Shanghai` |
| **Token 文件** | `{agentPath}/.sunergy-bot/token` |

---

## 二、能力地图

### 2.1 认证模块
| 功能 | 接口 | 说明 |
|------|------|------|
| 手机号登录 | `POST /auth/getToken/byPhonePassword` | phone + password |
| 邮箱登录 | `POST /auth/getToken/byEmailPassword` | email + password |
| 刷新令牌 | `POST /auth/refreshToken` | refreshToken |

### 2.2 站点模块
| 功能 | 接口 | 说明 |
|------|------|------|
| 站点列表（实时） | `GET /app/sites/` | 返回所有关联站点的实时数据概览 |
| 站点详情（实时） | `GET /app/sites/{id}` | 单个站点实时数据详情 |
| 站点实时功率 | `GET /app/sites/{id}/power/today` | 今日逆变器/功率数据 |
| 今日BESS数据 | `GET /app/sites/{id}/bess/today` | SOC、充放电量、当前功率 |
| 今日光伏数据 | `GET /app/sites/{id}/solars/today` | 发电量、实时功率、额定功率 |

### 2.3 图表模块
| 功能 | 接口 | 说明 |
|------|------|------|
| 日功率曲线（5分钟粒度） | `GET /app/sites/{id}/power/day` | timestamp=当日0点 |
| 日统计图表 | `GET /app/sites/{id}/charts/day` | timestamp=当月某日 |
| 月统计图表 | `GET /app/sites/{id}/charts/month` | timestamp=当年某月 |
| 年统计图表 | `GET /app/sites/{id}/charts/year` | timestamp=某年 |

### 2.4 收益/电量模块
| 功能 | 接口 | 说明 |
|------|------|------|
| 收益周统计 | `GET /app/sites/{id}/earnings/week` | 按日分段 |
| 收益年统计 | `GET /app/sites/{id}/earnings/year` | 按月分段 |
| 电量周统计 | `GET /app/sites/{id}/energy/week` | 按日分段 |

---

## 三、响应数据结构

### 统一响应格式
```json
{
  "code": 200,
  "success": true,
  "msg": "success.",
  "data": { ... }
}
```

### 站点列表 `GET /app/sites/`
```json
{
  "id": "1872845402077761538",
  "name": "James",
  "solarTotalPower": 0.0,
  "totalSoc": 42,
  "bessTotalPower": -99,
  "province": "NSW",
  "city": "Sydney",
  "timeZone": 11,
  "lastUpdateTime": 1751527937633
}
```

### 站点实时详情 `GET /app/sites/{id}`
```json
{
  "id": "1872845402077761538",
  "name": "James",
  "solarTotalPower": 0,
  "totalSoc": 40,
  "bessTotalPower": -99,
  "totalPower": -193,
  "consumption": -94,
  "todayRevenue": 0,
  "lastUpdateTime": 1751528058191
}
```

### 图表数据 series code 说明
| code | 含义 |
|------|------|
| `solarChg` | 光伏充电量（Wh） |
| `bessChg` | 储能充电量（Wh） |
| `bessDischg` | 储能放电量（Wh） |
| `gridPower` | 电网功率（kW） |
| `solarTotalPower` | 光伏功率（kW） |
| `consumption` | 负载消耗（kW） |
| `bessTotalPower` | 储能功率（kW） |
| `bessTotalSoc` | 储能SOC（%） |
| `earnings` | 收益金额 |

---

## 四、Python API 客户端

见 `scripts/sunergy_client.py`，支持：
- `login_phone(phone, password)` / `login_email(email, password)`
- `refresh_token(refresh_token)`
- `get_sites()` → 站点列表
- `get_site_detail(site_id)` → 站点实时详情
- `get_site_power_today(site_id)` → 今日功率
- `get_site_bess_today(site_id)` → 今日BESS
- `get_site_solar_today(site_id)` → 今日光伏
- `get_power_day(site_id, timestamp)` → 日功率5分钟曲线
- `get_charts_day(site_id, timestamp)` → 日统计
- `get_charts_month(site_id, timestamp)` → 月统计
- `get_charts_year(site_id, timestamp)` → 年统计
- `get_earnings_week(site_id, timestamp)` → 收益周报
- `get_earnings_year(site_id, timestamp)` → 收益年报
- `get_energy_week(site_id, timestamp)` → 电量周报

---

## 五、图表生成

### 5.1 核心脚本

| 脚本 | 功能 |
|------|------|
| `sunergy_client.py` | API客户端（认证+所有查询接口） |
| `chart_power.py` | 日功率曲线（5分钟粒度） |
| `chart_bess.py` | BESS状态分析（SOC+充放电） |
| `chart_month.py` | 月统计柱状图（光伏/储能充放电） |
| `chart_year.py` | 年统计柱状图 |
| `chart_earnings.py` | 收益走势图（周/月） |
| `chart_comparison.py` | 综合对比图（功率+SOC叠加） |

### 5.2 图表类型

- **日功率曲线**：横轴时间（HH:MM），纵轴 kW，多线叠加（电网/光伏/负载/储能）
- **SOC曲线**：横轴时间，纵轴 %，带充放电着色
- **月/年柱状图**：光伏充电、储能充放电三组柱状图
- **收益折线图**：按日或按月展示收益金额
- **综合对比图**：双Y轴（功率+SOC）

### 5.3 输出目录
图表统一输出到 `/tmp/sunergy_charts/`，文件名格式：
```
{site_id}_{chart_type}_{date}.png
```

### 5.4 图表回复规范（重要）

**图表必须作为独立图片消息发送，不嵌入 Markdown。**

所有图表生成后，回复分两条：
1. **文字回复**：发送纯文字数据摘要，不含图片
2. **图片消息**：通过 `message(channel=feishu, filePath="/tmp/sunergy_charts/xxx.png", message="图表说明")` 发送图片，作为独立消息

这样兼容不支持 Markdown 内嵌图片的终端。

**示例回复格式：**
```
James 电站 2026-04-28 日功率曲线：
  峰值功率：12.5 kW（光伏）
  充电量：45.3 kWh
  SOC范围：38% → 82%
  收益：$8.23
```
（图片消息单独发送，filePath 指向对应 PNG）

---

## 六、调用示例

### 6.1 查询站点列表
```bash
python3 ~/.openclaw/workspace/skills/sunergy-bot/scripts/query_sites.py
```

### 6.2 查询单站实时数据
```bash
python3 ~/.openclaw/workspace/skills/sunergy-bot/scripts/query_site_detail.py <site_id>
```

### 6.3 生成日功率图表（指定日期）
```bash
python3 ~/.openclaw/workspace/skills/sunergy-bot/scripts/chart_power.py \
  <site_id> <date_str>
# 示例: python3 chart_power.py 1872845402077761538 2026-04-08
```

### 6.4 生成月统计图表
```bash
python3 ~/.openclaw/workspace/skills/sunergy-bot/scripts/chart_month.py \
  <site_id> <year-month>
# 示例: python3 chart_month.py 1872845402077761538 2026-04
```

### 6.5 生成收益图表
```bash
python3 ~/.openclaw/workspace/skills/sunergy-bot/scripts/chart_earnings.py \
  <site_id> week  # 或 year
```

### 6.6 全站概览报告
```bash
python3 ~/.openclaw/workspace/skills/sunergy-bot/scripts/report_all.py
```

---

## 七、功率字段正负含义

| 字段 | 正值（>0） | 负值（<0） |
|------|-----------|------------|
| `totalPower` | 电网向用户供电 | 用户向电网送电 |
| `bessTotalPower` | 储能放电 | 储能充电 |
| `solarTotalPower` | 光伏发电中 | 无光伏/夜间 |
| `consumption` | 负载消耗 | — |

---

## 八、常见问题

**Q: token 过期怎么办？**
→ 使用 `sunergy_client.py` 的 `refresh_token()` 方法，或重新登录获取新 token。

**Q: 返回 401怎么处理？**
→ token 失效，需重新登录认证。

**Q: 图表乱码怎么办？**
→ matplotlib 已设置中文字体支持（DejaVu Sans → SimHei 备选）。
