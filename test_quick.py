"""Quick functional test for data fetch + valuation pipeline."""
import sys
sys.path.insert(0, "c:/2_Study/stock")

from src.fetcher.yahoo import fetch_stock_data

print("=== Fetching AAPL data ===")
data = fetch_stock_data("AAPL")
print(f"Ticker: {data['ticker']}")
print(f"Name: {data['name']}")
print(f"Price: {data['current_price']}")
print(f"Sector: {data['sector']}")
print(f"Market Cap: {data['market_cap']}")
print(f"PE: {data.get('trailing_pe')}")
print(f"FCF: {data.get('fcf')}")
print(f"ROIC: {data.get('roic')}")
print(f"Beta: {data.get('beta')}")
print(f"Shares Out: {data.get('shares_outstanding')}")
print("Data fetch OK\n")

# Test valuation
from src.valuation.aggregator import run_all_valuations
print("=== Running Valuation Models ===")
val = run_all_valuations(data, {})
print(f"Fair Value: ${val.get('fair_value', 'N/A')}")
print(f"Upside: {val.get('upside_pct', 'N/A')}%")
print(f"Signal: {val.get('signal', 'N/A')}")
for m in val.get("models_summary", []):
    print(f"  {m}")

# Test quality
from src.quality.piotroski import compute_piotroski
from src.quality.altman import compute_altman_z
print("\n=== Quality ===")
p = compute_piotroski(data)
print(f"Piotroski: {p['score']}/9 ({p['grade']})")
a = compute_altman_z(data)
print(f"Altman Z: {a.get('z_score')} ({a.get('zone')})")

# Test risk
from src.risk.metrics import compute_risk_metrics
print("\n=== Risk ===")
r = compute_risk_metrics(data)
print(f"Risk Level: {r['overall_risk']}")
print(f"Sharpe: {r['return_metrics']['sharpe_ratio']}")

# Test grading
from src.grading.category_grades import compute_all_grades
print("\n=== Category Grades ===")
# Build results dict like app.py does
from src.quality.beneish import compute_beneish
from src.quality.dupont import compute_dupont
from src.quality.earnings_quality import compute_earnings_quality, compute_eva, compute_quality_grade
from src.quant.signals import compute_quant_signals
from src.smart_money.signals import compute_smart_money
from src.sector.detector import detect_and_compute_sector_metrics

fake_results = {
    "data": data,
    "valuation": val,
    "piotroski": p,
    "altman": a,
    "beneish": compute_beneish(data),
    "dupont": compute_dupont(data),
    "earnings_quality": compute_earnings_quality(data),
    "eva": compute_eva(data),
    "quality_grade": compute_quality_grade(p, a, compute_beneish(data), compute_earnings_quality(data), compute_eva(data)),
    "smart_money": compute_smart_money(data),
    "quant": compute_quant_signals(data),
    "risk": r,
    "sector_metrics": detect_and_compute_sector_metrics(data),
    "macro": None,
}

grades = compute_all_grades(fake_results)
print(f"Overall: {grades['overall_grade']} ({grades['overall_score']}) -> {grades['signal']}")
for cat, info in grades["categories"].items():
    print(f"  {cat:15s}  {info['grade']:3s}  ({info['score']:.0f}/100)")

print("\n=== ALL TESTS PASSED ===")
