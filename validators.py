"""
请求验证模块
- Webhook Token 验证
- JSON 必填字段 + 枚举值校验
- 格式校验
"""

from typing import Dict, Any, Tuple, Optional

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
    """验证 Webhook Token"""
    if not token:
        raise ValidationError("MISSING_TOKEN", "Token is required", "token")
    cfg = get_config()
    if token != cfg.webhook_token:
        _logger.warning(f"Invalid token attempt: {token[:4]}***")
        raise ValidationError("INVALID_TOKEN", "Invalid webhook token", "token")
    return True


def validate_json_schema(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    校验 TradingView 消息格式
    必填: symbol, direction, amount, token
    可选: order_type, rate, stop_rate, limit_rate
    """
    if not isinstance(data, dict):
        raise ValidationError("INVALID_JSON", "Request body must be a JSON object")

    # 必填字段
    required = ["symbol", "direction", "amount", "token"]
    for field in required:
        if field not in data or data[field] is None:
            raise ValidationError("MISSING_FIELD", f"Missing required field: {field}", field)

    # Token 验证
    verify_token(str(data.get("token", "")))

    # symbol 格式
    symbol = str(data["symbol"]).strip()
    if not is_valid_symbol(symbol):
        raise ValidationError("INVALID_SYMBOL", f"Invalid symbol format: {symbol}", "symbol")

    # direction 枚举
    direction = str(data["direction"]).strip().upper()
    if direction not in ("BUY", "SELL"):
        raise ValidationError(
            "INVALID_DIRECTION",
            f"Invalid direction: {direction}, must be BUY or SELL",
            "direction"
        )

    # amount 类型和范围
    try:
        amount = int(data["amount"])
    except (ValueError, TypeError):
        raise ValidationError("INVALID_AMOUNT", f"Amount must be an integer: {data['amount']}", "amount")

    if amount <= 0:
        raise ValidationError("INVALID_AMOUNT", f"Amount must be positive: {amount}", "amount")

    # order_type 枚举
    order_type = str(data.get("order_type", "MARKET")).strip().upper()
    valid_order_types = ("MARKET", "STOP", "LIMIT")
    if order_type not in valid_order_types:
        raise ValidationError(
            "INVALID_ORDER_TYPE",
            f"Invalid order_type: {order_type}, must be one of {valid_order_types}",
            "order_type"
        )

    # rate（STOP/LIMIT 单必填）
    rate = data.get("rate")
    if rate is not None:
        try:
            rate = float(rate)
        except (ValueError, TypeError):
            raise ValidationError("INVALID_RATE", f"Rate must be a number: {rate}", "rate")
        if rate <= 0:
            raise ValidationError("INVALID_RATE", f"Rate must be positive: {rate}", "rate")

    # stop_rate / limit_rate（可选，附加单用）
    stop_rate = data.get("stop_rate")
    limit_rate = data.get("limit_rate")

    if stop_rate is not None:
        try:
            stop_rate = float(stop_rate)
        except (ValueError, TypeError):
            raise ValidationError("INVALID_STOP_RATE", "stop_rate must be a number", "stop_rate")

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
        "trade_id": data.get("trade_id"),  # 附加单用
    }
