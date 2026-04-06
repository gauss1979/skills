---
name: mx-sky-energy
description: mx-sky.com 能源管理系统 — 站点状态查询 + 收益分析 + 图表可视化。基于 OpenAPI 3.0，支持站点列表/实时数据/收益统计/功率图表/BESS状态，支持生成折线图/柱状图/饼图。触发场景：查询站点、查看电站、查看收益、查看功率、查看 BESS、分析收益、生成图表。
---

# mx-sky 能源管理技能

## 概述

结合 mx-sky OpenAPI 与 chart 技能，提供完整的能源管理能力：
- 📊 **站点管理**：列表查询、实时状态
- 💰 **收益分析**：日/周/月/年收益统计
- ⚡ **功率监控**：日/月/年功率图表数据
- 🔋 **BESS 状态**：电池充放电数据
- 📈 **图表生成**：自动生成可视化图表（折线/柱状/饼图）

## 服务配置

- **Base URL**: `http://web.aws.aiminis.com/api`
- **认证**: Bearer Token（必填，存储在 `~/.mx-sky/token` 文件中，或环境变量 `MX_SKY_TOKEN`）
- **Headers**:
  - `Authorization: Bearer <token>`（必填）
  - `tenantId: 3`（可选）
  - `timeZone: Australia/Sydney`（可选）

## Token 配置

Token 保存在 `~/.mx-sky/token` 文件中，首次使用需配置：
```bash
mkdir -p ~/.mx-sky
echo "你的BearerToken" > ~/.mx-sky/token
chmod 600 ~/.mx-sky/token
```

## 核心功能模块

### 1. 站点管理 (sites)

**查询站点列表**
```bash
# 直接 curl
curl -s "http://web.aws.aiminis.com/api/app/sites/" \
  -H "Authorization: Bearer $(cat ~/.mx-sky/token)" \
  -H "tenantId: 3"
```

**响应字段**: id, name, solarTotalPower, totalSoc, bessTotalPower, province, city, timeZone, lastUpdateTime

---

### 2. 实时数据 (realtime)

**查询站点实时详情**
```bash
curl -s "http://web.aws.aiminis.com/api/app/sites/{site_id}" \
  -H "Authorization: Bearer $(cat ~/.mx-sky/token)" \
  -H "timeZone: Australia/Sydney"
```

**响应字段**: id, name, solarTotalPower, totalSoc, bessTotalPower, totalPower, consumption, todayRevenue, province, city, locale

---

### 3. 收益查询 (earnings)

**日收益** — 站点今日BESS数据
```bash
curl -s "http://web.aws.aiminis.com/api/app/sites/{site_id}/bess/today" \
  -H "Authorization: Bearer $(cat ~/.mx-sky/token)"
```

**周收益**
```bash
TS=$(date -d "$(date +%Y-%m-%d) 00:00:00 UTC" +%s)000
curl -s "http://web.aws.aiminis.com/api/app/sites/{site_id}/earnings/week?timestamp=$TS" \
  -H "Authorization: Bearer $(cat ~/.mx-sky/token)" \
  -H "timeZone: Australia/Sydney"
```

**月收益**
```bash
TS=$(date -d "$(date +%Y-%m-01) 00:00:00 UTC" +%s)000
curl -s "http://web.aws.aiminis.com/api/app/sites/{site_id}/earnings/year?timestamp=$TS" \
  -H "Authorization: Bearer $(cat ~/.mx-sky/token)" \
  -H "timeZone: Australia/Sydney"
```

---

### 4. 功率图表 (power)

**日功率（5分钟粒度）**
```bash
TS=$(date -d "$(date +%Y-%m-%d) 00:00:00 UTC" +%s)000
curl -s "http://web.aws.aiminis.com/api/app/sites/{site_id}/power/day?timestamp=$TS" \
  -H "Authorization: Bearer $(cat ~/.mx-sky/token)" \
  -H "timeZone: Australia/Sydney"
```

**月统计图表**
```bash
TS=$(date -d "$(date +%Y-%m-01) 00:00:00 UTC" +%s)000
curl -s "http://web.aws.aiminis.com/api/app/sites/{site_id}/charts/month?timestamp=$TS" \
  -H "Authorization: Bearer $(cat ~/.mx-sky/token)" \
  -H "timeZone: Australia/Sydney"
```

---

### 5. 图表生成 (chart)

使用 `chart` 技能生成可视化图表，支持：
- `line` — 收益趋势、功率趋势
- `bar` — 日/周收益对比、充放电量对比
- `pie` — 收益结构占比

**生成图表工作流**：
1. 从 API 获取数据
2. 调用 `scripts/gen_energy_chart.py` 生成图表
3. 返回图表图片给用户

---

## 常用查询命令

| 场景 | 命令 |
|------|------|
| 查看所有站点 | `python3 scripts/mx_sky.py list` |
| 查看站点实时数据 | `python3 scripts/mx_sky.py realtime <site_id>` |
| 查看今日BESS | `python3 scripts/mx_sky.py bess <site_id>` |
| 查看日功率图表 | `python3 scripts/mx_sky.py power-day <site_id> [date]` |
| 查看月统计图表 | `python3 scripts/mx_sky.py chart-month <site_id> [year-month]` |
| 查看周收益 | `python3 scripts/mx_sky.py earnings-week <site_id>` |
| 查看年收益 | `python3 scripts/mx_sky.py earnings-year <site_id>` |
| 生成站点分析报告 | `python3 scripts/mx_sky.py report <site_id>` |

## 输出格式

所有查询返回统一格式：
```
[站点名称] [城市]
⚡ 光伏功率: X kW | 🔋 电池SOC: X% | 📊 电池功率: X kW
💰 今日收益: $X.XX | 📈 今日发电: X kWh
最后更新: YYYY-MM-DD HH:mm
```

## 注意事项

- 所有 timestamp 为毫秒级 Unix 时间戳
- BESS 功率负值 = 放电，正值 = 充电
- timeZone 默认 Australia/Sydney
- Token 过期后需重新配置 `~/.mx-sky/token`
