"""
配置管理模块
支持 config.json + 环境变量双重配置
敏感信息(FXCM_USERNAME, FXCM_PASSWORD)必须通过环境变量传入
"""

import os
import json
from pathlib import Path
from typing import Optional


BASE_DIR = Path(__file__).parent.resolve()
CONFIG_FILE = BASE_DIR / "config.json"


class Config:
    _instance: Optional["Config"] = None

    def __init__(self):
        self.fxcm_url: str = ""
        self.fxcm_username: str = ""
        self.fxcm_password: str = ""
        self.fxcm_connection: str = "Demo"
        self.fxcm_session_timeout: int = 300

        self.webhook_token: str = ""
        self.webhook_timeout: float = 2.5

        self.server_host: str = "0.0.0.0"
        self.server_port: int = 5000

        self.log_level: str = "INFO"

        self.risk_max_position_size: int = 100000
        self.risk_max_daily_trades: int = 50
        self.risk_max_loss_per_trade_pct: float = 2.0

        self._load()

    def _load(self):
        # Load config.json if exists
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            fxcm = data.get("fxcm", {})
            self.fxcm_url = fxcm.get("url", "www.fxcorporate.com/Hosts.jsp")
            self.fxcm_connection = fxcm.get("connection", "Demo")
            self.fxcm_session_timeout = fxcm.get("session_timeout_seconds", 300)

            webhook = data.get("webhook", {})
            self.webhook_timeout = webhook.get("timeout_seconds", 2.5)

            server = data.get("server", {})
            self.server_host = server.get("host", "0.0.0.0")
            self.server_port = server.get("port", 5000)

            logging_cfg = data.get("logging", {})
            self.log_level = logging_cfg.get("level", "INFO")

            risk = data.get("risk", {})
            self.risk_max_position_size = risk.get("max_position_size", 100000)
            self.risk_max_daily_trades = risk.get("max_daily_trades", 50)
            self.risk_max_loss_per_trade_pct = risk.get("max_loss_per_trade_pct", 2.0)

        # Environment variables override (sensitive fields MUST come from env)
        self.fxcm_username = os.environ.get("FXCM_USERNAME", self.fxcm_username)
        self.fxcm_password = os.environ.get("FXCM_PASSWORD", self.fxcm_password)
        self.webhook_token = os.environ.get("WEBHOOK_TOKEN", self.webhook_token)

        if not self.fxcm_username or not self.fxcm_password:
            raise ValueError(
                "FXCM_USERNAME and FXCM_PASSWORD environment variables are required. "
                "Set them before starting the server."
            )

        if not self.webhook_token:
            raise ValueError(
                "WEBHOOK_TOKEN environment variable is required."
            )

    @classmethod
    def get_instance(cls) -> "Config":
        if cls._instance is None:
            cls._instance = cls()
        return cls


def get_config() -> Config:
    """Shortcut for getting the singleton config instance."""
    return Config.get_instance()
