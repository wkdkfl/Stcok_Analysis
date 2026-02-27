"""
Chart generation module — all matplotlib/plotly charts for the Streamlit app.
"""

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from typing import Dict, Any, List, Optional

from src.market_context import (
    get_currency_symbol, get_chart_price_label, get_chart_value_label,
    format_chart_tick, get_chart_nav_label,
)


# ── Color Palette ────────────────────────────────────────
COLORS = {
    "primary": "#1976D2",
    "secondary": "#FF9800",
    "green": "#4CAF50",
    "red": "#F44336",
    "gray": "#9E9E9E",
    "light_bg": "#FAFAFA",
    "revenue": "#1976D2",
    "profit": "#4CAF50",
    "loss": "#F44336",
    "current_price": "#FF5722",
}


def style_fig(fig, ax):
    """Apply consistent styling to matplotlib figures."""
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(labelsize=9)
    return fig, ax


# ═══════════════════════════════════════════════════════════
# FINANCIALS CHARTS
# ═══════════════════════════════════════════════════════════

def chart_revenue_profit(data: Dict[str, Any], currency: str = "USD") -> Optional[plt.Figure]:
    """Revenue & Operating Income 5-year bar chart."""
    from src.fetcher.yahoo import get_stmt_series

    inc = data.get("income_stmt")
    if inc is None:
        return None

    rev_s = get_stmt_series(inc, ["Total Revenue", "Revenue"])
    ebit_s = get_stmt_series(inc, ["EBIT", "Operating Income"])

    if rev_s is None:
        return None

    fig, ax1 = plt.subplots(figsize=(8, 4))
    style_fig(fig, ax1)

    years = [str(d)[:4] for d in rev_s.index]
    x = np.arange(len(years))
    w = 0.35

    _sym = get_currency_symbol(currency)
    if currency == "KRW":
        _divisor = 1e12
        _unit_label = "조원"
        _tick_fmt = lambda x, _: f"{x:.1f}조"
    else:
        _divisor = 1e9
        _unit_label = f"Billions ({_sym})"
        _tick_fmt = lambda x, _: f"{_sym}{x:.1f}B"

    rev_vals = rev_s.values / _divisor
    ax1.bar(x - w / 2, rev_vals, w, label="Revenue", color=COLORS["revenue"], alpha=0.8)

    if ebit_s is not None and len(ebit_s) == len(rev_s):
        ebit_vals = ebit_s.values / _divisor
        colors = [COLORS["profit"] if v >= 0 else COLORS["loss"] for v in ebit_vals]
        ax1.bar(x + w / 2, ebit_vals, w, label="Operating Income", color=colors, alpha=0.8)

    ax1.set_xlabel("")
    ax1.set_ylabel(_unit_label)
    ax1.set_title("Revenue & Operating Income", fontsize=12, fontweight="bold")
    ax1.set_xticks(x)
    ax1.set_xticklabels(years)
    ax1.legend(loc="upper left", fontsize=8)
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(_tick_fmt))
    fig.tight_layout()
    return fig


def chart_margins(data: Dict[str, Any]) -> Optional[plt.Figure]:
    """Margin trends — Gross, Operating, Net."""
    from src.fetcher.yahoo import get_stmt_series

    inc = data.get("income_stmt")
    if inc is None:
        return None

    rev_s = get_stmt_series(inc, ["Total Revenue", "Revenue"])
    gp_s = get_stmt_series(inc, ["Gross Profit"])
    ebit_s = get_stmt_series(inc, ["EBIT", "Operating Income"])
    ni_s = get_stmt_series(inc, ["Net Income", "Net Income Common Stockholders"])

    if rev_s is None or gp_s is None:
        return None

    fig, ax = plt.subplots(figsize=(8, 4))
    style_fig(fig, ax)

    years = [str(d)[:4] for d in rev_s.index]

    def margin(num, denom):
        return (num.values / denom.values * 100) if len(num) == len(denom) else None

    gm = margin(gp_s, rev_s)
    if gm is not None:
        ax.plot(years, gm, "o-", label="Gross Margin", color="#1976D2", linewidth=2)

    if ebit_s is not None:
        om = margin(ebit_s, rev_s)
        if om is not None:
            ax.plot(years, om, "s-", label="Operating Margin", color="#4CAF50", linewidth=2)

    if ni_s is not None:
        nm = margin(ni_s, rev_s)
        if nm is not None:
            ax.plot(years, nm, "^-", label="Net Margin", color="#FF9800", linewidth=2)

    ax.set_ylabel("Margin (%)")
    ax.set_title("Profitability Margins", fontsize=12, fontweight="bold")
    ax.legend(fontsize=8)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter())
    ax.axhline(y=0, color="gray", linestyle="--", linewidth=0.5)
    fig.tight_layout()
    return fig


