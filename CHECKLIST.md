# Real 账号切换检查清单

从 Demo 账号切换到 Real 账号前的完整检查流程。

---

## 阶段一：Demo 测试验证

在切换前，确保以下测试全部通过：

- [ ] **服务启动正常**
  - `python webhook_server.py` 无报错
  - `curl http://localhost:5000/health` 返回 `{"status":"ok"}`

- [ ] **登录成功**
  - 服务日志显示 `FXCM login successful`
  - 能查询到账户余额

- [ ] **市价单测试通过**
  - 发送市价买单 `curl` 请求
  - 返回 `order_id`，无报错
  - FXCM 交易平台查到对应订单

- [ ] **限价/止损挂单测试通过**
  - 发送限价/止损单请求
  - 返回 `order_id`
  - FXCM 平台查到挂单

- [ ] **风控拒绝测试**
  - amount 超出限制 → 返回 403 + POSITION_SIZE_EXCEEDED
  - 无 Token → 返回 400 + MISSING_TOKEN
  - 错误 Token → 返回 400 + INVALID_TOKEN

- [ ] **TradingView webhook 联调**
  - 创建 TradingView 告警
  - 触发告警
  - 服务器收到请求并执行交易
  - TradingView 显示 "Webhook 发送成功"

---

## 阶段二：Real 账号准备

- [ ] 已获得 FXCM Real 账号
- [ ] Real 账号已完成身份验证（KYC）
- [ ] Real 账号有足够的保证金
- [ ] 知道 Real 账号的登录名和密码

---

## 阶段三：切换配置

1. 修改 `config.json`：
   ```json
   {
     "fxcm": {
       "connection": "Real"
     }
   }
   ```

2. 更新环境变量：
   ```bat
   set FXCM_USERNAME=你的Real用户名
   set FXCM_PASSWORD=你的Real密码
   ```

3. （可选）降低风控参数，先小资金测试：
   ```json
   {
     "risk": {
       "max_position_size": 5000,
       "max_daily_trades": 5
     }
   }
   ```

---

## 阶段四：Real 环境验证

- [ ] 服务重启后登录成功（日志显示 `FXCM login successful`）
- [ ] 查询 Real 账户余额正确
- [ ] 发送一笔**小额市价单**，确认成交
- [ ] 检查 `logs/trades.log` 确认交易记录
- [ ] TradingView 告警联调（小额）确认

---

## 阶段五：生产监控

切换后持续关注：

- [ ] `logs/app.log` 每天检查错误率
- [ ] `logs/trades.log` 记录所有交易
- [ ] 确认每日交易次数未超限
- [ ] 确认没有异常大额交易

---

## 回滚方案

如果出现问题：

1. **立即停止服务**：
   ```bat
   install_service.bat stop
   ```

2. **切回 Demo**：
   - 修改 `config.json` connection 为 `Demo`
   - 重启服务

3. **联系 FXCM**：`api@fxcm.com`

---

## 风险提示

⚠️ **Real 账号交易存在真实资金风险，请确保充分测试后再切换。**
