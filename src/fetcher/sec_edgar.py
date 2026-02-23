"""
SEC EDGAR 13F Filing Fetcher — Guru Investor Tracker

Fetches 13F-HR filings from SEC EDGAR to track famous investors' holdings.
Uses the EDGAR FULL-TEXT SEARCH & submissions API.

Rate limit: 10 req/sec (SEC requirement) → 0.15s delay between requests.
"""

import time
import json
import re
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional, Tuple
from functools import lru_cache
from datetime import datetime

import pandas as pd

from config import GURU_INVESTORS, SEC_EDGAR_HEADERS

# ── Session & Rate Limiting ───────────────────────────────
_last_request_time = 0.0
_MIN_INTERVAL = 0.15  # 150ms between SEC requests


def _get_sec_session():
    """Get a requests session for SEC EDGAR (no impersonation needed)."""
    try:
        from src.fetcher.ssl_session import get_session
        session = get_session()
        return session
    except Exception:
        import requests
        session = requests.Session()
        session.verify = False
        return session


def _sec_get(url: str, params: dict = None) -> Optional[dict]:
    """Rate-limited GET request to SEC EDGAR. Returns JSON or None."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)

    session = _get_sec_session()
    try:
        resp = session.get(url, headers=SEC_EDGAR_HEADERS, params=params, timeout=15)
        _last_request_time = time.time()
        if resp.status_code == 200:
            return resp.json()
        else:
            return None
    except Exception:
        return None


def _sec_get_text(url: str) -> Optional[str]:
    """Rate-limited GET request returning raw text."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)

    session = _get_sec_session()
    try:
        resp = session.get(url, headers=SEC_EDGAR_HEADERS, timeout=15)
        _last_request_time = time.time()
        if resp.status_code == 200:
            return resp.text
        return None
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════
#  Core: Fetch 13F filing data for a CIK
# ═══════════════════════════════════════════════════════════

_filing_cache: Dict[str, Any] = {}


def fetch_latest_13f(cik: str) -> Optional[Dict[str, Any]]:
    """
    Fetch the most recent 13F-HR filing for a given CIK.

    Returns
    -------
    {
        "filing_date": str,
        "report_date": str,
        "holdings": [
            {
                "name": str,           # company name (issuer)
                "cusip": str,
                "ticker": str | None,  # resolved ticker (best-effort)
                "shares": int,
                "value_usd": int,      # value in USD (reported in $1000s → converted)
                "option_type": str,    # "Put", "Call", or ""
            }, ...
        ],
        "total_value": int,
    }
    """
    cache_key = f"13f_{cik}"
    if cache_key in _filing_cache:
        cached = _filing_cache[cache_key]
        if time.time() - cached["_ts"] < 86400:
            return cached["data"]

    result = _fetch_13f_from_submissions(cik)
    _filing_cache[cache_key] = {"data": result, "_ts": time.time()}
    return result


