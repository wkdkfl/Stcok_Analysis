"""
Beneish M-Score — Earnings manipulation detector.
8-variable model. M > -1.78 suggests possible manipulation.
Used by short sellers and forensic accounting funds.
"""

from typing import Dict, Any
from src.fetcher.yahoo import _get_stmt_value


def compute_beneish(data: Dict[str, Any]) -> Dict[str, Any]:
    """Compute Beneish M-Score."""
    result = {
        "m_score": None,
        "manipulation_risk": "N/A",
        "components": {},
    }

    inc = data.get("income_stmt")
    bs = data.get("balance_sheet")
    cf = data.get("cashflow")

    if inc is None or bs is None:
        return result

    def curr(stmt, names): return _get_stmt_value(stmt, names, 0)
    def prev(stmt, names): return _get_stmt_value(stmt, names, 1)

    # Current Year
    rev = curr(inc, ["Total Revenue", "Revenue"])
    cogs = curr(inc, ["Cost Of Revenue"])
    sga = curr(inc, ["Selling General And Administration"])
    da = curr(inc, ["Depreciation And Amortization In Income Statement", "Reconciled Depreciation"]) or \
         (curr(cf, ["Depreciation And Amortization"]) if cf is not None and not cf.empty else None)
    ni = curr(inc, ["Net Income", "Net Income Common Stockholders"])
    ta = curr(bs, ["Total Assets"])
    ca = curr(bs, ["Current Assets"])
    cl = curr(bs, ["Current Liabilities"])
    ppe = curr(bs, ["Net PPE", "Property Plant And Equipment Net"])
    ltd = curr(bs, ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"])
    rec = curr(bs, ["Net Receivables", "Accounts Receivable"])
    cfo = curr(cf, ["Operating Cash Flow"]) if cf is not None and not cf.empty else None

    # Prior Year
    rev_p = prev(inc, ["Total Revenue", "Revenue"])
    cogs_p = prev(inc, ["Cost Of Revenue"])
    sga_p = prev(inc, ["Selling General And Administration"])
    da_p = prev(inc, ["Depreciation And Amortization In Income Statement", "Reconciled Depreciation"]) or \
           (prev(cf, ["Depreciation And Amortization"]) if cf is not None and not cf.empty else None)
    ta_p = prev(bs, ["Total Assets"])
    ca_p = prev(bs, ["Current Assets"])
    cl_p = prev(bs, ["Current Liabilities"])
    ppe_p = prev(bs, ["Net PPE", "Property Plant And Equipment Net"])
    ltd_p = prev(bs, ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"])
    rec_p = prev(bs, ["Net Receivables", "Accounts Receivable"])

    # Need enough data points
    required = [rev, rev_p, ta, ta_p]
    if any(v is None or v == 0 for v in required):
        return result

    components = {}

    # 1. DSRI — Days Sales in Receivables Index
    if rec and rec_p and rev and rev_p and rev > 0 and rev_p > 0:
        dsri = (rec / rev) / (rec_p / rev_p)
        components["DSRI"] = round(dsri, 4)
    else:
        dsri = 1.0
        components["DSRI"] = None

    # 2. GMI — Gross Margin Index
    if cogs and cogs_p and rev > 0 and rev_p > 0:
        gm = (rev - cogs) / rev
        gm_p = (rev_p - cogs_p) / rev_p
        gmi = gm_p / gm if gm != 0 else 1.0
        components["GMI"] = round(gmi, 4)
    else:
        gmi = 1.0
        components["GMI"] = None

    # 3. AQI — Asset Quality Index
    if ca and ppe and ta and ca_p and ppe_p and ta_p and ta > 0 and ta_p > 0:
        aq = 1 - (ca + ppe) / ta
        aq_p = 1 - (ca_p + ppe_p) / ta_p
        aqi = aq / aq_p if aq_p != 0 else 1.0
        components["AQI"] = round(aqi, 4)
    else:
        aqi = 1.0
        components["AQI"] = None

    # 4. SGI — Sales Growth Index
    sgi = rev / rev_p if rev_p != 0 else 1.0
    components["SGI"] = round(sgi, 4)

    # 5. DEPI — Depreciation Index
    if da and da_p and ppe and ppe_p:
        dep_rate = da / (da + ppe) if (da + ppe) != 0 else 0
        dep_rate_p = da_p / (da_p + ppe_p) if (da_p + ppe_p) != 0 else 0
        depi = dep_rate_p / dep_rate if dep_rate != 0 else 1.0
        components["DEPI"] = round(depi, 4)
    else:
        depi = 1.0
        components["DEPI"] = None

    # 6. SGAI — SGA Expense Index
    if sga and sga_p and rev > 0 and rev_p > 0:
        sgai = (sga / rev) / (sga_p / rev_p)
        components["SGAI"] = round(sgai, 4)
    else:
        sgai = 1.0
        components["SGAI"] = None

    # 7. LVGI — Leverage Index
    if ltd and cl and ta and ltd_p and cl_p and ta_p and ta > 0 and ta_p > 0:
        lev = (ltd + cl) / ta
        lev_p = (ltd_p + cl_p) / ta_p
        lvgi = lev / lev_p if lev_p != 0 else 1.0
        components["LVGI"] = round(lvgi, 4)
    else:
        lvgi = 1.0
        components["LVGI"] = None

    # 8. TATA — Total Accruals to Total Assets
    if ni is not None and cfo is not None and ta > 0:
        tata = (ni - cfo) / ta
        components["TATA"] = round(tata, 4)
    else:
        tata = 0.0
        components["TATA"] = None

    # M-Score = -4.84 + 0.92×DSRI + 0.528×GMI + 0.404×AQI + 0.892×SGI
    #           + 0.115×DEPI - 0.172×SGAI + 4.679×TATA - 0.327×LVGI
    m = (-4.84
         + 0.920 * dsri
         + 0.528 * gmi
         + 0.404 * aqi
         + 0.892 * sgi
         + 0.115 * depi
         - 0.172 * sgai
         + 4.679 * tata
         - 0.327 * lvgi)

    result["m_score"] = round(m, 2)
    result["components"] = components

    if m > -1.78:
        result["manipulation_risk"] = "⚠️ High (Possible Manipulation)"
    elif m > -2.22:
        result["manipulation_risk"] = "Moderate"
    else:
        result["manipulation_risk"] = "Low"

    return result