# ═══════════════════════════════════════════════════════════
# VALUATION CHARTS
# ═══════════════════════════════════════════════════════════

def chart_valuation_comparison(valuation_results: Dict[str, Any],
                                current_price: float,
                                currency: str = "USD") -> Optional[plt.Figure]:
    """Horizontal bar chart — all model fair values vs current price."""
    summary = valuation_results.get("models_summary", [])
    if not summary:
        return None

    models = []
    values = []
    colors = []

    for m in summary:
        fv = m.get("fair_value")
        if fv and fv > 0:
            models.append(m["model"])
            values.append(fv)
            colors.append(COLORS["green"] if fv > current_price else COLORS["red"])

    if not models:
        return None

    fig, ax = plt.subplots(figsize=(8, max(3, len(models) * 0.55)))
    style_fig(fig, ax)

    y = np.arange(len(models))
    ax.barh(y, values, color=colors, alpha=0.8, height=0.5)
    _sym = get_currency_symbol(currency)
    ax.axvline(x=current_price, color=COLORS["current_price"], linestyle="--",
               linewidth=2, label=f"Current: {_sym}{current_price:,.0f}")

    # Growth-adjusted aggregate fair value line
    adj_fv = valuation_results.get("fair_value_adjusted")
    if adj_fv and adj_fv > 0:
        ax.axvline(x=adj_fv, color="#7B1FA2", linestyle="-",
                   linewidth=2, alpha=0.8, label=f"Adj. FV: {_sym}{adj_fv:,.0f}")

    ax.set_yticks(y)
    ax.set_yticklabels(models, fontsize=9)
    ax.set_xlabel(f"Fair Value ({_sym})")
    ax.set_title("Valuation Model Comparison", fontsize=12, fontweight="bold")
    ax.legend(fontsize=8, loc="lower right")

    for i, v in enumerate(values):
        ax.text(v + current_price * 0.02, i, f"{_sym}{v:,.0f}", va="center", fontsize=8)

    fig.tight_layout()
    return fig


def chart_monte_carlo(mc_distribution: np.ndarray,
                      current_price: float, fair_value: float,
                      currency: str = "USD") -> Optional[plt.Figure]:
    """Monte Carlo DCF distribution histogram."""
    if mc_distribution is None or len(mc_distribution) == 0:
        return None

    fig, ax = plt.subplots(figsize=(8, 4))
    style_fig(fig, ax)

    _sym = get_currency_symbol(currency)
    ax.hist(mc_distribution, bins=80, color=COLORS["primary"], alpha=0.7, edgecolor="white")
    ax.axvline(current_price, color=COLORS["current_price"], linestyle="--",
               linewidth=2, label=f"Current: {_sym}{current_price:,.0f}")
    ax.axvline(fair_value, color=COLORS["green"], linestyle="-",
               linewidth=2, label=f"Fair Value: {_sym}{fair_value:,.0f}")

    p10 = np.percentile(mc_distribution, 10)
    p90 = np.percentile(mc_distribution, 90)
    ax.axvspan(p10, p90, alpha=0.1, color="green", label=f"10th-90th: {_sym}{p10:,.0f}-{_sym}{p90:,.0f}")

    ax.set_xlabel(f"Intrinsic Value ({_sym})")
    ax.set_ylabel("Frequency")
    ax.set_title("DCF Monte Carlo Simulation (10,000 runs)", fontsize=12, fontweight="bold")
    ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


# ═══════════════════════════════════════════════════════════
# QUALITY RADAR CHART (Plotly)
# ═══════════════════════════════════════════════════════════

