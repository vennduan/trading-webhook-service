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
from validators import validate_message, ValidationError
from risk_manager import check_risk, record_trade, RiskLimitExceeded
from trading import execute_trade, get_account


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
    期望 JSON body
    """
    cfg = get_config()

    # 解析请求体：优先 JSON，失败则用纯文本
    try:
        data = request.get_json(force=True, silent=True)
    except Exception:
        data = None

    # 如果 JSON 解析失败，尝试获取原始文本
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

    # 验证请求（自动识别 JSON 或纯文本）
    params = validate_message(data)
    print(f"[DEBUG] params validated: {params}", flush=True)

    # 风控检查
    try:
        print(f"[DEBUG] calling check_risk...", flush=True)
        try:
            check_risk(
                symbol=params["symbol"],
                direction=params["direction"],
                amount=params["amount"],
                rate=params["rate"],
            )
        except RiskLimitExceeded:
            raise  # re-raise to outer handler
        except Exception as e:
            import sys
            sys.stderr.write(f"[ERROR] check_risk threw: {type(e).__name__}: {e}\n")
            sys.stderr.flush()
            import traceback; traceback.print_exc()
            sys.stderr.flush()
            raise
        print(f"[DEBUG] check_risk passed", flush=True)
    except RiskLimitExceeded as e:
        return jsonify({
            "status": "error",
            "code": e.code,
            "message": e.message,
        }), 403

    # 执行交易
    try:
        # 确保 FXCM 连接
        print(f"[DEBUG] getting session...", flush=True)
        sm = get_session()
        print(f"[DEBUG] session: {sm}, connected: {sm.is_connected()}", flush=True)
        if not sm.ensure_connected():
            return jsonify({
                "status": "error",
                "code": "CONNECTION_ERROR",
                "message": "Failed to connect to FXCM",
            }), 503

        # 核心：下单
        print(f"[DEBUG] calling execute_trade...", flush=True)
        result = execute_trade(
            symbol=params["symbol"],
            direction=params["direction"],
            amount=params["amount"],
            order_type=params["order_type"],
            rate=params["rate"],
            trade_id=params.get("trade_id"),
        )

        # 记录交易
        record_trade({
            "symbol": params["symbol"],
            "direction": params["direction"],
            "amount": params["amount"],
            "order_type": params["order_type"],
            "rate": params["rate"],
            "order_id": result.get("order_id"),
        })

        _logger.info(
            f"Trade executed: {params['direction']} {params['amount']} "
            f"{params['symbol']} @ {params['rate'] or 'MARKET'}"
        )

        return jsonify({
            "status": "success",
            "order_id": result.get("order_id"),
            "message": (
                f"{params['direction']} {params['amount']} "
                f"{params['symbol']} @ {params['rate'] or 'MARKET'} executed"
            ),
        }), 200

    except Exception as e:
        import sys
        sys.stderr.write(f"[ERROR] Trade execution failed: {e}\n")
        sys.stderr.flush()
        import traceback
        traceback.print_exc()
        sys.stderr.flush()
        _logger.exception(f"Trade execution failed: {e}")
        return jsonify({
            "status": "error",
            "code": "TRADE_FAILED",
            "message": str(e),
        }), 500


@app.route("/health", methods=["GET"])
def health():
    """健康检查"""
    return jsonify({
        "status": "ok",
        "service": "trading-webhook-service",
    }), 200


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
