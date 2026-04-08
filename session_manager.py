"""
FXCM 会话管理模块
单例模式：全局唯一 ForexConnect 实例
自动重连 + 优雅登出
"""

import time
import signal
import threading
from typing import Optional
from contextlib import contextmanager

from forexconnect import ForexConnect, fxcorepy, Common
from config import get_config
from logger import get_logger, get_trade_logger, mask_sensitive
import symbols


_logger = get_logger("trading")
_trade_logger = get_trade_logger()


class SessionManager:
    _instance: Optional["SessionManager"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._fx: Optional[ForexConnect] = None
        self._connected: bool = False
        self._login_lock = threading.Lock()
        self._last_login_time: float = 0
        self._session_timeout: int = 300
        self._registered_exit: bool = False

    def _get_fx(self) -> ForexConnect:
        if self._fx is None:
            self._fx = ForexConnect()
        return self._fx

    def login(self, force: bool = False) -> bool:
        """登录 FXCM，自动重连保护（30秒内不重复登录，但会话已死时强制重连）"""
        with self._login_lock:
            if self._connected and not force:
                return True

            # 防重复登录：30秒冷却（但 _fx 已销毁说明会话已死，强制重连）
            now = time.time()
            if not force and (now - self._last_login_time) < 30 and self._fx is not None:
                return self._connected

            cfg = get_config()

            try:
                _logger.info(
                    f"Logging in to FXCM {cfg.fxcm_connection} as "
                    f"{mask_sensitive(cfg.fxcm_username, 3)}"
                )
                fx = self._get_fx()
                fx.login(
                    user_id=cfg.fxcm_username,
                    password=cfg.fxcm_password,
                    url=cfg.fxcm_url,
                    connection=cfg.fxcm_connection,
                    session_id=None,
                    pin=None,
                )
                self._connected = True
                self._last_login_time = now
                self._session_timeout = cfg.fxcm_session_timeout

                # 缓存可用品种
                self._cache_offers(fx)

                _logger.info("FXCM login successful")
                self._register_exit_handlers()
                return True

            except Exception as e:
                _logger.error(f"FXCM login failed: {e}")
                self._connected = False
                return False

    def _cache_offers(self, fx: ForexConnect):
        """获取并缓存 FXCM 可用品种"""
        try:
            offers_response = fx.login_rules.get_table_refresh_response(ForexConnect.OFFERS)
            reader = fx.session.response_reader_factory.create_reader(
                offers_response
            )
            offers = []
            for i in range(reader.size):
                row = reader.get_row(i)
                offers.append({"instrument": row.instrument, "offer_id": row.offer_id})
            symbols.cache_offers(offers)
        except Exception as e:
            _logger.warning(f"Failed to cache offers: {e}")

    def logout(self):
        """主动登出"""
        with self._login_lock:
            if not self._connected:
                return
            try:
                _logger.info("Logging out from FXCM")
                self._fx.logout()
            except Exception as e:
                _logger.warning(f"Logout error: {e}")
            finally:
                self._connected = False
                self._fx = None

    def ensure_connected(self) -> bool:
        """确保已连接，未连接则尝试登录"""
        if self._connected:
            return True
        return self.login()

    def is_connected(self) -> bool:
        return self._connected

    def health_check(self) -> bool:
        """
        健康检查：尝试访问会话，确认连接真实可用（非僵尸会话）
        """
        if not self._connected or self._fx is None:
            return False
        try:
            self._fx.get_table(ForexConnect.OFFERS)
            return True
        except Exception:
            # 会话已死，标记断开，由 ensure_connected 触发重连
            self._connected = False
            return False

    @property
    def fx(self) -> ForexConnect:
        """获取 ForexConnect 实例（需确保已登录）"""
        if not self._connected:
            raise RuntimeError("Not connected to FXCM. Call ensure_connected() first.")
        return self._get_fx()

    def _register_exit_handlers(self):
        """注册 Ctrl+C / SIGTERM 优雅退出"""
        if self._registered_exit:
            return
        self._registered_exit = True

        def _exit_handler(signum, frame):
            _logger.info(f"Received signal {signum}, shutting down...")
            self.logout()
            exit(0)

        try:
            signal.signal(signal.SIGINT, _exit_handler)
            signal.signal(signal.SIGTERM, _exit_handler)
        except (ValueError, OSError):
            # Windows 不支持某些信号
            pass

    @classmethod
    def get_instance(cls) -> "SessionManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance


@contextmanager
def fxcm_session():
    """上下文管理器：自动确保登录，退出时自动登出"""
    sm = SessionManager.get_instance()
    if not sm.ensure_connected():
        raise RuntimeError("Failed to connect to FXCM")
    try:
        yield sm
    finally:
        pass  # 不主动 logout，保持会话复用


def get_session() -> SessionManager:
    return SessionManager.get_instance()
