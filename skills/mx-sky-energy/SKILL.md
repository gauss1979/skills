---
name: sunergy-energy
description: sunergy.com 能源管理系统 — 站点管理 + 实时监控 + 收益分析 + 功率图表 + BESS状态 + 图表可视化。基于 OpenAPI 3.0，支持站点列表/实时数据/收益统计/功率图表/BESS状态，支持生成折线图/柱状图/饼图。触发场景：查询站点、查看电站、查看收益、查看功率、查看 BESS、分析收益、生成图表。
---

# Sunergy 能源管理技能

## 概述

结合 Sunergy OpenAPI 与 chart 技能，提供完整的能源管理能力：
- 📊 **站点管理**：列表查询、实时状态
- 💰 **收益分析**：日/周/月/年收益统计
- ⚡ **功率监控**：日/月/年功率图表数据
- 🔋 **BESS 状态**：电池充放电数据
- 📈 **图表生成**：自动生成可视化图表（折线/柱状/饼图）

## 服务配置

- **Base URL**: `http://web.aws.aiminis.com/api`
- **认证**: 手机号 + 密码 登录（凭证保存在 `~/.sunergy/credentials`，不写入记忆）
- **Headers**:
  - `tenantId: 3`（可选）
  - `timeZone: Australia/Sydney`（可选）

## 凭证配置

首次使用需配置手机号和密码：
```bash
mkdir -p ~/.sunergy
echo "phone=你的手机号" > ~/.sunergy/credentials
echo "password=你的密码" >> ~/.sunergy/credentials
chmod 600 ~/.sunergy/credentials

# 示例
mkdir -p ~/.sunergy
echo "phone=13301313667" > ~/.sunergy/credentials
echo "password=231456" >> ~/.sunergy/credentials
```

**注意**：凭证文件仅存储在本地，不写入记忆。

## 登录认证流程

1. 登录接口：`POST /auth/getToken/byPhonePassword`
   - 请求体：`{"phone":"手机号","password":"密码","type":false,"tenantId":"3","isNew":0}`
   - 响应：返回 `access_token`（Bearer Token，有效期7天）
2. 后续请求 Header：`Authorization: Bearer <access_token>`
3. Token 有效期：本地缓存，重复使用

## 核心功能模块

### 1. 站点管理 (sites)

**查询站点列表**
```bash
python3 scripts/mx_sky.py list
```

**响应字段**: id, name, solarTotalPower, totalSoc, bessTotalPower, province, city, timeZone, lastUpdateTime

---

### 2. 实时数据 (realtime)

**查询站点实时详情**
```bash
python3 scripts/mx_sky.py realtime <site_id>
```

**响应字段**: id, name, solarTotalPower, totalSoc, bessTotalPower, totalPower, consumption, todayRevenue, province, city, locale

---

### 3. 收益查询 (earnings)

| 场景 | 命令 |
|------|------|
| 查看周收益 | `python3 scripts/mx_sky.py earnings-week <site_id>` |
| 查看年收益 | `python3 scripts/mx_sky.py earnings-year <site_id>` |
| 查看今日BESS | `python3 scripts/mx_sky.py bess <site_id>` |
| 查看近N天发电量 | `python3 scripts/mx_sky.py solar <site_id> [days]` |
| 查看日功率图表 | `python3 scripts/mx_sky.py power-day <site_id> [date]` |
| 查看月统计图表 | `python3 scripts/mx_sky.py chart-month <site_id> [year-month]` |
| 生成站点分析报告 | `python3 scripts/mx_sky.py report <site_id>` |

---

## 图表生成

使用 `chart` 技能生成可视化图表：
- `line` — 收益趋势、功率趋势
- `bar` — 日/周收益对比、充放电量对比
- `pie` — 收益结构占比

图表输出目录：`~/.openclaw/workspace/memory/chart/output/`

---

## 输出格式

所有查询返回统一格式：
```
[站点名称] [城市]
⚡ 光伏功率: X kW | 🔋 电池SOC: X% | 📊 电池功率: X kW
💰 今日收益: $X.XX | 📈 今日发电: X kWh
最后更新: YYYY-MM-DD HH:mm
```

---

## 附录：API 参考手册

### 通用响应格式

```json
{
  "code": 200,
  "success": true,
  "msg": "success.",
  "data": { ... }
}
```

### 登录接口
```
POST /auth/getToken/byPhonePassword
Content-Type: application/json
Authorization: Basic c3VuOk5jdlJmL2EyZFBPTjU3Nm9HZkMvUXc9PQ==
Origin: http://web.aws.aiminis.com

{"phone":"手机号","password":"密码","type":false,"tenantId":"3","isNew":0}

响应:
{"code":200,"success":true,"data":{"access_token":"...","expires_in":604800,...}}
```

### 错误码

| code | 说明 |
|------|------|
| 200 | 成功 |
| 401 | 未授权（用户名/密码错误或 token 过期）|
| 403 | 禁止访问 |
| 404 | 资源不存在 |

### 接口详情

#### A. 获取站点列表
```
GET /app/sites/
```

#### B. 获取站点实时详情
```
GET /app/sites/{id}
```

#### C. 获取站点日统计图表（5分钟粒度）
```
GET /app/sites/{id}/power/day?timestamp=<ms>
```

#### D. 获取站点月统计图表
```
GET /app/sites/{id}/charts/month?timestamp=<ms>
```

#### E. 获取站点收益周统计
```
GET /app/sites/{id}/earnings/week?timestamp=<ms>
```

#### F. 获取站点收益年统计
```
GET /app/sites/{id}/earnings/year?timestamp=<ms>
```

#### G. 站点今日 BESS 数据
```
GET /app/sites/{id}/bess/today
```

#### H. 站点今日光伏数据
```
GET /app/sites/{id}/solars/today
```
