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
# PowerShell
$env:FXCM_USERNAME="D103538839"
$env:FXCM_PASSWORD="Rlit6"
$env:FXCM_CONNECTION="Demo"
$env:WEBHOOK_TOKEN="fdadfb2d9e06a3b856b2252e1dd74d0367d4da1a396bb5db900ed8935386b1f5"
```

## 3. 启动服务

```bash
py -3.7 webhook_server.py
```

服务运行在 `http://127.0.0.1:5000`

## 4. 测试

### 4.1 健康检查
```bash
curl http://127.0.0.1:5000/health
```

### 4.2 JSON webhook 测试（模拟 TradingView 告警）

**开仓 BUY：**
```bash
curl -X POST http://127.0.0.1:5000/webhook ^
  -H "Content-Type: application/json" ^
  -d "{\"symbol\":\"XAUUSD\",\"side\":\"buy\",\"amount\":\"2\",\"position\":\"long\",\"pre_position\":\"flat\",\"price\":\"4800.00\",\"bot_sec\":\"fdadfb2d9e06a3b856b2252e1dd74d0367d4da1a396bb5db900ed8935386b1f5\"}"
```

**开仓 SELL：**
```bash
curl -X POST http://127.0.0.1:5000/webhook ^
  -H "Content-Type: application/json" ^
  -d "{\"symbol\":\"XAUUSD\",\"side\":\"sell\",\"amount\":\"2\",\"position\":\"short\",\"pre_position\":\"flat\",\"price\":\"4800.00\",\"bot_sec\":\"fdadfb2d9e06a3b856b2252e1dd74d0367d4da1a396bb5db900ed8935386b1f5\"}"
```

**平仓（prev_position=short -> flat）：**
```bash
curl -X POST http://127.0.0.1:5000/webhook ^
  -H "Content-Type: application/json" ^
  -d "{\"symbol\":\"XAUUSD\",\"side\":\"buy\",\"amount\":\"2\",\"position\":\"flat\",\"pre_position\":\"long\",\"price\":\"4800.00\",\"bot_sec\":\"fdadfb2d9e06a3b856b2252e1dd74d0367d4da1a396bb5db900ed8935386b1f5\"}"
```

**完全平仓（direction=CLOSE）：**
```bash
curl -X POST http://127.0.0.1:5000/webhook ^
  -H "Content-Type: application/json" ^
  -d "{\"symbol\":\"XAUUSD\",\"direction\":\"CLOSE\",\"amount\":\"0\",\"bot_sec\":\"fdadfb2d9e06a3b856b2252e1dd74d0367d4da1a396bb5db900ed8935386b1f5\"}"
```

## 5. 本地单元测试（无需 FXCM 连接）

直接运行 Python 脚本：
```bash
py -3.7 test_json_webhook.py
```

这会测试 `validate_message` 解析逻辑，不走 FXCM API。

## 6. 预期结果

- 返回 `{"status": "success", ...}` + HTTP 200 = 下单成功
- 返回 `{"status": "error", ...}` = 验证/风控/交易失败
- FXCM Demo 账号：返回 200 但平台上可能无真实成交（Demo 账号行为）

## 7. 调试

查看日志确认状态机判断：
```bash
# webhook_server.py 中的日志
# action=buy position=long prev_position=flat -> trade_action=OPEN_LONG
```

字段别名映射（webhook.json 模板字段 → 内部字段）：
| 模板字段 | 内部字段 |
|---------|---------|
| side / action | direction |
| bot_sec / api_key | token |
| price | rate |
| contracts | amount |
| pre_position | prev_position |
| now_position_amount | position_size |
