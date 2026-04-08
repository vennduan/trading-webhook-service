# 本地测试指南

## 1. 环境准备

### Python 3.7
```powershell
py -3.7 -m pip install forexconnect flask python-dateutil
```

### FXCM 账号（Demo）
```
用户名: D103538839
密码:   Rlit6
服务器: Demo
```

## 2. 设置环境变量

```powershell
# PowerShell（当前窗口生效，服务需通过系统环境变量或 run.bat 设置）
$env:FXCM_USERNAME="D103538839"
$env:FXCM_PASSWORD="Rlit6"
$env:FXCM_CONNECTION="Demo"
$env:FXCM_URL="www.fxcorporate.com/Hosts.jsp"
$env:WEBHOOK_TOKEN="fdadfb2d9e06a3b856b2252e1dd74d0367d4da1a396bb5db900ed8935386b1f5"
```

## 3. 启动服务

```powershell
# 推荐用 run.bat（会自动检查环境变量）
py -3.7 webhook_server.py
```

服务运行在 `http://127.0.0.1:5000`

**启动后检查 FXCM 是否连接成功**，日志里应该有：
```
FXCM connection established at startup.
```
如果看到 `Failed to connect to FXCM at startup`，说明环境变量或账号有问题。

## 4. 测试

> 注意：Windows Server 上不要用 `curl`，用 `Invoke-RestMethod`

### 4.1 健康检查

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:5000/health" -Method GET
```

预期：`{"fxcm": "connected", "status": "ok", ...}`

### 4.2 JSON webhook 测试（模拟 TradingView 告警）

> **Windows PowerShell** 使用 `Invoke-RestMethod`，不是 `curl`

**开仓 BUY：**
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:5000/webhook" -Method POST `
  -ContentType "application/json" `
  -Body '{"symbol":"XAUUSD","direction":"BUY","amount":1,"order_type":"MARKET","token":"fdadfb2d9e06a3b856b2252e1dd74d0367d4da1a396bb5db900ed8935386b1f5","position":"long","prev_position":"flat"}'
```

**开仓 SELL：**
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:5000/webhook" -Method POST `
  -ContentType "application/json" `
  -Body '{"symbol":"XAUUSD","direction":"SELL","amount":1,"order_type":"MARKET","token":"fdadfb2d9e06a3b856b2252e1dd74d0367d4da1a396bb5db900ed8935386b1f5","position":"short","prev_position":"flat"}'
```

**平仓（prev_position=long -> flat）：**
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:5000/webhook" -Method POST `
  -ContentType "application/json" `
  -Body '{"symbol":"XAUUSD","direction":"SELL","amount":1,"order_type":"MARKET","token":"fdadfb2d9e06a3b856b2252e1dd74d0367d4da1a396bb5db900ed8935386b1f5","position":"flat","prev_position":"long"}'
```

**完全平仓（direction=CLOSE）：**
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:5000/webhook" -Method POST `
  -ContentType "application/json" `
  -Body '{"symbol":"XAUUSD","direction":"CLOSE","amount":"0","token":"fdadfb2d9e06a3b856b2252e1dd74d0367d4da1a396bb5db900ed8935386b1f5"}'
```

## 5. 验证交易真实成交

webhook 返回 `{"status":"success", "order_id":"..."}` 只表示 FXCM API 接受了这笔请求，不一定已成交。

**必须通过以下方式验证：**

### 方式 A：直接查询持仓（推荐）
```powershell
py -3.7 -c "from session_manager import get_session; from trading import get_positions, get_account; sm=get_session(); sm.login(force=True); print('account:', get_account()['account_id']); print('positions:', get_positions())"
```
如果持仓列表里有对应的 trade，说明真实成交了。

### 方式 B：登录 FXCM Trading Station Web
登录 https://www.fxcm.com/FXCMPositionStream/ ，确认账号余额和持仓。

## 6. 预期结果

| 结果 | 含义 |
|------|------|
| `{"status": "success", "order_id": "..."}` | FXCM API 接受了请求 |
| `{"status": "error", "code": "..."}` | 验证/风控/交易失败 |
| webhook 200 + 持仓里有订单 | 交易真实成交 |
| webhook 200 + 持仓里没有订单 | FXCM 会话异常，需重启服务 |

## 7. 常见问题

### Q: webhook 返回 success 但没有订单
A: 服务启动时 FXCM 会话没有正确建立。重启 `run.bat`，确认日志里有 `FXCM connection established at startup`。

### Q: FXCM 连接失败
A: 检查环境变量是否设置正确：`$env:FXCM_USERNAME`、`$env:FXCM_PASSWORD`、`$env:FXCM_CONNECTION`。

### Q: `Invoke-RestMethod` 报错
A: Windows Server 上 `curl` 是 `Invoke-WebRequest` 的别名，会报错。必须用 `Invoke-RestMethod`。

## 8. 本地单元测试（无需 FXCM 连接）

直接运行 Python 脚本：
```powershell
py -3.7 test_json_webhook.py
```

这会测试 `validate_message` 解析逻辑，不走 FXCM API。

## 9. 字段别名映射

| 模板字段 | 内部字段 |
|---------|---------|
| side / action | direction |
| bot_sec / api_key / secret | token |
| price | rate |
| contracts | amount |
| pre_position | prev_position |
| now_position_amount | position_size |
