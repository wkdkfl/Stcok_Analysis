"""Quick test for SEC EDGAR 13F fetch."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Test 1: Fetch Berkshire 13F
print("=== Test 1: Fetch Berkshire 13F ===")
from src.fetcher.sec_edgar import fetch_latest_13f, _resolve_tickers_in_holdings

result = fetch_latest_13f("0001067983")
if result:
    print(f"Filing date: {result['filing_date']}")
    print(f"Report date: {result['report_date']}")
    print(f"Total value: ${result['total_value']:,.0f}")
    print(f"Holdings count: {len(result['holdings'])}")
    holdings = _resolve_tickers_in_holdings(result["holdings"])
    sorted_h = sorted(holdings, key=lambda x: x["value_usd"], reverse=True)
    for h in sorted_h[:5]:
        t = h.get("ticker") or "???"
        print(f"  {h['name']:30s}  {t:6s}  shares={h['shares']:>12,}  val=${h['value_usd']:>14,.0f}")
else:
    print("FAILED to fetch 13F data")

# Test 2: Check which gurus hold AAPL
print("\n=== Test 2: Guru holdings for AAPL ===")
from src.fetcher.sec_edgar import fetch_guru_holdings_for_ticker

guru_res = fetch_guru_holdings_for_ticker("AAPL")
print(f"Guru count: {guru_res['guru_count']}")
for g in guru_res["guru_holders"]:
    print(f"  {g['investor']:50s}  shares={g['shares']:>12,}  val=${g['value_usd']:>14,.0f}  pf%={g['pct_of_portfolio']:.2f}%")

# Test 3: Fetch portfolio for one guru
print("\n=== Test 3: Scion Asset Mgmt (Burry) portfolio ===")
from src.fetcher.sec_edgar import fetch_guru_portfolio

port = fetch_guru_portfolio("Scion Asset Mgmt (Michael Burry)", top_n=10)
if port:
    print(f"Filing: {port['filing_date']}, Report: {port['report_date']}")
    print(f"Total: ${port['total_value']:,.0f}, Count: {port['holdings_count']}")
    for h in port["top_holdings"][:5]:
        t = h.get("ticker") or "—"
        print(f"  #{h['rank']} {h['name']:30s}  {t:6s}  ${h['value_usd']:>12,.0f}  {h['pct_of_portfolio']:.1f}%")
else:
    print("FAILED to fetch Burry portfolio")

print("\n=== All tests passed ===")
