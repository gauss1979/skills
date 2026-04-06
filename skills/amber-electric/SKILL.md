---
name: amber-electric
description: Amber Electric 澳大利亚能源零售商 API — 查询实时电价、电价预测、账单用量。支持 NEM（National Electricity Market）各州电价查询，结合 mx-sky 站点数据可计算最优充放电策略。触发场景：查电价、查电价预测、查账单、查用电量、分析售电收益。
---

# Amber Electric 技能

## 概述

Amber Electric 是澳大利亚能源零售商，提供实时电价数据（5/30分钟粒度）。结合 mx-sky 站点数据可分析收益、优化 BESS 调度策略。

## 服务配置

- **Base URL**: `https://api.amber.com.au/v1`
- **认证**: Bearer Token（必填，存储在 `~/.amber/token` 文件中）
- **Headers**: `Authorization: Bearer <token>`

## Token 配置

```bash
mkdir -p ~/.amber
echo "你的AmberBearerToken" > ~/.amber/token
chmod 600 ~/.amber/token
```

## 核心接口

### 1. 站点查询

```
GET /sites
```
返回用户所有站点信息：amber_site_id、NMI、channels（E1=购电通道、B1=售电通道）、供电公司、状态。

### 2. 电价预测

```
GET /sites/{amber_site_id}/prices/current
```
**Query 参数**：
| 参数 | 类型 | 说明 |
|------|------|------|
| `previous` | int | 查询过去30分钟价格数量 |
| `next` | int | 查询未来预测价格数量 |
| `resolution` | int | 5 或 30（5分钟/30分钟粒度） |

**返回字段**：
| 字段 | 说明 |
|------|------|
| `type` | ActualInterval=实际 / ForecastInterval=预测 |
| `perKwh` | 电价（cents/kWh） |
| `spotPerKwh` | 批发市场价（cents/kWh） |
| `channelType` | general=购电 / feedIn=售电 |
| `tariffInformation.period` | offPeak/offPeak/offPeak2/peak |
| `descriptor` | veryLow/low/high/veryHigh（价格信号） |

### 3. 用量/账单查询

```
GET /sites/{amber_site_id}/usage
```
**Query 参数**：
| 参数 | 说明 |
|------|------|
| `startDate` | 开始日期（ISO 8601: `2026-03-06T00:00:01Z`） |
| `endDate` | 结束日期（不超过7天） |

**返回字段**：
| 字段 | 说明 |
|------|------|
| `type` | ActualInterval=实际 / ForecastInterval=预测 |
| `duration` | 区间时长（分钟） |
| `perKwh` | 电价（cents/kWh） |
| `channelType` | general=购电 / feedIn=售电 |
| `spikeStatus` | none/spike（电网峰值） |

## 数据单位说明

- 电价 `perKwh`：**cents/kWh**（澳分/度）
- 时间：NEM 时间（UTC+10:00，AEST，无夏令时）
- 时区：AEST / AEDT（自动处理）

## 常用命令

| 场景 | 命令 |
|------|------|
| 查看所有站点 | `python3 scripts/amber.py list` |
| 查看当前电价 | `python3 scripts/amber.py price <site_id>` |
| 查看未来电价预测 | `python3 scripts/amber.py forecast <site_id> [hours]` |
| 查看用量账单 | `python3 scripts/amber.py usage <site_id> <start_date> <end_date>` |
| 电价分析报告 | `python3 scripts/amber.py report <site_id>` |

## 示例查询

```bash
# 查看站点
curl -s "https://api.amber.com.au/v1/sites" \
  -H "Authorization: Bearer $(cat ~/.amber/token)"

# 当前电价（购电+售电）
curl -s "https://api.amber.com.au/v1/sites/{id}/prices/current?previous=6&next=12&resolution=30" \
  -H "Authorization: Bearer $(cat ~/.amber/token)"

# 近7天用量
curl -s "https://api.amber.com.au/v1/sites/{id}/usage?startDate=2026-03-30T00:00:01Z&endDate=2026-04-06T00:00:01Z" \
  -H "Authorization: Bearer $(cat ~/.amber/token)"
```

## 注意事项

- Token 向 Amber API 获取，官网：https://www.amber.com.au/developers
- 电价为 cents/kWh，不是 AUD/kWh（需 ÷100 转 AUD）
- 售电（feedIn）和购电（general）价格分开
- 预测价格仅供参考，实际以 ActualInterval 为准
