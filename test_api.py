"""诊断脚本：探测 ForexConnect Python 3.7 实际 API"""
from session_manager import get_session

sm = get_session()
sm.login()
fx = sm.fx

# 探测 get_table
print("\n=== 探测 get_table ===")
table = fx.get_table(fx.TRADES)
print("table type:", type(table))
print("table attrs:", [a for a in dir(table) if not a.startswith('_')])

# 探测 refresh
print("\n=== 探测 refresh ===")
try:
    table.refresh()
    print("refresh OK")
except Exception as e:
    print("refresh failed:", e)

# 探测 response
print("\n=== 探测 get_refresh_response ===")
try:
    resp = table.get_refresh_response()
    print("get_refresh_response OK, type:", type(resp))
except Exception as e:
    print("get_refresh_response failed:", e)

# 探测 response_reader_factory
print("\n=== 探测 response_reader_factory ===")
try:
    reader = fx.session.response_reader_factory.create_reader(resp)
    print("create_reader OK, type:", type(reader))
except Exception as e:
    print("create_reader failed:", e)

# 探测 reader 方法
if 'reader' in dir():
    print("\n=== 探测 reader 属性 ===")
    print("reader attrs:", [a for a in dir(reader) if not a.startswith('_')])
    try:
        print("reader.size:", reader.size)
    except Exception as e:
        print("reader.size failed:", e)
    try:
        print("reader.count:", reader.count)
    except Exception as e:
        print("reader.count failed:", e)
    try:
        print("reader.__len__:", len(reader))
    except Exception as e:
        print("reader.__len__ failed:", e)
    try:
        print("reader.get_count():", reader.get_count())
    except Exception as e:
        print("reader.get_count() failed:", e)

# 探测 offers table
print("\n=== 探测 offers table ===")
try:
    offers_table = fx.get_table(fx.OFFERS)
    print("offers_table OK")
    offers_table.refresh()
    resp2 = offers_table.get_refresh_response()
    reader2 = fx.session.response_reader_factory.create_reader(resp2)
    print("offers reader type:", type(reader2))
    print("offers reader attrs:", [a for a in dir(reader2) if not a.startswith('_')])
except Exception as e:
    print("offers failed:", e)
