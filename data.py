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
    Nasdaq (NASDAQCOM)      average of the month's daily closes, calculated
                            by FRED (complete months only)
    Platinum (Pink Sheet)   average of daily rates, like gold
    Home prices (CSUSHPINSA) NOT an average of daily prices: Case-Shiller is
                            a three-month moving average of repeat home sales
                            (the "July" value covers May, June and July)
    Luxury homes (..XRHTNSA) same method as home prices, for the "high tier"
                            (the most expensive third of homes sold) of one city
    Comparison lines:
    CPI (CPIAUCNS)          prices collected throughout the month
    Wages (AHETPI)          average hourly earnings for the pay period that
                            includes the 12th of the month
    Money supply (M2SL)     the amount of M2 money in the month (seasonally
                            adjusted); a comparison line only
    Market size (only for the "Weight by market size" button):
    US stocks (World Bank)  value of US-listed domestic companies, year-end, $
    US homes (HNOREMQ027S)  households' and nonprofits' real estate at market
                            value, quarter-end, millions of $
    Crypto market caps      monthly average of daily market caps, $
    Gold                    a yearly stock table built from one World Gold
                            Council figure and USGS mine production (below)
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
WORLD_BANK_URL = "https://api.worldbank.org/v2/country/USA/indicator/CM.MKT.LCAP.CD"
SHILLER_PAGE = "https://shillerdata.com/"
PINK_SHEET_PAGE = "https://www.worldbank.org/en/research/commodity-markets"
# First month used for each Pink Sheet column (earlier prices were not set by
# a free market: gold was fixed, silver was held down by the US Treasury).
PINK_SHEET_STARTS = {"Gold": "1971-01-01", "Silver": "1968-01-01", "Platinum": "1960-01-01"}
# Luxury homes: Case-Shiller high-tier index for each city, in menu order.
LUXURY_CITIES = {
    "San Francisco": "SFXRHTNSA",
    "Los Angeles": "LXXRHTNSA",
    "San Diego": "SDXRHTNSA",
    "New York": "NYXRHTNSA",
    "Seattle": "SEXRHTNSA",
    "Boston": "BOXRHTNSA",
    "Washington DC": "WDXRHTNSA",
    "Miami": "MIXRHTNSA",
    "Chicago": "CHXRHTNSA",
}

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


def fred_series(series_id: str, api_key: str, monthly_average: bool = False) -> pd.DataFrame:
    """Download one monthly series from FRED, for example "CPIAUCNS".

    monthly_average: for daily series (such as NASDAQCOM), ask FRED for the
    average of each month. FRED leaves incomplete months empty; they are
    dropped like any other empty month.
    See the top of this file for what one monthly value is for each series.
    """
    params = {"series_id": series_id, "api_key": api_key, "file_type": "json"}
    if monthly_average:
        params.update({"frequency": "m", "aggregation_method": "avg"})
    observations = fetch(FRED_URL, FILE_TIMEOUT, "FRED", params).json()["observations"]
    table = pd.DataFrame(observations)[["date", "value"]]
    table["date"] = pd.to_datetime(table["date"])
    # FRED writes "." for months with no value; turn those into missing and drop them.
    table["value"] = pd.to_numeric(table["value"], errors="coerce")
    return table.dropna().reset_index(drop=True)


def fred_monthly_average(series_id: str, api_key: str) -> pd.DataFrame:
    """A daily FRED series (such as NASDAQCOM) as monthly averages."""
    return fred_series(series_id, api_key, monthly_average=True)


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


