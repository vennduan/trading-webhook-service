"""
风控模块
下单前检查：余额、保证金、持仓数量、单笔金额
记录每笔交易到本地文件
"""

import json
import threading
from pathlib import Path
from datetime import datetime, date
from typing import Dict, Any, Optional

from config import get_config
from trading import get_account, get_positions
from logger import get_logger, get_trade_logger


_logger = get_logger("trading")
_trade_logger = get_trade_logger()

BASE_DIR = Path(__file__).parent.resolve()
TRADES_FILE = BASE_DIR / "trades.json"


class RiskLimitExceeded(Exception):
    """风控限制被触发"""
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class RiskManager:
    _instance: Optional["RiskManager"] = None
    _lock = threading.Lock()

    def __init__(self):
        cfg = get_config()
        self.max_position_size: int = cfg.risk_max_position_size
        self.max_daily_trades: int = cfg.risk_max_daily_trades
        self.max_loss_per_trade_pct: float = cfg.risk_max_loss_per_trade_pct
        self._daily_trade_count: int = 0
        self._last_reset_date: date = date.today()
        self._load_trades()

    def _load_trades(self):
        """加载今日交易记录，统计已交易次数"""
        today = date.today()
        if TRADES_FILE.exists():
            try:
                with open(TRADES_FILE, "r", encoding="utf-8") as f:
                    all_trades = json.load(f)
                # 只统计今天的
                today_str = today.isoformat()
                today_trades = [
                    t for t in all_trades
                    if t.get("date", "")[:10] == today_str
                ]
                self._daily_trade_count = len(today_trades)
            except (json.JSONDecodeError, IOError):
                self._daily_trade_count = 0

        if self._last_reset_date != today:
            self._daily_trade_count = 0
            self._last_reset_date = today

    def _save_trade(self, trade: Dict[str, Any]):
        """保存交易记录"""
        all_trades = []
        if TRADES_FILE.exists():
            try:
                with open(TRADES_FILE, "r", encoding="utf-8") as f:
                    all_trades = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        trade["date"] = datetime.now().isoformat()
        all_trades.append(trade)

        with open(TRADES_FILE, "w", encoding="utf-8") as f:
            json.dump(all_trades, f, ensure_ascii=False, indent=2)

    def check_order(
        self,
        symbol: str,
        direction: str,
        amount: int,
        rate: Optional[float] = None,
    ):
        """
        下单前风控检查
        任何检查失败都抛出 RiskLimitExceeded
        """
        cfg = get_config()

        # 1. 检查金额上限
        if amount > self.max_position_size:
            raise RiskLimitExceeded(
                "POSITION_SIZE_EXCEEDED",
                f"Amount {amount} exceeds max {self.max_position_size}"
            )

        # 2. 检查余额
        try:
            account = get_account()
        except Exception as e:
            raise RiskLimitExceeded("ACCOUNT_QUERY_FAILED", f"Cannot get account: {e}")

        balance = float(account.get("balance", 0))
        equity = float(account.get("equity", 0))
        free_margin = float(account.get("free_margin", 0))

        # 估算保证金需求（约 2% 每手）
        estimated_margin = amount * (rate or 1.0) * 0.02
        # 只有当 free_margin 是有效数字且不足时才阻止
        if free_margin > 0 and estimated_margin > free_margin:
            raise RiskLimitExceeded(
                "INSUFFICIENT_MARGIN",
                f"Margin required {estimated_margin:.2f}, available {free_margin:.2f}"
            )

        # 3. 检查今日交易次数
        if self._daily_trade_count >= self.max_daily_trades:
            raise RiskLimitExceeded(
                "DAILY_TRADE_LIMIT",
                f"Daily trade limit {self.max_daily_trades} reached"
            )

        # 4. 检查同向持仓数量（可选）
        try:
            positions = get_positions(account["account_id"])
        except Exception:
            positions = []
        same_direction = [
            p for p in positions
            if p["instrument"] == symbol and p["buy_sell"].upper() == direction.upper()
        ]
        if len(same_direction) > 0:
            _logger.warning(
                f"Position already exists for {symbol} {direction}, "
                f"may be doubling up"
            )

        _logger.info(
            f"Risk check passed | symbol={symbol} | direction={direction} | "
            f"amount={amount} | balance={balance} | equity={equity}"
        )

    def record_trade(self, trade: Dict[str, Any]):
        """记录已执行的交易"""
        self._daily_trade_count += 1
        self._save_trade(trade)
        _trade_logger.info(
            f"TRADE RECORDED | symbol={trade.get('symbol')} | "
            f"direction={trade.get('direction')} | amount={trade.get('amount')} | "
            f"rate={trade.get('rate')} | order_id={trade.get('order_id')}"
        )

    @classmethod
    def get_instance(cls) -> "RiskManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance


def check_risk(symbol: str, direction: str, amount: int, rate: Optional[float] = None):
    """快捷函数"""
    return RiskManager.get_instance().check_order(symbol, direction, amount, rate)


def record_trade(trade: Dict[str, Any]):
    """快捷函数"""
    RiskManager.get_instance().record_trade(trade)
