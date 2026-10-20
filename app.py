"""Asset Inflation Tracker: the web page.

Run it with:  uv run streamlit run app.py

Streamlit re-runs this whole file from top to bottom every time someone
clicks or types on the page, so downloads are remembered with st.cache_data.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from calc import (
    INDEX_NAME,
    NO_DATA_REASON,
    market_weights_unchanged,
    waiting_lines,
    yearly_market_index,
    add_tables,
    asset_index,
    basket_sentences,
    cannot_measure,
    cpi_sentence,
    gold_market_value,
    gold_stock_table,
    home_market_value,
    investment_gold,
    keep_up_sentence,
    per_year,
    your_rate_sentences,
    asset_lines,
    basket_and_total,
    comparison_line,
    crypto_market_value,
    current_weights,
    last_month_set_by,
    line_up,
    make_100,
    market_caption,
    market_size_weights,
    months_between,
    needs_bitcoin_note,
    percent_text,
    percent_ticks,
    period_rates,
    rate_shortcut,
    set_section_total,
    split_categories,
    stock_market_value,
    split_evenly,
    treasury_market_value,
    summary_table,
    valid_months,
    weight_text,
    weights_add_up,
)
from data import (
    GOLD_INVESTMENT_TONNES,
    GOLD_STOCK_ANCHOR_DATE,
    GOLD_STOCK_ANCHOR_TONNES,
    GOLD_WORLD_PRODUCTION_TONNES,
    LUXURY_CITIES,
    PINK_SHEET_STARTS,
    crypto_market_cap,
    crypto,
    download_with_backup,
    fred_monthly_average,
    fred_series,
    pink_sheet,
    sp500,
    treasury_10y,
    treasury_bills,
    world_bank_us_market_cap,
)

# Every series: friendly name -> (backup file name, download function, inputs).
# FRED downloads also need the API key, which is added when downloading.
SERIES = {
    "CPI": ("CPIAUCNS", fred_series, ["CPIAUCNS"]),
    "Wages": ("AHETPI", fred_series, ["AHETPI"]),
    "US home prices": ("CSUSHPINSA", fred_series, ["CSUSHPINSA"]),
    "S&P 500": ("SP500", sp500, []),
    "Nasdaq": ("NASDAQCOM", fred_monthly_average, ["NASDAQCOM"]),
    "10-year Treasury": ("TREASURY_10Y", treasury_10y, []),
    "Gold": ("GOLD", pink_sheet, ["Gold"]),
    "Silver": ("SILVER", pink_sheet, ["Silver"]),
    "Platinum": ("PLATINUM", pink_sheet, ["Platinum"]),
    "Bitcoin": ("BTC", crypto, ["btc"]),
    "Ethereum": ("ETH", crypto, ["eth"]),
    "Zcash": ("ZEC", crypto, ["zec"]),
    "Monero": ("XMR", crypto, ["xmr"]),
    "Solana": ("SOL", crypto, ["sol"]),
}
M2 = "Money supply (M2)"
CASH_GOODS = "Cash (in consumer goods)"  # how much less cash buys at the store
CASH_BASKET = "Cash (in your basket)"  # how much less of your basket cash buys
SERIES[M2] = ("M2SL", fred_series, ["M2SL"])
# Yields for the "Your rate" shortcut buttons: button label and a line under it.
RATE_SHORTCUTS = {
    "10-year Treasury yield": ("Use 10-year Treasury yield", None),
    "3-month T-bill yield": ("Use 3-month T-bill yield", "About what safe cash earns (slightly understates it)."),
}
SERIES["10-year Treasury yield"] = ("GS10", fred_series, ["GS10"])
SERIES["3-month T-bill yield"] = ("TB3MS", fred_series, ["TB3MS"])
# Luxury homes: one series per city; only the selected city is downloaded.
LUXURY = "Luxury homes"
SERIES.update({
    f"{LUXURY} ({city})": (f"LUX_{series_id}", fred_series, [series_id])
    for city, series_id in LUXURY_CITIES.items()
})
# Market-size data for the "Weight by market size" button: which series give
# each asset's market value. Loaded only when needed (not with the prices).
COIN_CODES = {"Bitcoin": "btc", "Ethereum": "eth", "Zcash": "zec", "Monero": "xmr", "Solana": "sol"}
MARKET_SERIES = {
    "S&P 500": ["US stock market value"],
    "10-year Treasury": ["Treasury debt market value", "Treasury bills (monthly)", "Treasury bills (quarterly)"],
    "US home prices": ["US home market value", "US landlord home market value"],
    **{coin: [f"{coin} market cap"] for coin in COIN_CODES},
}
MARKET_ONLY = {name for names in MARKET_SERIES.values() for name in names}
SERIES.update({
    "US stock market value": ("US_MARKET_CAP", world_bank_us_market_cap, []),
    "Treasury debt market value": ("MVMTD027MNFRBDAL", fred_series, ["MVMTD027MNFRBDAL"]),
    "Treasury bills (monthly)": ("TREASURY_BILLS", treasury_bills, []),
    "Treasury bills (quarterly)": ("BOGZ1FL313161110Q", fred_series, ["BOGZ1FL313161110Q"]),
    "US home market value": ("HNOREMQ027S", fred_series, ["HNOREMQ027S"]),
    "US landlord home market value": ("NNBEMVQ027S", fred_series, ["NNBEMVQ027S"]),
    **{f"{coin} market cap": (f"CAP_{code.upper()}", crypto_market_cap, [code]) for coin, code in COIN_CODES.items()},
})
# Investment gold (tonnes) at each year-end, back to the year-end before our first gold price.
GOLD_INVESTMENT_BY_YEAR_END = {
    year: investment_gold(tonnes, GOLD_INVESTMENT_TONNES, GOLD_STOCK_ANCHOR_TONNES)
    for year, tonnes in gold_stock_table(
        GOLD_WORLD_PRODUCTION_TONNES, GOLD_STOCK_ANCHOR_TONNES, GOLD_STOCK_ANCHOR_DATE,
        pd.Timestamp(PINK_SHEET_STARTS["Gold"]),
    ).items()
}
FRED_DOWNLOADS = (fred_series, fred_monthly_average, treasury_10y)


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
    "Fixed Income": ["10-year Treasury"],
    "Real estate": ["US home prices"],
    "Commodities": ["Gold", "Silver", "Platinum"],
    "Crypto": ["Bitcoin", "Ethereum", "Zcash", "Monero", "Solana"],
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
    "show_m2": False,
    "your_rate": None,  # the "Your rate" box starts empty
    "yearly_update": False,  # turned on by "Weight by market size"
    "log_scale": True,
}
# A clearly different colour for each line (readable on light and dark backgrounds).
LINE_COLORS = {
    INDEX_NAME: "#3b82f6", "CPI": "#f59e0b", "Wages": "#10b981", M2: "#a855f7",
    # The cash lines are dashed, in the colour of what cash is measured against.
    CASH_GOODS: "#f59e0b", CASH_BASKET: "#3b82f6",
}
# Colours for the optional individual-asset lines (distinct from the main lines).
ASSET_COLORS = {
    "US home prices": "#a16207", "S&P 500": "#ef4444", "10-year Treasury": "#6366f1",
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
MARKET_SIZE_HELP = (
    "Weights each asset by its total market value, the way the S&P 500 weights its "
    "companies. US stocks are available from December 1975. Nasdaq, silver, platinum and "
    "luxury homes by city have no market-size data: if any are ticked, the button offers "
    "to untick them first."
)
MARKET_SIZE_NOTE = [
    "Each asset is weighted by the size of the market its price comes from. Stock, Treasury and "
    "home prices are US, so they use US market sizes; gold and crypto trade in one global market, "
    "so they use world totals. That gives gold more weight than it has in US wealth alone.",
    "US stocks: total value of US companies listed on US exchanges (World Bank).",
    "10-year Treasury: market value of all marketable Treasury debt (Federal Reserve Bank of "
    "Dallas) minus Treasury bills at face value (US Treasury; Federal Reserve before 2001), so "
    "it counts notes and bonds of every length, not only 10-year ones. Floating-rate notes may "
    "be included in the market-value figure (up to about 3% of it).",
    "US homes: owner-occupied and landlord-owned residential real estate, including land, plus "
    "nonprofits' property (Federal Reserve). Rental housing owned by large corporations and "
    "REITs isn't included.",
    "Gold: total from mining history (World Gold Council, USGS), investment gold only (not "
    "jewelry). The investment share uses today's figure for all years, so earlier years are "
    "estimates. USGS's yearly mining totals are lower than the World Gold Council's, so earlier "
    "years' gold stock, and gold's weight for older start months, is somewhat high.",
    "Crypto: Coin Metrics market caps (Solana's is an estimate).",
]
# Always shown under the tables.
GENERAL_NOTES = [
    "Rates are past rates, not forecasts.",
    "If you own the assets in your basket, you keep pace with it automatically (plus dividends, "
    "which aren't included here). The rate matters for money held in cash, savings or anything else.",
    "The rate only applies to the assets you put in your basket.",
    "Based on monthly averages; daily drops were larger.",
]
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
TREASURY_NOTE = (
    "10-year Treasury: price change of 10-year US Treasuries, interest not included. Most of a "
    "bond's return is interest, so this line shows only how the cost of buying bond income "
    "changed. Bond prices fall when interest rates rise, so this line drops in high-inflation "
    "periods like the 1970s and 2022. Market size counts longer-term Treasuries only; bills are "
    "left out because they behave like cash."
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


def mark_market_edited():
    """A weight button was pressed after "Weight by market size": the caption
    becomes "(edited)" even if the numbers happen to stay the same."""
    if "market" in st.session_state:
        # Store an updated copy: Streamlit may not keep a change made inside the saved value.
        st.session_state["market"] = {**st.session_state["market"], "edited": True}


def split_evenly_clicked():
    mark_market_edited()
    for asset, weight in split_evenly(checked_assets()).items():
        st.session_state[f"weight_{asset}"] = weight


def split_categories_clicked():
    """Equal shares for every category with a checked asset; proportions kept inside each."""
    mark_market_edited()
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
    mark_market_edited()
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
    mark_market_edited()
    current = section_weights(section)
    if not current:
        st.session_state["weights_message"] = f"Check at least one asset in {section} first."
        return
    for asset, weight in split_evenly(list(current), sum(current.values())).items():
        st.session_state[f"weight_{asset}"] = weight


def section_total_changed(section: str):
    """Typing a section total rescales that section right away (proportions kept)."""
    mark_market_edited()
    target = st.session_state[f"total_{section}"]
    current = section_weights(section)
    if target is None:  # the box was cleared: change nothing
        return
    if not current:
        st.session_state["weights_message"] = f"Check at least one asset in {section} first."
        return
    for asset, weight in set_section_total(current, target).items():
        st.session_state[f"weight_{asset}"] = weight


def market_values_at(start, assets: list[str]) -> dict[str, float | None]:
    """Each asset's market value in dollars at the start month; None = no data."""
    values = {}
    for asset in assets:
        try:
            # The asset's market-size tables, in the order listed in MARKET_SERIES.
            market = [load(name)[0] for name in MARKET_SERIES.get(asset, [])]
            if asset == "S&P 500":
                values[asset] = stock_market_value(start, market[0], tables[asset])
            elif asset == "10-year Treasury":
                values[asset] = treasury_market_value(start, *market, tables[asset])
            elif asset == "US home prices":
                # Households' homes + landlords' homes = all US homes.
                values[asset] = home_market_value(start, add_tables(*market), tables[asset])
            elif asset == "Gold":
                values[asset] = gold_market_value(start, GOLD_INVESTMENT_BY_YEAR_END, tables[asset])
            elif asset in MARKET_SERIES:  # a coin
                values[asset] = crypto_market_value(start, market[0], tables[asset])
        except Exception:  # could not be loaded and has no backup: no data
            values[asset] = None
    return values


