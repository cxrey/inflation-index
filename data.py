"""Download price data from each source.

Every function returns a table (pandas DataFrame) with two columns:
    date  - the month, stored as its first day (for example 2024-03-01)
    value - the price or index value for that month
"""

import pandas as pd
from fredapi import Fred


def fred_series(series_id: str, api_key: str) -> pd.DataFrame:
    """Download one monthly series from FRED, for example "CPIAUCNS"."""
    values = Fred(api_key=api_key).get_series(series_id)
    table = pd.DataFrame({"date": values.index, "value": values.to_numpy()})
    # FRED marks months with no value as missing; drop them.
    return table.dropna().reset_index(drop=True)


if __name__ == "__main__":
    # This part runs only when you type "uv run python data.py".
    # It prints the first and last 3 months of each series so you can
    # compare them with the FRED website.
    import tomllib

    with open(".streamlit/secrets.toml", "rb") as f:
        key = tomllib.load(f)["FRED_API_KEY"]

    for name, series_id in [
        ("CPI", "CPIAUCNS"),
        ("Wages", "AHETPI"),
        ("US home prices", "CSUSHPINSA"),
    ]:
        table = fred_series(series_id, key)
        print(f"\n{name} ({series_id}): {len(table)} months")
        print(table.head(3).to_string(index=False))
        print("...")
        print(table.tail(3).to_string(index=False, header=False))