def _fetch_13f_from_submissions(cik: str) -> Optional[Dict[str, Any]]:
    """Fetch 13F from SEC EDGAR submissions API."""
    # Step 1: Get recent filings list
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    data = _sec_get(url)
    if not data:
        return None

    recent = data.get("filings", {}).get("recent", {})
    if not recent:
        return None

    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])
    report_dates = recent.get("reportDate", [])

    # Step 2: Find latest 13F-HR
    idx_13f = None
    for i, form in enumerate(forms):
        if form in ("13F-HR", "13F-HR/A"):
            idx_13f = i
            break

    if idx_13f is None:
        return None

    filing_date = dates[idx_13f] if idx_13f < len(dates) else "N/A"
    report_date = report_dates[idx_13f] if idx_13f < len(report_dates) else filing_date
    accession = accessions[idx_13f].replace("-", "") if idx_13f < len(accessions) else None
    accession_dashed = accessions[idx_13f] if idx_13f < len(accessions) else None

    if not accession:
        return None

    # Step 3: Get the filing index to find the infotable XML
    cik_clean = cik.lstrip("0")
    index_url = f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/{accession}/index.json"
    index_data = _sec_get(index_url)

    infotable_url = None
    if index_data:
        items = index_data.get("directory", {}).get("item", [])
        # Priority 1: file with "infotable" in name
        for item in items:
            fname = item.get("name", "")
            if "infotable" in fname.lower() and fname.lower().endswith(".xml"):
                infotable_url = (
                    f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/"
                    f"{accession}/{fname}"
                )
                break
        # Priority 2: any .xml that is NOT index/primary_doc
        if not infotable_url:
            for item in items:
                fname = item.get("name", "")
                fl = fname.lower()
                if (fl.endswith(".xml")
                    and "index" not in fl
                    and fl != "primary_doc.xml"
                    and fl != "r1.xml"
                    and not fl.endswith("-index.xml")):
                    # Verify it contains 13F data by fetching a small portion
                    test_url = (
                        f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/"
                        f"{accession}/{fname}"
                    )
                    test_text = _sec_get_text(test_url)
                    if test_text and ("infotable" in test_text.lower()
                                      or "nameofissuer" in test_text.lower()):
                        infotable_url = test_url
                        break

    # Fallback: try primary doc or common filename patterns
    if not infotable_url:
        # Try common filenames
        for fname in ["infotable.xml", "primary_doc.xml", "InfoTable.xml"]:
            test_url = (
                f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/"
                f"{accession}/{fname}"
            )
            xml_text = _sec_get_text(test_url)
            if xml_text and "<informationTable" in xml_text.lower():
                infotable_url = test_url
                break

    if not infotable_url:
        # Try the primary document or look in filing detail
        detail_url = (
            f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/{accession}/"
        )
        html = _sec_get_text(detail_url)
        if html:
            # Parse links that contain "infotable" or end with .xml
            matches = re.findall(r'href="([^"]*(?:infotable|INFOTABLE)[^"]*\.xml)"', html, re.I)
            if not matches:
                matches = re.findall(r'href="([^"]*\.xml)"', html, re.I)
            if matches:
                fname = matches[0]
                if not fname.startswith("http"):
                    infotable_url = (
                        f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/"
                        f"{accession}/{fname}"
                    )
                else:
                    infotable_url = fname

    if not infotable_url:
        return None

    # Step 4: Parse 13F XML
    holdings = _parse_13f_xml(infotable_url)

    if not holdings:
        return None

    total_value = sum(h.get("value_usd", 0) for h in holdings)

    return {
        "filing_date": filing_date,
        "report_date": report_date,
        "holdings": holdings,
        "total_value": total_value,
    }


def _parse_13f_xml(url: str) -> List[Dict[str, Any]]:
    """Parse 13F information table XML into list of holdings."""
    xml_text = _sec_get_text(url)
    if not xml_text:
        return []

    holdings = []
    try:
        # Remove BOM if present
        xml_text = xml_text.lstrip("\ufeff")

        # Handle namespace variations
        # Common namespaces in 13F filings
        xml_text_clean = re.sub(r'xmlns[^"]*"[^"]*"', '', xml_text)

        root = ET.fromstring(xml_text_clean)

        # Find all infoTable entries (various tag patterns)
        entries = (
            root.findall(".//infoTable") or
            root.findall(".//{*}infoTable") or
            root.findall(".//InfoTable") or
            root.findall(".//{*}InfoTable")
        )

        # If no entries found with those tags, try finding all children with relevant sub-elements
        if not entries:
            for child in root.iter():
                tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if tag.lower() == "infotable":
                    entries.append(child)

        for entry in entries:
            h = _parse_entry(entry)
            if h:
                holdings.append(h)

    except ET.ParseError:
        # Try regex fallback for badly formed XML
        holdings = _parse_13f_regex(xml_text)
    except Exception:
        pass

    return holdings


