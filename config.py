"""
配置管理模块
支持 config.json + 环境变量双重配置
敏感信息必须通过环境变量传入
"""

import os
import json
from pathlib import Path


BASE_DIR = Path(__file__).parent.resolve()
CONFIG_FILE = BASE_DIR / "config.json"


def _load_json_config():
    """从 config.json 加载非敏感配置"""
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
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

        # 环境变量
        self.fxcm_username = os.environ.get("FXCM_USERNAME", "")
        self.fxcm_password = os.environ.get("FXCM_PASSWORD", "")
        self.fxcm_connection = os.environ.get("FXCM_CONNECTION", self.fxcm_connection)
        self.fxcm_url = os.environ.get("FXCM_URL", self.fxcm_url)

        self.webhook_token = os.environ.get("WEBHOOK_TOKEN", self.webhook_token)

        # 验证必填项
        if not self.fxcm_username or not self.fxcm_password:
            raise ValueError(
                "FXCM_USERNAME and FXCM_PASSWORD are required. "
                "Set them via environment variables:\n"
                "  $env:FXCM_USERNAME='your_username'\n"
                "  $env:FXCM_PASSWORD='your_password'\n"
                "  $env:FXCM_CONNECTION='Demo'  # or 'Real'"
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
