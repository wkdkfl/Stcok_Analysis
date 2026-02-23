"""Debug yfinance data fetch."""
import sys
sys.path.insert(0, "c:/2_Study/stock")

from src.fetcher.ssl_session import get_session
import yfinance as yf

session = get_session()
print(f"yfinance version: {yf.__version__}")
print(f"Session type: {type(session)}")

t = yf.Ticker("AAPL", session=session)

# Try each data source
print("\n--- info ---")
try:
    info = t.info
    if info:
        print(f"  Keys count: {len(info)}")
        for k in ["shortName", "currentPrice", "sector", "marketCap"]:
            print(f"  {k}: {info.get(k)}")
    else:
        print("  info is None/empty")
except Exception as e:
    print(f"  ERROR: {e}")

print("\n--- history ---")
try:
    h = t.history(period="5d")
    print(f"  Shape: {h.shape}")
    if not h.empty:
        print(f"  Last close: {h['Close'].iloc[-1]}")
    else:
        print("  Empty DataFrame")
except Exception as e:
    print(f"  ERROR: {e}")

print("\n--- financials ---")
try:
    f = t.financials
    if f is not None and not f.empty:
        print(f"  Shape: {f.shape}")
        print(f"  Columns (dates): {list(f.columns[:3])}")
    else:
        print("  Empty")
except Exception as e:
    print(f"  ERROR: {e}")

print("\n--- balance_sheet ---")
try:
    bs = t.balance_sheet
    if bs is not None and not bs.empty:
        print(f"  Shape: {bs.shape}")
    else:
        print("  Empty")
except Exception as e:
    print(f"  ERROR: {e}")

print("\n--- cashflow ---")
try:
    cf = t.cashflow
    if cf is not None and not cf.empty:
        print(f"  Shape: {cf.shape}")
    else:
        print("  Empty")
except Exception as e:
    print(f"  ERROR: {e}")

print("\nDONE")
