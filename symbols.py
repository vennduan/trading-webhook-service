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
    EURUSD -> EUR/USD (无slash的Forex对需转换)
    XAUUSD -> XAU/USD (无slash的贵金属需转换)
    """
    if not tv_symbol:
        raise ValueError("Symbol cannot be empty")
    s = tv_symbol.strip().upper()

    # 无slash -> 有slash 批量映射表
    slashless_map = {
        # Forex (主要货币对)
        "EURUSD": "EUR/USD",
        "GBPUSD": "GBP/USD",
        "USDJPY": "USD/JPY",
        "USDCHF": "USD/CHF",
        "AUDUSD": "AUD/USD",
        "USDCAD": "USD/CAD",
        "NZDUSD": "NZD/USD",
        # Forex (交叉盘)
        "EURJPY": "EUR/JPY",
        "GBPJPY": "GBP/JPY",
        "EURGBP": "EUR/GBP",
        "AUDJPY": "AUD/JPY",
        "EURCHF": "EUR/CHF",
        "GBPAUD": "GBP/AUD",
        "GBPCAD": "GBP/CAD",
        "GBPNZD": "GBP/NZD",
        "NZDJPY": "NZD/JPY",
        "AUDCAD": "AUD/CAD",
        "AUDCHF": "AUD/CHF",
        "AUDNZD": "AUD/NZD",
        "CADJPY": "CAD/JPY",
        "CADCHF": "CAD/CHF",
        "CHFJPY": "CHF/JPY",
        "EURAUD": "EUR/AUD",
        "EURCAD": "EUR/CAD",
        "EURNZD": "EUR/NZD",
        "USDSGD": "USD/SGD",
        "USDHKD": "USD/HKD",
        "USDNOK": "USD/NOK",
        "USDSEK": "USD/SEK",
        "USDDKK": "USD/DKK",
        "USDPLN": "USD/PLN",
        "USDZAR": "USD/ZAR",
        "USDTRY": "USD/TRY",
        "USDCNY": "USD/CNY",
        "USDINR": "USD/INR",
        "USDMXN": "USD/MXN",
        # 贵金属
        "XAUUSD": "XAU/USD",
        "XAGUSD": "XAU/USD",
        "XAUXAG": "XAU/XAG",
        "XAGEUR": "XAU/EUR",
        # 指数 (TradingView格式 -> FXCM格式)
        "US30": "US30",
        "US100": "USTECH",
        "US500": "US500",
        "US2000": "US2000",
        "GER40": "GER40",
        "GERMAN": "GER40",
        "UK100": "UK100",
        "FRA40": "FRA40",
        "ESP35": "ESP35",
        "ITA40": "ITA40",
        "EUSTX50": "EUSTX50",
        "JPN225": "JPN225",
        "AUS200": "AUS200",
        "NAS100": "NAS100",
        # 大宗商品
        "NATGAS": "NATGAS",
        "USOIL": "USOIL",
        "UKOIL": "UKOIL",
        "XBRUSD": "XBRUSD",
        "XTIUSD": "XTIUSD",
        "COPPER": "COPPER",
        "CORN": "CORN",
        "WHEAT": "WHEAT",
        "SOYBEAN": "SOYBEAN",
        "SUGAR": "SUGAR",
        "COFFEE": "COFFEE",
        "COCOA": "COCOA",
        "Cotton": "COTTON",
        # 加密货币
        "BTCUSD": "BTC/USD",
        "ETHUSD": "ETH/USD",
        "LTCUSD": "LTC/USD",
        "XRPUSD": "XRP/USD",
        "BCHUSD": "BCH/USD",
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
    # 允许的格式: EUR/USD, NATGAS, GER30, XAU/USD
    if "/" in s:
        parts = s.split("/")
        return len(parts) == 2 and all(p.isalpha() for p in parts)
    # 非slash符号：必须包含数字 或 长度>3（排除单纯的3字母货币代码如EUR）
    return s.isalnum() and len(s) > 3


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
