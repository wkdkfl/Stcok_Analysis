"""
Yahoo Finance data fetcher — primary data source for all financial data.
Uses yfinance library for price, financials, balance sheet, cash flow,
analyst estimates, insider transactions, and options data.
Parallelized: .info first, then remaining sub-calls via ThreadPool.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, Optional
import streamlit as st
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from config import CACHE_TTL
from src.fetcher.ssl_session import get_session


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def fetch_stock_data(ticker: str) -> Dict[str, Any]:
    """
    Fetch comprehensive stock data from Yahoo Finance.
    Returns a dictionary with all relevant financial data.
    """
    t = yf.Ticker(ticker, session=get_session())
    info = _safe_info(t)
    data: Dict[str, Any] = {}

    # ── Basic Info ───────────────────────────────────────
    data["ticker"] = ticker.upper()
    data["name"] = info.get("longName", info.get("shortName", ticker))
    data["sector"] = info.get("sector", "N/A")
    data["industry"] = info.get("industry", "N/A")
    data["country"] = info.get("country", "N/A")
    data["employees"] = info.get("fullTimeEmployees", None)
    data["description"] = info.get("longBusinessSummary", "")
    data["currency"] = info.get("currency", "USD")
    data["exchange"] = info.get("exchange", "")

    # ── Market detection ─────────────────────────────────
    from src.market_context import detect_market_from_data
    data["market"] = detect_market_from_data(data)

    # ── Price & Market Data ──────────────────────────────
    data["current_price"] = info.get("currentPrice", info.get("regularMarketPrice", None))
    data["market_cap"] = info.get("marketCap", None)
    data["enterprise_value"] = info.get("enterpriseValue", None)
    data["beta"] = info.get("beta", None)
    data["fifty_two_week_high"] = info.get("fiftyTwoWeekHigh", None)
    data["fifty_two_week_low"] = info.get("fiftyTwoWeekLow", None)
    data["avg_volume"] = info.get("averageVolume", None)
    data["shares_outstanding"] = info.get("sharesOutstanding", None)
    data["float_shares"] = info.get("floatShares", None)

    # ── Dividend Data ────────────────────────────────────
    data["dividend_rate"] = info.get("dividendRate", 0)
    data["dividend_yield"] = info.get("dividendYield", 0)
    data["payout_ratio"] = info.get("payoutRatio", 0)
    data["ex_dividend_date"] = info.get("exDividendDate", None)

    # ── Valuation Ratios ─────────────────────────────────
    data["trailing_pe"] = info.get("trailingPE", None)
    data["forward_pe"] = info.get("forwardPE", None)
    data["peg_ratio"] = info.get("pegRatio", None)
    data["price_to_book"] = info.get("priceToBook", None)
    data["price_to_sales"] = info.get("priceToSalesTrailing12Months", None)
    data["ev_to_ebitda"] = info.get("enterpriseToEbitda", None)
    data["ev_to_revenue"] = info.get("enterpriseToRevenue", None)
    data["price_to_fcf"] = _safe_div(data["market_cap"],
                                      info.get("freeCashflow", None))

    # ── Profitability ────────────────────────────────────
    data["gross_margin"] = info.get("grossMargins", None)
    data["operating_margin"] = info.get("operatingMargins", None)
    data["profit_margin"] = info.get("profitMargins", None)
    data["roe"] = info.get("returnOnEquity", None)
    data["roa"] = info.get("returnOnAssets", None)

    # ── Per-Share Data ───────────────────────────────────
    data["eps_trailing"] = info.get("trailingEps", None)
    data["eps_forward"] = info.get("forwardEps", None)
    data["bps"] = info.get("bookValue", None)
    data["revenue_per_share"] = info.get("revenuePerShare", None)

    # ── Analyst Estimates ────────────────────────────────
    data["target_mean"] = info.get("targetMeanPrice", None)
    data["target_high"] = info.get("targetHighPrice", None)
    data["target_low"] = info.get("targetLowPrice", None)
    data["recommendation"] = info.get("recommendationKey", None)
    data["num_analysts"] = info.get("numberOfAnalystOpinions", None)
    data["earnings_growth"] = info.get("earningsGrowth", None)
    data["revenue_growth"] = info.get("revenueGrowth", None)
    data["earnings_quarterly_growth"] = info.get("earningsQuarterlyGrowth", None)

    # ── Short Interest ───────────────────────────────────
    data["short_ratio"] = info.get("shortRatio", None)
    data["short_pct_float"] = info.get("shortPercentOfFloat",
                                        info.get("sharesPercentSharesOut", None))

    # ── Institutional / Insider Ownership ────────────────
    data["held_pct_insiders"] = info.get("heldPercentInsiders", None)
    data["held_pct_institutions"] = info.get("heldPercentInstitutions", None)

    # ── Financial Statements (Annual, up to 4 years) ─────
    # ── Parallel fetch: statements, history, holders, options ──
    def _f_inc_a(): return _safe_financials(t, "annual", "income")
    def _f_bs_a(): return _safe_financials(t, "annual", "balance")
    def _f_cf_a(): return _safe_financials(t, "annual", "cashflow")
    def _f_inc_q(): return _safe_financials(t, "quarterly", "income")
    def _f_bs_q(): return _safe_financials(t, "quarterly", "balance")
    def _f_cf_q(): return _safe_financials(t, "quarterly", "cashflow")
    def _f_hist(): return _safe_history(t, period="5y", interval="1d")
    def _f_insider(): return _safe_attr(t, "insider_transactions")
    def _f_inst(): return _safe_attr(t, "institutional_holders")
    def _f_major(): return _safe_attr(t, "major_holders")
    def _f_earnings(): return _safe_attr(t, "earnings_history")
    def _f_opt_dates(): return _safe_options_dates(t)
    def _f_opt_chain(): return _safe_options_chain(t)

    tasks = {
        "income_stmt": _f_inc_a,
        "balance_sheet": _f_bs_a,
        "cashflow": _f_cf_a,
        "income_stmt_q": _f_inc_q,
        "balance_sheet_q": _f_bs_q,
        "cashflow_q": _f_cf_q,
        "history": _f_hist,
        "insider_transactions": _f_insider,
        "institutional_holders": _f_inst,
        "major_holders": _f_major,
        "earnings_history": _f_earnings,
        "options_dates": _f_opt_dates,
        "options_chain": _f_opt_chain,
    }

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(fn): key for key, fn in tasks.items()}
        for future in as_completed(futures):
            key = futures[future]
            try:
                data[key] = future.result()
            except Exception:
                data[key] = None

    # ── Derived Metrics ──────────────────────────────────
    data = _compute_derived(data, info)

    return data


def _safe_info(t: yf.Ticker) -> dict:
    """Safely get ticker info."""
    try:
        return t.info or {}
    except Exception:
        return {}


def _safe_financials(t: yf.Ticker, period: str, stmt_type: str) -> Optional[pd.DataFrame]:
    """Safely get financial statements."""
    try:
        if period == "annual":
            if stmt_type == "income":
                return t.income_stmt
            elif stmt_type == "balance":
                return t.balance_sheet
            else:
                return t.cashflow
        else:
            if stmt_type == "income":
                return t.quarterly_income_stmt
            elif stmt_type == "balance":
                return t.quarterly_balance_sheet
            else:
                return t.quarterly_cashflow
    except Exception:
        return None


def _safe_history(t: yf.Ticker, period: str, interval: str) -> Optional[pd.DataFrame]:
    """Safely get historical prices."""
    try:
        h = t.history(period=period, interval=interval)
        return h if h is not None and not h.empty else None
    except Exception:
        return None


def _safe_attr(t: yf.Ticker, attr_name: str) -> Optional[pd.DataFrame]:
    """Safely get a Ticker attribute that returns a DataFrame."""
    try:
        val = getattr(t, attr_name, None)
        if val is not None and isinstance(val, pd.DataFrame) and not val.empty:
            return val
        return None
    except Exception:
        return None


def _safe_options_dates(t: yf.Ticker) -> list:
    """Safely get options expiration dates."""
    try:
        return list(t.options) if t.options else []
    except Exception:
        return []


def _safe_options_chain(t: yf.Ticker) -> Optional[dict]:
    """Get nearest-expiry options chain for put/call analysis."""
    try:
        dates = t.options
        if not dates:
            return None
        chain = t.option_chain(dates[0])
        return {"calls": chain.calls, "puts": chain.puts}
    except Exception:
        return None


def _safe_div(a, b) -> Optional[float]:
    """Safe division."""
    try:
        if a is not None and b is not None and b != 0:
            return a / b
    except (TypeError, ZeroDivisionError):
        pass
    return None


def _get_stmt_value(stmt: Optional[pd.DataFrame], row_names: list,
                    col_idx: int = 0) -> Optional[float]:
    """Get a value from a financial statement by trying multiple row names."""
    if stmt is None or stmt.empty:
        return None
    for name in row_names:
        if name in stmt.index:
            try:
                val = stmt.iloc[stmt.index.get_loc(name), col_idx]
                if pd.notna(val):
                    return float(val)
            except (IndexError, KeyError):
                continue
    return None


def get_stmt_series(stmt: Optional[pd.DataFrame], row_names: list) -> Optional[pd.Series]:
    """Get a time series (all columns) from a financial statement."""
    if stmt is None or stmt.empty:
        return None
    for name in row_names:
        if name in stmt.index:
            try:
                s = stmt.loc[name]
                if s.notna().any():
                    return s.astype(float)
            except Exception:
                continue
    return None


def _compute_derived(data: Dict[str, Any], info: dict) -> Dict[str, Any]:
    """Compute derived financial metrics from raw data."""
    inc = data.get("income_stmt")
    bs = data.get("balance_sheet")
    cf = data.get("cashflow")

    # ── Free Cash Flow ───────────────────────────────────
    op_cf = _get_stmt_value(cf, ["Operating Cash Flow", "Total Cash From Operating Activities"])
    capex = _get_stmt_value(cf, ["Capital Expenditure", "Capital Expenditures"])
    if op_cf is not None and capex is not None:
        data["fcf"] = op_cf + capex  # capex is typically negative
    else:
        data["fcf"] = info.get("freeCashflow", None)

    # ── EBIT / EBITDA ────────────────────────────────────
    data["ebit"] = _get_stmt_value(inc, ["EBIT", "Operating Income"])
    data["ebitda"] = _get_stmt_value(inc, ["EBITDA", "Normalized EBITDA"])
    if data["ebitda"] is None:
        data["ebitda"] = info.get("ebitda", None)

    # ── Revenue / Net Income ─────────────────────────────
    data["revenue"] = _get_stmt_value(inc, ["Total Revenue", "Revenue"])
    data["net_income"] = _get_stmt_value(inc, ["Net Income", "Net Income Common Stockholders"])
    data["gross_profit"] = _get_stmt_value(inc, ["Gross Profit"])
    data["interest_expense"] = _get_stmt_value(inc, ["Interest Expense", "Interest Expense Non Operating"])

    # ── Balance Sheet Items ──────────────────────────────
    data["total_assets"] = _get_stmt_value(bs, ["Total Assets"])
    data["total_liabilities"] = _get_stmt_value(bs, ["Total Liabilities Net Minority Interest", "Total Liab"])
    data["total_equity"] = _get_stmt_value(bs, ["Total Equity Gross Minority Interest",
                                                  "Stockholders Equity", "Total Stockholder Equity"])
    data["total_debt"] = _get_stmt_value(bs, ["Total Debt", "Long Term Debt And Capital Lease Obligation"])
    data["cash"] = _get_stmt_value(bs, ["Cash And Cash Equivalents", "Cash"])
    data["current_assets"] = _get_stmt_value(bs, ["Current Assets"])
    data["current_liabilities"] = _get_stmt_value(bs, ["Current Liabilities"])
    data["goodwill"] = _get_stmt_value(bs, ["Goodwill"])
    data["intangibles"] = _get_stmt_value(bs, ["Intangible Assets", "Other Intangible Assets"])
    data["retained_earnings"] = _get_stmt_value(bs, ["Retained Earnings"])
    data["working_capital"] = _get_stmt_value(bs, ["Working Capital"])

    # ── Depreciation & Amortization ──────────────────────
    data["depreciation"] = _get_stmt_value(cf, ["Depreciation And Amortization",
                                                  "Depreciation & Amortization"])

    # ── Stock Buyback ────────────────────────────────────
    data["buyback"] = _get_stmt_value(cf, ["Repurchase Of Capital Stock",
                                            "Common Stock Repurchased"])

    # ── Computed Ratios ──────────────────────────────────
    data["debt_to_equity"] = _safe_div(data.get("total_debt"), data.get("total_equity"))
    data["net_debt"] = None
    if data.get("total_debt") is not None and data.get("cash") is not None:
        data["net_debt"] = data["total_debt"] - data["cash"]
    data["net_debt_to_ebitda"] = _safe_div(data.get("net_debt"), data.get("ebitda"))
    data["interest_coverage"] = _safe_div(data.get("ebit"), abs(data["interest_expense"])
                                           if data.get("interest_expense") else None)
    data["current_ratio"] = _safe_div(data.get("current_assets"), data.get("current_liabilities"))

    # ── NOPAT & Invested Capital (for ROIC) ──────────────
    from src.market_context import detect_market, get_market_defaults
    _mkt = detect_market(data.get("ticker", ""))
    _mkt_defaults = get_market_defaults(_mkt)
    tax_rate = info.get("taxRate", _mkt_defaults["tax_rate"])
    if isinstance(tax_rate, (int, float)) and data.get("ebit"):
        data["nopat"] = data["ebit"] * (1 - tax_rate)
    else:
        data["nopat"] = None

    invested_capital = None
    if data.get("total_equity") is not None and data.get("total_debt") is not None:
        cash_val = data.get("cash") or 0
        invested_capital = data["total_equity"] + data["total_debt"] - cash_val
    data["invested_capital"] = invested_capital
    data["roic"] = _safe_div(data.get("nopat"), invested_capital)

    # ── Tangible Book Value ──────────────────────────────
    tbv = data.get("total_equity")
    if tbv is not None:
        tbv -= (data.get("goodwill") or 0) + (data.get("intangibles") or 0)
    data["tangible_book_value"] = tbv
    data["tbv_per_share"] = _safe_div(tbv, data.get("shares_outstanding"))

    # ── Cash Conversion Ratio ────────────────────────────
    data["cash_conversion"] = _safe_div(data.get("fcf"), data.get("net_income"))

    # ── Accrual Ratio ────────────────────────────────────
    if data.get("net_income") is not None and op_cf is not None and data.get("total_assets"):
        data["accrual_ratio"] = (data["net_income"] - op_cf) / data["total_assets"]
    else:
        data["accrual_ratio"] = None

    # ── Revenue & EPS Growth (YoY from statements) ───────
    rev_series = get_stmt_series(inc, ["Total Revenue", "Revenue"])
    if rev_series is not None and len(rev_series) >= 2:
        data["revenue_growth_hist"] = rev_series.pct_change(-1).dropna()
    else:
        data["revenue_growth_hist"] = None

    ni_series = get_stmt_series(inc, ["Net Income", "Net Income Common Stockholders"])
    if ni_series is not None and len(ni_series) >= 2:
        data["ni_growth_hist"] = ni_series.pct_change(-1).dropna()
    else:
        data["ni_growth_hist"] = None

    # ── Total Shareholder Yield ──────────────────────────
    div_paid = abs(_get_stmt_value(cf, ["Cash Dividends Paid",
                                         "Common Stock Dividend Paid"]) or 0)
    buyback_val = abs(data.get("buyback") or 0)
    mc = data.get("market_cap")
    if mc and mc > 0:
        data["total_shareholder_yield"] = (div_paid + buyback_val) / mc
    else:
        data["total_shareholder_yield"] = None

    return data
