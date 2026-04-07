"""
日志模块
- 按天分割日志到 logs/ 目录
- 交易相关日志独立记录到 trades.log
- 不记录敏感信息（密码、Token）
"""

import logging
import uuid
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler
from typing import Optional


BASE_DIR = Path(__file__).parent.resolve()
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# 日志格式
LOG_FORMAT = "%(asctime)s [%(levelname)s] [%(request_id)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 全局 request_id，Flask 中间件设置
_request_id: Optional[str] = None


class RequestIdFilter(logging.Filter):
    """每个日志行注入 request_id"""

    def filter(self, record):
        record.request_id = _request_id or "-"
        return True


def set_request_id(req_id: str):
    global _request_id
    _request_id = req_id


def clear_request_id():
    global _request_id
    _request_id = None


def _make_handler(
    filename: str, level: str = "INFO"
) -> TimedRotatingFileHandler:
    handler = TimedRotatingFileHandler(
        filename=str(LOGS_DIR / filename),
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    handler.setLevel(getattr(logging, level.upper()))
    fmt = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    handler.setFormatter(fmt)
    handler.addFilter(RequestIdFilter())
    return handler


def setup_logger(name: str = "trading", level: str = "INFO") -> logging.Logger:
    """
    创建 logger 实例，同时写入：
    - logs/app.log      : 所有日志
    - logs/trades.log   : 仅交易相关（包含订单/持仓/盈亏）
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    logger.handlers.clear()

    # 避免重复添加 handler
    if not logger.handlers:
        # 主日志
        app_handler = _make_handler("app.log", level)
        logger.addHandler(app_handler)

        # 交易日志（额外写入 trades.log）
        trade_logger = logging.getLogger(f"{name}.trades")
        trade_logger.setLevel(logging.INFO)
        trade_handler = _make_handler("trades.log", "INFO")
        trade_logger.addHandler(trade_handler)

    return logger


def get_logger(name: str = "trading") -> logging.Logger:
    return logging.getLogger(name)


def get_trade_logger() -> logging.Logger:
    return logging.getLogger("trading.trades")


def mask_sensitive(text: str, show_len: int = 4) -> str:
    """脱敏：只显示末尾 N 个字符"""
    if not text or len(text) <= show_len:
        return "***"
    return "*" * (len(text) - show_len) + text[-show_len:]