def crypto(asset: str, metric: str = "PriceUSD") -> pd.DataFrame:
    """Download a daily Coin Metrics series for one coin (for example "btc")
    and turn it into monthly averages (complete months only).

    metric: "PriceUSD" (the price, the default) or a market cap, see
    crypto_market_cap. Each value is the average of every day in that month.
    """
    params = {
        "assets": asset,
        "metrics": metric,
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
    if metric not in daily.columns:
        raise ValueError(f"Coin Metrics sent no {metric} data for '{asset}'.")
    daily = pd.DataFrame({
        "date": pd.to_datetime(daily["time"]).dt.tz_localize(None).dt.normalize(),
        "value": pd.to_numeric(daily[metric], errors="coerce"),
    })
    return monthly_average(daily.dropna())


# --- Market size (for the "Weight by market size" button) ---

def crypto_market_cap(asset: str) -> pd.DataFrame:
    """A coin's market cap in US dollars, as monthly averages (complete months only).

    The exact market cap (CapMrktCurUSD) from each coin's first day; Solana's
    exact figure isn't on Coin Metrics' free service, so its estimate
    (CapMrktEstUSD, from 11 April 2020) is used instead.
    """
    return crypto(asset, "CapMrktEstUSD" if asset == "sol" else "CapMrktCurUSD")


def world_bank_us_market_cap() -> pd.DataFrame:
    """Total value of US companies listed on US exchanges, in US dollars, at
    each year-end (World Bank indicator CM.MKT.LCAP.CD, from the World
    Federation of Exchanges; licence CC BY 4.0). Dated December of each year.
    """
    params = {"format": "json", "per_page": 1000}
    body = fetch(WORLD_BANK_URL, FILE_TIMEOUT, "the World Bank", params).json()
    if len(body) < 2 or not body[1]:
        raise ValueError("The World Bank sent no market-capitalization data.")
    table = pd.DataFrame({
        "date": [pd.Timestamp(year=int(row["date"]), month=12, day=1) for row in body[1]],
        "value": pd.to_numeric([row["value"] for row in body[1]], errors="coerce"),
    })
    return table.dropna().sort_values("date").reset_index(drop=True)


# Gold: the world's above-ground stock is built from two public sources.
# 1. One figure from the World Gold Council (Goldhub, "Above-ground stocks",
#    https://www.gold.org/goldhub/data/above-ground-stocks): 222,600 tonnes in
#    total at 30 June 2026, of which investment gold (bars and coins ~47,800 t,
#    ETFs ~4,000 t, central banks ~39,000 t) is about 90,800 t. Only this one
#    figure is used; no WGC data is downloaded.
GOLD_STOCK_ANCHOR_TONNES = 222_600
GOLD_STOCK_ANCHOR_DATE = pd.Timestamp("2026-06-30")
GOLD_INVESTMENT_TONNES = 90_800  # bars and coins + ETFs + central banks
# 2. World gold mine production in tonnes (public domain, U.S. Geological Survey):
#    1971-2022 from "Historical Statistics for Mineral and Material Commodities
#    in the United States" (Data Series 140, gold, world production column);
#    2023 from Mineral Commodity Summaries 2025; 2024 and 2025 (estimated) from
#    Mineral Commodity Summaries 2026, the latest edition.
GOLD_WORLD_PRODUCTION_TONNES = {
    1971: 1450, 1972: 1390, 1973: 1350, 1974: 1250, 1975: 1200, 1976: 1210,
    1977: 1210, 1978: 1210, 1979: 1210, 1980: 1220, 1981: 1280, 1982: 1340,
    1983: 1400, 1984: 1460, 1985: 1530, 1986: 1610, 1987: 1660, 1988: 1870,
    1989: 2010, 1990: 2180, 1991: 2160, 1992: 2260, 1993: 2280, 1994: 2260,
    1995: 2230, 1996: 2290, 1997: 2450, 1998: 2500, 1999: 2570, 2000: 2590,
    2001: 2600, 2002: 2550, 2003: 2540, 2004: 2420, 2005: 2470, 2006: 2370,
    2007: 2350, 2008: 2300, 2009: 2490, 2010: 2590, 2011: 2680, 2012: 2740,
    2013: 2960, 2014: 3040, 2015: 3100, 2016: 3180, 2017: 3260, 2018: 3310,
    2019: 3260, 2020: 3050, 2021: 3120, 2022: 3160,
    2023: 3250,  # Mineral Commodity Summaries 2025
    2024: 3280, 2025: 3300,  # Mineral Commodity Summaries 2026 (2025 estimated)
}


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
    show("PLATINUM", pink_sheet, "Platinum")
    show("NASDAQCOM", fred_series, "NASDAQCOM", key, True)
    show("M2SL", fred_series, "M2SL", key)
    for city, series_id in LUXURY_CITIES.items():
        table, note = download_with_backup(f"LUX_{series_id}", fred_series, series_id, key)
        first, last = table.iloc[0], table.iloc[-1]
        print(f"Luxury homes, {city} ({series_id}): {len(table)} months, "
              f"{first.date:%Y-%m} {first.value} to {last.date:%Y-%m} {last.value}" + (f"  NOTE: {note}" if note else ""))
    for coin in ["btc", "eth", "zec", "xmr", "sol"]:
        show(coin.upper(), crypto, coin)

    # Market size: US stocks (World Bank), US homes (FRED), crypto market caps.
    show("US_MARKET_CAP", world_bank_us_market_cap)
    show("HNOREMQ027S", fred_series, "HNOREMQ027S", key)
    for coin in ["btc", "eth", "zec", "xmr", "sol"]:
        show(f"CAP_{coin.upper()}", crypto_market_cap, coin)
    years = sorted(GOLD_WORLD_PRODUCTION_TONNES)
    print(f"\nGold production table: {len(years)} years, {years[0]}-{years[-1]}, "
          f"total {sum(GOLD_WORLD_PRODUCTION_TONNES.values()):,} t")
