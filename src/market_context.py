"""
Market Context — detect market from ticker, provide market-specific defaults,
and currency formatting utilities.

Supported markets:
  - US (default): NYSE, NASDAQ — USD
  - KR: KOSPI (.KS), KOSDAQ (.KQ) — KRW
"""

from typing import Dict, Any, Optional


# ═══════════════════════════════════════════════════════════
# MARKET DETECTION
# ═══════════════════════════════════════════════════════════

def detect_market(ticker: str) -> str:
    """
    Detect market from ticker suffix or exchange code.
    Returns "KR" for Korean, "JP" for Japanese, "CN" for Chinese, "US" otherwise.

    Korean tickers:  005930.KS (KOSPI), 035720.KQ (KOSDAQ)
    Japanese tickers: 7203.T (Tokyo)
    Chinese tickers:  600519.SS (Shanghai), 000001.SZ (Shenzhen)
    """
    t = ticker.upper().strip()
    if t.endswith(".KS") or t.endswith(".KQ"):
        return "KR"
    if t.endswith(".T"):
        return "JP"
    if t.endswith(".SS") or t.endswith(".SZ"):
        return "CN"
    return "US"


def detect_market_from_data(data: Dict[str, Any]) -> str:
    """
    Detect market from fetched stock data (currency / exchange fields).
    """
    currency = data.get("currency", "USD")
    exchange = data.get("exchange", "")

    if currency == "KRW":
        return "KR"
    if currency == "JPY":
        return "JP"
    if currency == "CNY":
        return "CN"
    if exchange in ("KSC", "KOE", "KSE"):
        return "KR"
    if exchange in ("JPX", "TYO", "TSE"):
        return "JP"
    if exchange in ("SHH", "SHZ", "SSE", "SZSE"):
        return "CN"
    return detect_market(data.get("ticker", ""))


def is_korean_ticker(ticker: str) -> bool:
    return detect_market(ticker) == "KR"

def is_japanese_ticker(ticker: str) -> bool:
    return detect_market(ticker) == "JP"

def is_chinese_ticker(ticker: str) -> bool:
    return detect_market(ticker) == "CN"


# ═══════════════════════════════════════════════════════════
# MARKET DEFAULTS
# ═══════════════════════════════════════════════════════════

_US_DEFAULTS = {
    "currency": "USD",
    "currency_symbol": "$",
    "tax_rate": 0.21,
    "risk_free_rate": 0.043,
    "equity_risk_premium": 0.055,
    "terminal_growth_rate": 0.025,
    "default_wacc": 0.10,
    "benchmark_index": "^GSPC",
    "benchmark_ticker": "SPY",
    "vix_ticker": "^VIX",
    "treasury_10y_ticker": "^TNX",
    "trading_days": 252,
}

_KR_DEFAULTS = {
    "currency": "KRW",
    "currency_symbol": "₩",
    "tax_rate": 0.242,          # 한국 법인세 최고세율 24.2%
    "risk_free_rate": 0.035,    # 국고채 10년물 ~3.5%
    "equity_risk_premium": 0.065,  # 한국 ERP ~6.5%
    "terminal_growth_rate": 0.02,  # 한국 잠재성장률 ~2%
    "default_wacc": 0.10,
    "benchmark_index": "^KS11",    # KOSPI
    "benchmark_ticker": "^KS11",
    "vix_ticker": None,            # V-KOSPI200은 yfinance 미지원
    "treasury_10y_ticker": None,   # 한국 국고채는 yfinance 미지원
    "trading_days": 252,           # 한국도 약 252일
}


_JP_DEFAULTS = {
    "currency": "JPY",
    "currency_symbol": "¥",
    "tax_rate": 0.3062,         # 일본 법인세 실효세율 ~30.62%
    "risk_free_rate": 0.01,     # JGB 10년물 ~1.0%
    "equity_risk_premium": 0.065,
    "terminal_growth_rate": 0.01,
    "default_wacc": 0.08,
    "benchmark_index": "^N225",
    "benchmark_ticker": "^N225",
    "vix_ticker": None,
    "treasury_10y_ticker": None,
    "trading_days": 245,
}

_CN_DEFAULTS = {
    "currency": "CNY",
    "currency_symbol": "¥",
    "tax_rate": 0.25,           # 중국 법인세 25%
    "risk_free_rate": 0.025,    # 중국 국채 10년물 ~2.5%
    "equity_risk_premium": 0.07,
    "terminal_growth_rate": 0.03,
    "default_wacc": 0.10,
    "benchmark_index": "000001.SS",
    "benchmark_ticker": "000001.SS",
    "vix_ticker": None,
    "treasury_10y_ticker": None,
    "trading_days": 244,
}


