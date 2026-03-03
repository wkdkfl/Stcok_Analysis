"""
Chart generation module — all Plotly charts for the Streamlit app.
"""

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


# ═══════════════════════════════════════════════════════════
# FINANCIALS CHARTS
# ═══════════════════════════════════════════════════════════

def chart_revenue_profit(data: Dict[str, Any], currency: str = "USD") -> Optional[go.Figure]:
    """Revenue & Operating Income 5-year bar chart (Plotly)."""
    from src.fetcher.yahoo import get_stmt_series

    inc = data.get("income_stmt")
    if inc is None:
        return None

    rev_s = get_stmt_series(inc, ["Total Revenue", "Revenue"])
    ebit_s = get_stmt_series(inc, ["EBIT", "Operating Income"])

    if rev_s is None:
        return None

    years = [str(d)[:4] for d in rev_s.index]
    _sym = get_currency_symbol(currency)
    if currency == "KRW":
        _divisor = 1e12
        _unit_label = "조원"
    else:
        _divisor = 1e9
        _unit_label = f"Billions ({_sym})"

    rev_vals = rev_s.values / _divisor

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=years, y=rev_vals, name="Revenue",
        marker_color=COLORS["revenue"], opacity=0.8,
    ))

    if ebit_s is not None and len(ebit_s) == len(rev_s):
        ebit_vals = ebit_s.values / _divisor
        colors = [COLORS["profit"] if v >= 0 else COLORS["loss"] for v in ebit_vals]
        fig.add_trace(go.Bar(
            x=years, y=ebit_vals, name="Operating Income",
            marker_color=colors, opacity=0.8,
        ))

    fig.update_layout(
        title=dict(text="Revenue & Operating Income", font=dict(size=14)),
        yaxis_title=_unit_label,
        barmode="group",
        height=350,
        margin=dict(l=40, r=20, t=40, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def chart_margins(data: Dict[str, Any]) -> Optional[go.Figure]:
    """Margin trends — Gross, Operating, Net (Plotly)."""
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

    years = [str(d)[:4] for d in rev_s.index]

    def margin(num, denom):
        return (num.values / denom.values * 100) if len(num) == len(denom) else None

    fig = go.Figure()

    gm = margin(gp_s, rev_s)
    if gm is not None:
        fig.add_trace(go.Scatter(
            x=years, y=gm, mode="lines+markers", name="Gross Margin",
            line=dict(color="#1976D2", width=2), marker=dict(size=6),
        ))

    if ebit_s is not None:
        om = margin(ebit_s, rev_s)
        if om is not None:
            fig.add_trace(go.Scatter(
                x=years, y=om, mode="lines+markers", name="Operating Margin",
                line=dict(color="#4CAF50", width=2), marker=dict(size=6, symbol="square"),
            ))

    if ni_s is not None:
        nm = margin(ni_s, rev_s)
        if nm is not None:
            fig.add_trace(go.Scatter(
                x=years, y=nm, mode="lines+markers", name="Net Margin",
                line=dict(color="#FF9800", width=2), marker=dict(size=6, symbol="triangle-up"),
            ))

    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
    fig.update_layout(
        title=dict(text="Profitability Margins", font=dict(size=14)),
        yaxis_title="Margin (%)",
        yaxis=dict(ticksuffix="%"),
        height=350,
        margin=dict(l=40, r=20, t=40, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


# ═══════════════════════════════════════════════════════════
# VALUATION CHARTS
# ═══════════════════════════════════════════════════════════

def chart_valuation_comparison(valuation_results: Dict[str, Any],
                                current_price: float,
                                currency: str = "USD") -> Optional[go.Figure]:
    """Horizontal bar chart — all model fair values vs current price (Plotly)."""
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

    _sym = get_currency_symbol(currency)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=models, x=values, orientation="h",
        marker_color=colors, opacity=0.8,
        text=[f"{_sym}{v:,.0f}" for v in values],
        textposition="outside",
        textfont=dict(size=10),
    ))

    fig.add_vline(
        x=current_price, line_dash="dash", line_color=COLORS["current_price"],
        line_width=2, annotation_text=f"Current: {_sym}{current_price:,.0f}",
        annotation_position="top right",
    )

    adj_fv = valuation_results.get("fair_value_adjusted")
    if adj_fv and adj_fv > 0:
        fig.add_vline(
            x=adj_fv, line_dash="solid", line_color="#7B1FA2",
            line_width=2, opacity=0.8,
            annotation_text=f"Adj. FV: {_sym}{adj_fv:,.0f}",
            annotation_position="bottom right",
        )

    fig.update_layout(
        title=dict(text="Valuation Model Comparison", font=dict(size=14)),
        xaxis_title=f"Fair Value ({_sym})",
        height=max(300, len(models) * 40),
        margin=dict(l=100, r=60, t=40, b=30),
        yaxis=dict(autorange="reversed"),
    )
    return fig


def chart_monte_carlo(mc_distribution: np.ndarray,
                      current_price: float, fair_value: float,
                      currency: str = "USD") -> Optional[go.Figure]:
    """Monte Carlo DCF distribution histogram (Plotly)."""
    if mc_distribution is None or len(mc_distribution) == 0:
        return None

    _sym = get_currency_symbol(currency)
    p10 = np.percentile(mc_distribution, 10)
    p90 = np.percentile(mc_distribution, 90)

    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=mc_distribution, nbinsx=80,
        marker_color=COLORS["primary"], opacity=0.7,
        name="Distribution",
    ))

    fig.add_vline(
        x=current_price, line_dash="dash", line_color=COLORS["current_price"],
        line_width=2, annotation_text=f"Current: {_sym}{current_price:,.0f}",
        annotation_position="top left",
    )
    fig.add_vline(
        x=fair_value, line_dash="solid", line_color=COLORS["green"],
        line_width=2, annotation_text=f"Fair Value: {_sym}{fair_value:,.0f}",
        annotation_position="top right",
    )
    fig.add_vrect(
        x0=p10, x1=p90, fillcolor="green", opacity=0.08,
        line_width=0, annotation_text=f"10th-90th",
        annotation_position="top left",
    )

    fig.update_layout(
        title=dict(text="DCF Monte Carlo (10,000 runs)", font=dict(size=14)),
        xaxis_title=f"Intrinsic Value ({_sym})",
        yaxis_title="Frequency",
        height=350,
        margin=dict(l=40, r=20, t=40, b=30),
        showlegend=False,
    )
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

