---
name: amber-electric
description: Amber Electric 澳大利亚能源零售商 API — 查询实时电价、电价预测、账单用量。支持 NEM（National Electricity Market）各州电价查询，结合 mx-sky 站点数据可计算最优充放电策略。触发场景：查电价、查电价预测、查账单、查用电量，分析售电收益。
---

# Amber Electric 技能

## 概述

Amber Electric 是澳大利亚能源零售商，提供实时电价数据（5/30分钟粒度）。结合 mx-sky 站点数据可分析收益、优化 BESS 调度策略。

## 服务配置

所有认证信息和站点配置统一存储在 `~/.amber/` 目录下：

| 文件 | 内容 |
|------|------|
| `~/.amber/token` | Bearer Token |
| `~/.amber/config.json` | 站点配置（站点ID、NMI、电网等） |

## Token 配置

```bash
# 首次使用：一步完成 Token 验证 + 站点配置自动保存
amber.py login <你的Token>
```

登录成功后会自动获取并保存站点信息，后续命令无需再传入站点ID。

```bash
# 查看当前 Token 状态
amber.py login
```

Token 失效时自动提示，无需手动处理。

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
| `startDate` | 开始日期（**YYYY-MM-DD** 格式，不是 ISO 8601） |
| `endDate` | 结束日期（不超过7天） |

**返回字段（Python预处理后）**：

| 字段 | 说明 |
|------|------|
| `kwh` | 直接是 kWh 数（不用计算） |
| `cost` | 直接是费用（**cents**，不用除100） |
| `perKwh` | 电价（cents/kWh） |
| `channelType` | general=购电 / feedIn=售电 |
| `feed_cost < 0` | 售电倒贴（被收费） |
| `feed_cost > 0` | 售电赚钱 |

## 数据单位说明

- 电价 `perKwh`：**cents/kWh**（澳分/度）
- `cost = perKwh × kwh`（**直接是 cents**，已验证）
- 时间：NEM 时间（UTC+10:00，AEST，无夏令时）

## 常用命令

| 场景 | 命令 |
|------|------|
| 配置/测试 Token | `amber.py login [token]` |
| 查看所有站点 | `amber.py list` |
| 查看当前电价 | `amber.py price [site_id]` |
| 查看未来电价预测 | `amber.py forecast [site_id] [小时]` |
| 查看用量账单 | `amber.py usage [site_id] <时间>` |
| 综合分析报告 | `amber.py report [site_id]` |

> site_id 可省略，首次登录后自动从 `~/.amber/config.json` 读取。

## 日期解析（自然语言）

`usage` 命令的 `<时间>` 参数支持自然语言：

| 用户输入 | 日期区间 |
|---------|---------|
| `昨天` / `yesterday` | 前一天 |
| `前天` | 前两天 |
| `近3天` / `近7天` / `近30天` | 自动计算 |
| `上周` | 上一个完整自然周（周一~周日） |
| `上上周` | 上上周（自然周） |
| `2026-04-01` | 单日 |
| `2026-04-01 2026-04-06` | 日期区间 |
| `2026年3月` | **暂不支持**（直接提示） |

## 输出格式（图表自动生成）

`usage` 和 `forecast` 命令执行后会**自动生成图表**：

```
[表格数据...]
📊 图表已生成: /path/to/chart.png
=================================================================
  🖼️ CHART_PATH=/path/to/chart.png
```

**回复规范**：
1. 执行脚本获取 `🖼️ CHART_PATH=...`
2. 使用 `message` 工具发送图片 + 文字摘要：
   - **Feishu**：channel=feishu，caption=文字摘要，media=CHART_PATH，target=当前会话用户 ID
   - **webchat**：暂不支持内嵌图片，建议用户切换至飞书以获得完整体验

## 示例查询

```bash
# 首次配置（一键完成）
amber.py login psk_xxx

# 后续使用（无需传站点ID）
amber.py price
amber.py forecast 6
amber.py usage 昨天
amber.py usage 上周
amber.py report
```

## 注意事项

- Token 认证信息仅存储在 `~/.amber/token`，**不写入记忆或技能文件**
- 认证失败或缺失时，技能会显示友好提示并引导重新输入
- `/usage` 接口日期格式为 **YYYY-MM-DD**（不是 ISO 8601）
- 售电（feedIn）perKwh 在某些时段为**负数**，此时售电反而被收费
- 预测价格仅供参考，实际以 ActualInterval 为准
