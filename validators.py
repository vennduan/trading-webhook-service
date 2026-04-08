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


# ──────────────────────────────────────────────────────────────
# 安全类型转换（不抛异常，鲁棒性）
# ──────────────────────────────────────────────────────────────

def _to_str(val, default=""):
    """安全转字符串，None/空返回默认值"""
    if val is None:
        return default
    s = str(val).strip()
    return s if s else default


def _to_float(val):
    """安全转 float，空/None/非法返回 None"""
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none"):
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _to_int(val):
    """安全转 int，空/None/非法返回 None"""
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return None


# ──────────────────────────────────────────────────────────────
# JSON 校验（已增强鲁棒性）
# ──────────────────────────────────────────────────────────────

def _validate_json(data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise ValidationError("INVALID_JSON", "Request body must be a JSON object")

    # ── 字段别名兼容（webhook.json 等多种模板）───────────────
    if "side" in data and "direction" not in data:
        data = dict(data)
        data["direction"] = data.pop("side")
    if "bot_sec" in data and "token" not in data:
        data = dict(data)
        data["token"] = data.pop("bot_sec")
    if "api_key" in data and "token" not in data:
        data = dict(data)
        data["token"] = data.pop("api_key")
    if "price" in data and "rate" not in data:
        data = dict(data)
        data["rate"] = data.pop("price")
    if "now_position_amount" in data and "position_size" not in data:
        data = dict(data)
        data["position_size"] = data.pop("now_position_amount")

    # ── token 校验（空 token 静默跳过，不强制）──────────────
    token = _to_str(data.get("token"))
    if token:
        try:
            verify_token(token)
        except ValidationError:
            raise

    # ── 必填字段容错（空值/未填充变量 → 明确错误）──────────
    direction_raw = _to_str(data.get("direction"))
    symbol_raw = _to_str(data.get("symbol"))
    amount_raw = _to_int(data.get("amount"))

    if not direction_raw:
        raise ValidationError("MISSING_FIELD", "direction/side is required", "direction")
    if not symbol_raw:
        raise ValidationError("MISSING_FIELD", "symbol is required", "symbol")
    if amount_raw is None:
        raise ValidationError("MISSING_FIELD", "amount is required", "amount")

    # ── 品种（literal {{ticker}} 未填充视为无效）────────────
    symbol = symbol_raw.upper()
    if symbol.startswith("{{") and symbol.endswith("}}"):
        raise ValidationError("INVALID_SYMBOL", f"Symbol not filled: {symbol}", "symbol")
    if not is_valid_symbol(symbol):
        raise ValidationError("INVALID_SYMBOL", f"Invalid symbol: {symbol}", "symbol")

    # ── 方向 ───────────────────────────────────────────────
    direction = direction_raw.upper()
    direction_map = {"B": "BUY", "S": "SELL"}
    if direction in direction_map:
        direction = direction_map[direction]
    if direction not in ("BUY", "SELL", "CLOSE"):
        raise ValidationError("INVALID_DIRECTION", f"Invalid direction: {direction}, must be BUY, SELL or CLOSE", "direction")

    # ── 手数 ───────────────────────────────────────────────
    amount = amount_raw
    if direction != "CLOSE" and amount <= 0:
        raise ValidationError("INVALID_AMOUNT", f"Invalid amount: {amount}", "amount")

    # ── 订单类型 ───────────────────────────────────────────
    order_type = _to_str(data.get("order_type"), "MARKET").upper()
    if direction == "CLOSE":
        order_type = "CLOSE"
    valid_order_types = ("MARKET", "STOP", "LIMIT", "CLOSE")
    if order_type not in valid_order_types:
        raise ValidationError("INVALID_ORDER_TYPE", f"Invalid order_type: {order_type}", "order_type")

    # ── 价格（容错：空/非法不报错，返回 None）───────────────
    rate = _to_float(data.get("rate"))
    stop_rate = _to_float(data.get("stop_rate"))
    limit_rate = _to_float(data.get("limit_rate"))

    return {
        "symbol": symbol,
        "direction": direction,
        "amount": amount,
        "order_type": order_type,
        "rate": rate,
        "stop_rate": stop_rate,
        "limit_rate": limit_rate,
        "trade_id": _to_str(data.get("trade_id")) or None,
        "position_size": _to_int(data.get("position_size")),
    }