def market_value_of(asset: str, month) -> float | None:
    """One asset's market value in a month (for updating weights every January)."""
    return market_values_at(month, [asset])[asset]


def all_yearly_prices(weights: dict[str, float], waiting: list[str]) -> pd.DataFrame:
    """Prices for updating weights every January: one row per month the basket
    (assets above 0%) has, one column per basket asset and per asset waiting to
    join (empty in months it has no price)."""
    rows = line_up({name: tables[name] for name in weights}).index
    return pd.DataFrame({
        name: tables[name].set_index(tables[name]["date"].dt.to_period("M").dt.to_timestamp())["value"].reindex(rows)
        for name in [*weights, *waiting]
    })


def rate_shortcut_clicked(text: str, value: float):
    """A "Use ... yield" button: fill the "Your rate" box with that yield."""
    st.session_state["your_rate"] = value
    st.session_state["rate_source"] = {"text": text, "value": value}


def market_size_clicked():
    # Applied further down, before the weight boxes are drawn (see apply_market_size).
    st.session_state["market_pressed"] = True


def apply_market_size(start):
    """Set every checked asset's weight to its share of the total market value.
    If any checked asset can never be measured (Nasdaq, silver, platinum, a
    city), change nothing and open the pop-up. An asset with no market-size
    data only for this date starts at 0% and waits to join in a later January."""
    assets = checked_assets()
    values = market_values_at(start, assets)
    reasons = cannot_measure(assets, values)
    never = {asset: reason for asset, reason in reasons.items() if reason != NO_DATA_REASON}
    waiting = [asset for asset, reason in reasons.items() if reason == NO_DATA_REASON]
    measured = [asset for asset in assets if asset not in reasons]
    if never:
        cannot_weight_dialog(start, never, measured, waiting)
        return
    weights = market_size_weights(measured, values)
    weights.update({asset: 0.0 for asset in waiting})
    for asset, weight in weights.items():
        st.session_state[f"weight_{asset}"] = weight
    st.session_state["market"] = {"start": start, "weights": weights, "waiting": waiting}
    st.session_state["yearly_update"] = True  # pressing the button turns January updates on
    # Keep this start month even if an unticked asset no longer limits the dates.
    st.session_state["earliest"] = None


