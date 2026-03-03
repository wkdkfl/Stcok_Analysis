"""
Screener Cache — manages universe ticker lists and lightweight stock data caching.
Fetches S&P 500 / NASDAQ 100 constituent lists from Wikipedia.
Caches scan results to JSON files with 24h TTL.
"""

import json
import os
import time
import threading
import tempfile
from collections import OrderedDict
from datetime import datetime, timedelta
from io import StringIO
from typing import Dict, List, Any, Optional

import pandas as pd
import requests
import yfinance as yf

# ── Path setup ───────────────────────────────────────────
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.normpath(os.path.join(_BASE_DIR, "..", ".."))
_DATA_DIR = os.path.join(_PROJECT_DIR, "data")
_CACHE_DIR = os.path.join(_DATA_DIR, "cache")
_UNIVERSE_DIR = os.path.join(_DATA_DIR, "universe")

SCREENER_CACHE_TTL = 86400  # 24 hours

_WIKI_HEADERS = {
    "User-Agent": "StockScreener/1.0 (stock-screener-app; Python/pandas)",
    "Accept": "text/html",
}


def _ensure_dirs():
    """Create cache and universe directories if they don't exist."""
    os.makedirs(_CACHE_DIR, exist_ok=True)
    os.makedirs(_UNIVERSE_DIR, exist_ok=True)


# ═══════════════════════════════════════════════════════════
# UNIVERSE MANAGEMENT
# ═══════════════════════════════════════════════════════════

def load_universe(name: str) -> List[Dict[str, str]]:
    """
    Load a universe ticker list.
    Priority: disk cache → Wikipedia fetch → hardcoded fallback.
    """
    _ensure_dirs()
    cache_file = os.path.join(_UNIVERSE_DIR, f"{name}.json")

    # 1. Try disk cache
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list) and len(data) > 10:
                return data
        except Exception:
            pass

    # 2. Fetch from Wikipedia
    tickers = _fetch_from_wikipedia(name)
    if tickers and len(tickers) > 10:
        _save_universe_cache(cache_file, tickers)
        return tickers

    # 3. Hardcoded fallback
    return _get_fallback_tickers(name)


def refresh_universe(name: str) -> List[Dict[str, str]]:
    """Force refresh universe from Wikipedia."""
    _ensure_dirs()
    cache_file = os.path.join(_UNIVERSE_DIR, f"{name}.json")

    tickers = _fetch_from_wikipedia(name)
    if tickers and len(tickers) > 10:
        _save_universe_cache(cache_file, tickers)
        return tickers

    # Fall back to existing cache
    return load_universe(name)


def _save_universe_cache(path: str, data: List[Dict]):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _fetch_from_wikipedia(name: str) -> List[Dict[str, str]]:
    """Fetch ticker list from Wikipedia or KRX sources."""
    try:
        if name == "sp500":
            return _fetch_sp500_wikipedia()
        elif name == "nasdaq100":
            return _fetch_nasdaq100_wikipedia()
        elif name == "sp500_nasdaq100":
            sp500 = _fetch_sp500_wikipedia()
            nasdaq100 = _fetch_nasdaq100_wikipedia()
            # Merge, dedup by ticker
            seen = {t["ticker"] for t in sp500}
            for t in nasdaq100:
                if t["ticker"] not in seen:
                    sp500.append(t)
                    seen.add(t["ticker"])
            return sp500
        elif name == "kospi200":
            return _fetch_kospi200()
        elif name == "kosdaq150":
            return _fetch_kosdaq150()
        return []
    except Exception:
        return []


def _fetch_sp500_wikipedia() -> List[Dict[str, str]]:
    """Fetch S&P 500 constituents from Wikipedia."""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    resp = requests.get(url, headers=_WIKI_HEADERS, timeout=30, verify=False)
    resp.raise_for_status()
    tables = pd.read_html(StringIO(resp.text), flavor="lxml")
    df = tables[0]
    tickers = []
    for _, row in df.iterrows():
        symbol = str(row.get("Symbol", "")).strip().replace(".", "-")
        if symbol and symbol != "nan":
            tickers.append({
                "ticker": symbol,
                "name": str(row.get("Security", "")),
                "sector": str(row.get("GICS Sector", "")),
                "industry": str(row.get("GICS Sub-Industry", "")),
            })
    return tickers


def _fetch_nasdaq100_wikipedia() -> List[Dict[str, str]]:
    """Fetch NASDAQ 100 constituents from Wikipedia."""
    url = "https://en.wikipedia.org/wiki/Nasdaq-100"
    resp = requests.get(url, headers=_WIKI_HEADERS, timeout=30, verify=False)
    resp.raise_for_status()
    tables = pd.read_html(StringIO(resp.text), flavor="lxml")
    for table in tables:
        cols = [str(c).lower() for c in table.columns]
        if "ticker" in cols or "symbol" in cols:
            tickers = []
            ticker_col = "Ticker" if "Ticker" in table.columns else "Symbol"
            name_col = "Company" if "Company" in table.columns else table.columns[0]
            for _, row in table.iterrows():
                symbol = str(row.get(ticker_col, "")).strip().replace(".", "-")
                if symbol and symbol != "nan" and len(symbol) <= 5:
                    tickers.append({
                        "ticker": symbol,
                        "name": str(row.get(name_col, "")),
                        "sector": str(row.get("GICS Sector", "")),
                        "industry": str(row.get("GICS Sub-Industry", "")),
                    })
            if len(tickers) >= 50:
                return tickers
    return []


