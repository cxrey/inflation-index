"""Download price data from each source.

Every download function returns a table (pandas DataFrame) with two columns:
    date  - the month, stored as its first day (for example 2024-03-01)
    value - the price or index value for that month

download_with_backup() wraps any of them: it retries temporary failures,
saves each successful download, and falls back to the saved copy.
"""

import html
import io
import re
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

FRED_URL = "https://api.stlouisfed.org/fred/series/observations"
SHILLER_PAGE = "https://shillerdata.com/"

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


def download_with_backup(name, download, *inputs, folder=SAVED_DATA, wait_seconds=WAIT_SECONDS):
    """Run download(*inputs), retrying temporary failures and keeping a backup.

    Returns (table, note). note is None when the data is fresh; otherwise it
    explains that the saved copy is being shown, and why.
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
        f"{name} could not be downloaded ({problem}). "
        f"Showing the copy saved on {saved_on} (latest month: {latest})."
    )
    return saved, note


def fred_series(series_id: str, api_key: str) -> pd.DataFrame:
    """Download one monthly series from FRED, for example "CPIAUCNS"."""
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
    """Download the S&P Composite price ("P" column) from Shiller's spreadsheet."""
    # The download link contains a version number that changes when the file
    # is updated, so find the current link on the web page each time.
    page = fetch(SHILLER_PAGE, PAGE_TIMEOUT, "shillerdata.com")
    match = re.search(r'href="([^"]*ie_data\.xls[^"]*)"', page.text)
    if match is None:
        raise ValueError(f"Could not find the ie_data.xls link on {SHILLER_PAGE}. The website may have changed.")
    link = html.unescape(match.group(1))
    if link.startswith("//"):
        link = "https:" + link

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
