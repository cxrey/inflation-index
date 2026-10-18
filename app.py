"""Wealth Inflation Tracker: the web page.

Run it with:  uv run streamlit run app.py

Streamlit re-runs this whole file from top to bottom every time someone
clicks or types on the page, so downloads are remembered with st.cache_data.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from calc import (
    INDEX_NAME,
    asset_lines,
    basket_and_total,
    change_table,
    chart_lines,
    current_weights,
    last_month_set_by,
    line_up,
    make_100,
    months_between,
    needs_bitcoin_note,
    percent_text,
    power_of_ten_ticks,
    set_section_total,
    split_categories,
    split_evenly,
    weights_add_up,
)
from data import (
    LUXURY_CITIES,
    crypto,
    download_with_backup,
    fred_monthly_average,
    fred_series,
    pink_sheet,
    sp500,
)

# Every series: friendly name -> (backup file name, download function, inputs).
# FRED downloads also need the API key, which is added when downloading.
SERIES = {
    "CPI": ("CPIAUCNS", fred_series, ["CPIAUCNS"]),
    "Wages": ("AHETPI", fred_series, ["AHETPI"]),
    "US home prices": ("CSUSHPINSA", fred_series, ["CSUSHPINSA"]),
    "S&P 500": ("SP500", sp500, []),
    "Nasdaq": ("NASDAQCOM", fred_monthly_average, ["NASDAQCOM"]),
    "Gold": ("GOLD", pink_sheet, ["Gold"]),
    "Silver": ("SILVER", pink_sheet, ["Silver"]),
    "Platinum": ("PLATINUM", pink_sheet, ["Platinum"]),
    "Bitcoin": ("BTC", crypto, ["btc"]),
    "Ethereum": ("ETH", crypto, ["eth"]),
    "Zcash": ("ZEC", crypto, ["zec"]),
    "Monero": ("XMR", crypto, ["xmr"]),
    "Solana": ("SOL", crypto, ["sol"]),
}
# Luxury homes: one series per city; only the selected city is downloaded.
LUXURY = "Luxury homes"
SERIES.update({
    f"{LUXURY} ({city})": (f"LUX_{series_id}", fred_series, [series_id])
    for city, series_id in LUXURY_CITIES.items()
})
FRED_DOWNLOADS = (fred_series, fred_monthly_average)


# Layer A: a successful download is remembered for 24 hours. A failed one is
# not remembered at all, so it is tried again next time.
@st.cache_data(ttl="24h", show_spinner=False)
def fresh_download(name: str) -> pd.DataFrame:
    _, download, inputs = SERIES[name]
    if download in FRED_DOWNLOADS:
        inputs = [*inputs, st.secrets["FRED_API_KEY"]]
    return download(*inputs)


# Layer B: the final result (fresh data, or the backup copy plus a note) is
# remembered for 1 hour, so a source that is down is only retried hourly.
@st.cache_data(ttl="1h", show_spinner=False)
def load(name: str) -> tuple[pd.DataFrame, str | None]:
    file_name, _, _ = SERIES[name]
    return download_with_backup(file_name, fresh_download, name, label=name)


# The basket choices, in fold-out sections in the sidebar. The luxury-homes
# cities are separate assets in their own section inside "Real estate".
ASSET_GROUPS = {
    "Equities": ["S&P 500", "Nasdaq"],
    "Commodities": ["Gold", "Silver", "Platinum"],
    "Crypto": ["Bitcoin", "Ethereum", "Zcash", "Monero", "Solana"],
    "Real estate": ["US home prices"],
}
MAIN_ASSETS = [asset for assets in ASSET_GROUPS.values() for asset in assets]
LUXURY_ASSETS = [f"{LUXURY} ({city})" for city in LUXURY_CITIES]
ASSETS = MAIN_ASSETS + LUXURY_ASSETS
# How the page looks on first load (and after Reset): every switch and box.
FIRST_LOAD = {
    **{f"use_{asset}": False for asset in ASSETS},
    "use_S&P 500": True,
    "weight_S&P 500": 100.0,
    # Every fold-out section starts closed.
    **{f"section_{group}": False for group in ASSET_GROUPS},
    "luxury_section": False,
    "show_assets": False,
    "show_wages": True,
    "log_scale": True,
}
# A clearly different colour for each line (readable on light and dark backgrounds).
LINE_COLORS = {INDEX_NAME: "#3b82f6", "CPI": "#f59e0b", "Wages": "#10b981"}
# Colours for the optional individual-asset lines (distinct from the main lines).
ASSET_COLORS = {
    "US home prices": "#a16207", "S&P 500": "#ef4444",
    "Nasdaq": "#0f766e", "Gold": "#eab308", "Silver": "#94a3b8", "Platinum": "#78716c",
    "Bitcoin": "#d946ef", "Ethereum": "#8b5cf6", "Zcash": "#84cc16",
    "Monero": "#ec4899", "Solana": "#06b6d4",
}
# Luxury-homes cities: shades of one orange/brown family, in city order.
ASSET_COLORS.update(zip(LUXURY_ASSETS, [
    "#7c2d12", "#9a3412", "#c2410c", "#ea580c", "#f97316",
    "#fb923c", "#b45309", "#d97706", "#92400e",
]))
DOMINANT_SHARE = 80  # warn when one asset is more than this % of the index
BITCOIN_NOTE = (
    "Bitcoin prices from 2010–2012 come from very thin trading (few trades on "
    "small early exchanges), so they are less reliable than later prices."
)
CASE_SHILLER_NOTE = (
    "US home prices and luxury homes (Case-Shiller) are three-month moving "
    "averages: each month's value covers that month and the two before it."
)
LUXURY_NOTE = (
    "Luxury homes are Case-Shiller's high tier: the most expensive third of "
    "homes sold in that city's area."
)
PLATINUM_NOTE = (
    "Before the 1970s, platinum was mostly sold at prices set by producers, "
    "not on an open market."
)


def month_name(date) -> str:
    return date.strftime("%B %Y")  # for example "January 2015"


def share_text(share: float) -> str:
    """52.2%, or <0.1% / >99.9% for shares that would round to 0.0% / 100.0%."""
    if 0 < share < 0.05:
        return "<0.1%"
    if 99.95 < share < 100:
        return ">99.9%"
    return f"{share:.1f}%"


def weight_text(weight: float) -> str:
    """100, 33.33 or 99.99: up to two decimals, without trailing zeros."""
    return f"{weight:.2f}".rstrip("0").rstrip(".")


def duration_text(months: int) -> str:
    """62 years and 8 months, 1 year, 5 months, 0 months."""
    years, months = divmod(months, 12)
    parts = []
    if years:
        parts.append(f"{years} year{'s' if years != 1 else ''}")
    if months or not years:
        parts.append(f"{months} month{'s' if months != 1 else ''}")
    return " and ".join(parts)


# --- Weight buttons (these run before the page is redrawn) ---

def checked_assets() -> list[str]:
    return [asset for asset in ASSETS if st.session_state.get(f"use_{asset}")]


def split_evenly_clicked():
    for asset, weight in split_evenly(checked_assets()).items():
        st.session_state[f"weight_{asset}"] = weight


def split_categories_clicked():
    """Equal shares for every category with a checked asset; proportions kept inside each."""
    categories = {
        group: {
            asset: st.session_state.get(f"weight_{asset}", 0.0)
            for asset in section_assets(group) if st.session_state.get(f"use_{asset}")
        }
        for group in ASSET_GROUPS
    }
    if not any(categories.values()):
        st.session_state["weights_message"] = "Check at least one asset first."
        return
    for asset, weight in split_categories(categories).items():
        st.session_state[f"weight_{asset}"] = weight


def make_100_clicked():
    current = {asset: st.session_state.get(f"weight_{asset}", 0.0) for asset in checked_assets()}
    if sum(current.values()) == 0:
        st.session_state["weights_message"] = "Give at least one asset a weight first."
        return
    for asset, weight in make_100(current).items():
        st.session_state[f"weight_{asset}"] = weight


def section_assets(section: str) -> list[str]:
    """The assets a section's buttons act on. Real estate includes its luxury-homes cities."""
    if section == LUXURY:
        return LUXURY_ASSETS
    return ASSET_GROUPS[section] + (LUXURY_ASSETS if section == "Real estate" else [])