def chart_quality_radar(data: Dict[str, Any], piotroski: Dict,
                        altman: Dict, eva_data: Dict) -> Optional[go.Figure]:
    """Radar chart for quality metrics."""
    categories = []
    values = []
    max_vals = []

    # Piotroski (0-9 → normalize to 0-100)
    f_score = piotroski.get("score", 0)
    categories.append("F-Score")
    values.append(f_score / 9 * 100)
    max_vals.append(100)

    # Altman Z (normalize: 0→0, 3→100)
    z = altman.get("z_score")
    if z is not None:
        categories.append("Z-Score")
        values.append(min(z / 3 * 100, 100))
        max_vals.append(100)

    # ROIC
    roic = data.get("roic")
    if roic is not None:
        categories.append("ROIC")
        values.append(min(roic * 100 * 3, 100))  # 33% ROIC = 100
        max_vals.append(100)

    # Operating Margin
    om = data.get("operating_margin")
    if om is not None:
        categories.append("Op. Margin")
        values.append(min(om * 100 * 2.5, 100))  # 40% = 100
        max_vals.append(100)

    # Revenue Growth
    rg = data.get("revenue_growth")
    if rg is not None:
        categories.append("Rev Growth")
        values.append(min(max(rg * 100 * 2, 0), 100))
        max_vals.append(100)

    # Cash Conversion
    ccr = data.get("cash_conversion")
    if ccr is not None:
        categories.append("Cash Conv.")
        values.append(min(max(ccr * 50, 0), 100))
        max_vals.append(100)

    if len(categories) < 3:
        return None

    # Close the radar
    categories.append(categories[0])
    values.append(values[0])

    fig = go.Figure(data=go.Scatterpolar(
        r=values,
        theta=categories,
        fill="toself",
        fillcolor="rgba(25, 118, 210, 0.2)",
        line=dict(color="#1976D2", width=2),
        marker=dict(size=6),
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100], showticklabels=False),
        ),
        showlegend=False,
        title="Quality Radar",
        height=400,
        margin=dict(l=60, r=60, t=60, b=40),
    )

    return fig


# ═══════════════════════════════════════════════════════════
# RISK CHARTS
# ═══════════════════════════════════════════════════════════

def chart_drawdown(data: Dict[str, Any]) -> Optional[plt.Figure]:
    """Drawdown area chart."""
    history = data.get("history")
    if history is None or len(history) < 100:
        return None

    close = history["Close"]
    daily_ret = close.pct_change().dropna()
    cum = (1 + daily_ret).cumprod()
    rolling_max = cum.cummax()
    dd = (cum / rolling_max - 1) * 100

    fig, ax = plt.subplots(figsize=(8, 3))
    style_fig(fig, ax)

    ax.fill_between(dd.index, dd.values, 0, color=COLORS["red"], alpha=0.4)
    ax.plot(dd.index, dd.values, color=COLORS["red"], linewidth=0.8)
    ax.set_ylabel("Drawdown (%)")
    ax.set_title("Historical Drawdown", fontsize=12, fontweight="bold")
    ax.yaxis.set_major_formatter(mticker.PercentFormatter())
    fig.tight_layout()
    return fig


def chart_price_with_ma(data: Dict[str, Any]) -> Optional[plt.Figure]:
    """Price chart with 50/200 MA and Bollinger Bands."""
    history = data.get("history")
    if history is None or len(history) < 50:
        return None

    close = history["Close"]

    fig, ax = plt.subplots(figsize=(10, 4))
    style_fig(fig, ax)

    ax.plot(close.index, close.values, color="#333", linewidth=1, label="Price", alpha=0.8)

    if len(close) >= 50:
        ma50 = close.rolling(50).mean()
        ax.plot(ma50.index, ma50.values, color=COLORS["primary"],
                linewidth=1.2, label="50-MA", alpha=0.8)

    if len(close) >= 200:
        ma200 = close.rolling(200).mean()
        ax.plot(ma200.index, ma200.values, color=COLORS["secondary"],
                linewidth=1.2, label="200-MA", alpha=0.8)

    # Bollinger Bands
    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    upper = sma20 + 2 * std20
    lower = sma20 - 2 * std20
    ax.fill_between(upper.index, upper.values, lower.values,
                    alpha=0.08, color=COLORS["primary"])

    ax.set_ylabel(get_chart_price_label(data.get("currency", "USD")))
    ax.set_title(f"{data.get('ticker', '')} — Price & Moving Averages", fontsize=12, fontweight="bold")
    ax.legend(fontsize=8, loc="upper left")
    fig.tight_layout()
    return fig


