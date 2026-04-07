"""
请求验证模块
- Webhook Token 验证
- JSON 必填字段 + 枚举值校验
- TradingView 纯文本消息解析
"""

import re
from typing import Dict, Any, Optional

from config import get_config
from symbols import is_valid_symbol
from logger import get_logger


_logger = get_logger("trading")


class ValidationError(Exception):
    def __init__(self, code: str, message: str, field: Optional[str] = None):
        self.code = code
        self.message = message
        self.field = field
        super().__init__(message)


def verify_token(token: str) -> bool:
    if not token:
        raise ValidationError("MISSING_TOKEN", "Token is required", "token")
    cfg = get_config()
    if token != cfg.webhook_token:
        _logger.warning(f"Invalid token attempt: {token[:4]}***")
        raise ValidationError("INVALID_TOKEN", "Invalid webhook token", "token")
    return True


def parse_tradingview_text(message: str) -> Dict[str, Any]:
    """
    解析 TradingView Pine Script 填充后的纯文本消息
    格式: Ripster EMA Clouds AI Strategy v1 (...)订单BUY@1成交EUR/USD。新策略仓位1
    """
    result = {}

    # 打印原始消息，方便调试
    # 提取方向和手数: 订单BUY@1  或 订单buy@2
    m = re.search(r'订单([A-Za-z]+)@(\d+)', message)
    if m:
        result["direction"] = m.group(1).upper()
        result["amount"] = int(m.group(2)) * 1000  # 1手=1000 units

    # 提取品种: 成交EUR/USD 或 成交XAUUSD
    m2 = re.search(r'成交([A-Za-z]+/[A-Za-z]+|[A-Za-z]{3,6})', message)
    if m2:
        result["symbol"] = m2.group(1).upper()

    # 提取新策略仓位
    m3 = re.search(r'新策略仓位(\d+)', message)
    if m3:
        result["position_size"] = int(m3.group(1))

    return result


def validate_message(data: Any) -> Dict[str, Any]:
    """
    自动识别 JSON 或纯文本，解析并校验
    """
    if isinstance(data, dict):
        return _validate_json(data)

    if isinstance(data, str):
        text = data.strip()
        if not text:
            raise ValidationError("INVALID_JSON", "Empty request body")

        parsed = parse_tradingview_text(text)
        if not parsed:
            raise ValidationError("INVALID_JSON", f"Cannot parse message: {text[:80]}")

        if "direction" not in parsed:
            raise ValidationError("MISSING_FIELD", "direction not found in message", "direction")
        direction = parsed["direction"].upper()
        direction_map = {"B": "BUY", "S": "SELL"}
        if direction in direction_map:
            direction = direction_map[direction]
        if direction not in ("BUY", "SELL"):
            raise ValidationError("INVALID_DIRECTION", f"Invalid direction: {direction}", "direction")

        if "symbol" not in parsed:
            raise ValidationError("MISSING_FIELD", "symbol not found in message", "symbol")
        symbol = parsed["symbol"]
        if not is_valid_symbol(symbol):
            raise ValidationError("INVALID_SYMBOL", f"Invalid symbol: {symbol}", "symbol")

        if "amount" not in parsed:
            raise ValidationError("MISSING_FIELD", "amount not found in message", "amount")
        amount = parsed["amount"]
        if amount <= 0:
            raise ValidationError("INVALID_AMOUNT", f"Invalid amount: {amount}", "amount")

        _logger.info(f"Parsed text message: {parsed}")

        return {
            "symbol": symbol,
            "direction": direction,
            "amount": amount,
            "order_type": "MARKET",
            "rate": None,
            "stop_rate": None,
            "limit_rate": None,
            "trade_id": None,
        }

    raise ValidationError("INVALID_JSON", "Request body must be JSON or plain text")


def _validate_json(data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise ValidationError("INVALID_JSON", "Request body must be a JSON object")

    required = ["symbol", "direction", "amount"]
    for field in required:
        if field not in data or data[field] is None:
            raise ValidationError("MISSING_FIELD", f"Missing required field: {field}", field)

    verify_token(str(data.get("token", "")))

    symbol = str(data["symbol"]).strip()
    if not is_valid_symbol(symbol):
        raise ValidationError("INVALID_SYMBOL", f"Invalid symbol format: {symbol}", "symbol")

    direction = str(data["direction"]).strip().upper()
    # 接受全写 BUY/SELL 或单字母 B/S
    direction_map = {"B": "BUY", "S": "SELL"}
    if direction in direction_map:
        direction = direction_map[direction]
    if direction not in ("BUY", "SELL"):
        raise ValidationError("INVALID_DIRECTION", f"Invalid direction: {direction}, must be BUY or SELL", "direction")

    try:
        amount = int(data["amount"])
    except (ValueError, TypeError):
        raise ValidationError("INVALID_AMOUNT", f"Amount must be an integer: {data['amount']}", "amount")

    if amount <= 0:
        raise ValidationError("INVALID_AMOUNT", f"Amount must be positive: {amount}", "amount")

    order_type = str(data.get("order_type", "MARKET")).strip().upper()
    valid_order_types = ("MARKET", "STOP", "LIMIT")
    if order_type not in valid_order_types:
        raise ValidationError("INVALID_ORDER_TYPE", f"Invalid order_type: {order_type}", "order_type")

    rate = data.get("rate")
    if rate is not None:
        try:
            rate = float(rate)
        except (ValueError, TypeError):
            raise ValidationError("INVALID_RATE", f"Rate must be a number: {rate}", "rate")
        if rate <= 0:
            raise ValidationError("INVALID_RATE", f"Rate must be positive: {rate}", "rate")

    stop_rate = data.get("stop_rate")
    if stop_rate is not None:
        try:
            stop_rate = float(stop_rate)
        except (ValueError, TypeError):
            raise ValidationError("INVALID_STOP_RATE", "stop_rate must be a number", "stop_rate")

    limit_rate = data.get("limit_rate")
    if limit_rate is not None:
        try:
            limit_rate = float(limit_rate)
        except (ValueError, TypeError):
            raise ValidationError("INVALID_LIMIT_RATE", "limit_rate must be a number", "limit_rate")

    return {
        "symbol": symbol,
        "direction": direction,
        "amount": amount,
        "order_type": order_type,
        "rate": rate,
        "stop_rate": stop_rate,
        "limit_rate": limit_rate,
        "trade_id": data.get("trade_id"),
    }
