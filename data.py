"""Download price data from each source.

Every function returns a table (pandas DataFrame) with two columns:
    date  - the month, stored as its first day (for example 2024-03-01)
    value - the price or index value for that month
"""

import html
import io
import re

import pandas as pd
import requests
from fredapi import Fred

SHILLER_PAGE = "https://shillerdata.com/"


def fred_series(series_id: str, api_key: str) -> pd.DataFrame:
    """Download one monthly series from FRED, for example "CPIAUCNS"."""
    values = Fred(api_key=api_key).get_series(series_id)
    table = pd.DataFrame({"date": values.index, "value": values.to_numpy()})
    # FRED marks months with no value as missing; drop them.
    return table.dropna().reset_index(drop=True)


def shiller_date(number: float) -> pd.Timestamp:
    """Convert Shiller's decimal date to the first day of that month.

    1871.01 -> 1871-01-01. October is stored as 2026.1 (the spreadsheet drops
    the trailing zero of 2026.10), so the part after the point is multiplied
    by 100 and rounded: .1 -> month 10, not month 1.
    """
    year = int(number)
    month = round((number - year) * 100)
    return pd.Timestamp(year=year, month=month, day=1)


def sp500() -> pd.DataFrame:
    """Download the S&P Composite price ("P" column) from Shiller's spreadsheet."""
    # The download link contains a version number that changes when the file
    # is updated, so find the current link on the web page each time.
    page = requests.get(SHILLER_PAGE, timeout=30)
    page.raise_for_status()
    match = re.search(r'href="([^"]*ie_data\.xls[^"]*)"', page.text)
    if match is None:
        raise ValueError(f"Could not find the ie_data.xls link on {SHILLER_PAGE}. The website may have changed.")
    link = html.unescape(match.group(1))
    if link.startswith("//"):
        link = "https:" + link

    file = requests.get(link, timeout=60)
    file.raise_for_status()
    # Row 8 of the "Data" sheet holds the column names ("Date", "P", ...).
    sheet = pd.read_excel(io.BytesIO(file.content), sheet_name="Data", header=7, engine="xlrd")

    table = pd.DataFrame({
        "date": pd.to_numeric(sheet["Date"], errors="coerce"),
        "value": pd.to_numeric(sheet["P"], errors="coerce"),
    })
    # Remove the text notes below the data (their "date" is not a number).
    table = table.dropna()
    table["date"] = table["date"].map(shiller_date)
    # Remove the current month: its price is not a full monthly average yet.
    this_month = pd.Timestamp.today().to_period("M").to_timestamp()
    table = table[table["date"] < this_month]
    return table.reset_index(drop=True)


if __name__ == "__main__":
    # This part runs only when you type "uv run python data.py".
    # It prints the first and last 3 months of each series so you can
    # compare them with the source websites.
    import tomllib

    with open(".streamlit/secrets.toml", "rb") as f:
        key = tomllib.load(f)["FRED_API_KEY"]

    def show(name, table):
        print(f"\n{name}: {len(table)} months")
        print(table.head(3).to_string(index=False))
        print("...")
        print(table.tail(3).to_string(index=False, header=False))

    show("CPI (CPIAUCNS)", fred_series("CPIAUCNS", key))
    show("Wages (AHETPI)", fred_series("AHETPI", key))
    show("US home prices (CSUSHPINSA)", fred_series("CSUSHPINSA", key))
    show("S&P 500 (Shiller)", sp500())
