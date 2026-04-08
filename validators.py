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
    支持: 开仓 BUY/SELL, 平仓 CLOSE/EXIT, 做多/做空/出场/入场
    """
    result = {}

    # ── 1. 识别动作类型（开仓 / 平仓）─────────────────────────────
    # 平仓信号: 出场, 平仓, EXIT, CLOSE, CLOSEALL, flatten
    close_patterns = [
        r'出场', r'平仓', r'EXIT', r'CLOSE', r'FLATTEN',
        r'多头出场', r'空头出场', r'多头平仓', r'空头平仓',
    ]
    is_close = any(re.search(p, message, re.IGNORECASE) for p in close_patterns)
    if is_close:
        result["action"] = "CLOSE"
        # 平仓消息可能带手数或仓位信息
        m_pos = re.search(r'新策略仓位(\d+)', message)
        if m_pos:
            result["position_size"] = int(m_pos.group(1))
        # 品种提取
        m_sym = re.search(r'成交([A-Za-z]+/[A-Za-z]+|[A-Za-z]{3,6})', message)
        if m_sym:
            result["symbol"] = m_sym.group(1).upper()
        return result

    # 开仓信号: 订单BUY@1, 订单SELL@2
    # 也支持中文: 做多, 做空, 入场
    open_patterns = [
        r'订单([A-Za-z]+)@(\d+)',          # 订单BUY@1
        r'做多@(\d+)',                       # 做多@1
        r'做空@(\d+)',                       # 做空@1
        r'入场@(\d+)',                       # 入场@1
        r'多单开@(\d+)',                     # 多单开@1
        r'空单开@(\d+)',                     # 空单开@1
    ]
    for pat in open_patterns:
        m = re.search(pat, message)
        if m:
            if len(m.groups()) == 2:
                result["direction"] = m.group(1).upper()
                result["amount"] = int(m.group(2))
            else:
                # 入场/做多/做空 无手数字段，设为默认值
                result["amount"] = int(m.group(1))
                # 从消息判断方向
                if re.search(r'做多|多单开|入场.*多|BUY', message, re.IGNORECASE):
                    result["direction"] = "BUY"
                elif re.search(r'做空|空单开|入场.*空|SELL', message, re.IGNORECASE):
                    result["direction"] = "SELL"
            break

    # ── 2. 品种提取 ─────────────────────────────────────────────
    m_sym = re.search(r'成交([A-Za-z]+/[A-Za-z]+|[A-Za-z]{3,6})', message)
    if m_sym:
        result["symbol"] = m_sym.group(1).upper()

    # ── 3. 新策略仓位（持仓数量）──────────────────────────────────
    m_pos = re.search(r'新策略仓位(\d+)', message)
    if m_pos:
        result["position_size"] = int(m_pos.group(1))

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

        # ── 平仓信号 ───────────────────────────────────────────
        if parsed.get("action") == "CLOSE":
            symbol = parsed.get("symbol", "")
            if symbol and not is_valid_symbol(symbol):
                raise ValidationError("INVALID_SYMBOL", f"Invalid symbol: {symbol}", "symbol")
            _logger.info(f"Parsed close message: {parsed}")
            return {
                "symbol": symbol,
                "direction": "CLOSE",
                "amount": 0,
                "order_type": "CLOSE",
                "rate": None,
                "stop_rate": None,
                "limit_rate": None,
                "trade_id": None,
                "position_size": parsed.get("position_size"),
            }

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

    # ── 字段别名兼容（webhook.json 等多种模板）───────────────
    # side / direction 统一
    if "side" in data and "direction" not in data:
        data = dict(data)
        data["direction"] = data.pop("side")
    # bot_sec / api_key -> token
    if "bot_sec" in data and "token" not in data:
        data = dict(data)
        data["token"] = data.pop("bot_sec")
    if "api_key" in data and "token" not in data:
        data = dict(data)
        data["token"] = data.pop("api_key")
    # price -> rate
    if "price" in data and "rate" not in data:
        data = dict(data)
        data["rate"] = data.pop("price")
    # now_position_amount / position_size -> position_size（记录用，不影响业务）
    if "now_position_amount" in data and "position_size" not in data:
        data = dict(data)
        data["position_size"] = data.pop("now_position_amount")
    # 忽略多余字段: position, pre_position, bot_sec(已转token)

    required = ["symbol", "direction", "amount"]
    for field in required:
        if field not in data or data[field] is None:
            raise ValidationError("MISSING_FIELD", f"Missing required field: {field}", field)

    verify_token(str(data.get("token", "")))

    symbol = str(data["symbol"]).strip()
    if not is_valid_symbol(symbol):
        raise ValidationError("INVALID_SYMBOL", f"Invalid symbol format: {symbol}", "symbol")

    direction = str(data["direction"]).strip().upper()
    # 接受全写 BUY/SELL/CLOSE 或单字母 B/S
    direction_map = {"B": "BUY", "S": "SELL"}
    if direction in direction_map:
        direction = direction_map[direction]
    if direction not in ("BUY", "SELL", "CLOSE"):
        raise ValidationError("INVALID_DIRECTION", f"Invalid direction: {direction}, must be BUY, SELL or CLOSE", "direction")

    try:
        amount = int(data["amount"])
    except (ValueError, TypeError):
        raise ValidationError("INVALID_AMOUNT", f"Amount must be an integer: {data['amount']}", "amount")

    if direction != "CLOSE" and amount <= 0:
        raise ValidationError("INVALID_AMOUNT", f"Amount must be positive: {amount}", "amount")

    order_type = str(data.get("order_type", "MARKET")).strip().upper()
    if direction == "CLOSE":
        order_type = "CLOSE"
    valid_order_types = ("MARKET", "STOP", "LIMIT", "CLOSE")
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