def _fetch_kospi200() -> List[Dict[str, str]]:
    """Fetch KOSPI 200 constituents from Wikipedia (Korean)."""
    url = "https://en.wikipedia.org/wiki/KOSPI_200"
    try:
        resp = requests.get(url, headers=_WIKI_HEADERS, timeout=30, verify=False)
        resp.raise_for_status()
        tables = pd.read_html(StringIO(resp.text), flavor="lxml")
        for table in tables:
            cols = [str(c).lower() for c in table.columns]
            if any(k in " ".join(cols) for k in ["code", "ticker", "symbol", "종목코드"]):
                tickers = []
                # Try to find the code/ticker column
                code_col = None
                name_col = None
                for c in table.columns:
                    cl = str(c).lower()
                    if cl in ("code", "ticker", "symbol", "종목코드"):
                        code_col = c
                    elif cl in ("company", "name", "종목명", "기업명"):
                        name_col = c
                if code_col is None:
                    continue
                if name_col is None:
                    name_col = table.columns[0] if table.columns[0] != code_col else table.columns[1]
                for _, row in table.iterrows():
                    code = str(row.get(code_col, "")).strip()
                    # Pad to 6 digits if numeric
                    if code.isdigit():
                        code = code.zfill(6)
                        ticker = f"{code}.KS"
                    elif code.endswith(".KS") or code.endswith(".KQ"):
                        ticker = code
                    else:
                        continue
                    tickers.append({
                        "ticker": ticker,
                        "name": str(row.get(name_col, "")),
                        "sector": "",
                        "industry": "",
                    })
                if len(tickers) >= 50:
                    return tickers
    except Exception:
        pass
    return _get_fallback_tickers("kospi200")


def _fetch_kosdaq150() -> List[Dict[str, str]]:
    """Fetch KOSDAQ 150 constituents — fallback to hardcoded list."""
    # KOSDAQ 150 has no reliable Wikipedia page; use fallback
    return _get_fallback_tickers("kosdaq150")