def untick_and_weight(assets: list[str]):
    """The pop-up's "Untick these" button: untick them, then weight the rest
    (on the full rerun that follows)."""
    for asset in assets:
        st.session_state[f"use_{asset}"] = False
    st.session_state["market_pressed"] = True


@st.dialog("Not every asset can be weighted by market size")
def cannot_weight_dialog(start, reasons: dict[str, str], measurable: list[str], waiting: list[str]):
    """Nothing has changed yet: the user either unticks the assets that can't be
    measured (and the rest are weighted by market size), or cancels."""
    st.write(f"These can't be weighted by market size for {month_name(start)}:")
    st.markdown("\n".join(f"- **{asset}**: {reason}" for asset, reason in reasons.items()))
    st.write(f"Can be weighted by market size: {', '.join(measurable)}.")
    if waiting:
        st.write(f"No market-size data yet, so they start at 0% and join in a later January: {', '.join(waiting)}.")
    if st.button("Untick these and weight the rest by market size", type="primary",
                 on_click=untick_and_weight, args=(list(reasons),)):
        st.rerun()  # a full rerun closes the pop-up and applies the weights
    if st.button("Cancel"):
        st.rerun()


def reset_clicked():
    """Back to the first-load page. Each box is set explicitly (not just
    forgotten), so the browser shows the reset values too."""
    st.session_state.pop("market", None)  # removes the market-size caption
    st.session_state.pop("rate_source", None)  # the "Your rate" box is emptied
    for asset in ASSETS:
        st.session_state.pop(f"weight_{asset}", None)
    st.session_state.update(FIRST_LOAD)
    # The start month goes back to the earliest month (set where the menu is made).
    st.session_state.pop("start", None)
    st.session_state.pop("earliest", None)