def chart_drawdown(data: Dict[str, Any]) -> Optional[go.Figure]:
    """Drawdown area chart (Plotly)."""
    history = data.get("history")
    if history is None or len(history) < 100:
        return None

    close = history["Close"]
    daily_ret = close.pct_change().dropna()
    cum = (1 + daily_ret).cumprod()
    rolling_max = cum.cummax()
    dd = (cum / rolling_max - 1) * 100

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dd.index, y=dd.values,
        fill="tozeroy", mode="lines",
        name="Drawdown",
        line=dict(color=COLORS["red"], width=0.8),
        fillcolor="rgba(244,67,54,0.3)",
    ))
    fig.update_layout(
        title=dict(text="Historical Drawdown", font=dict(size=14)),
        yaxis_title="Drawdown (%)",
        yaxis=dict(ticksuffix="%"),
        height=280,
        margin=dict(l=40, r=20, t=40, b=30),
    )
    return fig


def chart_price_with_ma(data: Dict[str, Any]) -> Optional[go.Figure]:
    """Price chart with 50/200 MA and Bollinger Bands (Plotly)."""
    history = data.get("history")
    if history is None or len(history) < 50:
        return None

    close = history["Close"]

    fig = go.Figure()

    # Price
    fig.add_trace(go.Scatter(
        x=close.index, y=close.values,
        mode="lines", name="Price",
        line=dict(color="#333", width=1), opacity=0.8,
    ))

    # 50-MA
    if len(close) >= 50:
        ma50 = close.rolling(50).mean()
        fig.add_trace(go.Scatter(
            x=ma50.index, y=ma50.values,
            mode="lines", name="50-MA",
            line=dict(color=COLORS["primary"], width=1.2), opacity=0.8,
        ))

    # 200-MA
    if len(close) >= 200:
        ma200 = close.rolling(200).mean()
        fig.add_trace(go.Scatter(
            x=ma200.index, y=ma200.values,
            mode="lines", name="200-MA",
            line=dict(color=COLORS["secondary"], width=1.2), opacity=0.8,
        ))

    # Bollinger Bands
    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    upper = sma20 + 2 * std20
    lower = sma20 - 2 * std20

    fig.add_trace(go.Scatter(
        x=upper.index, y=upper.values,
        mode="lines", name="BB Upper",
        line=dict(width=0), showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=lower.index, y=lower.values,
        mode="lines", name="BB Lower",
        fill="tonexty", fillcolor=f"rgba(25,118,210,0.06)",
        line=dict(width=0), showlegend=False,
    ))

    fig.update_layout(
        title=dict(text=f"{data.get('ticker', '')} — Price & Moving Averages", font=dict(size=14)),
        yaxis_title=get_chart_price_label(data.get("currency", "USD")),
        height=380,
        margin=dict(l=40, r=20, t=40, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
    )
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
