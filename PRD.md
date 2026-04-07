# TradingView Webhook 交易服务 PRD

## 1. 项目概述

**项目名称**: trading-webhook-service
**类型**: 后台交易服务
**功能**: 接收 TradingView webhook 告警，自动在 FXCM 账户执行交易
**运行环境**: Windows Server + Python 3.8.6 + ForexConnect API

---

## 2. 功能需求

### 2.1 核心功能

| 功能 | 描述 |
|------|------|
| Webhook 接收 | 监听 POST 请求，接收 TradingView 告警 |
| 消息解析 | 解析 JSON 消息，提取交易参数 |
| 自动交易 | 调用 ForexConnect API 执行买入/卖出 |
| 日志记录 | 记录所有请求、响应、交易结果 |
| 健康检查 | 提供 GET /health 接口 |

### 2.2 交易操作

| 操作 | 说明 |
|------|------|
| 市价单 | 按当前市场价执行 BUY/SELL |
| 止损单 | 创建 STOP ENTRY 订单 |
| 限价单 | 创建 LIMIT ENTRY 订单 |
| 修改订单 | 编辑现有订单价格 |
| 附加止损/限价 | 给持仓附加止盈/止损 |

### 2.3 TradingView 消息格式

```json
{
  "symbol": "EUR/USD",
  "direction": "BUY",
  "amount": 10000,
  "order_type": "MARKET",
  "rate": 1.0850,
  "stop_rate": 1.0800,
  "limit_rate": 1.0900,
  "token": "your-secret-token"
}
```

| 字段 | 必填 | 说明 |
|------|------|------|
| symbol | 是 | 交易品种，如 EUR/USD |
| direction | 是 | BUY 或 SELL |
| amount | 是 | 交易数量（单位） |
| order_type | 否 | MARKET / STOP / LIMIT，默认 MARKET |
| rate | 否 | 指定价格（限价/止损单用） |
| stop_rate | 否 | 止损价 |
| limit_rate | 否 | 止盈价 |
| token | 是 | 验证令牌 |

---

## 3. 非功能需求

### 3.1 性能
- Webhook 响应时间 < 3 秒（TradingView 超时时间）
- 支持并发请求（ Flask 单线程，必要时加 gunicorn）

### 3.2 安全
- Webhook Token 验证
- 敏感配置通过环境变量或配置文件管理
- 日志不记录密码

### 3.3 可靠性
- ForexConnect 连接异常时返回明确错误码
- 交易执行失败时重试 1 次
- 日志持久化到文件

---

## 4. 项目结构

```
trading-webhook-service/
├── PRD.md              # 本文档
├── TASKS.json          # 任务清单
├── requirements.txt     # Python 依赖
├── config.py            # 配置文件
├── webhook_server.py    # Flask 服务入口
├── trading.py           # ForexConnect 交易封装
├── logger.py            # 日志模块
├── validators.py        # 请求验证
├── run.bat              # Windows 启动脚本
└── logs/                # 日志目录
```

---

## 5. API 接口

### POST /webhook
接收 TradingView 告警，执行交易。

**请求**: JSON Body
**响应**:
```json
{
  "status": "success",
  "order_id": "12345",
  "message": "BUY 10000 EUR/USD @ 1.0850 executed"
}
```

**错误响应**:
```json
{
  "status": "error",
  "code": "INVALID_TOKEN",
  "message": "Invalid webhook token"
}
```

### GET /health
健康检查。

**响应**:
```json
{
  "status": "ok",
  "service": "trading-webhook-service"
}
```

---

## 6. 配置项

| 配置项 | 说明 | 示例 |
|--------|------|------|
| FXCM_URL | 服务器地址 | www.fxcorporate.com/Hosts.jsp |
| FXCM_USERNAME | FXCM 用户名 | - |
| FXCM_PASSWORD | FXCM 密码 | - |
| FXCM_CONNECTION | Demo / Real | Real |
| WEBHOOK_TOKEN | 验证令牌 | - |
| LISTEN_HOST | 监听地址 | 0.0.0.0 |
| LISTEN_PORT | 监听端口 | 5000 |
| LOG_LEVEL | 日志级别 | INFO |

---

## 7. 错误码

| 代码 | 说明 |
|------|------|
| INVALID_TOKEN | Token 验证失败 |
| INVALID_JSON | JSON 解析失败 |
| MISSING_FIELD | 缺少必填字段 |
| INVALID_SYMBOL | 无效的交易品种 |
| CONNECTION_ERROR | FXCM 连接失败 |
| TRADE_FAILED | 交易执行失败 |
| TIMEOUT | 请求超时 |

---

## 8. 安全注意事项

1. FXCM 密码不要写入代码，使用环境变量或单独配置文件
2. 服务器防火墙仅开放必要端口
3. 建议配合 VPN 或内网使用
4. 生产环境务必使用 Real 账号前先在 Demo 充分测试