def _get_text(element, *tag_names) -> Optional[str]:
    """Get text from a child element, trying multiple tag name variations."""
    for tag in tag_names:
        # Try direct
        el = element.find(tag)
        if el is not None and el.text:
            return el.text.strip()
        # Try case-insensitive via iteration
        for child in element:
            child_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if child_tag.lower() == tag.lower():
                if child.text:
                    return child.text.strip()
                # Check for nested child text
                for sub in child:
                    sub_tag = sub.tag.split("}")[-1] if "}" in sub.tag else sub.tag
                    if sub.text:
                        return sub.text.strip()
    return None


def _parse_entry(entry) -> Optional[Dict[str, Any]]:
    """Parse a single 13F holding entry."""
    try:
        name = _get_text(entry, "nameOfIssuer", "NameOfIssuer", "nameofissuer")
        cusip = _get_text(entry, "cusip", "CUSIP", "Cusip")
        value_str = _get_text(entry, "value", "Value")
        shares_str = None
        option_type = ""

        # Shares or principal can be nested in shrsOrPrnAmt
        for child in entry:
            child_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if child_tag.lower() in ("shrsorprnamt", "shrsOrPrnAmt"):
                shares_str = _get_text(child, "sshPrnamt", "SshPrnamt", "sshprnamt")
                sh_type = _get_text(child, "sshPrnamtType", "SshPrnamtType", "sshprnamttype")
                break

        if not shares_str:
            shares_str = _get_text(entry, "sshPrnamt", "SshPrnamt")

        # Put/Call
        option_type = _get_text(entry, "putCall", "PutCall", "putcall") or ""

        value_usd = int(float(value_str)) if value_str else 0  # value is in USD
        shares = int(float(shares_str)) if shares_str else 0

        if not name:
            return None

        return {
            "name": name,
            "cusip": cusip or "",
            "ticker": None,  # resolved later
            "shares": shares,
            "value_usd": value_usd,
            "option_type": option_type.upper() if option_type else "",
        }
    except Exception:
        return None


def _parse_13f_regex(text: str) -> List[Dict[str, Any]]:
    """Regex fallback parser for 13F XML."""
    holdings = []
    blocks = re.findall(
        r'<(?:\w+:)?infoTable[^>]*>(.*?)</(?:\w+:)?infoTable>',
        text, re.DOTALL | re.IGNORECASE
    )
    for block in blocks:
        name_m = re.search(r'<(?:\w+:)?nameOfIssuer[^>]*>(.*?)</', block, re.I)
        cusip_m = re.search(r'<(?:\w+:)?cusip[^>]*>(.*?)</', block, re.I)
        value_m = re.search(r'<(?:\w+:)?value[^>]*>(.*?)</', block, re.I)
        shares_m = re.search(r'<(?:\w+:)?sshPrnamt[^>]*>(.*?)</', block, re.I)
        putcall_m = re.search(r'<(?:\w+:)?putCall[^>]*>(.*?)</', block, re.I)

        name = name_m.group(1).strip() if name_m else None
        if not name:
            continue

        value_usd = int(float(value_m.group(1).strip())) if value_m else 0  # value in USD
        shares = int(float(shares_m.group(1).strip())) if shares_m else 0

        holdings.append({
            "name": name,
            "cusip": cusip_m.group(1).strip() if cusip_m else "",
            "ticker": None,
            "shares": shares,
            "value_usd": value_usd,  # value is in USD
            "option_type": (putcall_m.group(1).strip().upper() if putcall_m else ""),
        })

    return holdings


# ═══════════════════════════════════════════════════════════
#  Ticker Resolution (CUSIP → Ticker via company name fuzzy match)
# ═══════════════════════════════════════════════════════════

