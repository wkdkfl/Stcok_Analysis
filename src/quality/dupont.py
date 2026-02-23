"""
DuPont 5-Factor Decomposition.
ROE = Tax Burden × Interest Burden × Operating Margin × Asset Turnover × Equity Multiplier
Diagnoses WHY ROE changed over time.
"""

from typing import Dict, Any, List
from src.fetcher.yahoo import _get_stmt_value


def compute_dupont(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute 5-Factor DuPont decomposition.
    """
    result = {
        "roe": None,
        "decomposition": {},
        "time_series": [],  # for multi-year analysis
    }

    inc = data.get("income_stmt")
    bs = data.get("balance_sheet")

    if inc is None or bs is None:
        return result

    # Compute for each available year
    n_cols = min(inc.shape[1], bs.shape[1]) if inc is not None and bs is not None else 0

    for i in range(n_cols):
        year_data = _compute_year(inc, bs, i)
        if year_data:
            result["time_series"].append(year_data)

    # Current year decomposition
    if result["time_series"]:
        result["decomposition"] = result["time_series"][0]
        result["roe"] = result["time_series"][0].get("roe")

    return result


def _compute_year(inc, bs, col_idx: int) -> dict:
    """Compute DuPont for a single year."""
    try:
        ni = _get_stmt_value(inc, ["Net Income", "Net Income Common Stockholders"], col_idx)
        ebt = _get_stmt_value(inc, ["Pretax Income"], col_idx)
        ebit = _get_stmt_value(inc, ["EBIT", "Operating Income"], col_idx)
        rev = _get_stmt_value(inc, ["Total Revenue", "Revenue"], col_idx)
        ta = _get_stmt_value(bs, ["Total Assets"], col_idx)
        equity = _get_stmt_value(bs, ["Total Equity Gross Minority Interest",
                                       "Stockholders Equity"], col_idx)

        if not all([ni, ebt, ebit, rev, ta, equity]) or any(
            v == 0 for v in [ebt, ebit, rev, ta, equity]
        ):
            return None

        # 5-Factor DuPont
        tax_burden = ni / ebt                    # NI / EBT
        interest_burden = ebt / ebit              # EBT / EBIT
        operating_margin = ebit / rev             # EBIT / Revenue
        asset_turnover = rev / ta                 # Revenue / Total Assets
        equity_multiplier = ta / equity           # Total Assets / Equity

        roe = tax_burden * interest_burden * operating_margin * asset_turnover * equity_multiplier

        # Get year label from column
        try:
            year = str(inc.columns[col_idx])[:4]
        except Exception:
            year = str(col_idx)

        return {
            "year": year,
            "roe": round(roe * 100, 2),
            "tax_burden": round(tax_burden, 4),
            "interest_burden": round(interest_burden, 4),
            "operating_margin": round(operating_margin * 100, 2),
            "asset_turnover": round(asset_turnover, 4),
            "equity_multiplier": round(equity_multiplier, 2),
        }

    except Exception:
        return None
