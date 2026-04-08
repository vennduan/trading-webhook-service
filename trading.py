"""
ForexConnect 交易逻辑封装
所有 FXCM 交易操作入口
包含重试机制（最多2次）
"""

import time
from typing import Optional, Dict, Any, List

from forexconnect import fxcorepy, ForexConnect, Common
from session_manager import get_session
from logger import get_logger, get_trade_logger
from symbols import tv_to_fxcm, is_valid_symbol, normalize_symbol


_logger = get_logger("trading")
_trade_logger = get_trade_logger()


# 重试装饰器
def retry(max_attempts: int = 2, delay: float = 1.0):
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_err = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_err = e
                    if attempt < max_attempts - 1:
                        _logger.warning(
                            f"{func.__name__} attempt {attempt+1} failed: {e}, "
                            f"retrying in {delay}s..."
                        )
                        time.sleep(delay)
                    else:
                        _logger.error(f"{func.__name__} failed after {max_attempts} attempts")
            raise last_err
        return wrapper
    return decorator


# ──────────────────────────────────────────────────────────────
# 账户 & 报价查询
# ──────────────────────────────────────────────────────────────

@retry(max_attempts=2)
def get_account(account_id: Optional[str] = None) -> Dict[str, Any]:
    """获取账户信息"""
    sm = get_session()
    sm.ensure_connected()

    fx = sm.fx
    if account_id:
        account = Common.get_account(fx, account_id)
    else:
        login_rules = fx.login_rules
        accounts_response = login_rules.get_table_refresh_response(ForexConnect.ACCOUNTS)
        reader = fx.session.response_reader_factory.create_reader(
            accounts_response
        )
        if reader.size == 0:
            raise ValueError("No accounts found")
        account = reader.get_row(0)

    return {
        "account_id": account.get_cell(0),
        "balance": account.get_cell(3),
        "equity": account.get_cell(4),
        "margin": account.get_cell(5),
        "free_margin": account.get_cell(5),
        "margin_level": None,
        "currency": "USD",
    }


@retry(max_attempts=2)
def get_offer(symbol: str) -> Optional[Dict[str, Any]]:
    """获取品种报价"""
    sm = get_session()
    sm.ensure_connected()

    fx = sm.fx
    fxcm_symbol = tv_to_fxcm(symbol)

    login_rules = fx.login_rules
    offers_response = login_rules.get_table_refresh_response(ForexConnect.OFFERS)
    reader = fx.session.response_reader_factory.create_reader(offers_response)

    for i in range(reader.size):
        row = reader.get_row(i)
        if str(row.get_cell(1)) == fxcm_symbol:
            return {
                "offer_id": row.get_cell(0),
                "instrument": row.get_cell(1),
                "bid": row.get_cell(3),
                "ask": row.get_cell(4),
                "pip_cost": row.get_cell(11),
                "trade_precision": row.get_cell(14),
            }
    return None