def section_weights(section: str) -> dict[str, float]:
    """The section's checked assets and their current weights."""
    return {
        asset: st.session_state.get(f"weight_{asset}", 0.0)
        for asset in section_assets(section) if st.session_state.get(f"use_{asset}")
    }


def section_split_clicked(section: str):
    """Share the section's current total equally among its checked assets."""
    current = section_weights(section)
    if not current:
        st.session_state["weights_message"] = f"Check at least one asset in {section} first."
        return
    for asset, weight in split_evenly(list(current), sum(current.values())).items():
        st.session_state[f"weight_{asset}"] = weight


def section_total_changed(section: str):
    """Typing a section total rescales that section right away (proportions kept)."""
    target = st.session_state[f"total_{section}"]
    current = section_weights(section)
    if target is None:  # the box was cleared: change nothing
        return
    if not current:
        st.session_state["weights_message"] = f"Check at least one asset in {section} first."
        return
    for asset, weight in set_section_total(current, target).items():
        st.session_state[f"weight_{asset}"] = weight


def reset_clicked():
    """Back to the first-load page. Each box is set explicitly (not just
    forgotten), so the browser shows the reset values too."""
    for asset in ASSETS:
        st.session_state.pop(f"weight_{asset}", None)
    st.session_state.update(FIRST_LOAD)
    # The start month goes back to the earliest month (set where the menu is made).
    st.session_state.pop("start", None)
    st.session_state.pop("earliest", None)


