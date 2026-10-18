"""Download price data from each source.

Every download function returns a table (pandas DataFrame) with two columns:
    date  - the month, stored as its first day (for example 2024-03-01)
    value - the price or index value for that month

download_with_backup() wraps any of them: it retries temporary failures,
saves each successful download, and falls back to the saved copy.

What one monthly value is, for each series:
    Assets (all are monthly averages of daily prices, except home prices):
    S&P 500 (Shiller "P")   average of the month's daily closing prices
    Gold (Pink Sheet)       average of daily rates (stated in the file)
    Silver (Pink Sheet)     London afternoon fixing; the World Bank does not
                            say "average" for silver, but its monthly prices
                            are generally averages of daily quotes
    Crypto (Coin Metrics)   our own average of daily PriceUSD values,
                            complete months only (see calc.monthly_average)
    Home prices (CSUSHPINSA) NOT an average of daily prices: Case-Shiller is
                            a three-month moving average of repeat home sales
                            (the "July" value covers May, June and July)
    Comparison lines:
    CPI (CPIAUCNS)          prices collected throughout the month
    Wages (AHETPI)          average hourly earnings for the pay period that
                            includes the 12th of the month
"""

import html
import io
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests

from calc import monthly_average

FRED_URL = "https://api.stlouisfed.org/fred/series/observations"
COINMETRICS_URL = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
SHILLER_PAGE = "https://shillerdata.com/"
PINK_SHEET_PAGE = "https://www.worldbank.org/en/research/commodity-markets"
# First month used for each Pink Sheet column (earlier prices were not set by
# a free market: gold was fixed, silver was held down by the US Treasury).
PINK_SHEET_STARTS = {"Gold": "1971-01-01", "Silver": "1968-01-01"}

# Time limits in seconds.
PAGE_TIMEOUT = 10  # web pages
FILE_TIMEOUT = 20  # data files and FRED data

ATTEMPTS = 3  # the first try plus 2 retries
WAIT_SECONDS = 3  # pause between attempts
SAVED_DATA = Path("saved_data")


class TemporaryDownloadError(Exception):
    """A download failure that may succeed if tried again."""


def fetch(url: str, timeout: int, source: str, params: dict | None = None) -> requests.Response:
    """Download a web address, sorting failures into temporary and permanent.

    Error messages name the source but never the web address, because the
    FRED address contains the API key.
    """
    try:
        response = requests.get(url, params=params, timeout=timeout)
    # "from None" hides the original error, whose message includes the address.
    except requests.Timeout:
        raise TemporaryDownloadError(f"{source} did not respond within {timeout} seconds") from None
    except (requests.ConnectionError, requests.exceptions.ChunkedEncodingError):
        raise TemporaryDownloadError(f"could not connect to {source}") from None

    status = response.status_code
    if status == 429 or 500 <= status <= 599:
        raise TemporaryDownloadError(f"{source} returned error {status} ({response.reason})")
    if status >= 400:
        raise ValueError(f"{source} returned error {status} ({response.reason})")
    return response


def download_with_backup(name, download, *inputs, folder=SAVED_DATA, wait_seconds=WAIT_SECONDS, label=None):
    """Run download(*inputs), retrying temporary failures and keeping a backup.

    Returns (table, note). note is None when the data is fresh; otherwise it
    explains that the saved copy is being shown, and why.

    name is the backup file name; label is the name used in the note
    (for example "S&P 500" instead of "SP500"). Without a label, name is used.
    """
    path = Path(folder) / f"{name}.csv"
    problem = None
    for attempt in range(ATTEMPTS):
        if attempt > 0:
            time.sleep(wait_seconds)
        try:
            table = download(*inputs)
        except TemporaryDownloadError as error:
            problem = error  # may work next time: try again
            continue
        except Exception as error:
            problem = error  # will not fix itself: stop trying
            break
        path.parent.mkdir(exist_ok=True)
        table.to_csv(path, index=False)
        return table, None

    if not path.exists():
        raise problem
    saved = pd.read_csv(path, parse_dates=["date"])
    saved_on = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")
    latest = saved["date"].max().strftime("%B %Y")
    note = (
        f"{label or name} could not be downloaded ({problem}). "
        f"Showing the copy saved on {saved_on} (latest month: {latest})."
    )
    return saved, note


def find_link(page_url: str, file_name: str, source: str) -> str:
    """Find the current download link for file_name on a web page.

    Download links often contain a version number that changes when the file
    is updated, so the link is looked up on the page each time.
    """
    page = fetch(page_url, PAGE_TIMEOUT, source)
    match = re.search(r'href="([^"]*' + re.escape(file_name) + r'[^"]*)"', page.text)
    if match is None:
        raise ValueError(f"Could not find the {file_name} link on {page_url}. The website may have changed.")
    # urljoin turns a short link like "//host/file" or "/file" into a full address.
    return urljoin(page_url, html.unescape(match.group(1)))


