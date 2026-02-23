"""
Global configuration for Stock Intrinsic Value Analyzer.
"""

# ── FRED API ────────────────────────────────────────────────
# 무료 키 발급: https://fred.stlouisfed.org/docs/api/api_key.html
FRED_API_KEY = ""  # 여기에 FRED API 키를 입력하세요 (없어도 기본 동작 가능)

# ── DCF 기본 가정 ───────────────────────────────────────────
DCF_DEFAULTS = {
    "high_growth_years": 5,
    "fade_years": 5,
    "terminal_growth_rate": 0.025,        # 2.5%
    "risk_free_rate": 0.043,               # 10Y Treasury (동적 업데이트)
    "equity_risk_premium": 0.055,          # Damodaran ERP
    "default_wacc": 0.10,                  # 10%
    "tax_rate": 0.21,                      # US corporate
    "monte_carlo_simulations": 10_000,
    "growth_rate_std": 0.03,               # MC 시뮬레이션 변동
    "wacc_std": 0.02,
    "margin_std": 0.05,
}

# ── 밸류에이션 모델 가중치 ──────────────────────────────────
MODEL_WEIGHTS = {
    "dcf": 0.30,
    "reverse_dcf": 0.0,       # 시그널 전용, 가격 산출에 미포함
    "residual_income": 0.15,
    "epv": 0.15,
    "ddm": 0.10,              # 배당주만 활성
    "multiples": 0.20,
    "graham": 0.10,
}

# ── 섹터별 평균 배수 (Fallback) ─────────────────────────────
# data/sector_benchmarks.json 에서 동적 로드, 이것은 하드코딩 폴백
SECTOR_MULTIPLES_FALLBACK = {
    "Technology":        {"ev_ebitda": 20.0, "pe": 28.0, "ps": 6.0},
    "Healthcare":        {"ev_ebitda": 15.0, "pe": 22.0, "ps": 4.0},
    "Financial Services":{"ev_ebitda": 12.0, "pe": 13.0, "ps": 3.0},
    "Consumer Cyclical":  {"ev_ebitda": 14.0, "pe": 20.0, "ps": 2.0},
    "Consumer Defensive": {"ev_ebitda": 14.0, "pe": 22.0, "ps": 2.5},
    "Industrials":       {"ev_ebitda": 13.0, "pe": 20.0, "ps": 2.0},
    "Energy":            {"ev_ebitda": 6.0,  "pe": 10.0, "ps": 1.2},
    "Real Estate":       {"ev_ebitda": 18.0, "pe": 35.0, "ps": 7.0},
    "Communication Services": {"ev_ebitda": 12.0, "pe": 18.0, "ps": 3.0},
    "Utilities":         {"ev_ebitda": 12.0, "pe": 18.0, "ps": 2.5},
    "Basic Materials":   {"ev_ebitda": 8.0,  "pe": 14.0, "ps": 1.5},
}

# ── 섹터 ETF 매핑 (섹터 순환 분석용) ────────────────────────
SECTOR_ETFS = {
    "Technology": "XLK",
    "Healthcare": "XLV",
    "Financial Services": "XLF",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Industrials": "XLI",
    "Energy": "XLE",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
    "Utilities": "XLU",
    "Basic Materials": "XLB",
}

# ── Fama-French 팩터 URL ─────────────────────────────────────
FF_FACTORS_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_5_Factors_2x3_daily_CSV.zip"
FF_MOMENTUM_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Momentum_Factor_daily_CSV.zip"

# ── FRED 시리즈 ID ────────────────────────────────────────────
FRED_SERIES = {
    "treasury_10y": "DGS10",
    "treasury_2y": "DGS2",
    "fed_funds": "FEDFUNDS",
    "ig_spread": "BAMLC0A0CM",
    "hy_spread": "BAMLH0A0HYM2",
    "vix": "VIXCLS",
    "consumer_sentiment": "UMCSENT",
}

# ── SEC EDGAR (Guru Investor Tracker) ─────────────────────────
SEC_EDGAR_BASE_URL = "https://efts.sec.gov/LATEST/search-index"
SEC_EDGAR_SUBMISSIONS_URL = "https://data.sec.gov/submissions"
SEC_EDGAR_ARCHIVES_URL = "https://www.sec.gov/cgi-bin/browse-edgar"
SEC_EDGAR_FULL_INDEX = "https://efts.sec.gov/LATEST"
SEC_EDGAR_HEADERS = {
    "User-Agent": "StockAnalyzer/1.0 (stock-analyzer@example.com)",
    "Accept-Encoding": "gzip, deflate",
}
SEC_CACHE_TTL = 86400  # 24h — 13F는 분기별이므로 하루 캐시

# 유명 투자자 CIK 매핑 (SEC EDGAR 기준)
GURU_INVESTORS = {
    "Berkshire Hathaway (Warren Buffett)":      "0001067983",
    "Bridgewater Associates (Ray Dalio)":        "0001350694",
    "Scion Asset Mgmt (Michael Burry)":          "0001649339",
    "Pershing Square (Bill Ackman)":             "0001336528",
    "Appaloosa Management (David Tepper)":       "0001656456",
    "Baupost Group (Seth Klarman)":              "0001061768",
    "Oaktree Capital (Howard Marks)":            "0000949509",
    "Icahn Enterprises (Carl Icahn)":            "0000921669",
    "Duquesne Family Office (Stanley Druckenmiller)": "0001536411",
    "Third Point (Dan Loeb)":                    "0001040273",
    "Soros Fund Management":                     "0001029160",
    "Tiger Global Management":                   "0001167483",
    "Greenlight Capital (David Einhorn)":        "0001079114",
    "Himalaya Capital (Li Lu)":                  "0001709323",
    "Renaissance Technologies":                  "0001037389",
}

# ── UI ───────────────────────────────────────────────────────
CACHE_TTL = 3600  # 초단위
MAX_TICKERS = 10
