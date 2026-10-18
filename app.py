"""Wealth Inflation Tracker: the web page.

Run it with:  uv run streamlit run app.py

Streamlit re-runs this whole file from top to bottom every time someone
clicks or types on the page, so downloads are remembered with st.cache_data.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from calc import INDEX_NAME, change_table, chart_lines, last_month_set_by, line_up, months_between
from data import crypto, download_with_backup, fred_series, pink_sheet, sp500

# Every series: friendly name -> (backup file name, download function, inputs).
# FRED downloads also need the API key, which is added when downloading.
SERIES = {
    "CPI": ("CPIAUCNS", fred_series, ["CPIAUCNS"]),
    "Wages": ("AHETPI", fred_series, ["AHETPI"]),
    "US home prices": ("CSUSHPINSA", fred_series, ["CSUSHPINSA"]),
    "S&P 500": ("SP500", sp500, []),
    "Gold": ("GOLD", pink_sheet, ["Gold"]),
    "Silver": ("SILVER", pink_sheet, ["Silver"]),
    "Bitcoin": ("BTC", crypto, ["btc"]),
    "Ethereum": ("ETH", crypto, ["eth"]),
    "Zcash": ("ZEC", crypto, ["zec"]),
    "Monero": ("XMR", crypto, ["xmr"]),
    "Solana": ("SOL", crypto, ["sol"]),
}


# Layer A: a successful download is remembered for 24 hours. A failed one is
# not remembered at all, so it is tried again next time.
@st.cache_data(ttl="24h", show_spinner=False)
def fresh_download(name: str) -> pd.DataFrame:
    _, download, inputs = SERIES[name]
    if download is fred_series:
        inputs = [*inputs, st.secrets["FRED_API_KEY"]]
    return download(*inputs)


# Layer B: the final result (fresh data, or the backup copy plus a note) is
# remembered for 1 hour, so a source that is down is only retried hourly.
@st.cache_data(ttl="1h", show_spinner=False)
def load(name: str) -> tuple[pd.DataFrame, str | None]:
    file_name, _, _ = SERIES[name]
    return download_with_backup(file_name, fresh_download, name, label=name)


ASSETS = [name for name in SERIES if name not in ("CPI", "Wages")]
DEFAULT_WEIGHTS = {"S&P 500": 100}  # ticked when the page first opens
# A clearly different colour for each line (readable on light and dark backgrounds).
LINE_COLORS = {INDEX_NAME: "#3b82f6", "CPI": "#f59e0b", "Wages": "#10b981"}
CASE_SHILLER_NOTE = (
    "US home prices (Case-Shiller) are a three-month moving average: each "
    "month's value covers that month and the two before it."
)


def month_name(date) -> str:
    return date.strftime("%B %Y")  # for example "January 2015"


def percent_text(value) -> str:
    """+9,931.90%, -19.00%, or a dash when there is no value."""
    return "—" if pd.isna(value) else f"{value:+,.2f}%"


def duration_text(months: int) -> str:
    """62 years and 8 months, 1 year, 5 months, 0 months."""
    years, months = divmod(months, 12)
    parts = []
    if years:
        parts.append(f"{years} year{'s' if years != 1 else ''}")
    if months or not years:
        parts.append(f"{months} month{'s' if months != 1 else ''}")
    return " and ".join(parts)


st.set_page_config(page_title="Wealth Inflation Tracker")
st.title("Wealth Inflation Tracker")

# Everything below the title goes into this container, so the sources line
# (written next) always stays at the bottom, even when the page stops early.
main = st.container()
st.caption(
    "Sources: CPI, wages and US home prices from "
    "[FRED](https://fred.stlouisfed.org/), Federal Reserve Bank of St. Louis · "
    "S&P 500 from [Robert Shiller](https://shillerdata.com/) · "
    "Gold and silver from the [World Bank Pink Sheet](https://www.worldbank.org/en/research/commodity-markets) · "
    "Crypto data: [Coin Metrics](https://coinmetrics.io/)\n\n"
    "This product uses the FRED® API but is not endorsed or certified by the "
    "Federal Reserve Bank of St. Louis."
)

with main:
    # Check that the key exists without showing it. (Streamlit displays any value
    # left alone on its own line, so never write st.secrets[...] by itself.)
    try:
        has_key = "FRED_API_KEY" in st.secrets
    except Exception:  # there is no secrets.toml file at all
        has_key = False
    if not has_key:
        st.error("No FRED API key found. Add the line FRED_API_KEY = \"...\" to .streamlit/secrets.toml.")
        st.stop()

    tables = {}
    for name in SERIES:
        with st.spinner(f"Downloading {name}…"):
            try:
                table, note = load(name)
            except Exception as error:
                st.error(f"{name} could not be loaded: {error}")
                continue
        if note:
            st.warning(note)
        tables[name] = table

# --- Controls in the sidebar ---
st.sidebar.header("Your assets")
weights = {}  # ticked assets with a weight above 0%, in whole percent
for name in ASSETS:
    tick_column, weight_column = st.sidebar.columns([3, 2], vertical_alignment="center")
    ticked = tick_column.checkbox(
        name,
        value=name in DEFAULT_WEIGHTS,
        key=f"use_{name}",
        disabled=name not in tables,  # could not be loaded and has no backup
    )
    if ticked and name in tables:
        weight = weight_column.number_input(
            f"{name} weight (%)",
            min_value=0,
            max_value=100,
            value=DEFAULT_WEIGHTS.get(name, 0),
            step=1,
            key=f"weight_{name}",
            label_visibility="collapsed",
        )
        if weight > 0:  # 0% counts as not selected
            weights[name] = weight

total = sum(weights.values())
if total == 100:
    st.sidebar.caption("Total: 100%")
else:
    st.sidebar.error(f"Weights add up to {total}%. They must add up to 100%.")

st.sidebar.header("Compare with")
st.sidebar.caption("CPI is always shown.")
# Wages start in 1964; turning them off lets the chart start as early as CPI (1913).
show_wages = st.sidebar.checkbox("Wages", value=True, key="show_wages")
comparisons = ["CPI", "Wages"] if show_wages else ["CPI"]

with main:
    for needed in comparisons:
        if needed not in tables:
            st.error(f"{needed} could not be loaded, so the chart can't be drawn.")
            st.stop()
    if not weights:
        st.info("Choose at least one asset.")
        st.stop()

    # Line up only the series that are shown.
    chosen = {name: tables[name] for name in [*comparisons, *weights]}
    lined_up = line_up(chosen)
    if lined_up.empty:
        st.error("The selected series have no months in common.")
        st.stop()

# The start-month menu offers only months where every chosen series has data.
months = list(lined_up.index)
earliest = months[0]
chosen_start = st.session_state.get("start")
# Move to the earliest month if the chosen month is no longer offered, or if
# it was the earliest month before this change (so it follows the earliest).
if chosen_start not in months or chosen_start == st.session_state.get("earliest"):
    st.session_state["start"] = earliest
st.session_state["earliest"] = earliest
start = st.sidebar.selectbox("Start month", months, format_func=month_name, key="start")

with main:
    if total != 100:
        st.stop()  # the sidebar already explains the problem

    lines = chart_lines(lined_up, start, weights)
    log_scale = st.toggle("Logarithmic scale", value=True, key="log_scale")

    figure = go.Figure()
    for name in lines.columns:
        figure.add_trace(go.Scatter(
            x=lines.index, y=lines[name], name=name, mode="lines",
            line={"color": LINE_COLORS[name]},
            hovertemplate="%{y:,.1f}",
        ))
    figure.add_hline(y=100, line_dash="dot", line_width=1, line_color="gray")  # the start level
    figure.update_layout(
        hovermode="x unified",  # hovering shows every line for that month
        yaxis_title="Index (start month = 100)",
        yaxis_type="log" if log_scale else "linear",
        legend={"orientation": "h", "y": 1.1},
        margin={"t": 40},
    )
    figure.update_xaxes(hoverformat="%B %Y")
    st.plotly_chart(
        figure,
        alt=f"Line chart of {', '.join(lines.columns)}, all starting at 100 in {month_name(start)}.",
    )

    end = lines.index[-1]
    set_by = ", ".join(last_month_set_by(chosen))
    st.caption(
        f"Start: {month_name(start)} · Data through: {month_name(end)} (set by {set_by}) · "
        f"{len(lines)} monthly values"
    )

    # The % change table (yearly change is left empty for periods under 12 months).
    changes = change_table(lines)
    st.markdown(
        f"**Change from {month_name(start)} to {month_name(end)} "
        f"({duration_text(months_between(start, end))})**"
    )
    st.table(
        changes.map(percent_text).rename_axis("Line"),
        alt="Table of total and yearly percent change for each line on the chart.",
    )
    if "US home prices" in weights:
        st.info(CASE_SHILLER_NOTE)
