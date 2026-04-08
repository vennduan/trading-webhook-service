"""
模拟 TradingView JSON webhook 请求，测试完整链路
"""
import sys
import os

# 设置环境变量（模拟服务器配置）
os.environ["FXCM_USERNAME"] = os.environ.get("FXCM_USERNAME", "")
os.environ["FXCM_PASSWORD"] = os.environ.get("FXCM_PASSWORD", "")
os.environ["FXCM_CONNECTION"] = "Demo"
os.environ["WEBHOOK_TOKEN"] = "fdadfb2d9e06a3b856b2252e1dd74d0367d4da1a396bb5db900ed8935386b1f5"

from validators import validate_message
from trading import execute_trade
from session_manager import get_session


def test_json_webhook():
    # 模拟 TradingView 发来的 JSON webhook
    json_data = {
        "symbol": "XAUUSD",
        "side": "buy",
        "amount": "2",
        "now_position_amount": "1",
        "position": "long",
        "pre_position": "short",
        "price": "4800.00",
        "bot_sec": "fdadfb2d9e06a3b856b2252e1dd74d0367d4da1a396bb5db900ed8935386b1f5"
    }

    print("=" * 60)
    print("测试: JSON webhook -> validate_message -> execute_trade")
    print("=" * 60)
    print(f"\n1. 输入数据: {json_data}")

    # Step 1: 验证消息
    print("\n2. 调用 validate_message()...")
    try:
        params = validate_message(json_data)
        print(f"   解析结果: {params}")
    except Exception as e:
        print(f"   验证失败: {e}")
        return

    # Step 2: 连接 FXCM
    print("\n3. 连接 FXCM...")
    sm = get_session()
    sm.login()
    print(f"   连接状态: {sm.is_connected()}")

    # Step 3: 执行交易
    print("\n4. 调用 execute_trade()...")
    try:
        result = execute_trade(
            symbol=params["symbol"],
            direction=params["direction"],
            amount=params["amount"],
            order_type=params["order_type"],
            rate=params.get("rate"),
        )
        print(f"   执行结果: {result}")
    except Exception as e:
        print(f"   执行失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_json_webhook()
