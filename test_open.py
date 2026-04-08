"""只测下单，不碰 get_positions"""
from trading import execute_trade
from session_manager import get_session

sm = get_session()
sm.login()

print("connected:", sm.is_connected())
r = execute_trade('XAUUSD', 'BUY', 1, 'MARKET', None, None)
print("result:", r)
