"""
交易品种映射模块
TradingView 格式: EUR/USD (slash)
FXCM 格式:       EURUSD (no slash)
"""

from typing import Dict, Optional
from logger import get_logger

logger = get_logger("trading")


# 常用品种映射表（静态 fallback）
_TV_TO_FXCM: Dict[str, str] = {
    "EUR/USD": "EUR/USD",
    "GBP/USD": "GBP/USD",
    "USD/JPY": "USD/JPY",
    "USD/CHF": "USD/CHF",
    "AUD/USD": "AUD/USD",
    "USD/CAD": "USD/CAD",
    "NZD/USD": "NZD/USD",
    "EUR/JPY": "EUR/JPY",
    "GBP/JPY": "GBP/JPY",
    "EUR/GBP": "EUR/GBP",
    "AUD/JPY": "AUD/JPY",
    "EUR/CHF": "EUR/CHF",
    "XAU/USD": "XAU/USD",  # Gold
    "NATGAS": "NATGAS",
    "GER30": "GER30",
    "US30": "US30",
    "USTECH": "USTECH",
    "UK100": "UK100",
}

_FXCM_TO_TV: Dict[str, str] = {v: k for k, v in _TV_TO_FXCM.items()}


def tv_to_fxcm(tv_symbol: str) -> str:
    """
    TradingView 格式 -> FXCM 格式
    EUR/USD -> EUR/USD (FXCM也用 slash 格式，Python API兼容)
    XAUUSD -> XAU/USD (无slash的贵金属需转换)
    """
    if not tv_symbol:
        raise ValueError("Symbol cannot be empty")
    s = tv_symbol.strip()
    # 无slash的贵金属转换
    slashless_map = {
        "XAUUSD": "XAU/USD",
        "XAUXAG": "XAU/XAG",
        "XAGEUR": "XAU/EUR",
    }
    if s in slashless_map:
        return slashless_map[s]
    return s


def fxcm_to_tv(fxcm_symbol: str) -> str:
    """FXCM 格式 -> TradingView 格式"""
    return fxcm_symbol.strip()


def normalize_symbol(symbol: str) -> str:
    """统一格式：去除空格、大写化"""
    return symbol.strip().upper()


def is_valid_symbol(symbol: str) -> bool:
    """简单格式校验"""
    if not symbol:
        return False
    s = symbol.strip().upper()
    # 允许的格式: EUR/USD, NATGAS, XAU/USD
    if "/" in s:
        parts = s.split("/")
        return len(parts) == 2 and all(p.isalpha() for p in parts)
    return s.isalpha()


def format_for_display(symbol: str) -> str:
    """友好显示格式"""
    return symbol.upper()


# 缓存 FXCM 返回的可用品种
_offer_cache: Optional[Dict[str, str]] = None


def cache_offers(offers: list):
    """从 FXCM 返回的 offer 列表缓存品种映射"""
    global _offer_cache
    _offer_cache = {}
    for offer in offers:
        instr = offer.get("instrument", "")
        if instr:
            _offer_cache[instr.upper()] = instr
    logger.info(f"Cached {len(_offer_cache)} offers from FXCM")


def get_all_fxcm_symbols() -> list:
    """返回所有已缓存的 FXCM 品种"""
    if _offer_cache:
        return list(_offer_cache.values())
    # Return static list as fallback
    return list(_TV_TO_FXCM.values())
