"""
账号配置脚本
用法:
  python switch_account.py                    # 交互式设置环境变量
  python switch_account.py --set             # 交互式设置
  python switch_account.py --show            # 显示当前配置（不显示密码）

直接设置环境变量（永久生效需通过系统环境变量或重启服务后失效）:
  $env:FXCM_USERNAME="D103538839"
  $env:FXCM_PASSWORD="Rlit6"
  $env:FXCM_CONNECTION="Demo"
  $env:FXCM_URL="www.fxcorporate.com/Hosts.jsp"
"""

import os
import sys
import argparse


def mask(s: str, vis: int = 3) -> str:
    if len(s) <= vis:
        return "*" * len(s)
    return s[:vis] + "*" * (len(s) - vis)


def show_current():
    username = os.environ.get("FXCM_USERNAME", "")
    password = os.environ.get("FXCM_PASSWORD", "")
    connection = os.environ.get("FXCM_CONNECTION", "")
    url = os.environ.get("FXCM_URL", "")

    print(f"\n{'='*50}")
    print(f"{'当前 FXCM 账号配置':^50}")
    print(f"{'='*50}")
    print(f"  FXCM_USERNAME   : {mask(username) if username else '(未设置)'}")
    print(f"  FXCM_PASSWORD   : {mask(password) if password else '(未设置)'}")
    print(f"  FXCM_CONNECTION : {connection or '(未设置, 默认Demo)'}")
    print(f"  FXCM_URL        : {url or '(未设置, 默认www.fxcorporate.com/Hosts.jsp)'}")
    print(f"\n注意: 以下环境变量已设置，需重启 webhook 服务生效")
    print(f"  run.bat 窗口需关闭重开，或重启 Windows 服务\n")


def interactive_set():
    print("\n--- 设置 FXCM 账号环境变量 ---")
    print("（直接设置当前进程环境变量，服务重启后需重新设置）\n")

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

    os.environ["FXCM_USERNAME"] = username
    os.environ["FXCM_PASSWORD"] = password
    os.environ["FXCM_CONNECTION"] = connection
    os.environ["FXCM_URL"] = "www.fxcorporate.com/Hosts.jsp"

    print(f"\n环境变量已设置:")
    print(f"  FXCM_USERNAME   = {username}")
    print(f"  FXCM_PASSWORD   = {mask(password)}")
    print(f"  FXCM_CONNECTION = {connection}")
    print(f"\n重启 webhook 服务使生效（关闭 run.bat 窗口重新打开）")


def main():
    parser = argparse.ArgumentParser(description="FXCM 账号配置工具")
    parser.add_argument("--show", action="store_true", help="显示当前环境变量配置")
    parser.add_argument("--set", action="store_true", help="交互式设置环境变量")
    args = parser.parse_args()

    if args.show:
        show_current()
    elif args.set:
        interactive_set()
    else:
        show_current()
        print("\n使用 --set 重新设置账号")
        print("  python switch_account.py --set")


if __name__ == "__main__":
    main()