def _get_fallback_tickers(name: str) -> List[Dict[str, str]]:
    """Hardcoded fallback — top companies by sector."""
    fallback = [
        # Technology
        {"ticker": "AAPL", "name": "Apple Inc.", "sector": "Information Technology", "industry": "Consumer Electronics"},
        {"ticker": "MSFT", "name": "Microsoft Corp.", "sector": "Information Technology", "industry": "Software"},
        {"ticker": "NVDA", "name": "NVIDIA Corp.", "sector": "Information Technology", "industry": "Semiconductors"},
        {"ticker": "AVGO", "name": "Broadcom Inc.", "sector": "Information Technology", "industry": "Semiconductors"},
        {"ticker": "ADBE", "name": "Adobe Inc.", "sector": "Information Technology", "industry": "Software"},
        {"ticker": "CRM", "name": "Salesforce Inc.", "sector": "Information Technology", "industry": "Software"},
        {"ticker": "AMD", "name": "AMD Inc.", "sector": "Information Technology", "industry": "Semiconductors"},
        {"ticker": "INTC", "name": "Intel Corp.", "sector": "Information Technology", "industry": "Semiconductors"},
        {"ticker": "ORCL", "name": "Oracle Corp.", "sector": "Information Technology", "industry": "Software"},
        {"ticker": "CSCO", "name": "Cisco Systems", "sector": "Information Technology", "industry": "Networking"},
        {"ticker": "IBM", "name": "IBM Corp.", "sector": "Information Technology", "industry": "IT Services"},
        {"ticker": "TXN", "name": "Texas Instruments", "sector": "Information Technology", "industry": "Semiconductors"},
        {"ticker": "QCOM", "name": "Qualcomm", "sector": "Information Technology", "industry": "Semiconductors"},
        # Communication Services
        {"ticker": "GOOGL", "name": "Alphabet Inc.", "sector": "Communication Services", "industry": "Internet Content"},
        {"ticker": "META", "name": "Meta Platforms", "sector": "Communication Services", "industry": "Internet Content"},
        {"ticker": "NFLX", "name": "Netflix Inc.", "sector": "Communication Services", "industry": "Entertainment"},
        {"ticker": "DIS", "name": "Walt Disney Co.", "sector": "Communication Services", "industry": "Entertainment"},
        {"ticker": "CMCSA", "name": "Comcast Corp.", "sector": "Communication Services", "industry": "Telecom"},
        {"ticker": "VZ", "name": "Verizon", "sector": "Communication Services", "industry": "Telecom"},
        {"ticker": "T", "name": "AT&T Inc.", "sector": "Communication Services", "industry": "Telecom"},
        # Consumer Discretionary
        {"ticker": "AMZN", "name": "Amazon.com", "sector": "Consumer Discretionary", "industry": "Internet Retail"},
        {"ticker": "TSLA", "name": "Tesla Inc.", "sector": "Consumer Discretionary", "industry": "Auto Manufacturers"},
        {"ticker": "HD", "name": "Home Depot", "sector": "Consumer Discretionary", "industry": "Home Improvement"},
        {"ticker": "MCD", "name": "McDonald's Corp.", "sector": "Consumer Discretionary", "industry": "Restaurants"},
        {"ticker": "NKE", "name": "Nike Inc.", "sector": "Consumer Discretionary", "industry": "Footwear"},
        {"ticker": "SBUX", "name": "Starbucks Corp.", "sector": "Consumer Discretionary", "industry": "Restaurants"},
        {"ticker": "LOW", "name": "Lowe's", "sector": "Consumer Discretionary", "industry": "Home Improvement"},
        # Consumer Staples
        {"ticker": "WMT", "name": "Walmart Inc.", "sector": "Consumer Staples", "industry": "Discount Stores"},
        {"ticker": "PG", "name": "Procter & Gamble", "sector": "Consumer Staples", "industry": "Household Products"},
        {"ticker": "KO", "name": "Coca-Cola Co.", "sector": "Consumer Staples", "industry": "Beverages"},
        {"ticker": "PEP", "name": "PepsiCo Inc.", "sector": "Consumer Staples", "industry": "Beverages"},
        {"ticker": "COST", "name": "Costco Wholesale", "sector": "Consumer Staples", "industry": "Discount Stores"},
        {"ticker": "PM", "name": "Philip Morris", "sector": "Consumer Staples", "industry": "Tobacco"},
        # Healthcare
        {"ticker": "UNH", "name": "UnitedHealth Group", "sector": "Health Care", "industry": "Healthcare Plans"},
        {"ticker": "JNJ", "name": "Johnson & Johnson", "sector": "Health Care", "industry": "Drug Manufacturers"},
        {"ticker": "LLY", "name": "Eli Lilly", "sector": "Health Care", "industry": "Drug Manufacturers"},
        {"ticker": "PFE", "name": "Pfizer Inc.", "sector": "Health Care", "industry": "Drug Manufacturers"},
        {"ticker": "ABBV", "name": "AbbVie Inc.", "sector": "Health Care", "industry": "Drug Manufacturers"},
        {"ticker": "MRK", "name": "Merck & Co.", "sector": "Health Care", "industry": "Drug Manufacturers"},
        {"ticker": "TMO", "name": "Thermo Fisher", "sector": "Health Care", "industry": "Diagnostics & Research"},
        {"ticker": "ABT", "name": "Abbott Laboratories", "sector": "Health Care", "industry": "Medical Devices"},
        # Financials
        {"ticker": "BRK-B", "name": "Berkshire Hathaway", "sector": "Financials", "industry": "Insurance"},
        {"ticker": "JPM", "name": "JPMorgan Chase", "sector": "Financials", "industry": "Banks"},
        {"ticker": "V", "name": "Visa Inc.", "sector": "Financials", "industry": "Credit Services"},
        {"ticker": "MA", "name": "Mastercard", "sector": "Financials", "industry": "Credit Services"},
        {"ticker": "BAC", "name": "Bank of America", "sector": "Financials", "industry": "Banks"},
        {"ticker": "GS", "name": "Goldman Sachs", "sector": "Financials", "industry": "Capital Markets"},
        {"ticker": "MS", "name": "Morgan Stanley", "sector": "Financials", "industry": "Capital Markets"},
        {"ticker": "BLK", "name": "BlackRock", "sector": "Financials", "industry": "Asset Management"},
        # Industrials
        {"ticker": "CAT", "name": "Caterpillar Inc.", "sector": "Industrials", "industry": "Farm & Heavy Equipment"},
        {"ticker": "GE", "name": "GE Aerospace", "sector": "Industrials", "industry": "Aerospace & Defense"},
        {"ticker": "BA", "name": "Boeing Co.", "sector": "Industrials", "industry": "Aerospace & Defense"},
        {"ticker": "LMT", "name": "Lockheed Martin", "sector": "Industrials", "industry": "Aerospace & Defense"},
        {"ticker": "HON", "name": "Honeywell", "sector": "Industrials", "industry": "Conglomerates"},
        {"ticker": "UPS", "name": "United Parcel Service", "sector": "Industrials", "industry": "Freight"},
        {"ticker": "RTX", "name": "RTX Corp.", "sector": "Industrials", "industry": "Aerospace & Defense"},
        {"ticker": "DE", "name": "Deere & Co.", "sector": "Industrials", "industry": "Farm Equipment"},
        # Energy
        {"ticker": "XOM", "name": "Exxon Mobil", "sector": "Energy", "industry": "Oil & Gas Integrated"},
        {"ticker": "CVX", "name": "Chevron Corp.", "sector": "Energy", "industry": "Oil & Gas Integrated"},
        {"ticker": "COP", "name": "ConocoPhillips", "sector": "Energy", "industry": "Oil & Gas E&P"},
        {"ticker": "SLB", "name": "Schlumberger", "sector": "Energy", "industry": "Oil & Gas Services"},
        # Utilities
        {"ticker": "NEE", "name": "NextEra Energy", "sector": "Utilities", "industry": "Utilities"},
        {"ticker": "DUK", "name": "Duke Energy", "sector": "Utilities", "industry": "Utilities"},
        {"ticker": "SO", "name": "Southern Co.", "sector": "Utilities", "industry": "Utilities"},
        # Real Estate
        {"ticker": "AMT", "name": "American Tower", "sector": "Real Estate", "industry": "REIT"},
        {"ticker": "PLD", "name": "Prologis Inc.", "sector": "Real Estate", "industry": "REIT"},
        {"ticker": "CCI", "name": "Crown Castle", "sector": "Real Estate", "industry": "REIT"},
        # Materials
        {"ticker": "LIN", "name": "Linde PLC", "sector": "Materials", "industry": "Specialty Chemicals"},
        {"ticker": "APD", "name": "Air Products", "sector": "Materials", "industry": "Specialty Chemicals"},
        {"ticker": "SHW", "name": "Sherwin-Williams", "sector": "Materials", "industry": "Specialty Chemicals"},
    ]

    if name == "nasdaq100":
        nasdaq_tickers = {
            "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "TSLA",
            "AVGO", "ADBE", "CRM", "AMD", "INTC", "CSCO", "ORCL",
            "PEP", "COST", "NFLX", "QCOM", "TXN", "HON",
        }
        return [t for t in fallback if t["ticker"] in nasdaq_tickers]

    # ── Korean market fallbacks ──
    kr_kospi = [
        {"ticker": "005930.KS", "name": "삼성전자", "sector": "Information Technology", "industry": "Semiconductors"},
        {"ticker": "000660.KS", "name": "SK하이닉스", "sector": "Information Technology", "industry": "Semiconductors"},
        {"ticker": "373220.KS", "name": "LG에너지솔루션", "sector": "Industrials", "industry": "Electrical Equipment"},
        {"ticker": "207940.KS", "name": "삼성바이오로직스", "sector": "Health Care", "industry": "Biotechnology"},
        {"ticker": "005380.KS", "name": "현대자동차", "sector": "Consumer Discretionary", "industry": "Auto Manufacturers"},
        {"ticker": "006400.KS", "name": "삼성SDI", "sector": "Information Technology", "industry": "Electrical Equipment"},
        {"ticker": "051910.KS", "name": "LG화학", "sector": "Materials", "industry": "Specialty Chemicals"},
        {"ticker": "035420.KS", "name": "NAVER", "sector": "Communication Services", "industry": "Internet Content"},
        {"ticker": "000270.KS", "name": "기아", "sector": "Consumer Discretionary", "industry": "Auto Manufacturers"},
        {"ticker": "068270.KS", "name": "셀트리온", "sector": "Health Care", "industry": "Biotechnology"},
        {"ticker": "105560.KS", "name": "KB금융", "sector": "Financials", "industry": "Banks"},
        {"ticker": "055550.KS", "name": "신한지주", "sector": "Financials", "industry": "Banks"},
        {"ticker": "035720.KS", "name": "카카오", "sector": "Communication Services", "industry": "Internet Content"},
        {"ticker": "003670.KS", "name": "포스코퓨처엠", "sector": "Materials", "industry": "Steel"},
        {"ticker": "028260.KS", "name": "삼성물산", "sector": "Industrials", "industry": "Conglomerates"},
        {"ticker": "012330.KS", "name": "현대모비스", "sector": "Consumer Discretionary", "industry": "Auto Parts"},
        {"ticker": "066570.KS", "name": "LG전자", "sector": "Consumer Discretionary", "industry": "Consumer Electronics"},
        {"ticker": "096770.KS", "name": "SK이노베이션", "sector": "Energy", "industry": "Oil & Gas Refining"},
        {"ticker": "034730.KS", "name": "SK", "sector": "Industrials", "industry": "Conglomerates"},
        {"ticker": "003550.KS", "name": "LG", "sector": "Industrials", "industry": "Conglomerates"},
        {"ticker": "032830.KS", "name": "삼성생명", "sector": "Financials", "industry": "Insurance"},
        {"ticker": "015760.KS", "name": "한국전력", "sector": "Utilities", "industry": "Utilities"},
        {"ticker": "009150.KS", "name": "삼성전기", "sector": "Information Technology", "industry": "Electronic Components"},
        {"ticker": "086790.KS", "name": "하나금융지주", "sector": "Financials", "industry": "Banks"},
        {"ticker": "010130.KS", "name": "고려아연", "sector": "Materials", "industry": "Metals & Mining"},
        {"ticker": "017670.KS", "name": "SK텔레콤", "sector": "Communication Services", "industry": "Telecom"},
        {"ticker": "030200.KS", "name": "KT", "sector": "Communication Services", "industry": "Telecom"},
        {"ticker": "018260.KS", "name": "삼성에스디에스", "sector": "Information Technology", "industry": "IT Services"},
        {"ticker": "011170.KS", "name": "롯데케미칼", "sector": "Materials", "industry": "Specialty Chemicals"},
        {"ticker": "033780.KS", "name": "KT&G", "sector": "Consumer Staples", "industry": "Tobacco"},
    ]
    kr_kosdaq = [
        {"ticker": "247540.KQ", "name": "에코프로비엠", "sector": "Materials", "industry": "Specialty Chemicals"},
        {"ticker": "091990.KQ", "name": "셀트리온헬스케어", "sector": "Health Care", "industry": "Biotechnology"},
        {"ticker": "263750.KQ", "name": "펄어비스", "sector": "Communication Services", "industry": "Electronic Gaming"},
        {"ticker": "086520.KQ", "name": "에코프로", "sector": "Materials", "industry": "Specialty Chemicals"},
        {"ticker": "196170.KQ", "name": "알테오젠", "sector": "Health Care", "industry": "Biotechnology"},
        {"ticker": "403870.KQ", "name": "HPSP", "sector": "Information Technology", "industry": "Semiconductors"},
        {"ticker": "145020.KQ", "name": "휴젤", "sector": "Health Care", "industry": "Biotechnology"},
        {"ticker": "357780.KQ", "name": "솔브레인", "sector": "Materials", "industry": "Specialty Chemicals"},
        {"ticker": "058470.KQ", "name": "리노공업", "sector": "Information Technology", "industry": "Semiconductors"},
        {"ticker": "112040.KQ", "name": "위메이드", "sector": "Communication Services", "industry": "Electronic Gaming"},
        {"ticker": "383220.KQ", "name": "F&F", "sector": "Consumer Discretionary", "industry": "Apparel"},
        {"ticker": "293490.KQ", "name": "카카오게임즈", "sector": "Communication Services", "industry": "Electronic Gaming"},
        {"ticker": "041510.KQ", "name": "에스엠", "sector": "Communication Services", "industry": "Entertainment"},
        {"ticker": "035900.KQ", "name": "JYP Ent.", "sector": "Communication Services", "industry": "Entertainment"},
        {"ticker": "352820.KQ", "name": "하이브", "sector": "Communication Services", "industry": "Entertainment"},
    ]

    if name == "kospi200":
        return kr_kospi
    if name == "kosdaq150":
        return kr_kosdaq

    return fallback