# Well-known CUSIP → Ticker map (covers top holdings)
_CUSIP_TICKER_MAP = {
    "037833100": "AAPL", "594918104": "MSFT", "023135106": "AMZN",
    "30303M102": "META", "02079K305": "GOOGL", "02079K107": "GOOG",
    "67066G104": "NVDA", "88160R101": "TSLA", "084670702": "BRK-B",
    "46625H100": "JPM",  "91324P102": "UNH",  "478160104": "JNJ",
    "92826C839": "V",    "22160K105": "COST",  "742718109": "PG",
    "57636Q104": "MA",   "654106103": "NKE",   "172967424": "C",
    "110122108": "BMY",  "256135203": "DG",    "007903107": "AMD",
    "14149Y108": "CRM",  "19260Q107": "COIN",
    "437076102": "HD",   "20030N101": "CMCSA", "00287Y109": "ABBV",
    "46120E602": "INTC", "882508104": "TXN",   "29786A106": "ETSY",
    "88579Y101": "TMO",  "58933Y105": "MRK",
    "532457108": "LLY",  "345838106": "F",     "026874784": "AIG",
    "500754106": "KO",   "718172109": "PFE",   "98978V103": "ZM",
    "40432F101": "HCA",  "00724F101": "ADBE",  "86800U104": "SBUX",
    "808513105": "SCHW", "89417E109": "TGT",   "00206R102": "T",
    "060505104": "BAC",
    "931142103": "WMT",  "78462F103": "SPY",   "464287200": "IVV",
    "922908363": "VOO",
    # Additional well-known CUSIPs
    "025816109": "AXP",  # American Express
    "191216100": "KO",   # Coca-Cola (alt CUSIP)
    "17275R102": "CSCO", # Cisco
    "11135F101": "AVGO", # Broadcom
    "68389X105": "ORCL", # Oracle
    "747525103": "QCOM", # Qualcomm
    "02079K107": "GOOG", # Alphabet Class C
    "92343V104": "VZ",   # Verizon
    "713448108": "PEP",  # PepsiCo
    "254687106": "DIS",  # Disney
    "38141G104": "GS",   # Goldman Sachs
    "617446448": "MS",   # Morgan Stanley
    "949746101": "WFC",  # Wells Fargo
    "17296Q100": "COIN", # Coinbase (alt)
    "30231G102": "XOM",  # Exxon
    "166764100": "CVX",  # Chevron
    "20825C104": "COP",  # ConocoPhillips
    "12572Q105": "CME",  # CME Group
    "149123101": "CAT",  # Caterpillar
    "243893300": "DE",   # Deere
    "902973304": "UPS",  # UPS
}


