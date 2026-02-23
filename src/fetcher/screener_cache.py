"""
Screener Cache — manages universe ticker lists and lightweight stock data caching.
Fetches S&P 500 / NASDAQ 100 constituent lists from Wikipedia.
Caches scan results to JSON files with 24h TTL.
"""

import json
import os
import time
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
    """Fetch ticker list from Wikipedia."""
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

    return fallback


# ═══════════════════════════════════════════════════════════
# LIGHTWEIGHT DATA FETCHING
# ═══════════════════════════════════════════════════════════

def fetch_light_info(ticker: str) -> Optional[Dict[str, Any]]:
    """
    Fetch lightweight stock info (.info only, no statements/history).
    Returns a flat dict with key financial metrics, or None on failure.
    """
    try:
        from src.fetcher.ssl_session import get_session
        t = yf.Ticker(ticker, session=get_session())
        info = t.info or {}

        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if not price:
            return None

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
    """Save scan results to JSON file."""
    _ensure_dirs()
    date_str = datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(_CACHE_DIR, f"screener_{universe_name}_{date_str}.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(scan_data, f, ensure_ascii=False, default=str)
    except Exception:
        pass


def scan_universe(universe_name: str, progress_bar=None, status_text=None) -> Dict[str, Any]:
    """
    Scan all tickers in a universe with lightweight data fetch + screener grades.
    Shows progress via optional Streamlit widgets.
    """
    from src.grading.screener_grades import compute_screener_grades

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
    failed = []
    start_time = time.time()

    for i, t_info in enumerate(tickers):
        ticker = t_info["ticker"]

        if progress_bar:
            progress_bar.progress((i + 1) / total)
        if status_text:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed if elapsed > 0 else 1
            remaining = (total - i - 1) / rate if rate > 0 else 0
            status_text.text(
                f"스캔 중: {ticker} ({i+1}/{total}) | "
                f"성공: {len(results)} | 실패: {len(failed)} | "
                f"남은 시간: ~{remaining/60:.1f}분"
            )

        try:
            stock_info = fetch_light_info(ticker)
            if stock_info:
                grades = compute_screener_grades(stock_info)
                stock_info["grades"] = grades
                results.append(stock_info)
            else:
                failed.append(ticker)
        except Exception:
            failed.append(ticker)

        # Throttle to avoid rate limiting
        time.sleep(0.15)

    scan_data = {
        "universe": universe_name,
        "scan_time": datetime.now().isoformat(),
        "total_scanned": total,
        "successful": len(results),
        "failed": len(failed),
        "failed_tickers": failed[:50],
        "stocks": results,
    }

    # Save to disk
    save_cached_scan(universe_name, scan_data)

    return scan_data
