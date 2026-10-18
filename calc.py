"""Calculations for the Wealth Inflation Tracker.

Every function here expects monthly data with one row per month, where each
month is stored as its first day (for example 2024-03-01 for March 2024).
The first row is always the start month.
"""

import pandas as pd

# How far the weights may be from adding up to exactly 1. Computers store
# decimals like 0.1 only approximately, so an exact check could wrongly fail.
TOLERANCE = 1e-6


def monthly_average(daily: pd.DataFrame) -> pd.DataFrame:
    """Turn daily prices (columns date, value) into monthly averages.

    Only complete months are kept: a month missing even one day is left out,
    because an average of a few days is not comparable to a full month.
    """
    daily = daily.drop_duplicates("date")  # so a repeated day can't count twice
    month = daily["date"].dt.to_period("M")
    grouped = daily.groupby(month)["value"]
    table = pd.DataFrame({"value": grouped.mean(), "days": grouped.count()})
    days_in_month = table.index.days_in_month
    table = table[table["days"] == days_in_month]
    return pd.DataFrame({
        "date": table.index.to_timestamp(),  # first day of each month
        "value": table["value"].to_numpy(),
    })


def line_up(series: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Combine several monthly tables (columns date, value) into one table.

    series: a name for each table, for example {"CPI": ..., "Bitcoin": ...}.
    Returns one row per month and one column per name, keeping only months
    where every table has a value. This one rule sets the first month, the
    last month, and skips gaps in the middle (such as October 2025 CPI).

    Dates are matched by year and month only, so 2024-01-31 and 2024-01-01
    both count as January 2024 (every series holds one value per month).
    If no month is shared, the returned table is empty.
    """
    columns = {}
    for name, table in series.items():
        values = table.set_index(table["date"].dt.to_period("M"))["value"]
        repeated = values.index[values.index.duplicated()]
        if len(repeated) > 0:
            raise ValueError(f"{name} has more than one value for {repeated[0]}.")
        columns[name] = values
    lined_up = pd.concat(columns, axis=1, sort=True).dropna()
    lined_up.index = lined_up.index.to_timestamp()  # back to the first day of each month
    lined_up.index.name = "date"
    return lined_up


INDEX_NAME = "Your asset index"


def chart_lines(lined_up: pd.DataFrame, start, weights: dict[str, int]) -> pd.DataFrame:
    """Calculate the chart's lines, all starting at 100 in the start month.

    lined_up: the table from line_up(), with CPI, the assets and, if shown,
              Wages as columns.
    start:    the start month; earlier months are left out.
    weights:  each asset's weight in whole percent, for example {"Gold": 60}.

    Returns "Your asset index", "CPI" and, only if lined_up has it, "Wages".
    (The brief has three lines; Wages is optional by the user's choice.)
    """
    data = lined_up.loc[start:]
    fractions = {name: weight / 100 for name, weight in weights.items()}
    lines = pd.DataFrame({INDEX_NAME: asset_index(data[list(fractions)], fractions)})
    for name in ["CPI", "Wages"]:
        if name in data.columns:
            lines[name] = rebase(data[name])
    return lines


def last_month_set_by(series: dict[str, pd.DataFrame]) -> list[str]:
    """Names of the series whose data ends earliest.

    These decide the last month of the chart. If several end in the same
    month, all of them are returned.
    """
    last = {name: table["date"].max().to_period("M") for name, table in series.items()}
    earliest = min(last.values())
    return [name for name, month in last.items() if month == earliest]


def rebase(values: pd.Series) -> pd.Series:
    """Rescale a series so it starts at 100: 100 × value_t / value_0.

    Used for CPI and wages.
    """
    if values.isna().any():
        raise ValueError("Some months have no value. Trim the data first.")
    start = values.iloc[0]
    if not start > 0:
        raise ValueError(f"The start value must be greater than 0, but it is {start}.")
    return 100 * values / start


def asset_index(prices: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    """Combine several assets into one index that starts at 100.

    Formula: I_t = 100 × sum of (w_i × p_i,t / p_i,0)

    prices:  one column per asset, one row per month; the first row is the
             start month.
    weights: each asset's share as a fraction, for example
             {"gold": 0.5, "bitcoin": 0.5}. Must add up to 1.
    """
    if set(weights) != set(prices.columns):
        raise ValueError(
            f"Weights are for {sorted(weights)}, but prices are for {sorted(prices.columns)}."
        )
    if any(w < 0 for w in weights.values()):
        raise ValueError("Weights cannot be negative.")
    total = sum(weights.values())
    if abs(total - 1) > TOLERANCE:
        raise ValueError(f"Weights must add up to 1 (100%), but they add up to {total}.")
    if prices.isna().any().any():
        raise ValueError("Some months have a missing price. Trim the data first.")

    start_prices = prices.iloc[0]
    if not (start_prices > 0).all():
        raise ValueError("Every start-month price must be greater than 0.")

    # Each asset's price relative to its start month (1.2 means up 20%).
    relative = prices / start_prices
    # Multiply each asset's column by its weight, add across assets, scale to 100.
    index = 100 * (relative * pd.Series(weights)).sum(axis=1)
    return index.rename("asset_index")
