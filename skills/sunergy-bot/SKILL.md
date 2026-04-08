---
name: sunergy-bot
description: Sunergy (mx-sky) 能源管理系统 API 查询与图表生成技能。当用户需要查询电站功率数据、BESS状态、发电量等，并生成可视化图表时使用。支持直接调用 API 生成折线图、柱状图等。触发场景：查询功率、查看图表、生成功率曲线、BESS 状态分析。
---

# SunergyBot 技能

## 概述

直接调用 Sunergy API 查询电站数据并生成可视化图表。

## API 配置

- **Base URL**: `http://web.aws.aiminis.com/api`
- **Token**: `~/.mx-sky/token` 文件中读取，或使用内置 token
- **TenantId**: `3`

## 核心接口

### 日功率图表数据

```
GET /mobile/chart/site/{siteId}/power/day
```

**参数**:
- `siteId`: 站点ID
- `start`: 开始时间戳（毫秒）
- `end`: 结束时间戳（毫秒）
- `timeSpan`: 时间粒度（默认5分钟）

**返回字段**:
- `totalPower`: 总有功功率 (kW)
- `consumption`: 消耗电量 (kWh)
- `totalBessPower`: 储能功率 (kW)
- `totalBessSoc`: 储能SOC (%)

## 使用方法

### 方式1：使用脚本查询并生成图表

```bash
python3 ~/.openclaw/workspace/skills/sunergy-query/scripts/query_and_chart.py \
  <site_id> <start_timestamp> <end_timestamp>
```

示例（查询2026-04-08数据）:
```bash
python3 ~/.openclaw/workspace/skills/sunergy-query/scripts/query_and_chart.py \
  1872845402077761538 1775577600280 1775663999999
```

### 方式2：在代码中调用

参考 `scripts/query_and_chart.py` 的实现逻辑：

1. 构建请求（带 Bearer Token）
2. 解析 JSON 响应
3. 使用 matplotlib 生成图表

## 输出规范

图表输出到 `/tmp/` 目录：
- `power_day_chart.png`: 分项图表（4个子图）
- `power_combined_chart.png`: 综合对比图

