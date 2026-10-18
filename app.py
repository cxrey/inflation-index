"""Wealth Inflation Tracker: the web page.

Run it with:  uv run streamlit run app.py

Streamlit re-runs this whole file from top to bottom every time someone
clicks or types on the page, so downloads are remembered with st.cache_data.
"""

import pandas as pd
import streamlit as st

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


st.set_page_config(page_title="Wealth Inflation Tracker")
st.title("Wealth Inflation Tracker")

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

# Temporary summary, to confirm everything loaded (replaced in 7c and 7d).
st.subheader("Loaded data")
st.table(
    pd.DataFrame([
        {
            "Series": name,
            "First month": table["date"].min().strftime("%B %Y"),
            "Last month": table["date"].max().strftime("%B %Y"),
            "Months": len(table),
        }
        for name, table in tables.items()
    ]).set_index("Series")
)

st.caption(
    "Sources: CPI, wages and US home prices from "
    "[FRED](https://fred.stlouisfed.org/), Federal Reserve Bank of St. Louis · "
    "S&P 500 from [Robert Shiller](https://shillerdata.com/) · "
    "Gold and silver from the [World Bank Pink Sheet](https://www.worldbank.org/en/research/commodity-markets) · "
    "Crypto data: [Coin Metrics](https://coinmetrics.io/)\n\n"
    "This product uses the FRED® API but is not endorsed or certified by the "
    "Federal Reserve Bank of St. Louis."
)
