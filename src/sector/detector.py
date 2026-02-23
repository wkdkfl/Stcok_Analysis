"""
Sector-specific metrics detector and router.
Auto-detects sector from yfinance and computes relevant specialized metrics.
"""

from typing import Dict, Any
from src.fetcher.yahoo import _get_stmt_value, get_stmt_series


def detect_and_compute_sector_metrics(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Detect sector and compute specialized metrics.
    """
    sector = data.get("sector", "")
    industry = data.get("industry", "").lower()

    result = {
        "sector": sector,
        "industry": data.get("industry", ""),
        "metrics": {},
        "sector_type": "General",
    }

    if sector == "Technology" or "software" in industry or "saas" in industry:
        result["metrics"] = _compute_tech_metrics(data)
        result["sector_type"] = "Technology / SaaS"

    elif sector == "Financial Services" or "bank" in industry:
        result["metrics"] = _compute_financial_metrics(data)
        result["sector_type"] = "Financials / Banks"

    elif sector == "Real Estate" or "reit" in industry:
        result["metrics"] = _compute_reit_metrics(data)
        result["sector_type"] = "Real Estate / REIT"

    elif sector == "Healthcare" or "biotech" in industry or "pharma" in industry:
        result["metrics"] = _compute_healthcare_metrics(data)
        result["sector_type"] = "Healthcare / Biotech"

    elif sector in ("Consumer Cyclical", "Consumer Defensive") or "retail" in industry:
        result["metrics"] = _compute_retail_metrics(data)
        result["sector_type"] = "Consumer / Retail"

    elif sector == "Energy" or "oil" in industry:
        result["metrics"] = _compute_energy_metrics(data)
        result["sector_type"] = "Energy"

    else:
        result["metrics"] = _compute_general_metrics(data)
        result["sector_type"] = f"General ({sector})"

    return result


def _compute_tech_metrics(data: Dict[str, Any]) -> Dict:
    """Technology / SaaS specific metrics."""
    metrics = {}

    rev_growth = data.get("revenue_growth")
    fcf = data.get("fcf")
    rev = data.get("revenue")

    # Rule of 40
    if rev_growth is not None and fcf is not None and rev and rev > 0:
        fcf_margin = fcf / rev
        rule_of_40 = (rev_growth + fcf_margin) * 100
        metrics["rule_of_40"] = round(rule_of_40, 1)
        metrics["rule_of_40_pass"] = rule_of_40 >= 40

    # Revenue growth rate
    if rev_growth:
        metrics["revenue_growth"] = round(rev_growth * 100, 1)

    # FCF Margin
    if fcf and rev and rev > 0:
        metrics["fcf_margin"] = round((fcf / rev) * 100, 1)

    # R&D intensity
    inc = data.get("income_stmt")
    rd = _get_stmt_value(inc, ["Research And Development", "Research Development"])
    if rd and rev and rev > 0:
        metrics["rd_intensity"] = round((rd / rev) * 100, 1)

    # SGA Ratio
    sga = _get_stmt_value(inc, ["Selling General And Administration"])
    if sga and rev and rev > 0:
        metrics["sga_ratio"] = round((sga / rev) * 100, 1)

    # Gross Margin
    gm = data.get("gross_margin")
    if gm:
        metrics["gross_margin"] = round(gm * 100, 1)

    # Magic Number approximation (net new revenue / prior S&M)
    rev_series = get_stmt_series(inc, ["Total Revenue", "Revenue"])
    sga_series = get_stmt_series(inc, ["Selling General And Administration"])
    if rev_series is not None and sga_series is not None and len(rev_series) >= 2 and len(sga_series) >= 2:
        try:
            new_rev = float(rev_series.iloc[0]) - float(rev_series.iloc[1])
            prior_sga = float(sga_series.iloc[1])
            if prior_sga > 0:
                magic_number = new_rev / prior_sga
                metrics["magic_number"] = round(magic_number, 2)
        except Exception:
            pass

    return metrics


def _compute_financial_metrics(data: Dict[str, Any]) -> Dict:
    """Financial / Banks metrics."""
    metrics = {}

    # Tangible Book Value per share
    tbvps = data.get("tbv_per_share")
    if tbvps:
        metrics["tangible_bv_per_share"] = round(tbvps, 2)
        current = data.get("current_price", 0)
        if current and tbvps > 0:
            metrics["price_to_tbv"] = round(current / tbvps, 2)

    # ROTCE approximation
    ni = data.get("net_income")
    tbv = data.get("tangible_book_value")
    if ni and tbv and tbv > 0:
        metrics["rotce"] = round((ni / tbv) * 100, 1)

    # Efficiency ratio approximation (non-interest expense / revenue)
    inc = data.get("income_stmt")
    rev = data.get("revenue")
    op_exp = _get_stmt_value(inc, ["Total Operating Expenses", "Operating Expense"])
    if op_exp and rev and rev > 0:
        metrics["efficiency_ratio"] = round((op_exp / rev) * 100, 1)

    # D/E
    metrics["debt_to_equity"] = data.get("debt_to_equity")

    return metrics


def _compute_reit_metrics(data: Dict[str, Any]) -> Dict:
    """Real Estate / REIT metrics."""
    metrics = {}

    # FFO approximation: Net Income + Depreciation
    ni = data.get("net_income")
    dep = data.get("depreciation")
    shares = data.get("shares_outstanding")
    current = data.get("current_price")

    if ni is not None and dep is not None:
        ffo = ni + abs(dep)
        metrics["ffo"] = round(ffo / 1e6, 1)  # in millions
        if shares and shares > 0:
            ffo_per_share = ffo / shares
            metrics["ffo_per_share"] = round(ffo_per_share, 2)
            if current and current > 0:
                metrics["p_ffo"] = round(current / ffo_per_share, 1)

    # AFFO approximation: FFO - CapEx
    capex = _get_stmt_value(data.get("cashflow"), ["Capital Expenditure"])
    if ni is not None and dep is not None and capex is not None:
        affo = ni + abs(dep) + capex  # capex is negative
        metrics["affo"] = round(affo / 1e6, 1)
        if shares and shares > 0:
            affo_per_share = affo / shares
            metrics["affo_per_share"] = round(affo_per_share, 2)

    # Dividend yield
    metrics["dividend_yield"] = round((data.get("dividend_yield") or 0) * 100, 2)

    return metrics


def _compute_healthcare_metrics(data: Dict[str, Any]) -> Dict:
    """Healthcare / Biotech metrics."""
    metrics = {}

    # Cash runway (cash / quarterly burn rate)
    cash = data.get("cash")
    cf_q = data.get("cashflow_q")
    if cash and cf_q is not None:
        op_cf_q = _get_stmt_value(cf_q, ["Operating Cash Flow"], 0)
        if op_cf_q and op_cf_q < 0:
            quarters = cash / abs(op_cf_q)
            metrics["cash_runway_quarters"] = round(quarters, 1)
            metrics["cash_runway_years"] = round(quarters / 4, 1)

    # R&D Intensity
    inc = data.get("income_stmt")
    rd = _get_stmt_value(inc, ["Research And Development"])
    rev = data.get("revenue")
    if rd and rev and rev > 0:
        metrics["rd_intensity"] = round((rd / rev) * 100, 1)
    elif rd:
        metrics["rd_spend"] = round(rd / 1e6, 1)  # in millions

    # Cash position
    if cash:
        metrics["cash_position"] = round(cash / 1e6, 1)

    # Profit status
    ni = data.get("net_income")
    metrics["profitable"] = ni is not None and ni > 0

    return metrics


def _compute_retail_metrics(data: Dict[str, Any]) -> Dict:
    """Consumer / Retail metrics."""
    metrics = {}

    # Inventory Turnover = COGS / Avg Inventory
    inc = data.get("income_stmt")
    bs = data.get("balance_sheet")

    cogs = _get_stmt_value(inc, ["Cost Of Revenue"])
    inventory = _get_stmt_value(bs, ["Inventory"])
    if cogs and inventory and inventory > 0:
        metrics["inventory_turnover"] = round(cogs / inventory, 1)

    # Gross margin
    gm = data.get("gross_margin")
    if gm:
        metrics["gross_margin"] = round(gm * 100, 1)

    # Revenue per employee
    rev = data.get("revenue")
    emp = data.get("employees")
    if rev and emp and emp > 0:
        metrics["revenue_per_employee"] = round(rev / emp)

    # Same-store-sales not available from yfinance — note this
    metrics["note"] = "SSS data requires 10-K filing (not available via API)"

    return metrics


def _compute_energy_metrics(data: Dict[str, Any]) -> Dict:
    """Energy sector metrics."""
    metrics = {}

    # CapEx / Revenue
    cf = data.get("cashflow")
    capex = _get_stmt_value(cf, ["Capital Expenditure"])
    rev = data.get("revenue")
    if capex and rev and rev > 0:
        metrics["capex_to_revenue"] = round(abs(capex) / rev * 100, 1)

    # FCF Yield
    fcf = data.get("fcf")
    mc = data.get("market_cap")
    if fcf and mc and mc > 0:
        metrics["fcf_yield"] = round(fcf / mc * 100, 1)

    # Depreciation adequacy
    dep = data.get("depreciation")
    if dep and capex:
        metrics["dep_to_capex"] = round(abs(dep) / abs(capex) * 100, 1)

    # Dividend yield
    metrics["dividend_yield"] = round((data.get("dividend_yield") or 0) * 100, 2)

    return metrics


def _compute_general_metrics(data: Dict[str, Any]) -> Dict:
    """General metrics for unclassified sectors."""
    return {
        "gross_margin": round((data.get("gross_margin") or 0) * 100, 1),
        "operating_margin": round((data.get("operating_margin") or 0) * 100, 1),
        "roic": round((data.get("roic") or 0) * 100, 1),
        "revenue_growth": round((data.get("revenue_growth") or 0) * 100, 1),
    }