st.set_page_config(page_title="Asset Inflation Tracker")
if "first_load_done" not in st.session_state:
    st.session_state.update(FIRST_LOAD)
    st.session_state["first_load_done"] = True
st.title("Asset Inflation Tracker")
st.caption("Choose your assets and weights in the sidebar.")

# Everything below goes into this container, so the sources line (written
# next) always stays at the bottom, even when the page stops early.
main = st.container()
st.caption(
    "Sources: CPI, wages, money supply, Nasdaq, 10-year Treasury yields, US home prices and luxury homes from "
    "[FRED](https://fred.stlouisfed.org/), Federal Reserve Bank of St. Louis · "
    "S&P 500 from [Robert Shiller](https://shillerdata.com/) · "
    "Gold, silver and platinum from the [World Bank Pink Sheet](https://www.worldbank.org/en/research/commodity-markets) · "
    "Crypto data: [Coin Metrics](https://coinmetrics.io/) · "
    "Market sizes: US stocks from the [World Bank](https://data.worldbank.org/indicator/CM.MKT.LCAP.CD) "
    "(World Federation of Exchanges data, CC BY 4.0), US homes from FRED (Federal Reserve), "
    "Treasury debt from the [Federal Reserve Bank of Dallas](https://www.dallasfed.org/research/econdata/govdebt) "
    "(via FRED), the [US Treasury](https://fiscaldata.treasury.gov/datasets/monthly-statement-public-debt/) "
    "and FRED (Federal Reserve), "
    "gold from the [World Gold Council](https://www.gold.org/goldhub/data/above-ground-stocks) and "
    "[USGS](https://www.usgs.gov/centers/national-minerals-information-center/gold-statistics-and-information)\n\n"
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
    to_load = [
        name for name in SERIES
        if not name.startswith(LUXURY) and name not in MARKET_ONLY
    ]
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

# "Weight by market size" was pressed: set the weights now, before the weight
# boxes are drawn, using the start month shown when it was pressed.
if st.session_state.pop("market_pressed", False) and st.session_state.get("start") is not None:
    apply_market_size(st.session_state["start"])

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
# The dates: only the basket's assets above 0% and CPI decide them. Worked out
# here already, because the market-size button depends on the start month.
basket_tables = {name: tables[name] for name in weights}
months = valid_months(basket_tables, tables["CPI"]) if "CPI" in tables else []
if months:
    earliest = months[0]
    chosen_start = st.session_state.get("start")
    # Move to the earliest month if the chosen month is no longer offered, or if
    # it was the earliest month before this change (so it follows the earliest).
    if chosen_start not in months or chosen_start == st.session_state.get("earliest"):
        st.session_state["start"] = earliest
    st.session_state["earliest"] = earliest
start_month = st.session_state.get("start") if months else None

# The market-size button only works if a checked asset has market-size data then
# (any others are offered for unticking in the pop-up).
market_help = MARKET_SIZE_HELP
market_ok = False
if start_month is not None:
    unmeasurable = cannot_measure(list(checked), market_values_at(start_month, list(checked)))
    market_ok = any(asset not in unmeasurable for asset in checked)
    if checked and not market_ok:
        market_help += f"\n\nNone of your ticked assets has market-size data for {month_name(start_month)}."

with st.sidebar.container(horizontal=True):
    st.button("Split evenly", on_click=split_evenly_clicked)
    st.button("Split categories evenly", on_click=split_categories_clicked)
    st.button("Make it 100%", on_click=make_100_clicked)
    st.button("Weight by market size", on_click=market_size_clicked, disabled=not market_ok,
              help=market_help)
    st.button("Reset", on_click=reset_clicked)
if "weights_message" in st.session_state:
    st.sidebar.info(st.session_state.pop("weights_message"))
# After "Weight by market size": what it set, and whether it has been edited since.
market_state = st.session_state.get("market")
market_lines = market_caption(market_state, checked, start_month)
for line in market_lines:
    st.sidebar.caption(line)
# Assets waiting to join (0% at the start month): filled in once the index is
# worked out, because when they join depends on it.
waiting_area = st.sidebar.container()
waiting = (market_state or {}).get("waiting", [])
# Updating every January is only possible while the weights are exactly what
# the button set; any edit, or another start month, turns it off.
market_unchanged = market_weights_unchanged(market_state, checked, start_month)
if not market_unchanged:
    st.session_state["yearly_update"] = False
yearly = False
if market_state:  # shown once the button has been pressed (until Reset)
    yearly = st.sidebar.checkbox("Update to market size every January", key="yearly_update",
                                 disabled=not market_unchanged)
with st.sidebar.expander("How market size is measured"):
    st.markdown("\n".join(f"- {line}" for line in MARKET_SIZE_NOTE))
st.sidebar.caption(
    "Weights reset to market size every January." if yearly else
    "Weights are set at the start month and change as prices move (no rebalancing)."
)
show_assets = st.sidebar.checkbox("Show individual assets", key="show_assets")

st.sidebar.header("Compare with")
st.sidebar.caption("CPI is always shown.")
# Wages and money supply are drawn only where they have data: they never
# change the start or end month.
show_wages = st.sidebar.checkbox("Wages", key="show_wages")
show_m2 = st.sidebar.checkbox(M2, key="show_m2")

with main:
    # The main results go above the chart; this area is filled further down,
    # once the start and end months are known.
    results_area = st.container()
    # Drawn before anything that can stop the page: Streamlit forgets a
    # switch's setting whenever a run ends without drawing it.
    log_scale = st.toggle("Logarithmic scale", key="log_scale")

    if "CPI" not in tables:
        st.error("CPI could not be loaded, so the chart can't be drawn.")
        st.stop()
    if not weights:
        st.info("Choose at least one asset and give it a weight.")
    elif not weights_ok:
        st.warning("Weights must add up to 100%. Results for your basket are hidden until they do.")

    if not months:
        st.error("The selected series have no months in common.")
        st.stop()

# The start-month menu offers only months where the basket and CPI have data
# (the month itself was worked out above, before the weight buttons).
start = st.sidebar.selectbox("Start month", months, format_func=month_name, key="start")

with main:
    end = months[-1]
    show_basket = bool(weights) and weights_ok

    # Every month from start to end, so a missing month shows as a break in
    # its line (October 2025 CPI) and a line that ends early simply stops.
    reweights = {}  # market-size weights set at the start month and each January
    if show_basket:
        prices = line_up(basket_tables).loc[start:end]  # the basket's own months
        if yearly:
            # The basket's months, with every checked asset (including any waiting to join).
            yearly_prices = all_yearly_prices(weights, waiting)
            index, reweights = yearly_market_index(yearly_prices.loc[:end], start, market_value_of)
            # An asset that joined later also decides the end month from then on.
            joined_tables = {name: tables[name] for name in waiting if any(name in w for w in reweights.values())}
            if joined_tables:
                last = min(table["date"].max() for table in joined_tables.values())
                end = max(month for month in months if month <= last)
                basket_tables = {**basket_tables, **joined_tables}
                prices = prices.loc[:end]
            index = index.loc[:end]
        else:
            index = asset_index(prices, {name: weight / 100 for name, weight in weights.items()})
    if waiting and market_unchanged:  # in the sidebar, under the market-size caption
        waiting_area.caption("\n".join(f"- {line}" for line in waiting_lines(waiting, reweights, yearly)))
    lines = pd.DataFrame(index=pd.date_range(start, end, freq="MS"))
    if show_basket:
        lines[INDEX_NAME] = index
    comparison_notes = []
    for name, shown in [("CPI", True), ("Wages", show_wages), (M2, show_m2)]:
        if not shown:
            continue
        if name not in tables:
            comparison_notes.append(f"{name} could not be loaded.")
            continue
        line, note = comparison_line(name, tables[name], start, end)
        if note:
            comparison_notes.append(note)  # for example "Wages data starts in January 1964."
        else:
            lines[name] = line

    # --- Main results: rates per year from start to end ---
    period_months = months_between(start, end)
    basket_rate = (
        per_year(lines[INDEX_NAME].iloc[0], lines[INDEX_NAME].iloc[-1], period_months)
        if show_basket else None
    )
    cpi_rate = per_year(lines["CPI"].iloc[0], lines["CPI"].iloc[-1], period_months)
    with results_area:
        for sentence in basket_sentences(basket_rate, start, end):
            st.markdown(f"#### {sentence}")
        if cpi := cpi_sentence(cpi_rate):
            st.markdown(f"#### {cpi}")
        if keep_up := keep_up_sentence(basket_rate):
            st.markdown(keep_up)
        if period_months < 12:
            st.info("Rates per year need at least 12 months between the start and end month.")
        box_column, shortcut_column = st.columns([3, 2])
        your_rate = box_column.number_input(
            "Your rate (% per year)",
            min_value=-99.99,  # must be above -100%
            max_value=1000.0,
            step=0.5,
            format="%.2f",
            placeholder="What your money earns, for example 4 for a 4% savings account",
            key="your_rate",
        )
        # Which shortcut filled the box, shown while the box still holds its value.
        source = st.session_state.get("rate_source")
        if source and your_rate == source["value"]:
            box_column.caption(f"{source['text']}: {source['value']:.2f}%")
        for name, (label, explanation) in RATE_SHORTCUTS.items():
            if name in tables:
                text, value = rate_shortcut(name, tables[name])
                shortcut_column.button(label, on_click=rate_shortcut_clicked, args=(text, value))
            else:  # could not be loaded and has no backup
                shortcut_column.button(label, disabled=True)
            if explanation:
                shortcut_column.caption(explanation)
        if your_rate is not None:
            for sentence in your_rate_sentences(your_rate / 100, basket_rate, cpi_rate):
                st.markdown(sentence)

    # --- The chart: % change since the start month ---
    # The lines are kept as levels (100 = the start month). The chart adds the
    # two cash lines: how much less cash buys, 100 × start / now (as a level).
    chart = lines.copy()
    chart[CASH_GOODS] = 100 * 100 / lines["CPI"]  # always shown; breaks where CPI does
    if show_basket:
        chart[CASH_BASKET] = 100 * 100 / lines[INDEX_NAME]
        if show_assets:  # each asset on its own (the tables don't include these)
            chart = chart.join(asset_lines(prices, start, weights))

    figure = go.Figure()
    for name in chart.columns:
        if name in (CASH_GOODS, CASH_BASKET):  # dashed, in the colour of what cash is measured against
            style = {"color": LINE_COLORS[name], "dash": "dash"}
        elif name in LINE_COLORS:  # the main lines: index, CPI, wages, money supply
            style = {"color": LINE_COLORS[name]}
        else:  # individual assets: thinner and dotted, so the main lines stand out
            style = {"color": ASSET_COLORS[name], "width": 1.5, "dash": "dot"}
        change = chart[name] - 100  # % change since the start month
        figure.add_trace(go.Scatter(
            x=chart.index,
            # A log axis can't show 0% or negative numbers, so it draws the level
            # (100 = start) and its labels say the % change instead.
            y=chart[name] if log_scale else change,
            customdata=change,
            name=name,
            mode="lines",
            line=style,
            hovertemplate="%{customdata:+,.1f}%",  # hovering shows each line's % change
        ))
    figure.add_hline(y=100 if log_scale else 0, line_dash="dot", line_width=1, line_color="gray")
    # The line's label is placed on its own: on a log axis, Plotly reads a
    # label's height as a power of ten, so the start level 100 is written as 2.
    # It sits at the right end, where the lines have usually moved away from 0%.
    figure.add_annotation(
        x=end, y=2 if log_scale else 0, text=f"Start: {month_name(start)} = 0%",
        showarrow=False, xanchor="right", yanchor="bottom", font={"color": "gray"},
    )
    figure.update_layout(
        hovermode="x unified",  # hovering shows every line for that month
        yaxis_title="% change since the start month",
        yaxis_type="log" if log_scale else "linear",
        legend={"orientation": "h", "y": 1.1},
        margin={"t": 40},
    )
    figure.update_xaxes(hoverformat="%B %Y")
    if log_scale:  # % labels at powers of ten: -90%, 0%, +900%, ...
        values, labels = percent_ticks(chart.min().min(), chart.max().max())
        figure.update_yaxes(tickvals=values, ticktext=labels)
    else:
        figure.update_yaxes(tickformat="+,.0f", ticksuffix="%")
    st.plotly_chart(
        figure,
        alt=f"Line chart of the % change of {', '.join(chart.columns)} since {month_name(start)}.",
    )

    set_by = ", ".join(last_month_set_by({**basket_tables, "CPI": tables["CPI"]}))
    st.caption(f"Start: {month_name(start)} · Data through: {month_name(end)} (set by {set_by})")
    for note in comparison_notes:
        st.info(note)

    # --- Rates over different periods: each calculated fresh, ending at the end month ---
    st.markdown(f"**Rates per year over different periods (to {month_name(end)})**")
    cpi_values = tables["CPI"].set_index("date")["value"]
    if show_basket and yearly:  # each period: market-size weights at its start, updated every January
        periods = period_rates(all_yearly_prices(weights, waiting), cpi_values, weights, end,
                               market_value=market_value_of)
    else:
        all_prices = line_up({name: tables[name] for name in weights}) if show_basket else pd.DataFrame()
        periods = period_rates(all_prices, cpi_values, weights if show_basket else {}, end)
    period_rows = {"CPI": periods["CPI"]}
    if show_basket:
        period_rows = {INDEX_NAME: periods["basket"], **period_rows}
    st.table(
        pd.DataFrame({
            name: {
                f"{years} year{'s' if years > 1 else ''}": percent_text(None if rate is None else rate * 100)
                for years, rate in rates.items()
            }
            for name, rates in period_rows.items()
        }).T.rename_axis("Line"),
        alt="Table of the basket and CPI per year over the last 1, 3, 5, 10 and 20 years.",
    )
    st.caption("These rates ignore the start month you picked. If they differ a lot, no single rate is reliable.")

    # --- Summary table: total change, change per year and worst drop since the start month ---
    summary = summary_table(lines)
    # A line that ends before the end month is measured to its own last month.
    summary.index = [
        f"{name} (through {month_name(lines[name].last_valid_index())})"
        if lines[name].last_valid_index() < end else name
        for name in summary.index
    ]
    st.markdown(
        f"**Summary from {month_name(start)} to {month_name(end)} "
        f"({duration_text(months_between(start, end))})**"
    )
    st.table(
        pd.DataFrame({
            "Total change": summary["Total change"].map(lambda value: percent_text(value, show_multiple=True)),
            "Change per year": summary["Change per year"].map(percent_text),
            "Worst drop": summary["Worst drop"].map(lambda value: "0.00%" if value == 0 else percent_text(value)),
        }).rename_axis("Line"),
        alt="Table of total change, change per year and worst drop for each line.",
    )

    if show_basket:
        # Current weights: faster-rising assets become a bigger share over time
        # (counted from the last January when the weights are updated every January).
        if yearly:
            last_set = max(month for month in reweights if month <= end)
            shares = current_weights(yearly_prices.loc[:end], last_set,
                                     {name: 100 * share for name, share in reweights[last_set].items()})
        else:
            shares = current_weights(prices, start, weights)
        st.caption(
            f"Current weights ({month_name(prices.index[-1])}): "
            + " · ".join(f"{name} {share_text(share)}" for name, share in shares.items())
        )
        if len(shares) >= 2:  # with one asset it is always 100%, so no warning
            for name, share in shares.items():
                if share > DOMINANT_SHARE:
                    st.warning(
                        f"{name} now makes up {share_text(share)} of your index, "
                        f"so the index mostly follows {name}."
                    )
    # Notes about the data itself are shown whenever the asset is above 0%.
    if "US home prices" in weights or any(name.startswith(LUXURY) for name in weights):
        st.info(CASE_SHILLER_NOTE)
    if any(name.startswith(LUXURY) for name in weights):
        st.info(LUXURY_NOTE)
    if "10-year Treasury" in weights:
        st.info(TREASURY_NOTE)
    if "Platinum" in weights:
        st.info(PLATINUM_NOTE)
    if needs_bitcoin_note(weights, start):
        st.info(BITCOIN_NOTE)

    st.markdown("**Notes**")
    st.caption("\n".join(f"- {note}" for note in GENERAL_NOTES))
