@echo off
:: 本地测试脚本 — 模拟 TradingView 发送 POST 请求到 localhost:5000
:: 前提：服务器已启动 (python webhook_server.py)

set BASE_URL=http://localhost:5000
set TOKEN=YOUR-WEBHOOK-TOKEN-HERE

echo ========================================
echo  Trading Webhook Local Test Suite
echo ========================================
echo.

:: 测试 1: 健康检查
echo [Test 1] GET /health
curl -s "%BASE_URL%/health"
echo.
echo.

:: 测试 2: 市价买单 (正常)
echo [Test 2] POST /webhook — MARKET BUY
curl -s -X POST "%BASE_URL%/webhook" ^
  -H "Content-Type: application/json" ^
  -d "{\"symbol\":\"EUR\/USD\",\"direction\":\"BUY\",\"amount\":1000,\"order_type\":\"MARKET\",\"token\":\"%TOKEN%\"}"
echo.
echo.

:: 测试 3: 市价卖单 (正常)
echo [Test 3] POST /webhook — MARKET SELL
curl -s -X POST "%BASE_URL%/webhook" ^
  -H "Content-Type: application/json" ^
  -d "{\"symbol\":\"GBP\/USD\",\"direction\":\"SELL\",\"amount\":1000,\"order_type\":\"MARKET\",\"token\":\"%TOKEN%\"}"
echo.
echo.

:: 测试 4: 限价买单
echo [Test 4] POST /webhook — LIMIT BUY
curl -s -X POST "%BASE_URL%/webhook" ^
  -H "Content-Type: application/json" ^
  -d "{\"symbol\":\"USD\/JPY\",\"direction\":\"BUY\",\"amount\":1000,\"order_type\":\"LIMIT\",\"rate\":148.500,\"token\":\"%TOKEN%\"}"
echo.
echo.

:: 测试 5: 止损卖单
echo [Test 5] POST /webhook — STOP SELL
curl -s -X POST "%BASE_URL%/webhook" ^
  -H "Content-Type: application/json" ^
  -d "{\"symbol\":\"EUR\/JPY\",\"direction\":\"SELL\",\"amount\":1000,\"order_type\":\"STOP\",\"rate\":162.000,\"token\":\"%TOKEN%\"}"
echo.
echo.

:: 测试 6: Token 错误
echo [Test 6] POST /webhook — WRONG TOKEN (expect 400)
curl -s -X POST "%BASE_URL%/webhook" ^
  -H "Content-Type: application/json" ^
  -d "{\"symbol\":\"EUR\/USD\",\"direction\":\"BUY\",\"amount\":1000,\"order_type\":\"MARKET\",\"token\":\"WRONG\"}"
echo.
echo.

:: 测试 7: 缺少必填字段
echo [Test 7] POST /webhook — MISSING AMOUNT (expect 400)
curl -s -X POST "%BASE_URL%/webhook" ^
  -H "Content-Type: application/json" ^
  -d "{\"symbol\":\"EUR\/USD\",\"direction\":\"BUY\",\"order_type\":\"MARKET\",\"token\":\"%TOKEN%\"}"
echo.
echo.

:: 测试 8: 无效品种
echo [Test 8] POST /webhook — INVALID SYMBOL (expect 400)
curl -s -X POST "%BASE_URL%/webhook" ^
  -H "Content-Type: application/json" ^
  -d "{\"symbol\":\"INVALID\/XYZ\",\"direction\":\"BUY\",\"amount\":1000,\"order_type\":\"MARKET\",\"token\":\"%TOKEN%\"}"
echo.
echo.

:: 测试 9: 无效 direction
echo [Test 9] POST /webhook — INVALID DIRECTION (expect 400)
curl -s -X POST "%BASE_URL%/webhook" ^
  -H "Content-Type: application/json" ^
  -d "{\"symbol\":\"EUR\/USD\",\"direction\":\"HOLD\",\"amount\":1000,\"order_type\":\"MARKET\",\"token\":\"%TOKEN%\"}"
echo.
echo.

echo ========================================
echo  Test suite complete
echo ========================================