def _resolve_ticker(name: str, cusip: str) -> Optional[str]:
    """Resolve a 13F holding to a ticker symbol (best-effort)."""
    # 1) CUSIP lookup
    if cusip and cusip in _CUSIP_TICKER_MAP:
        return _CUSIP_TICKER_MAP[cusip]

    # 2) Company name heuristic
    name_upper = name.upper().strip()
    # Common name → ticker mappings
    _NAME_MAP = {
        "APPLE": "AAPL", "MICROSOFT": "MSFT", "AMAZON": "AMZN",
        "ALPHABET": "GOOGL", "META PLATFORMS": "META", "NVIDIA": "NVDA",
        "TESLA": "TSLA", "BERKSHIRE": "BRK-B", "JPMORGAN": "JPM",
        "UNITEDHEALTH": "UNH", "JOHNSON & JOHNSON": "JNJ", "VISA": "V",
        "MASTERCARD": "MA", "PROCTER": "PG", "COSTCO": "COST",
        "HOME DEPOT": "HD", "WALMART": "WMT",
        "COCA COLA": "KO", "COCA-COLA": "KO",
        "PFIZER": "PFE", "MERCK": "MRK", "ELI LILLY": "LLY",
        "GENERAL ELECTRIC": "GE", "GENERAL MOTORS": "GM", "FORD MOTOR": "F",
        "BOEING": "BA", "INTEL": "INTC", "ADVANCED MICRO": "AMD",
        "SALESFORCE": "CRM", "ADOBE": "ADBE", "NETFLIX": "NFLX",
        "STARBUCKS": "SBUX", "NIKE": "NKE", "DISNEY": "DIS",
        "GOLDMAN SACHS": "GS", "MORGAN STANLEY": "MS",
        "BANK OF AMERICA": "BAC", "BANK AMERICA": "BAC",
        "WELLS FARGO": "WFC",
        "CITIGROUP": "C", "CHARLES SCHWAB": "SCHW",
        "BROADCOM": "AVGO", "QUALCOMM": "QCOM", "ORACLE": "ORCL",
        "CISCO": "CSCO", "COMCAST": "CMCSA", "VERIZON": "VZ",
        "AT&T": "T", "PEPSICO": "PEP", "ABBVIE": "ABBV",
        "THERMO FISHER": "TMO", "DANAHER": "DHR",
        "SERVICENOW": "NOW", "INTUIT": "INTU", "PAYPAL": "PYPL",
        "AIRBNB": "ABNB", "UBER": "UBER", "SHOPIFY": "SHOP",
        "PALANTIR": "PLTR", "SNOWFLAKE": "SNOW", "COINBASE": "COIN",
        "TARGET": "TGT", "LOWE": "LOW", "CATERPILLAR": "CAT",
        "DEERE": "DE", "3M": "MMM", "HONEYWELL": "HON",
        "RAYTHEON": "RTX", "LOCKHEED": "LMT", "NORTHROP": "NOC",
        "EXXON": "XOM", "CHEVRON": "CVX", "CONOCOPHILLIPS": "COP",
        "SPDR S&P": "SPY", "ISHARES CORE": "IVV",
        "AMERICAN EXPRESS": "AXP", "AMEX": "AXP",
        "KRAFT HEINZ": "KHC", "OCCIDENTAL": "OXY",
        "CHARTER COMM": "CHTR", "MOODY": "MCO",
        "DAVITA": "DVA", "LIBERTY MEDIA": "LSXM",
        "KROGER": "KR", "SIRIUS": "SIRI",
        "VERISIGN": "VRSN", "T-MOBILE": "TMUS",
        "MOLINA": "MOH", "LULULEMON": "LULU",
        "BRUKER": "BRKR",
    }

    for pattern, ticker in _NAME_MAP.items():
        if pattern in name_upper:
            return ticker

    return None


def _resolve_tickers_in_holdings(holdings: List[Dict]) -> List[Dict]:
    """Resolve ticker symbols for all holdings."""
    for h in holdings:
        if not h.get("ticker"):
            h["ticker"] = _resolve_ticker(h.get("name", ""), h.get("cusip", ""))
    return holdings


# ═══════════════════════════════════════════════════════════
#  Public API — For a specific ticker
# ═══════════════════════════════════════════════════════════

def fetch_guru_holdings_for_ticker(ticker: str) -> Dict[str, Any]:
    """
    Find which guru investors hold a given ticker.

    Returns
    -------
    {
        "ticker": str,
        "guru_holders": [
            {
                "investor": str,       # name (e.g. "Berkshire Hathaway (Warren Buffett)")
                "shares": int,
                "value_usd": int,
                "pct_of_portfolio": float,
                "filing_date": str,
                "report_date": str,
            }, ...
        ],
        "guru_count": int,
        "total_guru_value": int,  # total value held by all gurus
    }
    """
    ticker_upper = ticker.upper().strip()
    guru_holders = []

    for investor_name, cik in GURU_INVESTORS.items():
        try:
            filing = fetch_latest_13f(cik)
            if not filing or not filing.get("holdings"):
                continue

            holdings = _resolve_tickers_in_holdings(filing["holdings"])
            total_pf = filing.get("total_value", 1)

            for h in holdings:
                # Match by ticker or by company name partial match
                resolved = h.get("ticker", "")
                match = False
                if resolved and resolved.upper() == ticker_upper:
                    match = True
                elif not resolved:
                    # Try fuzzy name match with ticker (e.g., "AAPL" in "APPLE INC")
                    # This is imperfect but helps
                    pass

                if match and h.get("option_type", "") == "":
                    pct = (h["value_usd"] / total_pf * 100) if total_pf > 0 else 0
                    guru_holders.append({
                        "investor": investor_name,
                        "shares": h["shares"],
                        "value_usd": h["value_usd"],
                        "pct_of_portfolio": round(pct, 2),
                        "filing_date": filing.get("filing_date", "N/A"),
                        "report_date": filing.get("report_date", "N/A"),
                    })
                    break  # One entry per investor

        except Exception:
            continue

    # Sort by value descending
    guru_holders.sort(key=lambda x: x["value_usd"], reverse=True)
    total_guru_value = sum(g["value_usd"] for g in guru_holders)

    return {
        "ticker": ticker_upper,
        "guru_holders": guru_holders,
        "guru_count": len(guru_holders),
        "total_guru_value": total_guru_value,
    }


