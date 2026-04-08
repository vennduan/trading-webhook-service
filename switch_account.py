"""
账号切换脚本
用法:
  python switch_account.py                    # 交互式选择
  python switch_account.py --list            # 仅列出已配置账号
  python switch_account.py --use DEMO_001     # 切换到指定账号
  python switch_account.py --add              # 添加新账号
  python switch_account.py --remove DEMO_001 # 删除账号
"""

import os
import sys
import json
import argparse
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
ACCOUNTS_FILE = BASE_DIR / "accounts.json"
ACTIVE_FILE = BASE_DIR / ".active_account"


def load_accounts() -> dict:
    if not ACCOUNTS_FILE.exists():
        return {"accounts": {}}
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return {"accounts": {}}
            return json.loads(content)
    except (json.JSONDecodeError, IOError):
        return {"accounts": {}}


def save_accounts(data: dict):
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_active() -> str:
    if ACTIVE_FILE.exists():
        return ACTIVE_FILE.read_text().strip()
    return ""


def set_active(name: str):
    with open(ACTIVE_FILE, "w", encoding="utf-8") as f:
        f.write(name)


def mask(s: str, vis: int = 3) -> str:
    if len(s) <= vis:
        return "*" * len(s)
    return s[:vis] + "*" * (len(s) - vis)


def list_accounts():
    data = load_accounts()
    active = get_active()
    accounts = data.get("accounts", {})

    if not accounts:
        print("未配置任何账号。请运行: python switch_account.py --add")
        return

    print(f"\n{'='*50}")
    print(f"{'账号切换器':^50}")
    print(f"{'='*50}")
    print(f"{'序号':<6} {'名称':<15} {'类型':<8} {'用户名':<15} {'状态'}")
    print("-" * 50)

    for i, (name, acc) in enumerate(accounts.items(), 1):
        status = "← 当前" if name == active else ""
        print(
            f"{i:<6} {name:<15} {acc.get('connection','Demo'):<8} "
            f"{mask(acc.get('username','')):<15} {status}"
        )
    print()


def add_account():
    data = load_accounts()
    print("\n--- 添加新账号 ---")

    name = input("账号名称 (如 DEMO_001, REAL_001): ").strip()
    if not name:
        print("名称不能为空")
        return
    if name in data.get("accounts", {}):
        print(f"账号 '{name}' 已存在，请使用其他名称")
        return

    username = input("FXCM 用户名: ").strip()
    if not username:
        print("用户名不能为空")
        return

    password = input("FXCM 密码: ").strip()
    if not password:
        print("密码不能为空")
        return

    connection = input("连接类型 (Demo / Real) [Demo]: ").strip() or "Demo"
    if connection not in ("Demo", "Real"):
        print("无效的连接类型")
        return

    if "accounts" not in data:
        data["accounts"] = {}

    data["accounts"][name] = {
        "username": username,
        "password": password,
        "connection": connection,
        "url": "www.fxcorporate.com/Hosts.jsp",
    }
    save_accounts(data)
    print(f"\n账号 '{name}' 已添加")


def remove_account():
    data = load_accounts()
    accounts = data.get("accounts", {})
    if not accounts:
        print("没有可删除的账号")
        return

    list_accounts()
    name = input("输入要删除的账号名称: ").strip()

    if name not in accounts:
        print(f"账号 '{name}' 不存在")
        return

    active = get_active()
    if name == active:
        set_active("")

    del data["accounts"][name]
    save_accounts(data)
    print(f"账号 '{name}' 已删除")


def switch_to(name: str):
    data = load_accounts()
    accounts = data.get("accounts", {})

    if name not in accounts:
        print(f"账号 '{name}' 不存在。可用: {', '.join(accounts.keys())}")
        sys.exit(1)

    acc = accounts[name]
    os.environ["FXCM_USERNAME"] = acc["username"]
    os.environ["FXCM_PASSWORD"] = acc["password"]
    os.environ["FXCM_CONNECTION"] = acc.get("connection", "Demo")
    os.environ["FXCM_URL"] = acc.get("url", "www.fxcorporate.com/Hosts.jsp")

    set_active(name)

    print(f"\n已切换到账号: {name} ({acc.get('connection')})")
    print(f"  用户名: {mask(acc['username'])}")
    print(f"\n注意: 环境变量已设置，请重启 webhook 服务使生效")
    print(f"  Windows: 重启 run.bat / install_service.bat")


def interactive():
    data = load_accounts()
    accounts = data.get("accounts", {})
    active = get_active()

    if not accounts:
        print("未配置任何账号")
        add_account()
        return

    list_accounts()

    print("操作: [数字]切换  [A]添加  [R]删除  [Q]退出")
    choice = input("选择: ").strip().upper()

    if choice == "Q":
        return
    elif choice == "A":
        add_account()
    elif choice == "R":
        remove_account()
    elif choice.isdigit():
        idx = int(choice) - 1
        names = list(accounts.keys())
        if 0 <= idx < len(names):
            switch_to(names[idx])
        else:
            print("无效序号")
    else:
        # 尝试直接按名称切换
        switch_to(choice)


def main():
    parser = argparse.ArgumentParser(description="FXCM 账号切换工具")
    parser.add_argument("--list", action="store_true", help="仅列出已配置账号")
    parser.add_argument("--add", action="store_true", help="添加新账号")
    parser.add_argument("--remove", metavar="NAME", help="删除指定账号")
    parser.add_argument("--use", metavar="NAME", help="切换到指定账号")
    args = parser.parse_args()

    if args.list:
        list_accounts()
    elif args.add:
        add_account()
    elif args.remove:
        # 先加载要删除的账号名到上下文中
        name = args.remove
        data = load_accounts()
        if name not in data.get("accounts", {}):
            print(f"账号 '{name}' 不存在")
            sys.exit(1)
        # 复用 remove_account 逻辑但指定 name
        active = get_active()
        if name == active:
            set_active("")
        del data["accounts"][name]
        save_accounts(data)
        print(f"账号 '{name}' 已删除")
    elif args.use:
        switch_to(args.use)
    else:
        interactive()


if __name__ == "__main__":
    main()
