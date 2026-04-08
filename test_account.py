"""查询 FXCM 账户信息"""
from trading import get_account
from session_manager import get_session

sm = get_session()
sm.login()

acct = get_account()
print("Account info:")
for k, v in acct.items():
    print(f"  {k}: {v}")
