"""
Flask Webhook 服务
POST /webhook — 接收 TradingView 告警
GET  /health — 健康检查
GET  /account — 账户信息查询
"""

import uuid
import time
from flask import Flask, request, jsonify
from config import get_config
from logger import setup_logger, set_request_id, clear_request_id, get_logger, mask_sensitive
from session_manager import get_session
from validators import validate_message, ValidationError, _determine_action
from risk_manager import check_risk, record_trade, RiskLimitExceeded
from trading import execute_trade, get_account, close_all_positions, close_position, get_positions
from forexconnect.errors import RequestFailedError


# 初始化日志
setup_logger(level=get_config().log_level)
_logger = get_logger("trading")

app = Flask(__name__)


@app.before_request
def inject_request_id():
    """每个请求分配唯一ID"""
    req_id = str(uuid.uuid4())[:8]
    set_request_id(req_id)


@app.after_request
def log_response(response):
    """请求/响应日志"""
    clear_request_id()
    return response


# ──────────────────────────────────────────────────────────────
# 错误处理
# ──────────────────────────────────────────────────────────────

@app.errorhandler(ValidationError)
def handle_validation_error(e):
    return jsonify({
        "status": "error",
        "code": e.code,
        "message": e.message,
        "field": e.field,
    }), 400


@app.errorhandler(RiskLimitExceeded)
def handle_risk_error(e):
    return jsonify({
        "status": "error",
        "code": e.code,
        "message": e.message,
    }), 403


@app.errorhandler(Exception)
def handle_generic_error(e):
    _logger.exception(f"Unhandled error: {e}")
    return jsonify({
        "status": "error",
        "code": "INTERNAL_ERROR",
        "message": str(e),
    }), 500


# ──────────────────────────────────────────────────────────────
# 路由
# ──────────────────────────────────────────────────────────────