# ═══════════════════════════════════════════════════════════
# LIGHTWEIGHT DATA FETCHING (with in-memory cache)
# ═══════════════════════════════════════════════════════════

_MAX_CACHE_SIZE = 500  # LRU limit for in-memory cache
_light_info_cache: OrderedDict = OrderedDict()  # {ticker: {"data": ..., "_ts": float}}
_light_info_lock = threading.Lock()
_LIGHT_INFO_TTL = 14400  # 4 hours


def fetch_light_info(ticker: str) -> Optional[Dict[str, Any]]:
    """
    Fetch lightweight stock info (.info only, no statements/history).
    Returns a flat dict with key financial metrics, or None on failure.
    Cached in-memory for 4 hours. Thread-safe with LRU eviction.
    """
    ticker = ticker.upper().strip()
    with _light_info_lock:
        cached = _light_info_cache.get(ticker)
        if cached and (time.time() - cached.get("_ts", 0)) < _LIGHT_INFO_TTL:
            _light_info_cache.move_to_end(ticker)  # LRU touch
            return cached["data"]

    result = _fetch_light_info_raw(ticker)

    with _light_info_lock:
        _light_info_cache[ticker] = {"data": result, "_ts": time.time()}
        _light_info_cache.move_to_end(ticker)
        # Evict oldest if over size limit
        while len(_light_info_cache) > _MAX_CACHE_SIZE:
            _light_info_cache.popitem(last=False)

    return result