@retry(max_attempts=2)
def get_positions(account_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    查询所有持仓（Python 3.7 ForexConnect 兼容）
    使用 fx.get_table().get_row() 代替 response_reader，避免 response_reader API 不稳定
    """
    sm = get_session()
    sm.ensure_connected()

    fx = sm.fx
    trades_table = fx.get_table(ForexConnect.TRADES)

    positions = []
    try:
        total = trades_table.size
    except Exception:
        return []

    for i in range(total):
        try:
            row = trades_table.get_row(i)
        except Exception:
            break
        if row is None:
            break
        try:
            row_account_id = row.account_id
            row_instrument = row.instrument
            row_trade_id = row.trade_id
            row_offer_id = row.offer_id
            row_amount = row.amount
            row_buy_sell = row.buy_sell
            row_open_rate = row.open_rate
            row_pl = row.pl
        except Exception:
            break
        if account_id and row_account_id != account_id:
            continue
        positions.append({
            "trade_id": row_trade_id,
            "offer_id": row_offer_id,
            "instrument": row_instrument,
            "amount": row_amount,
            "buy_sell": row_buy_sell,
            "open_rate": row_open_rate,
            "pl": row_pl,
            "account_id": row_account_id,
        })

    return positions


@retry(max_attempts=2)
def get_orders(account_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """查询所有挂单"""
    sm = get_session()
    sm.ensure_connected()

    fx = sm.fx
    orders_table = fx.get_table(ForexConnect.ORDERS)
    reader = fx.session.response_reader_factory.create_reader(
        orders_table.get_refresh_response()
    )

    orders = []
    for i in range(reader.size):
        row = reader.get_row(i)
        if account_id and row.account_id != account_id:
            continue
        orders.append({
            "order_id": row.order_id,
            "offer_id": row.offer_id,
            "instrument": row.instrument,
            "type": row.type,
            "buy_sell": row.buy_sell,
            "rate": row.rate,
            "amount": row.amount,
            "status": row.status,
            "account_id": row.account_id,
        })
    return orders


# ──────────────────────────────────────────────────────────────
# 订单工具
# ──────────────────────────────────────────────────────────────

def _get_account_and_offer(symbol: str, account_id: Optional[str] = None):
    """获取账户和报价，内部用"""
    fxcm_symbol = tv_to_fxcm(symbol)
    account = get_account(account_id)
    offer = get_offer(fxcm_symbol)
    if offer is None:
        raise ValueError(f"Invalid symbol: {symbol}")
    return account, offer


def _calculate_amount(symbol: str, lots: int, account: Dict) -> int:
    """lots 转成 units"""
    sm = get_session()
    fx = sm.fx
    login_rules = fx.login_rules
    trading_settings = login_rules.trading_settings_provider
    base_unit_size = trading_settings.get_base_unit_size(symbol, account)
    return base_unit_size * lots


# ──────────────────────────────────────────────────────────────
# 市价单
# ──────────────────────────────────────────────────────────────

@retry(max_attempts=2)
def place_market_order(
    symbol: str,
    direction: str,
    amount: int,
    account_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    市价单 BUY or SELL
    direction: "BUY" or "SELL"
    amount: 单位（不是手数）
    """
    sm = get_session()
    sm.ensure_connected()

    account, offer = _get_account_and_offer(symbol, account_id)

    fx = sm.fx
    fxcm_symbol = tv_to_fxcm(symbol)

    buy_sell = fxcorepy.Constants.BUY if direction.upper() == "BUY" else fxcorepy.Constants.SELL

    request = fx.create_order_request(
        command=fxcorepy.Constants.Commands.CREATE_ORDER,
        order_type=fxcorepy.Constants.Orders.TRUE_MARKET_OPEN,
        OFFER_ID=offer["offer_id"],
        ACCOUNT_ID=account["account_id"],
        BUY_SELL=buy_sell,
        AMOUNT=amount,
        RATE=offer["ask"] if buy_sell == fxcorepy.Constants.BUY else offer["bid"],
    )

    resp = fx.send_request(request)
    order_id = resp.order_id

    _trade_logger.info(
        f"MARKET ORDER | direction={direction} | symbol={symbol} | "
        f"amount={amount} | order_id={order_id}"
    )

    return {
        "order_id": order_id,
        "symbol": symbol,
        "direction": direction,
        "amount": amount,
        "rate": offer["ask"] if direction.upper() == "BUY" else offer["bid"],
    }


# ──────────────────────────────────────────────────────────────
# 止损挂单 / 限价挂单
# ──────────────────────────────────────────────────────────────

@retry(max_attempts=2)
def place_stop_order(
    symbol: str,
    direction: str,
    amount: int,
    rate: float,
    account_id: Optional[str] = None,
) -> Dict[str, Any]:
    """止损挂单（STOP ENTRY）"""
    return _place_entry_order(symbol, direction, amount, rate, "STOP", account_id)


@retry(max_attempts=2)
def place_limit_order(
    symbol: str,
    direction: str,
    amount: int,
    rate: float,
    account_id: Optional[str] = None,
) -> Dict[str, Any]:
    """限价挂单（LIMIT ENTRY）"""
    return _place_entry_order(symbol, direction, amount, rate, "LIMIT", account_id)


def _place_entry_order(
    symbol: str,
    direction: str,
    amount: int,
    rate: float,
    order_type: str,  # "STOP" or "LIMIT"
    account_id: Optional[str] = None,
) -> Dict[str, Any]:
    sm = get_session()
    sm.ensure_connected()

    account, offer = _get_account_and_offer(symbol, account_id)
    fx = sm.fx

    buy_sell = fxcorepy.Constants.BUY if direction.upper() == "BUY" else fxcorepy.Constants.SELL
    fc_order_type = (
        fxcorepy.Constants.Orders.STOP_ENTRY if order_type == "STOP"
        else fxcorepy.Constants.Orders.LIMIT_ENTRY
    )

    request = fx.create_order_request(
        command=fxcorepy.Constants.Commands.CREATE_ORDER,
        order_type=fc_order_type,
        OFFER_ID=offer["offer_id"],
        ACCOUNT_ID=account["account_id"],
        BUY_SELL=buy_sell,
        AMOUNT=amount,
        RATE=rate,
    )

    resp = fx.send_request(request)
    order_id = resp.order_id

    _trade_logger.info(
        f"{order_type} ORDER | direction={direction} | symbol={symbol} | "
        f"amount={amount} | rate={rate} | order_id={order_id}"
    )

    return {
        "order_id": order_id,
        "status": resp.status,
        "symbol": symbol,
        "direction": direction,
        "amount": amount,
        "rate": rate,
        "order_type": order_type,
    }


# ──────────────────────────────────────────────────────────────
# 附加止损 / 限价到持仓
# ──────────────────────────────────────────────────────────────

@retry(max_attempts=2)
def attach_stop_to_position(
    symbol: str,
    trade_id: str,
    rate: float,
    buy_sell: str,  # 方向（需与持仓相反）
    amount: Optional[int] = None,
    account_id: Optional[str] = None,
) -> Dict[str, Any]:
    """给持仓附加止损"""
    return _attach_sl_to_position(symbol, trade_id, rate, buy_sell, "S", amount, account_id)


@retry(max_attempts=2)
def attach_limit_to_position(
    symbol: str,
    trade_id: str,
    rate: float,
    buy_sell: str,
    amount: Optional[int] = None,
    account_id: Optional[str] = None,
) -> Dict[str, Any]:
    """给持仓附加限价（止盈）"""
    return _attach_sl_to_position(symbol, trade_id, rate, buy_sell, "L", amount, account_id)


def _attach_sl_to_position(
    symbol: str,
    trade_id: str,
    rate: float,
    buy_sell: str,
    order_type: str,  # "S" = Stop, "L" = Limit
    amount: Optional[int],
    account_id: Optional[str],
) -> Dict[str, Any]:
    sm = get_session()
    sm.ensure_connected()

    account, offer = _get_account_and_offer(symbol, account_id)
    fx = sm.fx

    if amount is None:
        positions = get_positions(account["account_id"])
        pos = next((p for p in positions if p["trade_id"] == trade_id), None)
        if pos is None:
            raise ValueError(f"Position {trade_id} not found")
        amount = abs(pos["amount"])

    request = fx.create_order_request(
        order_type=order_type,
        OFFER_ID=offer["offer_id"],
        ACCOUNT_ID=account["account_id"],
        BUY_SELL=buy_sell.upper(),
        AMOUNT=amount,
        RATE=rate,
        TRADE_ID=trade_id,
    )

    resp = fx.send_request(request)
    order_id = resp.order_id

    _trade_logger.info(
        f"ATTACH {order_type} | trade_id={trade_id} | symbol={symbol} | "
        f"amount={amount} | rate={rate} | order_id={order_id}"
    )

    return {
        "order_id": order_id,
        "status": resp.status,
        "trade_id": trade_id,
        "order_type": order_type,
        "rate": rate,
    }


# ──────────────────────────────────────────────────────────────
# 修改挂单
# ──────────────────────────────────────────────────────────────

@retry(max_attempts=2)
def edit_order(
    order_id: str,
    new_rate: float,
    symbol: Optional[str] = None,
    account_id: Optional[str] = None,
) -> Dict[str, Any]:
    """修改挂单价格"""
    sm = get_session()
    sm.ensure_connected()

    fx = sm.fx
    offer = get_offer(symbol) if symbol else None

    request = fx.create_order_request(
        command=fxcorepy.Constants.Commands.EDIT_ORDER,
        order_type="S",
        OFFER_ID=offer["offer_id"] if offer else None,
        ACCOUNT_ID=account_id,
        RATE=new_rate,
        ORDER_ID=order_id,
    )

    resp = fx.send_request(request)

    _trade_logger.info(
        f"EDIT ORDER | order_id={order_id} | new_rate={new_rate}"
    )

    return {
        "order_id": order_id,
        "status": resp.status,
        "new_rate": new_rate,
    }


# ──────────────────────────────────────────────────────────────
# 取消挂单
# ──────────────────────────────────────────────────────────────

@retry(max_attempts=2)
def cancel_order(order_id: str) -> Dict[str, Any]:
    """取消挂单"""
    sm = get_session()
    sm.ensure_connected()

    fx = sm.fx
    orders = get_orders()
    order = next((o for o in orders if o["order_id"] == order_id), None)
    if not order:
        raise ValueError(f"Order {order_id} not found")

    request = fx.create_order_request(
        command=fxcorepy.Constants.Commands.CREATE_ORDER,
        order_type="CR",
        OFFER_ID=order["offer_id"],
        ACCOUNT_ID=order["account_id"],
        ORDER_ID=order_id,
    )

    resp = fx.send_request(request)

    _trade_logger.info(f"CANCEL ORDER | order_id={order_id}")

    return {
        "order_id": order_id,
        "status": resp.status,
    }


# ──────────────────────────────────────────────────────────────
# 平仓
# ──────────────────────────────────────────────────────────────

@retry(max_attempts=2)
def close_position(trade_id: str, amount: Optional[int] = None) -> Dict[str, Any]:
    """
    平掉指定持仓
    trade_id: FXCM trade_id
    amount:   平仓数量，不传则全部平
    """
    sm = get_session()
    sm.ensure_connected()

    fx = sm.fx
    positions = get_positions()
    trade = next((p for p in positions if p["trade_id"] == trade_id), None)
    if not trade:
        raise ValueError(f"Trade {trade_id} not found, no open position")

    close_amount = amount if amount is not None else abs(trade["amount"])
    # FXCM 平仓用 SELL 关闭多头，用 BUY 关闭空头
    buy_sell = fxcorepy.Constants.SELL if trade["buy_sell"] == "B" else fxcorepy.Constants.BUY

    # TRUE_MARKET_CLOSE = 不需要 rate，FXCM 自动以市场价平仓
    request = fx.create_order_request(
        command=fxcorepy.Constants.Commands.CREATE_ORDER,
        order_type=fxcorepy.Constants.Orders.TRUE_MARKET_CLOSE,
        OFFER_ID=trade["offer_id"],
        ACCOUNT_ID=trade["account_id"],
        BUY_SELL=buy_sell,
        AMOUNT=close_amount,
        TRADE_ID=trade_id,
    )
    resp = fx.send_request(request)

    # resp 可能有 order_id 属性，status 不一定存在
    try:
        status = resp.status
    except AttributeError:
        status = None

    _trade_logger.info(
        f"CLOSE POSITION | trade_id={trade_id} | amount={close_amount} "
        f"| instrument={trade['instrument']} | status={status}"
    )

    return {
        "trade_id": trade_id,
        "status": status,
        "closed_amount": close_amount,
    }


@retry(max_attempts=2)
def close_all_positions(symbol: Optional[str] = None) -> Dict[str, Any]:
    """
    平掉所有持仓，或指定品种的全部持仓
    symbol: 可选，如 "EUR/USD"，不传则全部平
    """
    sm = get_session()
    sm.ensure_connected()

    fx = sm.fx
    positions = get_positions()
    if symbol:
        fxcm_sym = tv_to_fxcm(symbol)
        positions = [p for p in positions if tv_to_fxcm(p["instrument"]) == fxcm_sym]

    if not positions:
        return {"closed": [], "message": "No open positions"}

    closed = []
    errors = []
    for pos in positions:
        try:
            result = close_position(pos["trade_id"])
            closed.append({"trade_id": pos["trade_id"], "status": result["status"]})
        except Exception as e:
            errors.append({"trade_id": pos["trade_id"], "error": str(e)})

    return {"closed": closed, "errors": errors}


# ──────────────────────────────────────────────────────────────
# 统一入口：按 order_type 分发
# ──────────────────────────────────────────────────────────────

def execute_trade(
    symbol: str,
    direction: str,
    amount: int,
    order_type: str = "MARKET",
    rate: Optional[float] = None,
    trade_id: Optional[str] = None,
    account_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    统一交易入口
    order_type: MARKET / STOP / LIMIT
    """
    direction = direction.upper()
    order_type = order_type.upper()

    if not is_valid_symbol(symbol):
        raise ValueError(f"Invalid symbol: {symbol}")

    if direction not in ("BUY", "SELL"):
        raise ValueError(f"Invalid direction: {direction}, must be BUY or SELL")

    if amount <= 0:
        raise ValueError(f"Amount must be positive: {amount}")

    if order_type == "MARKET":
        return place_market_order(symbol, direction, amount, account_id)

    elif order_type == "STOP":
        if rate is None:
            raise ValueError("STOP order requires rate parameter")
        return place_stop_order(symbol, direction, amount, rate, account_id)

    elif order_type == "LIMIT":
        if rate is None:
            raise ValueError("LIMIT order requires rate parameter")
        return place_limit_order(symbol, direction, amount, rate, account_id)

    else:
        raise ValueError(f"Unknown order_type: {order_type}")