@app.route("/webhook", methods=["POST"])
def webhook():
    """
    接收 TradingView Webhook 告警，执行交易
    基于 position/prev_position 状态机判断开仓/平仓
    """
    _logger.warning(
        f"[WEBHOOK START] content_type={request.content_type} "
        f"content_length={request.content_length} remote_addr={request.remote_addr}"
    )
    cfg = get_config()

    # 解析请求体：优先 JSON，失败则用纯文本
    try:
        data = request.get_json(force=True, silent=True)
    except Exception:
        data = None

    if data is None:
        raw = request.get_data(as_text=True)
        if raw:
            _logger.info(f"Webhook received (text): {raw[:100]}")
            data = raw
        else:
            return jsonify({
                "status": "error",
                "code": "INVALID_JSON",
                "message": "Empty request body",
            }), 400

    _logger.info(f"Webhook received: {data}")

    # 验证并解析（返回 trade_action: OPEN_LONG/OPEN_SHORT/CLOSE_LONG/CLOSE_SHORT/NO_ACTION）
    params = validate_message(data)

    trade_action = params.get("trade_action", "NO_ACTION")
    symbol = params["symbol"]

    # ── NO_ACTION: 无仓位变化（重复信号/反手过渡态）──────────────────
    if trade_action == "NO_ACTION":
        _logger.info(
            f"No action: position={params.get('position')} "
            f"prev={params.get('prev_position')} action={params.get('direction')}"
        )
        return jsonify({
            "status": "success",
            "message": "no action (position unchanged)",
        }), 200

    try:
        # 确保 FXCM 连接
        sm = get_session()
        if not sm.ensure_connected():
            return jsonify({
                "status": "error",
                "code": "CONNECTION_ERROR",
                "message": "Failed to connect to FXCM",
            }), 503

        # ── prev_position 为空时 fallback 为 "flat"（首次信号正常行为）─
        prev = params.get("prev_position")
        if not prev:
            prev = "flat"
            params = dict(params)
            params["prev_position"] = "flat"
            trade_action = _determine_action(
                params["direction"], params["position"], "flat"
            )
            params["trade_action"] = trade_action
            trade_action = trade_action
            _logger.info(
                f"prev_position was empty, treated as flat -> trade_action={trade_action}"
            )

        # ── 风控检查（仅开仓过风控，平仓直接过）──────────────────
        if trade_action.startswith("OPEN"):
            check_risk(
                symbol=symbol,
                direction=params["direction"],
                amount=params["amount"],
                rate=params["rate"],
            )

        # ── 平仓：CLOSE_LONG / CLOSE_SHORT ───────────────────────
        if trade_action in ("CLOSE_LONG", "CLOSE_SHORT"):
            positions = get_positions()
            # buy_sell: "B"=多头, "S"=空头
            target_bs = "B" if trade_action == "CLOSE_LONG" else "S"
            to_close = [
                p for p in positions
                if p["instrument"] == symbol and p["buy_sell"] == target_bs
            ]
            if not to_close:
                _logger.info(f"No {trade_action} position for {symbol}")
                return jsonify({
                    "status": "success",
                    "message": f"no {trade_action} position for {symbol}",
                }), 200

            closed = []
            for pos in to_close:
                try:
                    result = close_position(pos["trade_id"])
                    closed.append({"trade_id": pos["trade_id"], "status": result["status"]})
                except Exception as e:
                    _logger.error(f"Failed to close trade {pos['trade_id']}: {e}")

            record_trade({
                "symbol": symbol,
                "direction": trade_action,
                "amount": 0,
                "order_type": "CLOSE",
                "rate": None,
                "order_id": None,
            })

            _logger.info(f"Close {trade_action}: {closed}")
            return jsonify({
                "status": "success",
                "message": f"{trade_action} executed: {closed}",
            }), 200

        # ── 开仓：OPEN_LONG / OPEN_SHORT ─────────────────────────
        result = execute_trade(
            symbol=symbol,
            direction=params["direction"],
            amount=params["amount"],
            order_type=params["order_type"],
            rate=params["rate"],
            trade_id=params.get("trade_id"),
        )

        record_trade({
            "symbol": symbol,
            "direction": params["direction"],
            "amount": params["amount"],
            "order_type": params["order_type"],
            "rate": params["rate"],
            "order_id": result.get("order_id"),
        })

        _logger.info(
            f"Trade executed: {trade_action} {params['amount']} "
            f"{symbol} @ {params['rate'] or 'MARKET'}"
        )

        return jsonify({
            "status": "success",
            "order_id": result.get("order_id"),
            "message": (
                f"{trade_action} {params['amount']} "
                f"{symbol} @ {params['rate'] or 'MARKET'} executed"
            ),
        }), 200

    except RiskLimitExceeded as e:
        return jsonify({
            "status": "error",
            "code": e.code,
            "message": e.message,
        }), 403

    except RequestFailedError as e:
        _logger.error(f"Trade rejected by FXCM: {e}")
        return jsonify({
            "status": "error",
            "code": "TRADE_REJECTED",
            "message": str(e),
        }), 400

    except Exception as e:
        _logger.exception(f"Trade execution failed: {e}")
        return jsonify({
            "status": "error",
            "code": "TRADE_FAILED",
            "message": str(e),
        }), 500


@app.route("/health", methods=["GET"])
def health():
    """健康检查（含 FXCM 会话状态）"""
    sm = get_session()
    fxcm_ok = sm.health_check()
    return jsonify({
        "status": "ok" if fxcm_ok else "degraded",
        "service": "trading-webhook-service",
        "fxcm": "connected" if fxcm_ok else "disconnected",
    }), 200 if fxcm_ok else 503


@app.route("/account", methods=["GET"])
def account():
    """查询账户信息（需 Token 验证）"""
    try:
        token = request.args.get("token") or (request.get_json() or {}).get("token", "")
        if not token:
            raise ValidationError("MISSING_TOKEN", "Token required", "token")
        from validators import verify_token
        verify_token(token)

        sm = get_session()
        if not sm.ensure_connected():
            return jsonify({
                "status": "error",
                "code": "CONNECTION_ERROR",
            }), 503

        acct = get_account()
        return jsonify({
            "status": "ok",
            "account": acct,
        }), 200

    except ValidationError as e:
        return jsonify({"status": "error", "code": e.code, "message": e.message}), 400
    except Exception as e:
        return jsonify({"status": "error", "code": "INTERNAL_ERROR", "message": str(e)}), 500


# ──────────────────────────────────────────────────────────────
# 启动
# ──────────────────────────────────────────────────────────────

def main():
    cfg = get_config()
    _logger.info(
        f"Starting trading-webhook-service on "
        f"{cfg.server_host}:{cfg.server_port}"
    )
    app.run(
        host=cfg.server_host,
        port=cfg.server_port,
        threaded=True,
    )


if __name__ == "__main__":
    main()