# Key fields used to detect sparse API responses
_SPARSE_CHECK_FIELDS = [
    "revenueGrowth", "operatingMargins", "returnOnEquity", "freeCashflow",
    "debtToEquity", "trailingPE", "enterpriseToEbitda", "priceToBook",
]


def _fetch_light_info_raw(ticker: str) -> Optional[Dict[str, Any]]:
    """Raw fetch without cache. Auto-retries on transient network errors.
    Also retries once if the response is sparse (>70% of key fields null)."""
    from src.fetcher.retry import with_retry

    @with_retry(max_retries=2, backoff=0.5)
    def _inner():
        from src.fetcher.ssl_session import get_session
        _s = get_session()
        t = yf.Ticker(ticker, session=_s) if _s else yf.Ticker(ticker)
        info = t.info or {}

        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if not price:
            return None

        # Sparse response detection: if >70% of key fields are null, retry once
        null_count = sum(1 for f in _SPARSE_CHECK_FIELDS if info.get(f) is None)
        if null_count > len(_SPARSE_CHECK_FIELDS) * 0.7:
            import time as _time
            _time.sleep(1.0)
            t2 = yf.Ticker(ticker, session=_s) if _s else yf.Ticker(ticker)
            info2 = t2.info or {}
            null_count2 = sum(1 for f in _SPARSE_CHECK_FIELDS if info2.get(f) is None)
            if null_count2 < null_count:
                info = info2

        # debt_to_equity from info is in percentage form (e.g., 176.29 = 176.29%)
        # Convert to ratio form (1.7629) for consistency with grade_financial
        de_raw = info.get("debtToEquity")
        de_ratio = de_raw / 100.0 if de_raw is not None else None

        return {
            "ticker": ticker.upper(),
            "name": info.get("longName", info.get("shortName", ticker)),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "country": info.get("country", "N/A"),
            "market_cap": info.get("marketCap"),
            "current_price": price,
            "enterprise_value": info.get("enterpriseValue"),
            # Valuation ratios
            "trailing_pe": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "peg_ratio": info.get("pegRatio"),
            "price_to_book": info.get("priceToBook"),
            "price_to_sales": info.get("priceToSalesTrailing12Months"),
            "ev_to_ebitda": info.get("enterpriseToEbitda"),
            "ev_to_revenue": info.get("enterpriseToRevenue"),
            # Profitability
            "revenue_growth": info.get("revenueGrowth"),
            "operating_margin": info.get("operatingMargins"),
            "profit_margin": info.get("profitMargins"),
            "gross_margin": info.get("grossMargins"),
            "roe": info.get("returnOnEquity"),
            "roa": info.get("returnOnAssets"),
            # Dividend & other
            "dividend_yield": info.get("dividendYield"),
            "beta": info.get("beta"),
            "debt_to_equity": de_ratio,
            "fcf": info.get("freeCashflow"),
            "revenue": info.get("totalRevenue"),
            "employees": info.get("fullTimeEmployees"),
            "shares_outstanding": info.get("sharesOutstanding"),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
        }

    try:
        return _inner()
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════
# SCAN CACHE MANAGEMENT
# ═══════════════════════════════════════════════════════════