# ═══════════════════════════════════════════════════════════
# COMPARISON HEATMAP (Multi-Ticker)
# ═══════════════════════════════════════════════════════════

def chart_comparison_heatmap(tickers_data: List[Dict[str, Any]],
                             valuations: List[Dict[str, Any]]) -> Optional[go.Figure]:
    """Create comparison heatmap for multiple tickers."""
    if not tickers_data or len(tickers_data) < 2:
        return None

    metrics = [
        ("P/E", "trailing_pe", False),
        ("Fwd P/E", "forward_pe", False),
        ("P/B", "price_to_book", False),
        ("EV/EBITDA", "ev_to_ebitda", False),
        ("Gross Margin %", "gross_margin", True),
        ("Op Margin %", "operating_margin", True),
        ("Net Margin %", "profit_margin", True),
        ("ROE %", "roe", True),
        ("ROIC %", "roic", True),
        ("Rev Growth %", "revenue_growth", True),
        ("D/E", "debt_to_equity", False),
        ("Current Ratio", "current_ratio", True),
        ("Beta", "beta", False),
        ("Div Yield %", "dividend_yield", True),
    ]

    tickers = [d.get("ticker", "?") for d in tickers_data]
    z_vals = []
    y_labels = []
    text_vals = []

    for label, key, higher_better in metrics:
        row = []
        text_row = []
        for d in tickers_data:
            val = d.get(key)
            if val is not None and isinstance(val, (int, float)):
                if "margin" in key.lower() or key in ["roe", "roic", "revenue_growth", "dividend_yield"]:
                    display = f"{val * 100:.1f}%"
                    row.append(val * 100)
                else:
                    display = f"{val:.2f}"
                    row.append(val)
                text_row.append(display)
            else:
                row.append(None)
                text_row.append("N/A")

        # Normalize row for coloring (higher is better → green, lower → red)
        valid = [v for v in row if v is not None]
        if valid and max(valid) != min(valid):
            norm = []
            for v in row:
                if v is None:
                    norm.append(0.5)
                else:
                    n = (v - min(valid)) / (max(valid) - min(valid))
                    norm.append(n if higher_better else 1 - n)
            z_vals.append(norm)
        else:
            z_vals.append([0.5] * len(tickers))

        y_labels.append(label)
        text_vals.append(text_row)

    fig = go.Figure(data=go.Heatmap(
        z=z_vals,
        x=tickers,
        y=y_labels,
        text=text_vals,
        texttemplate="%{text}",
        textfont={"size": 11},
        colorscale=[[0, "#F44336"], [0.5, "#FFFFFF"], [1, "#4CAF50"]],
        showscale=False,
        hoverongaps=False,
    ))

    fig.update_layout(
        title="Multi-Ticker Comparison",
        height=max(400, len(metrics) * 35),
        margin=dict(l=120, r=20, t=50, b=30),
        yaxis=dict(autorange="reversed"),
    )

    return fig


# ═══════════════════════════════════════════════════════════
# PORTFOLIO / BACKTEST CHARTS
# ═══════════════════════════════════════════════════════════