def fred_series(series_id: str, api_key: str) -> pd.DataFrame:
    """Download one monthly series from FRED, for example "CPIAUCNS".

    See the top of this file for what one monthly value is for each series.
    """
    params = {"series_id": series_id, "api_key": api_key, "file_type": "json"}
    observations = fetch(FRED_URL, FILE_TIMEOUT, "FRED", params).json()["observations"]
    table = pd.DataFrame(observations)[["date", "value"]]
    table["date"] = pd.to_datetime(table["date"])
    # FRED writes "." for months with no value; turn those into missing and drop them.
    table["value"] = pd.to_numeric(table["value"], errors="coerce")
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
    """Download the S&P Composite price ("P" column) from Shiller's spreadsheet.

    Each value is the average of that month's daily closing prices.
    """
    link = find_link(SHILLER_PAGE, "ie_data.xls", "shillerdata.com")
    file = fetch(link, FILE_TIMEOUT, "Shiller's spreadsheet")
    # Row 8 of the "Data" sheet holds the column names ("Date", "P", ...).
    sheet = pd.read_excel(io.BytesIO(file.content), sheet_name="Data", header=7, engine="xlrd")
    for column in ["Date", "P"]:
        if column not in sheet.columns:
            raise ValueError(f"Shiller's spreadsheet has no '{column}' column. Its layout may have changed.")

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


def pink_date(text: str) -> pd.Timestamp:
    """Convert a Pink Sheet month like "1960M01" to 1960-01-01."""
    year, month = text.split("M")
    return pd.Timestamp(year=int(year), month=int(month), day=1)


def pink_sheet(column: str) -> pd.DataFrame:
    """Download one column ("Gold" or "Silver") from the World Bank Pink Sheet.

    Gold is an average of daily rates; silver is the London afternoon fixing,
    generally averaged by month (the World Bank does not state it for silver).
    """
    link = find_link(PINK_SHEET_PAGE, "CMO-Historical-Data-Monthly.xlsx", "worldbank.org")
    file = fetch(link, FILE_TIMEOUT, "the Pink Sheet file")
    # Row 5 of the "Monthly Prices" sheet holds the column names ("Gold", ...).
    sheet = pd.read_excel(io.BytesIO(file.content), sheet_name="Monthly Prices", header=4, engine="openpyxl")
    if column not in sheet.columns:
        raise ValueError(f"The Pink Sheet has no '{column}' column. Its layout may have changed.")

    months = sheet.iloc[:, 0].astype(str)
    # Keep only rows whose first cell is a month like "1960M01" (this drops
    # the units row and any notes).
    is_month = months.str.fullmatch(r"\d{4}M\d{2}")
    table = pd.DataFrame({
        "date": months[is_month].map(pink_date),
        "value": pd.to_numeric(sheet.loc[is_month, column], errors="coerce"),
    })
    table = table.dropna()
    table = table[table["date"] >= pd.Timestamp(PINK_SHEET_STARTS[column])]
    return table.reset_index(drop=True)


def crypto(asset: str) -> pd.DataFrame:
    """Download daily prices for one coin (for example "btc") from Coin Metrics
    and turn them into monthly averages (complete months only).

    Each value is the average of every daily price in that month.
    """
    params = {
        "assets": asset,
        "metrics": "PriceUSD",
        "frequency": "1d",
        "page_size": 10000,  # the most days Coin Metrics sends per reply
        "paging_from": "start",
    }
    rows = []
    url = COINMETRICS_URL
    # Longer histories come in several replies; each reply links to the next.
    while url:
        body = fetch(url, FILE_TIMEOUT, "Coin Metrics", params).json()
        rows += body["data"]
        url = body.get("next_page_url")
        params = None  # the next-page link already contains all the settings

    daily = pd.DataFrame(rows)
    if "PriceUSD" not in daily.columns:
        raise ValueError(f"Coin Metrics sent no PriceUSD data for '{asset}'.")
    daily = pd.DataFrame({
        "date": pd.to_datetime(daily["time"]).dt.tz_localize(None).dt.normalize(),
        "value": pd.to_numeric(daily["PriceUSD"], errors="coerce"),
    })
    return monthly_average(daily.dropna())


if __name__ == "__main__":
    # This part runs only when you type "uv run python data.py".
    # It prints the first and last 3 months of each series so you can
    # compare them with the source websites.
    import tomllib

    with open(".streamlit/secrets.toml", "rb") as f:
        key = tomllib.load(f)["FRED_API_KEY"]

    def show(name, download, *inputs):
        table, note = download_with_backup(name, download, *inputs)
        print(f"\n{name}: {len(table)} months")
        if note:
            print(f"NOTE: {note}")
        print(table.head(3).to_string(index=False))
        print("...")
        print(table.tail(3).to_string(index=False, header=False))

    show("CPIAUCNS", fred_series, "CPIAUCNS", key)
    show("AHETPI", fred_series, "AHETPI", key)
    show("CSUSHPINSA", fred_series, "CSUSHPINSA", key)
    show("SP500", sp500)
    show("GOLD", pink_sheet, "Gold")
    show("SILVER", pink_sheet, "Silver")
    for coin in ["btc", "eth", "zec", "xmr", "sol"]:
        show(coin.upper(), crypto, coin)