def load_cached_scan(universe_name: str) -> Optional[Dict[str, Any]]:
    """Load cached scan results if they exist and are fresh (< 24h)."""
    _ensure_dirs()

    for days_back in range(2):
        date_str = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        path = os.path.join(_CACHE_DIR, f"screener_{universe_name}_{date_str}.json")
        if os.path.exists(path):
            try:
                age = time.time() - os.path.getmtime(path)
                if age < SCREENER_CACHE_TTL:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if data and isinstance(data.get("stocks"), list) and len(data["stocks"]) > 0:
                        return data
            except Exception:
                continue
    return None


def save_cached_scan(universe_name: str, scan_data: Dict[str, Any]):
    """Save scan results to JSON file (atomic write to prevent corruption)."""
    _ensure_dirs()
    date_str = datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(_CACHE_DIR, f"screener_{universe_name}_{date_str}.json")
    try:
        # Atomic write: write to temp file, then rename
        fd, tmp_path = tempfile.mkstemp(
            dir=_CACHE_DIR, suffix=".tmp", prefix="screener_"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(scan_data, f, ensure_ascii=False, default=str)
            # On Windows, remove target first if it exists
            if os.path.exists(path):
                os.replace(tmp_path, path)
            else:
                os.rename(tmp_path, path)
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except Exception:
        pass


def scan_universe(universe_name: str, progress_bar=None, status_text=None) -> Dict[str, Any]:
    """
    Scan all tickers in a universe with lightweight data fetch + screener grades.
    Uses ThreadPoolExecutor for 5-10x speedup over sequential scanning.
    Shows progress via optional Streamlit widgets.
    """
    from src.grading.screener_grades import compute_screener_grades
    from src.fetcher.parallel import batch_fetch

    tickers = load_universe(universe_name)
    total = len(tickers)
    if total == 0:
        return {
            "universe": universe_name,
            "scan_time": datetime.now().isoformat(),
            "total_scanned": 0,
            "successful": 0,
            "failed": 0,
            "failed_tickers": [],
            "stocks": [],
        }

    results = []
    failed_list = []
    start_time = time.time()

    # Build ticker → name map
    ticker_list = [t["ticker"] for t in tickers]

    def _fetch_and_grade(ticker: str):
        stock_info = fetch_light_info(ticker)
        if stock_info:
            grades = compute_screener_grades(stock_info)
            stock_info["grades"] = grades
            return stock_info
        return None

    # Progress tracking (thread-safe via list append)
    _done = [0]  # mutable counter in list

    def _on_progress(done, tot, item, success):
        _done[0] = done
        if progress_bar:
            progress_bar.progress(done / tot)
        if status_text:
            elapsed = time.time() - start_time
            rate = done / elapsed if elapsed > 0 else 1
            remaining = (tot - done) / rate if rate > 0 else 0
            ok = done - len(failed_list)
            status_text.text(
                f"스캔 중: {item} ({done}/{tot}) | "
                f"성공: {ok} | 실패: {len(failed_list)} | "
                f"남은 시간: ~{remaining/60:.1f}분"
            )

    # Parallel fetch: 20 workers, 0.05s inter-worker delay
    fetched, fetch_failed = batch_fetch(
        fn=_fetch_and_grade,
        items=ticker_list,
        max_workers=20,
        delay=0.05,
        on_progress=_on_progress,
    )

    results = [v for v in fetched.values() if v is not None]
    failed_list = fetch_failed

    scan_data = {
        "universe": universe_name,
        "scan_mode": "index",
        "scan_time": datetime.now().isoformat(),
        "total_scanned": total,
        "successful": len(results),
        "failed": len(failed_list),
        "failed_tickers": failed_list[:50],
        "stocks": results,
    }

    # Save to disk
    save_cached_scan(universe_name, scan_data)

    return scan_data


# ═══════════════════════════════════════════════════════════
# COUNTRY-BASED FULL STOCK SCAN (yfinance Screener API)
# ═══════════════════════════════════════════════════════════

def _build_country_cache_key(region_codes: List[str], min_market_cap: float) -> str:
    """Build a deterministic cache key for country-based scans."""
    codes_str = "_".join(sorted(region_codes))
    cap_str = f"{int(min_market_cap)}"
    return f"all_{codes_str}_{cap_str}"


def fetch_stocks_by_countries(
    region_codes: List[str],
    min_market_cap: float = 0,
    progress_bar=None,
    status_text=None,
) -> List[Dict[str, Any]]:
    """
    Fetch all stocks for given countries via yfinance Screener API with pagination.
    Returns a list of stock dicts compatible with the existing scan pipeline.

    Args:
        region_codes: List of region codes (e.g. ["us", "kr"])
        min_market_cap: Minimum market cap in USD (0 = no filter)
        progress_bar: Optional Streamlit progress bar
        status_text: Optional Streamlit text widget for status updates
    """
    from yfinance import EquityQuery

    # Build query
    filters = []

    # Region filter
    if len(region_codes) == 1:
        filters.append(EquityQuery('eq', ['region', region_codes[0]]))
    else:
        region_queries = [EquityQuery('eq', ['region', rc]) for rc in region_codes]
        filters.append(EquityQuery('or', region_queries))

    # Market cap filter
    if min_market_cap > 0:
        filters.append(EquityQuery('gt', ['intradaymarketcap', min_market_cap]))

    # Combine filters
    if len(filters) == 1:
        query = filters[0]
    else:
        query = EquityQuery('and', filters)

    all_quotes = []
    offset = 0
    PAGE_SIZE = 250  # Yahoo max per page
    total_expected = None

    while True:
        try:
            result = yf.screen(query, offset=offset, size=PAGE_SIZE)
            quotes = result.get('quotes', [])
            total_expected = result.get('total', total_expected)

            if not quotes:
                break

            all_quotes.extend(quotes)

            if status_text and total_expected:
                status_text.text(
                    f"종목 목록 수집 중: {len(all_quotes)}/{total_expected} "
                    f"({len(all_quotes)/total_expected*100:.0f}%)"
                )
            if progress_bar and total_expected:
                progress_bar.progress(min(len(all_quotes) / total_expected, 1.0))

            offset += PAGE_SIZE
            if total_expected and offset >= total_expected:
                break
            if len(quotes) < PAGE_SIZE:
                break

            # Small delay to be nice to Yahoo
            time.sleep(0.2)

        except Exception as e:
            if status_text:
                status_text.text(f"페이지네이션 오류 (offset={offset}): {e}")
            break

    return all_quotes


# ── Ticker suffix → country name mapping ─────────────────

_TICKER_SUFFIX_COUNTRY = {
    ".KS": "South Korea",
    ".KQ": "South Korea",
    ".T": "Japan",
    ".SS": "China",
    ".SZ": "China",
    ".HK": "Hong Kong",
    ".L": "United Kingdom",
    ".DE": "Germany",
    ".PA": "France",
    ".TO": "Canada",
    ".AX": "Australia",
}


def _detect_country_from_ticker(ticker: str) -> str:
    """Detect country from ticker suffix. Falls back to 'United States'."""
    t_upper = ticker.upper().strip()
    for suffix, country in _TICKER_SUFFIX_COUNTRY.items():
        if t_upper.endswith(suffix.upper()):
            return country
    return "United States"


# Preferred share / non-common-stock ticker patterns
import re as _re
_PREFERRED_RE = _re.compile(
    r'-P[A-Z]?$'      # MS-PI, WFC-PY
    r'|\^[A-Z]+$'     # BRK^B (some feeds)
    r'|\.PR[A-Z]?$'   # BAC.PRA
    r'|-[A-Z]$'        # PBR-A (preferred ADR class)
    r'|[A-Z]{4,}F$'    # BACHF, NSRGF (OTC foreign)
    r'|[A-Z]{4,}Y$'    # BNDSY (OTC ADR)
)


def _convert_screener_quote(quote: dict) -> Optional[Dict[str, Any]]:
    """Convert a yfinance Screener quote dict to our internal stock format.
    Returns None for non-equity securities or suspected preferred/OTC tickers."""
    # Filter out non-equity quote types
    quote_type = quote.get("quoteType", "EQUITY")
    if quote_type not in ("EQUITY", ""):
        return None

    mc = quote.get("marketCap")
    price = quote.get("regularMarketPrice")
    dy = quote.get("dividendYield")
    ticker_str = quote.get("symbol", "")

    # Filter out preferred shares, OTC foreign, etc. by ticker pattern
    if _PREFERRED_RE.search(ticker_str):
        return None

    # ── Country detection: use ticker suffix (listing exchange), not region ──
    country = _detect_country_from_ticker(ticker_str)

    # ── Dividend yield normalization ──
    # Screener API sometimes returns percentage (5.32) instead of ratio (0.0532)
    if dy is not None and dy > 1.0:
        dy = dy / 100.0

    return {
        "ticker": ticker_str,
        "name": quote.get("longName") or quote.get("shortName", ""),
        "sector": quote.get("sector", "N/A"),
        "industry": quote.get("industry", "N/A"),
        "country": country,
        "market_cap": mc,
        "current_price": price,
        "enterprise_value": quote.get("enterpriseValue"),
        # Valuation ratios
        "trailing_pe": quote.get("trailingPE"),
        "forward_pe": quote.get("forwardPE"),
        "peg_ratio": quote.get("pegRatio"),
        "price_to_book": quote.get("priceToBook"),
        "price_to_sales": quote.get("priceToSalesTrailing12Months"),
        "ev_to_ebitda": quote.get("enterpriseToEbitda"),
        "ev_to_revenue": quote.get("enterpriseToRevenue"),
        # Profitability
        "revenue_growth": quote.get("revenueGrowth"),
        "operating_margin": quote.get("operatingMargins"),
        "profit_margin": quote.get("profitMargins"),
        "gross_margin": quote.get("grossMargins"),
        "roe": quote.get("returnOnEquity"),
        "roa": quote.get("returnOnAssets"),
        # Dividend & other
        "dividend_yield": dy,
        "beta": quote.get("beta"),
        "debt_to_equity": None,  # Not in screener response
        "fcf": None,  # Not in screener response
        "revenue": quote.get("totalRevenue"),
        "employees": quote.get("fullTimeEmployees"),
        "shares_outstanding": quote.get("sharesOutstanding"),
        "fifty_two_week_high": quote.get("fiftyTwoWeekHigh"),
        "fifty_two_week_low": quote.get("fiftyTwoWeekLow"),
    }


def scan_by_countries(
    region_codes: List[str],
    min_market_cap: float = 0,
    progress_bar=None,
    status_text=None,
    enrich_top_n: int = 500,
) -> Dict[str, Any]:
    """
    Scan all stocks for given countries using yfinance Screener API.
    Phase 1: Bulk fetch via Screener API (fast, 250/page).
    Phase 2: Enrich top N stocks (by market cap) with individual .info calls
             to get missing financial data for accurate grading.

    Args:
        region_codes: List of region codes (e.g. ["us", "kr"])
        min_market_cap: Minimum market cap in USD
        progress_bar: Optional Streamlit progress bar
        status_text: Optional Streamlit text widget
        enrich_top_n: Max number of stocks to enrich with .info (default 500)
    """
    from src.grading.screener_grades import compute_screener_grades
    from src.fetcher.parallel import batch_fetch

    start_time = time.time()
    cache_key = _build_country_cache_key(region_codes, min_market_cap)

    # ── Phase 1: Bulk fetch via Screener API ─────────────
    if status_text:
        status_text.text("Phase 1/3: yfinance Screener API로 종목 목록 수집 중...")
    if progress_bar:
        progress_bar.progress(0)

    raw_quotes = fetch_stocks_by_countries(
        region_codes, min_market_cap, progress_bar, status_text
    )

    if not raw_quotes:
        return {
            "universe": cache_key,
            "scan_time": datetime.now().isoformat(),
            "scan_mode": "country",
            "total_scanned": 0,
            "successful": 0,
            "failed": 0,
            "failed_tickers": [],
            "stocks": [],
        }

    # ── Convert quotes to internal format ────────────────
    if status_text:
        status_text.text(f"Phase 1/3: {len(raw_quotes)}개 종목 변환 중...")

    converted = []
    for quote in raw_quotes:
        try:
            stock = _convert_screener_quote(quote)
            if stock is not None and stock.get("current_price") and stock.get("ticker"):
                converted.append(stock)
        except Exception:
            pass

    # ── Phase 2: Enrich top N with individual .info calls ─
    # Sort by market cap descending to prioritize large/liquid stocks
    converted.sort(key=lambda s: s.get("market_cap") or 0, reverse=True)
    to_enrich = converted[:enrich_top_n]

    # Identify stocks needing enrichment (key financial fields all null)
    _ENRICH_FIELDS = [
        "revenue_growth", "operating_margin", "roe", "debt_to_equity",
        "fcf", "revenue", "trailing_pe", "forward_pe", "price_to_book",
        "ev_to_ebitda", "ev_to_revenue", "price_to_sales",
    ]

    def _needs_enrichment(stock: dict) -> bool:
        non_null = sum(1 for f in _ENRICH_FIELDS if stock.get(f) is not None)
        return non_null < 6  # Less than half of 12 key fields → enrich via .info

    tickers_to_enrich = [s["ticker"] for s in to_enrich if _needs_enrichment(s)]
    # Build ticker → stock mapping for quick access
    ticker_to_stock = {s["ticker"]: s for s in converted}

    if tickers_to_enrich:
        if status_text:
            status_text.text(
                f"Phase 2/3: {len(tickers_to_enrich)}개 종목 재무 데이터 보강 중... "
                f"(개별 .info 호출, 병렬 20워커)"
            )
        if progress_bar:
            progress_bar.progress(0)

        enrich_start = time.time()

        def _on_enrich_progress(done, tot, item, success):
            if progress_bar:
                progress_bar.progress(done / tot)
            if status_text:
                elapsed = time.time() - enrich_start
                rate = done / elapsed if elapsed > 0 else 1
                remaining = (tot - done) / rate if rate > 0 else 0
                status_text.text(
                    f"Phase 2/3: 보강 중 {item} ({done}/{tot}) | "
                    f"남은 시간: ~{remaining/60:.1f}분"
                )

        enriched_results, enrich_failed = batch_fetch(
            fn=fetch_light_info,
            items=tickers_to_enrich,
            max_workers=20,
            delay=0.05,
            on_progress=_on_enrich_progress,
        )

        # Merge enriched data back
        for ticker, info_data in enriched_results.items():
            if info_data and ticker in ticker_to_stock:
                stock = ticker_to_stock[ticker]
                # Only fill null fields from .info; preserve non-null screener data
                for key in _ENRICH_FIELDS + ["sector", "industry", "country"]:
                    if stock.get(key) is None or stock.get(key) == "N/A":
                        val = info_data.get(key)
                        if val is not None and val != "N/A":
                            stock[key] = val
                # Also fill dividend_yield, beta if missing
                for extra_key in ["dividend_yield", "beta"]:
                    if stock.get(extra_key) is None:
                        val = info_data.get(extra_key)
                        if val is not None:
                            stock[extra_key] = val

    # ── Phase 3: Compute grades ──────────────────────────
    if status_text:
        status_text.text(f"Phase 3/3: {len(converted)}개 종목 등급 산출 중...")
    if progress_bar:
        progress_bar.progress(0)

    results = []
    failed_count = 0
    total = len(converted)

    for i, stock in enumerate(converted):
        try:
            grades = compute_screener_grades(stock)
            stock["grades"] = grades
            results.append(stock)
        except Exception:
            failed_count += 1

        if progress_bar and total > 0:
            progress_bar.progress((i + 1) / total)

    elapsed = time.time() - start_time

    scan_data = {
        "universe": cache_key,
        "scan_mode": "country",
        "scan_time": datetime.now().isoformat(),
        "total_scanned": len(raw_quotes),
        "successful": len(results),
        "failed": failed_count,
        "failed_tickers": [],
        "enriched": len(tickers_to_enrich) - len(enrich_failed) if tickers_to_enrich else 0,
        "stocks": results,
    }

    # Save to disk cache
    save_cached_scan(cache_key, scan_data)

    return scan_data