def chart_portfolio_equity_curve(
    nav: "pd.Series",
    benchmark_nav: "pd.Series" = None,
    title: str = "포트폴리오 수익률 곡선",
    currency: str = "USD",
) -> go.Figure:
    """Equity-curve line chart — portfolio NAV vs benchmark."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=nav.index, y=nav.values,
        mode="lines", name="Portfolio",
        line=dict(color=COLORS["primary"], width=2),
    ))
    if benchmark_nav is not None and not benchmark_nav.empty:
        fig.add_trace(go.Scatter(
            x=benchmark_nav.index, y=benchmark_nav.values,
            mode="lines", name="Benchmark",
            line=dict(color=COLORS["secondary"], width=1.5, dash="dot"),
        ))
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title=get_chart_nav_label(currency),
        hovermode="x unified",
        height=420,
        margin=dict(l=50, r=20, t=50, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def chart_portfolio_drawdown(nav: "pd.Series", title: str = "드로우다운") -> go.Figure:
    """Drawdown area chart from NAV series."""
    daily_ret = nav.pct_change().fillna(0)
    cum = (1 + daily_ret).cumprod()
    dd = (cum / cum.cummax() - 1) * 100

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dd.index, y=dd.values,
        fill="tozeroy",
        mode="lines",
        name="Drawdown",
        line=dict(color=COLORS["red"], width=1),
        fillcolor="rgba(244,67,54,0.25)",
    ))
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Drawdown (%)",
        height=300,
        margin=dict(l=50, r=20, t=50, b=40),
    )
    return fig


def chart_correlation_heatmap(corr: "pd.DataFrame", title: str = "종목 간 상관관계") -> go.Figure:
    """Correlation matrix heatmap."""
    fig = go.Figure(data=go.Heatmap(
        z=corr.values,
        x=list(corr.columns),
        y=list(corr.index),
        text=corr.round(2).values,
        texttemplate="%{text}",
        textfont={"size": 11},
        colorscale=[[0, "#F44336"], [0.5, "#FFFFFF"], [1, "#4CAF50"]],
        zmin=-1, zmax=1,
        showscale=True,
    ))
    fig.update_layout(
        title=title,
        height=max(350, len(corr) * 40),
        margin=dict(l=80, r=20, t=50, b=40),
    )
    return fig


def chart_weight_allocation(
    weights: Dict[str, float],
    title: str = "포트폴리오 비중",
) -> go.Figure:
    """Pie/donut chart of portfolio weight allocation."""
    labels = list(weights.keys())
    values = [w * 100 for w in weights.values()]

    fig = go.Figure(data=go.Pie(
        labels=labels,
        values=values,
        hole=0.4,
        textinfo="label+percent",
        textposition="inside",
        marker=dict(colors=[
            "#1976D2", "#FF9800", "#4CAF50", "#F44336", "#9C27B0",
            "#00BCD4", "#795548", "#607D8B", "#E91E63", "#CDDC39",
            "#3F51B5", "#FF5722", "#009688", "#FFC107", "#8BC34A",
        ][:len(labels)]),
    ))
    fig.update_layout(
        title=title,
        height=380,
        margin=dict(l=20, r=20, t=50, b=20),
        showlegend=True,
    )
    return fig


def chart_rolling_sharpe(
    rolling_sharpe: "pd.Series",
    title: str = "Rolling Sharpe Ratio (1Y)",
) -> go.Figure:
    """Rolling Sharpe ratio line chart."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=rolling_sharpe.index, y=rolling_sharpe.values,
        mode="lines", name="Rolling Sharpe",
        line=dict(color=COLORS["primary"], width=1.5),
    ))
    # Reference lines
    fig.add_hline(y=0, line_dash="dash", line_color=COLORS["gray"], opacity=0.6)
    fig.add_hline(y=1, line_dash="dot", line_color=COLORS["green"], opacity=0.4,
                  annotation_text="1.0", annotation_position="bottom right")
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Sharpe Ratio",
        height=320,
        margin=dict(l=50, r=20, t=50, b=40),
    )
    return fig


def chart_backtest_trades(
    trades_log: list,
    title: str = "리밸런싱 이력",
    currency: str = "USD",
) -> go.Figure:
    """Bar chart showing portfolio value at each rebalance point + transaction costs."""
    if not trades_log:
        fig = go.Figure()
        fig.update_layout(title=title, annotations=[dict(
            text="매매 이력 없음", xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False, font=dict(size=16),
        )])
        return fig

    dates = [t["date"] for t in trades_log]
    values = [t["portfolio_value"] for t in trades_log]
    costs = [t["cost"] for t in trades_log]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=dates, y=values,
        name="포트폴리오 가치",
        marker_color=COLORS["primary"],
    ))
    fig.add_trace(go.Bar(
        x=dates, y=costs,
        name="거래 비용",
        marker_color=COLORS["red"],
        yaxis="y2",
    ))
    fig.update_layout(
        title=title,
        xaxis_title="리밸런싱 일자",
        yaxis=dict(title=f"포트폴리오 가치 ({get_currency_symbol(currency)})"),
        yaxis2=dict(title=f"거래 비용 ({get_currency_symbol(currency)})", overlaying="y", side="right"),
        barmode="group",
        height=380,
        margin=dict(l=60, r=60, t=50, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig
