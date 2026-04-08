"""
配置管理模块
支持 config.json + 环境变量双重配置
敏感信息(FXCM_USERNAME, FXCM_PASSWORD)必须通过环境变量传入
"""

import os
import json
from pathlib import Path


BASE_DIR = Path(__file__).parent.resolve()
CONFIG_FILE = BASE_DIR / "config.json"
ACCOUNTS_FILE = BASE_DIR / "accounts.json"
ACTIVE_FILE = BASE_DIR / ".active_account"


def _load_json_config():
    """从 config.json 加载非敏感配置"""
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _load_active_account() -> dict:
    """从 accounts.json 加载当前激活账号"""
    if not ACCOUNTS_FILE.exists():
        return {}
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not ACTIVE_FILE.exists():
            return {}
        active_name = ACTIVE_FILE.read_text().strip()
        accounts = data.get("accounts", {})
        if active_name and active_name in accounts:
            return accounts[active_name]
        return {}
    except (json.JSONDecodeError, IOError, FileNotFoundError):
        return {}


class Config:
    def __init__(self):
        data = _load_json_config()

        # FXCM
        fxcm = data.get("fxcm", {})
        self.fxcm_url = fxcm.get("url", "www.fxcorporate.com/Hosts.jsp")
        self.fxcm_connection = fxcm.get("connection", "Demo")
        self.fxcm_session_timeout = int(fxcm.get("session_timeout_seconds", 300))

        # Webhook
        webhook = data.get("webhook", {})
        self.webhook_token = webhook.get("token", "")
        self.webhook_timeout = float(webhook.get("timeout_seconds", 2.5))

        # Server
        server = data.get("server", {})
        self.server_host = server.get("host", "0.0.0.0")
        self.server_port = int(server.get("port", 5000))

        # Logging
        logging_cfg = data.get("logging", {})
        self.log_level = logging_cfg.get("level", "INFO")

        # Risk
        risk = data.get("risk", {})
        self.risk_max_position_size = int(risk.get("max_position_size", 100000))
        self.risk_max_daily_trades = int(risk.get("max_daily_trades", 50))
        self.risk_max_loss_per_trade_pct = float(risk.get("max_loss_per_trade_pct", 2.0))

        # 环境变量 > accounts.json 激活账号 > 空
        self.fxcm_username = os.environ.get("FXCM_USERNAME", "")
        self.fxcm_password = os.environ.get("FXCM_PASSWORD", "")

        # 如果环境变量未设置，尝试从 accounts.json 激活账号读取
        if not self.fxcm_username or not self.fxcm_password:
            active_account = _load_active_account()
            if active_account:
                self.fxcm_username = active_account.get("username", "")
                self.fxcm_password = active_account.get("password", "")
                self.fxcm_connection = active_account.get("connection", self.fxcm_connection)

        self.webhook_token = os.environ.get("WEBHOOK_TOKEN", self.webhook_token)

        # 验证必填项
        if not self.fxcm_username or not self.fxcm_password:
            raise ValueError(
                "FXCM_USERNAME and FXCM_PASSWORD are required. "
                "Set them via environment variables, or configure via:\n"
                "  python switch_account.py --add   # 添加账号\n"
                "  python switch_account.py --use <name>  # 切换账号"
            )
        if not self.webhook_token:
            raise ValueError(
                "WEBHOOK_TOKEN is required. "
                "Set it in config.json or WEBHOOK_TOKEN environment variable."
            )


# 单例
_instance = None


def get_config():
    global _instance
    if _instance is None:
        _instance = Config()
    return _instance
