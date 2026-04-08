"""
请求验证模块
- Webhook Token 验证
- JSON 必填字段 + 枚举值校验
- TradingView 纯文本消息解析
- position/prev_position 状态机判断（开仓/平仓/反手）
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

    # ── 1. 识别动作类型（开仓 / 平仓）─────────────────────────────
    close_patterns = [
        r'出场', r'平仓', r'EXIT', r'CLOSE', r'FLATTEN',
        r'多头出场', r'空头出场', r'多头平仓', r'空头平仓',
    ]
    is_close = any(re.search(p, message, re.IGNORECASE) for p in close_patterns)
    if is_close:
        result["action"] = "CLOSE"
        m_pos = re.search(r'新策略仓位(\d+)', message)
        if m_pos:
            result["position_size"] = int(m_pos.group(1))
        m_sym = re.search(r'成交([A-Za-z]+/[A-Za-z]+|[A-Za-z]{3,6})', message)
        if m_sym:
            result["symbol"] = m_sym.group(1).upper()
        return result

    # 开仓: 订单BUY@1, 订单SELL@2, 做多, 做空, 入场
    open_patterns = [
        r'订单([A-Za-z]+)@(\d+)',
        r'做多@(\d+)', r'做空@(\d+)', r'入场@(\d+)',
        r'多单开@(\d+)', r'空单开@(\d+)',
    ]
    for pat in open_patterns:
        m = re.search(pat, message)
        if m:
            if len(m.groups()) == 2:
                result["direction"] = m.group(1).upper()
                result["amount"] = int(m.group(2))
            else:
                result["amount"] = int(m.group(1))
                if re.search(r'做多|多单开|入场.*多|BUY', message, re.IGNORECASE):
                    result["direction"] = "BUY"
                elif re.search(r'做空|空单开|入场.*空|SELL', message, re.IGNORECASE):
                    result["direction"] = "SELL"
            break

    m_sym = re.search(r'成交([A-Za-z]+/[A-Za-z]+|[A-Za-z]{3,6})', message)
    if m_sym:
        result["symbol"] = m_sym.group(1).upper()

    m_pos = re.search(r'新策略仓位(\d+)', message)
    if m_pos:
        result["position_size"] = int(m_pos.group(1))

    return result


# ──────────────────────────────────────────────────────────────
# 安全类型转换（不抛异常，鲁棒性）
# ──────────────────────────────────────────────────────────────

def _to_str(val, default=""):
    if val is None:
        return default
    s = str(val).strip()
    return s if s else default


def _to_float(val):
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
# position 状态机：判断最终交易动作
# ──────────────────────────────────────────────────────────────
# position / prev_position 枚举: "long", "short", "flat"
# action 枚举: "buy", "sell"

def _determine_action(
    action: str,
    position: Optional[str],
    prev_position: Optional[str],
) -> str:
    """
    结合 action + position + prev_position 确定最终动作
    返回: OPEN_LONG / OPEN_SHORT / CLOSE_LONG / CLOSE_SHORT / NO_ACTION
    """
    pos = _to_str(position).lower()
    prev = _to_str(prev_position).lower()
    act = _to_str(action).lower()

    # 状态机
    if pos == "long" and prev != "long":
        return "OPEN_LONG"
    elif pos == "short" and prev != "short":
        return "OPEN_SHORT"
    elif pos == "flat" and prev == "long":
        return "CLOSE_LONG"
    elif pos == "flat" and prev == "short":
        return "CLOSE_SHORT"
    elif pos == "flat" and prev == "flat":
        return "NO_ACTION"  # 无仓位变化（重复信号等）
    else:
        # 反手: 先平后开，等价于 CLOSE + OPEN
        # 简化处理：若 action=buy 则为 OPEN_SHORT（空转多）
        # 但 FXCM 需要分两步，这里保守返回 NO_ACTION 让上层处理
        return "NO_ACTION"


def validate_message(data: Any) -> Dict[str, Any]:
    if isinstance(data, dict):
        return _validate_json(data)

    if isinstance(data, str):
        text = data.strip()
        if not text:
            raise ValidationError("INVALID_JSON", "Empty request body")

        parsed = parse_tradingview_text(text)
        if not parsed:
            raise ValidationError("INVALID_JSON", f"Cannot parse message: {text[:80]}")

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
                "trade_action": "CLOSE_LONG",  # 纯文本模式统一视为 CLOSE_LONG
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
            raise ValidationError("MISSING_FIELD", "amount is required", "amount")
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
            "trade_action": "OPEN_LONG" if direction == "BUY" else "OPEN_SHORT",
        }

    raise ValidationError("INVALID_JSON", "Request body must be JSON or plain text")


# ──────────────────────────────────────────────────────────────
# JSON 校验（position 状态机 + order_id 去重）
# ──────────────────────────────────────────────────────────────

# order_id 去重集合（进程内去重，TradingView 幂等机制兜底）
_processed_ids: set = set()


def _validate_json(data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise ValidationError("INVALID_JSON", "Request body must be a JSON object")

    # ── 字段别名兼容 ──────────────────────────────────────────
    # id -> order_id（去重用）
    if "id" in data and "order_id" not in data:
        data = dict(data)
        data["order_id"] = data.pop("id")
    # action (TradingView) -> direction
    if "action" in data and "direction" not in data:
        data = dict(data)
        data["direction"] = data.pop("action")
    if "side" in data and "direction" not in data:
        data = dict(data)
        data["direction"] = data.pop("side")
    # bot_sec / api_key / secret -> token
    for alias in ("bot_sec", "api_key", "secret"):
        if alias in data and "token" not in data:
            data = dict(data)
            data["token"] = data.pop(alias)
    # price -> rate
    if "price" in data and "rate" not in data:
        data = dict(data)
        data["rate"] = data.pop("price")
    # contracts -> amount
    if "contracts" in data and "amount" not in data:
        data = dict(data)
        data["amount"] = data.pop("contracts")
    # now_position_amount / position_size -> position_size
    if "now_position_amount" in data and "position_size" not in data:
        data = dict(data)
        data["position_size"] = data.pop("now_position_amount")

    # ── token 校验 ─────────────────────────────────────────────
    token = _to_str(data.get("token"))
    if token:
        try:
            verify_token(token)
        except ValidationError:
            raise

    # ── order_id 去重 ─────────────────────────────────────────
    order_id = _to_str(data.get("id"))
    if order_id and order_id in _processed_ids:
        raise ValidationError("DUPLICATE_ORDER", f"Duplicate order_id: {order_id}", "id")
    if order_id:
        _processed_ids.add(order_id)
        # 限制集合大小，防止内存泄漏
        if len(_processed_ids) > 10000:
            _processed_ids.clear()

    # ── 必填字段 ───────────────────────────────────────────────
    direction_raw = _to_str(data.get("direction"))
    symbol_raw = _to_str(data.get("symbol"))
    amount_raw = _to_int(data.get("amount"))

    if not direction_raw:
        raise ValidationError("MISSING_FIELD", "direction/action is required", "direction")
    if not symbol_raw:
        raise ValidationError("MISSING_FIELD", "symbol is required", "symbol")
    if amount_raw is None:
        raise ValidationError("MISSING_FIELD", "amount/contracts is required", "amount")

    # ── 品种 ─────────────────────────────────────────────────
    symbol = symbol_raw.upper()
    if symbol.startswith("{{") and symbol.endswith("}}"):
        raise ValidationError("INVALID_SYMBOL", f"Symbol not filled: {symbol}", "symbol")
    if not is_valid_symbol(symbol):
        raise ValidationError("INVALID_SYMBOL", f"Invalid symbol: {symbol}", "symbol")

    # ── 方向（TradingView action 只有 buy/sell）───────────────
    direction = direction_raw.upper()
    direction_map = {"B": "BUY", "S": "SELL"}
    if direction in direction_map:
        direction = direction_map[direction]
    if direction not in ("BUY", "SELL"):
        raise ValidationError("INVALID_DIRECTION", f"Invalid direction: {direction}, must be BUY or SELL", "direction")

    # ── 手数 ─────────────────────────────────────────────────
    amount = amount_raw
    if amount <= 0:
        raise ValidationError("INVALID_AMOUNT", f"Invalid amount: {amount}", "amount")

    # ── 订单类型（JSON 模式不支持纯 CLOSE，由 position 状态机决定）─
    order_type_raw = _to_str(data.get("order_type"), "MARKET").upper()
    valid_order_types = ("MARKET", "STOP", "LIMIT")
    if order_type_raw not in valid_order_types:
        raise ValidationError("INVALID_ORDER_TYPE", f"Invalid order_type: {order_type_raw}", "order_type")

    # ── 价格（容错）──────────────────────────────────────────
    rate = _to_float(data.get("rate"))
    stop_rate = _to_float(data.get("stop_rate"))
    limit_rate = _to_float(data.get("limit_rate"))

    # ── position 状态机 ───────────────────────────────────────
    position = _to_str(data.get("position"))
    prev_position = _to_str(data.get("prev_position"))
    trade_action = _determine_action(direction, position, prev_position)

    _logger.info(
        f"action={direction} position={position} prev_position={prev_position} "
        f"-> trade_action={trade_action}"
    )

    return {
        "symbol": symbol,
        "direction": direction,
        "amount": amount,
        "order_type": order_type_raw,
        "rate": rate,
        "stop_rate": stop_rate,
        "limit_rate": limit_rate,
        "trade_id": _to_str(data.get("trade_id")) or None,
        "position_size": _to_int(data.get("position_size")),
        "order_id": order_id,
        # 状态机解析结果
        "trade_action": trade_action,   # OPEN_LONG / OPEN_SHORT / CLOSE_LONG / CLOSE_SHORT / NO_ACTION
        "position": position or None,
        "prev_position": prev_position or None,
    }
