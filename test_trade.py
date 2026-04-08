from trading import execute_trade, get_positions
from session_manager import get_session

sm = get_session()
sm.login()
print('positions:', get_positions())

r = execute_trade('XAUUSD', 'BUY', 1, 'MARKET', None, None)
print('result:', r)

print('positions after:', get_positions())