def get_market_defaults(market: str = "US") -> Dict[str, Any]:
    """Return market-specific default parameters."""
    if market == "KR":
        return dict(_KR_DEFAULTS)
    if market == "JP":
        return dict(_JP_DEFAULTS)
    if market == "CN":
        return dict(_CN_DEFAULTS)
    return dict(_US_DEFAULTS)


def get_dcf_overrides(market: str = "US") -> Dict[str, Any]:
    """
    Return DCF parameter overrides for a given market.
    These can be merged with DCF_DEFAULTS via {**DCF_DEFAULTS, **overrides}.
    """
    defaults = get_market_defaults(market)
    return {
        "risk_free_rate": defaults["risk_free_rate"],
        "equity_risk_premium": defaults["equity_risk_premium"],
        "tax_rate": defaults["tax_rate"],
        "terminal_growth_rate": defaults["terminal_growth_rate"],
    }


# ═══════════════════════════════════════════════════════════
# CURRENCY FORMATTING
# ═══════════════════════════════════════════════════════════

def get_currency_symbol(currency: str = "USD") -> str:
    """Return the symbol for a given currency code."""
    return {"USD": "$", "KRW": "₩", "JPY": "¥", "CNY": "¥"}.get(currency, currency + " ")


def format_price(value, currency: str = "USD", default: str = "N/A") -> str:
    """
    Format a stock price with appropriate currency symbol and decimals.
    USD: $178.72   KRW: ₩68,500
    """
    if value is None:
        return default
    try:
        v = float(value)
        sym = get_currency_symbol(currency)
        if currency == "KRW":
            return f"{sym}{v:,.0f}"
        if currency == "JPY":
            return f"{sym}{v:,.0f}"
        return f"{sym}{v:,.2f}"
    except (ValueError, TypeError):
        return default


def format_market_cap(value, currency: str = "USD", default: str = "N/A") -> str:
    """
    Format market cap with appropriate scale.
    USD: $1.2T / $450.3B / $12.5M
    KRW: 405.3조원 / 3,450억원 / 125억원
    """
    if value is None:
        return default
    try:
        v = float(value)
        if currency == "KRW":
            if abs(v) >= 1e12:
                return f"{v/1e12:,.1f}조원"
            elif abs(v) >= 1e8:
                return f"{v/1e8:,.0f}억원"
            else:
                return f"₩{v:,.0f}"
        else:
            sym = get_currency_symbol(currency)
            if abs(v) >= 1e12:
                return f"{sym}{v/1e12:.1f}T"
            elif abs(v) >= 1e9:
                return f"{sym}{v/1e9:.1f}B"
            elif abs(v) >= 1e6:
                return f"{sym}{v/1e6:.0f}M"
            return f"{sym}{v:,.0f}"
    except (ValueError, TypeError):
        return default


def format_money(value, currency: str = "USD", default: str = "N/A") -> str:
    """
    Format a monetary value (general purpose — for revenue, debt, etc.).
    USD: $1.2T / $450.3B / $12.5M
    KRW: 1.2조원 / 3,450억원
    """
    return format_market_cap(value, currency, default)


def format_stmt_value(value, currency: str = "USD", default: str = "N/A") -> str:
    """
    Format financial statement values with scale label.
    USD: $ millions   KRW: 억원
    """
    if value is None:
        return default
    try:
        v = float(value)
        if currency == "KRW":
            return f"{v/1e8:,.0f}"  # 억원 단위
        return f"{v/1e6:,.0f}"      # $ millions
    except (ValueError, TypeError):
        return default


def get_stmt_unit_label(currency: str = "USD") -> str:
    """Return the label for financial statement unit."""
    if currency == "KRW":
        return "(억원)"
    return "($ millions)"


def get_chart_price_label(currency: str = "USD") -> str:
    """Return Y-axis label for price charts."""
    sym = get_currency_symbol(currency)
    return f"Price ({sym})"


def get_chart_value_label(currency: str = "USD") -> str:
    """Return Y-axis label for value charts (revenue, etc.)."""
    if currency == "KRW":
        return "조원"
    return "Billions ($)"


def get_chart_nav_label(currency: str = "USD") -> str:
    """Return Y-axis label for NAV charts."""
    sym = get_currency_symbol(currency)
    return f"NAV ({sym})"


def format_chart_tick(value, currency: str = "USD") -> str:
    """Format a chart tick value."""
    if currency == "KRW":
        return f"{value:.1f}조"
    return f"${value:.1f}B"


def get_fair_value_col_header(currency: str = "USD") -> str:
    """Column header for fair value tables."""
    sym = get_currency_symbol(currency)
    return f"Fair Value ({sym})"
