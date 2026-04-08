"""探测 ForexConnect Python 3.7 reader 正确遍历方式"""
from session_manager import get_session

sm = get_session()
sm.login()
fx = sm.fx

print("=== 探测 TRADES table reader ===")
try:
    trades_table = fx.get_table(fx.TRADES)
    resp = trades_table.get_refresh_response()
    reader = fx.session.response_reader_factory.create_reader(resp)
    print("reader type:", type(reader))
    print("reader attrs:", [a for a in dir(reader) if not a.startswith('_')])

    # 尝试各种可能的计数方式
    for attr in ('size', 'count', 'getSize', 'getCount', 'Size', 'Count', 'length'):
        try:
            val = getattr(reader, attr)
            print(f"  .{attr} = {val}")
        except Exception as e:
            print(f"  .{attr} failed: {e}")

    # 尝试 __len__
    try:
        print(f"  len(reader) = {len(reader)}")
    except Exception as e:
        print(f"  len(reader) failed: {e}")

    # 尝试遍历
    print("\n=== 尝试遍历 ===")
    try:
        for i, row in enumerate(reader):
            print(f"  row {i}: trade_id={row.trade_id} instrument={row.instrument}")
            if i > 5:
                print("  ...(more)")
                break
    except Exception as e:
        print(f"  遍历失败: {e}")

    # 尝试用 while 循环
    print("\n=== 尝试 while 循环 ===")
    try:
        resp2 = trades_table.get_refresh_response()
        reader2 = fx.session.response_reader_factory.create_reader(resp2)
        i = 0
        while True:
            try:
                row = reader2.next()
                if row is None:
                    break
                print(f"  row {i}: trade_id={row.trade_id}")
                i += 1
                if i > 5:
                    print("  ...(more)")
                    break
            except Exception as e:
                print(f"  next() 失败 at {i}: {e}")
                break
    except Exception as e:
        print(f"  while 循环失败: {e}")

except Exception as e:
    print(f"整体失败: {e}")
    import traceback
    traceback.print_exc()
