# TradingView Webhook 交易服务

接收 TradingView 告警 webhook，自动在 FXCM 账户执行交易。

---

## 环境要求

- Windows Server（测试通过：Windows Server）
- Python 3.8.6+
- FXCM 交易账户（Demo 或 Real）
- ForexConnect API

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

验证安装：
```bash
python -c "from forexconnect import ForexConnect; print('OK')"
```

### 2. 配置

复制配置示例文件：
```bat
copy config.json.example config.json
```

编辑 `config.json`：
```json
{
  "fxx": {
    "url": "www.fxcorporate.com/Hosts.jsp",
    "connection": "Demo",
    "session_timeout_seconds": 300
  },
  "webhook": {
    "token": "YOUR-WEBHOOK-TOKEN-HERE",
    "timeout_seconds": 2.5
  },
  "server": {
    "host": "0.0.0.0",
    "port": 5000
  },
  "logging": {
    "level": "INFO"
  },
  "risk": {
    "max_position_size": 100000,
    "max_daily_trades": 50,
    "max_loss_per_trade_pct": 2.0
  }
}
```

设置环境变量（敏感信息，**不要写入 config.json**）：
```bat
set FXCM_USERNAME=your_username
set FXCM_PASSWORD=your_password
set WEBHOOK_TOKEN=your_secret_token
```

### 3. 启动服务

```bat
run.bat
```

服务启动后监听 `http://0.0.0.0:5000`

---

## API 接口

### POST /webhook

接收 TradingView 告警，执行交易。

**请求示例**：
```json
{
  "symbol": "EUR/USD",
  "direction": "BUY",
  "amount": 10000,
  "order_type": "MARKET",
  "token": "your_secret_token"
}
```

**order_type**：`MARKET`（市价单）、`STOP`（止损挂单）、`LIMIT`（限价挂单）

**带指定价格的挂单**：
```json
{
  "symbol": "EUR/USD",
  "direction": "BUY",
  "amount": 10000,
  "order_type": "LIMIT",
  "rate": 1.0850,
  "token": "your_secret_token"
}
```

**成功响应**：
```json
{
  "status": "success",
  "order_id": "12345",
  "message": "BUY 10000 EUR/USD @ MARKET executed"
}
```

**错误响应**：
```json
{
  "status": "error",
  "code": "INVALID_TOKEN",
  "message": "Invalid webhook token"
}
```

### GET /health

健康检查：
```bash
curl http://localhost:5000/health
```

### GET /account?token=xxx

查询账户余额（需 Token）：
```bash
curl "http://localhost:5000/account?token=your_secret_token"
```

---

## TradingView 配置

1. 在 TradingView 图表上创建告警
2. 勾选 **"Webhook URL"**
3. 填入：`http://你的服务器IP:5000/webhook`
4. 告警消息格式（JSON）：

```json
{"symbol":"EUR/USD","direction":"BUY","amount":10000,"order_type":"MARKET","token":"your_secret_token"}
```

**注意**：TradingView 只能回调公网可达的地址，本地 `localhost` 不行。

---

## Windows 服务化（NSSM）

### 安装 NSSM

下载：[https://nssm.cc/download](https://nssm.cc/download)
将 `nssm.exe` 放到本目录或系统 PATH。

### 安装服务

```bat
install_service.bat install
```

### 管理服务

```bat
install_service.bat start   # 启动
install_service.bat stop    # 停止
install_service.bat restart  # 重启
install_service.bat uninstall  # 卸载
```

服务会自动开机启动。

---

## 日志

日志位于 `logs/` 目录：

| 文件 | 内容 |
|------|------|
| `app.log` | 所有请求/响应日志 |
| `trades.log` | 交易操作记录 |

日志按天自动分割，保留 30 天。

---

## 错误码

| 代码 | 说明 |
|------|------|
| INVALID_TOKEN | Token 验证失败 |
| INVALID_JSON | JSON 解析失败 |
| MISSING_FIELD | 缺少必填字段 |
| INVALID_SYMBOL | 无效交易品种 |
| INVALID_DIRECTION | 方向必须是 BUY 或 SELL |
| INVALID_ORDER_TYPE | 订单类型必须是 MARKET/STOP/LIMIT |
| INSUFFICIENT_MARGIN | 保证金不足 |
| POSITION_SIZE_EXCEEDED | 超出单笔最大金额 |
| DAILY_TRADE_LIMIT | 超过每日交易次数上限 |
| CONNECTION_ERROR | FXCM 连接失败 |
| TRADE_FAILED | 交易执行失败 |

---

## 安全注意事项

1. **FXCM 密码**不要写入代码或 config.json，通过环境变量传入
2. 服务器防火墙仅开放 5000 端口
3. 使用 `Demo` 账号充分测试后再切换到 `Real`
4. 建议配合 VPN 或内网使用
5. 查看 `logs/trades.log` 监控所有交易操作

---

## 从 Demo 切换到 Real

1. 确认 Demo 测试全部通过
2. 修改 `config.json`：`"connection": "Real"`
3. 更新环境变量中的账号密码为 Real 账号
4. 重启服务
5. 用小金额做一次真实交易验证

---

## 常见问题

**Q: 服务启动报错 "Failed to connect to FXCM"**
- 检查网络是否能访问 `www.fxcorporate.com`
- 确认 FXCM_USERNAME 和 FXCM_PASSWORD 环境变量已设置
- Demo 账号是否有效

**Q: TradingView 告警没有触发**
- 确认 webhook URL 是公网可访问的（不是 localhost）
- 确认服务器防火墙开放了 5000 端口
- 查看 `logs/app.log` 是否有请求记录

**Q: 交易被执行但返回错误**
- 查看 `logs/trades.log` 确认交易记录
- 检查 FXCM 账户余额和保证金是否足够
- 确认交易品种和数量格式正确

**Q: 如何停止服务**
- 如果是命令行运行：Ctrl+C
- 如果是 NSSM 服务：`install_service.bat stop`