# ═══════════════════════════════════════════════════════════
#  Public API — Full portfolio of a specific guru
# ═══════════════════════════════════════════════════════════

def fetch_guru_portfolio(investor_name: str, top_n: int = 20) -> Optional[Dict[str, Any]]:
    """
    Fetch top N holdings for a specific guru investor.

    Returns
    -------
    {
        "investor": str,
        "filing_date": str,
        "report_date": str,
        "total_value": int,
        "holdings_count": int,
        "top_holdings": [
            {
                "rank": int,
                "name": str,
                "ticker": str | None,
                "shares": int,
                "value_usd": int,
                "pct_of_portfolio": float,
            }, ...
        ],
    }
    """
    cik = GURU_INVESTORS.get(investor_name)
    if not cik:
        return None

    filing = fetch_latest_13f(cik)
    if not filing or not filing.get("holdings"):
        return None

    holdings = _resolve_tickers_in_holdings(filing["holdings"])
    total = filing.get("total_value", 1)

    # Filter out options (puts/calls) and sort by value
    equity_holdings = [h for h in holdings if h.get("option_type", "") == ""]
    equity_holdings.sort(key=lambda x: x["value_usd"], reverse=True)

    top = []
    for i, h in enumerate(equity_holdings[:top_n]):
        pct = (h["value_usd"] / total * 100) if total > 0 else 0
        top.append({
            "rank": i + 1,
            "name": h["name"],
            "ticker": h.get("ticker") or "—",
            "shares": h["shares"],
            "value_usd": h["value_usd"],
            "pct_of_portfolio": round(pct, 2),
        })

    return {
        "investor": investor_name,
        "filing_date": filing.get("filing_date", "N/A"),
        "report_date": filing.get("report_date", "N/A"),
        "total_value": total,
        "holdings_count": len(equity_holdings),
        "top_holdings": top,
    }


# ═══════════════════════════════════════════════════════════
#  Public API — Compare two filings (quarter-over-quarter)
# ═══════════════════════════════════════════════════════════

def fetch_filing_changes(cik: str) -> Optional[Dict[str, Any]]:
    """
    Compare latest vs previous 13F filing to detect new buys, sells, increases, decreases.

    Returns
    -------
    {
        "new_positions": [...],
        "closed_positions": [...],
        "increased": [...],
        "decreased": [...],
    }
    or None if insufficient data.
    """
    # Get submissions to find last two 13F filings
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    data = _sec_get(url)
    if not data:
        return None

    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])

    # Find the two most recent 13F filings
    filing_indices = []
    for i, form in enumerate(forms):
        if form in ("13F-HR", "13F-HR/A"):
            filing_indices.append(i)
        if len(filing_indices) == 2:
            break

    if len(filing_indices) < 2:
        return None

    # We already have the latest via fetch_latest_13f, get the previous one
    # For now, return None — full QoQ comparison is complex
    # This can be expanded later
    return None
