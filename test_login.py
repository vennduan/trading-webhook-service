from session_manager import get_session
sm = get_session()
sm.login()
print("Login OK, connected:", sm.is_connected())