st.set_page_config(page_title="Wealth Inflation Tracker")
if "first_load_done" not in st.session_state:
    st.session_state.update(FIRST_LOAD)
    st.session_state["first_load_done"] = True
st.title("Wealth Inflation Tracker")
st.caption("Choose your assets and weights in the sidebar.")

# Everything below goes into this container, so the sources line (written
# next) always stays at the bottom, even when the page stops early.
main = st.container()
st.caption(
    "Sources: CPI, wages, Nasdaq, US home prices and luxury homes from "
    "[FRED](https://fred.stlouisfed.org/), Federal Reserve Bank of St. Louis · "
    "S&P 500 from [Robert Shiller](https://shillerdata.com/) · "
    "Gold, silver and platinum from the [World Bank Pink Sheet](https://www.worldbank.org/en/research/commodity-markets) · "
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
    # Every series except luxury homes, plus only the luxury-homes cities that are ticked.
    to_load = [name for name in SERIES if not name.startswith(LUXURY)]
    to_load += [city for city in LUXURY_ASSETS if st.session_state.get(f"use_{city}")]
    for name in to_load:
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
checked = {}  # every checked asset's weight in %, including 0%


def asset_row(place, asset: str, label: str, widths=(3, 2)):
    """One asset: a checkbox and, when checked, its weight box."""
    tick_column, weight_column = place.columns(list(widths), vertical_alignment="center")
    ticked = tick_column.checkbox(
        label,
        key=f"use_{asset}",
        # A main asset that could not be loaded (and has no backup) can't be
        # chosen; a luxury-homes city is only downloaded once it is ticked.
        disabled=asset in MAIN_ASSETS and asset not in tables,
    )
    if ticked and asset in tables:
        if f"weight_{asset}" not in st.session_state:
            st.session_state[f"weight_{asset}"] = 0.0  # a newly checked asset starts at 0%
        checked[asset] = weight_column.number_input(
            f"{asset} weight (%)",
            min_value=0.0,
            max_value=100.0,
            step=1.0,
            format="%.2f",
            key=f"weight_{asset}",
            label_visibility="collapsed",
        )
    else:
        st.session_state.pop(f"weight_{asset}", None)  # unchecking removes the weight


def selected_text(names: list[str], labels: list[str]) -> str:
    """The checked assets among `names` with their weights: "S&P 500 (100%), Nasdaq (0%)"."""
    return ", ".join(
        f"{label} ({weight_text(checked[name])}%)"
        for name, label in zip(names, labels) if name in checked
    )


# The section shows just the city name ("Wash. DC" is shortened so it fits
# next to its weight box; everywhere else it is "Luxury homes (Washington DC)").
CITY_LABELS = [{"Washington DC": "Wash. DC"}.get(city, city) for city in LUXURY_CITIES]
def section_controls(section: str):
    """A section's total box (always showing the real total; typing in it
    rescales the section) and its small Split evenly button."""
    # Fill the box with the section's real total before drawing it, so it is
    # always up to date after any tick, weight change or button.
    st.session_state[f"total_{section}"] = sum(section_weights(section).values())
    tick_column, button_column = st.columns([3, 2], vertical_alignment="center")
    tick_column.number_input(
        f"{section} section total (%)",
        min_value=0.0,
        max_value=100.0,
        step=1.0,
        format="%.2f",
        key=f"total_{section}",
        on_change=section_total_changed,
        args=(section,),
        label_visibility="collapsed",
    )
    button_column.button("Split evenly", key=f"split_{section}", type="tertiary",
                         on_click=section_split_clicked, args=(section,))


def section_share() -> dict[str, float]:
    """Each section's current share: the weights of its checked assets added up."""
    return {
        section: sum(checked.get(asset, 0.0) for asset in section_assets(section))
        for section in [*ASSET_GROUPS, LUXURY]
    }


# Section headings must never change: Streamlit treats a section whose heading
# changes as a new one and closes it. So what is selected goes on a line below.
for group, assets in ASSET_GROUPS.items():
    with st.sidebar.expander(group, key=f"section_{group}", on_change="rerun"):
        section_controls(group)
        for asset in assets:
            asset_row(st, asset, asset)
        if group == "Real estate":
            # The nine luxury-homes cities, each its own asset with its own weight.
            with st.expander(f"{LUXURY} (by city)", key="luxury_section", on_change="rerun"):
                section_controls(LUXURY)
                for city, label in zip(LUXURY_ASSETS, CITY_LABELS):
                    # The nested section is narrower: give the city names more room.
                    asset_row(st, city, label, widths=(5, 3))
            if cities := selected_text(LUXURY_ASSETS, CITY_LABELS):
                st.caption(f"Selected ({weight_text(section_share()[LUXURY])}%): {cities}")
    selected = selected_text(assets, assets)
    if group == "Real estate" and (cities := selected_text(LUXURY_ASSETS, CITY_LABELS)):
        selected = ", ".join(filter(None, [selected, f"luxury homes: {cities}"]))
    if selected:
        st.sidebar.caption(f"Selected ({weight_text(section_share()[group])}%): {selected}")

weights, total = basket_and_total(checked)  # weights: the basket, assets above 0%
weights_ok = weights_add_up(total)
if weights_ok:
    st.sidebar.caption(f"Total: {weight_text(total)}%")
else:
    st.sidebar.error(f"Total: {weight_text(total)}%. Weights must add up to 100%.")
with st.sidebar.container(horizontal=True):
    st.button("Split evenly", on_click=split_evenly_clicked)
    st.button("Split categories evenly", on_click=split_categories_clicked)
    st.button("Make it 100%", on_click=make_100_clicked)
    st.button("Reset", on_click=reset_clicked)
if "weights_message" in st.session_state:
    st.sidebar.info(st.session_state.pop("weights_message"))
st.sidebar.caption("Weights are set at the start month and change as prices move (no rebalancing).")
show_assets = st.sidebar.checkbox("Show individual assets", key="show_assets")

st.sidebar.header("Compare with")
st.sidebar.caption("CPI is always shown.")
# Wages start in 1964; turning them off lets the chart start as early as CPI (1913).
show_wages = st.sidebar.checkbox("Wages", key="show_wages")
comparisons = ["CPI", "Wages"] if show_wages else ["CPI"]

with main:
    # Drawn before anything that can stop the page: Streamlit forgets a
    # switch's setting whenever a run ends without drawing it.
    log_scale = st.toggle("Logarithmic scale", key="log_scale")

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
    if not weights_ok:
        st.stop()  # the sidebar already explains the problem

    lines = chart_lines(lined_up, start, weights)

    # The chart may also show each asset on its own; the % change table does not.
    chart = pd.concat([lines, asset_lines(lined_up, start, weights)], axis=1) if show_assets else lines

    figure = go.Figure()
    for name in chart.columns:
        if name in LINE_COLORS:  # the main lines: index, CPI, wages
            style = {"color": LINE_COLORS[name]}
        else:  # individual assets: thinner and dotted, so the main lines stand out
            style = {"color": ASSET_COLORS[name], "width": 1.5, "dash": "dot"}
        figure.add_trace(go.Scatter(
            x=chart.index, y=chart[name], name=name, mode="lines",
            line=style,
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
    if log_scale:  # label only 1, 10, 100, 1k, 10k, ... so the axis stays readable
        values, labels = power_of_ten_ticks(chart.min().min(), chart.max().max())
        figure.update_yaxes(tickvals=values, ticktext=labels)
    st.plotly_chart(
        figure,
        alt=f"Line chart of {', '.join(chart.columns)}, all starting at 100 in {month_name(start)}.",
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
    formatted = pd.DataFrame({
        "Total change": changes["Total change"].map(lambda value: percent_text(value, show_multiple=True)),
        "Yearly change": changes["Yearly change"].map(percent_text),
    }).rename_axis("Line")
    st.table(
        formatted,
        alt="Table of total and yearly percent change for each line on the chart.",
    )

    # Current weights: faster-rising assets become a bigger share over time.
    shares = current_weights(lined_up, start, weights)
    st.caption(
        f"Current weights ({month_name(end)}): "
        + " · ".join(f"{name} {share_text(share)}" for name, share in shares.items())
    )
    if len(shares) >= 2:  # with one asset it is always 100%, so no warning
        for name, share in shares.items():
            if share > DOMINANT_SHARE:
                st.warning(
                    f"{name} now makes up {share_text(share)} of your index, "
                    f"so the index mostly follows {name}."
                )
    if "US home prices" in weights or any(name.startswith(LUXURY) for name in weights):
        st.info(CASE_SHILLER_NOTE)
    if any(name.startswith(LUXURY) for name in weights):
        st.info(LUXURY_NOTE)
    if "Platinum" in weights:
        st.info(PLATINUM_NOTE)
    if needs_bitcoin_note(weights, start):
        st.info(BITCOIN_NOTE)
