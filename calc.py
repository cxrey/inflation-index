"""Calculations for the Asset Inflation Tracker.

Every function here expects monthly data with one row per month, where each
month is stored as its first day (for example 2024-03-01 for March 2024).
The first row is always the start month.
"""

import math

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


INDEX_NAME = "Your asset index"  # the basket's line in the chart and tables


def asset_lines(lined_up: pd.DataFrame, start, weights: dict[str, int]) -> pd.DataFrame:
    """One line per selected asset, each starting at 100 in the start month.

    Used for the optional "Show individual assets" lines on the chart.
    """
    data = lined_up.loc[start:]
    return pd.DataFrame({name: rebase(data[name]) for name in weights})


def current_weights(lined_up: pd.DataFrame, start, weights: dict[str, int]) -> pd.Series:
    """Each asset's share of the index in the last month, in percent.

    The index buys and holds, so an asset that rises faster becomes a bigger
    share: share_i = w_i × (p_i,now / p_i,start), divided by the same summed
    over all assets. Example: A and B at 50% each, A up 20% and B up 10%:
    A = 0.6 / 1.15 = 52.17%, B = 0.55 / 1.15 = 47.83%.
    """
    data = lined_up.loc[start:]
    held = pd.Series({
        name: weight / 100 * data[name].iloc[-1] / data[name].iloc[0]
        for name, weight in weights.items()
    })
    return 100 * held / held.sum()


BITCOIN_RELIABLE_FROM = pd.Timestamp("2013-01-01")


def needs_bitcoin_note(weights: dict[str, int], start) -> bool:
    """True when Bitcoin is selected and the chart starts before 2013.

    Bitcoin prices from 2010-2012 come from very thin trading, so the page
    shows a note about them.
    """
    return "Bitcoin" in weights and start < BITCOIN_RELIABLE_FROM


def valid_months(basket: dict[str, pd.DataFrame], cpi: pd.DataFrame) -> list[pd.Timestamp]:
    """The months the chart can start and end in.

    Only the basket's assets (those above 0%) and CPI decide them: a month
    counts if every one of them has a value. Wages and money supply never
    limit the dates. With no basket asset above 0%, CPI alone decides.
    """
    return list(line_up({**basket, "CPI": cpi}).index)


def comparison_line(name: str, table: pd.DataFrame, start, end) -> tuple[pd.Series | None, str | None]:
    """A comparison line (CPI, wages, money supply) from start to end, starting at 100.

    Every month from start to end is included, so a missing month shows as a
    break in the line (such as October 2025 CPI) and a line whose data ends
    early simply stops. If the line has no value in the start month, it is
    not drawn: the result is (None, a note such as "Wages data starts in
    January 1964.").
    """
    values = table.set_index(table["date"].dt.to_period("M").dt.to_timestamp())["value"]
    if start not in values.index:
        first = values.index.min()
        if first > start:
            return None, f"{name} data starts in {first:%B %Y}."
        return None, f"{name} has no value for {start:%B %Y}."
    months = pd.date_range(start, end, freq="MS")
    return 100 * values.reindex(months) / values[start], None


def percent_ticks(low: float, high: float) -> tuple[list[float], list[str]]:
    """Log-axis labels as % change, for lines drawn as levels where 100 = the start.

    A level of 10 is -90%, 100 is 0%, 1,000 is +900%. Labels go at every power
    of 10 from below `low` to above `high`; when the chart spans 3 powers of
    ten or fewer, -50% (level 50) and +100% (level 200) are added too.
    Example: 60 to 1,000 -> -90%, -50%, 0%, +100%, +900%.
    """
    first, last = math.floor(math.log10(low)), math.ceil(math.log10(high))
    levels = [10.0 ** exponent for exponent in range(first, last + 1)]
    if last - first <= 3:
        levels = sorted(levels + [50.0, 200.0])
    labels = []
    for level in levels:
        change = level - 100
        # Below a level of 1, more decimals are needed: 0.1 -> -99.9%, 0.01 -> -99.99%.
        decimals = max(0, -math.floor(math.log10(level)))
        labels.append("0%" if change == 0 else f"{change:+,.{decimals}f}%")
    return levels, labels


def months_between(start: pd.Timestamp, end: pd.Timestamp) -> int:
    """Calendar months from start to end: January 2024 to January 2026 is 24.

    Counted from the dates, not from table rows, so a skipped month (such as
    October 2025) does not make the period look shorter.
    """
    return (end.year - start.year) * 12 + (end.month - start.month)


def change_table(lines: pd.DataFrame) -> pd.DataFrame:
    """Total and yearly % change of each line, from its first to its last month.

    Total change  = (end / start - 1) × 100
    Yearly change = ((end / start) ^ (12 / months) - 1) × 100, the steady
                    yearly rate giving the same total. Left empty (missing)
                    when the period is shorter than 12 months, because
                    turning a short period into a yearly rate exaggerates it.
    """
    rows = {}
    for name in lines.columns:
        # Each line from its first to its last value: a line may stop early
        # (money supply ends a month before CPI) or have gaps (October 2025 CPI).
        values = lines[name].dropna()
        months = months_between(values.index[0], values.index[-1])
        growth = values.iloc[-1] / values.iloc[0]
        rows[name] = {
            "Total change": (growth - 1) * 100,
            "Yearly change": (growth ** (12 / months) - 1) * 100 if months >= 12 else None,
        }
    return pd.DataFrame.from_dict(rows, orient="index")


def summary_table(lines: pd.DataFrame) -> pd.DataFrame:
    """Total change, change per year and worst drop of each line, all in %.

    Each line is measured from its first to its last value (see change_table).
    Worst drop: the biggest fall from a previous high, 100, 150, 75, 120 -> -50%.
    """
    table = change_table(lines).rename(columns={"Yearly change": "Change per year"})
    table["Worst drop"] = [100 * worst_drop(lines[name].dropna()) for name in table.index]
    return table


def percent_text(value: float, show_multiple: bool = False) -> str:
    """Write a % change for the table.

    Under 1,000%: two decimals, for example +990.42% or -19.00%.
    1,000% or more: no decimals, and with show_multiple the multiple of the
    start value, for example +24,755,848% (247,559×). The multiple is
    1 + change / 100; it gets one decimal below 100× (+1,000% is 11.0×).
    No value (yearly change for a short period): a dash.
    """
    if pd.isna(value):
        return "—"
    if abs(round(value, 2)) < 1000:
        return f"{value:+,.2f}%"
    text = f"{value:+,.0f}%"
    if show_multiple:
        multiple = 1 + value / 100
        text += f" ({multiple:,.0f}×)" if multiple >= 100 else f" ({multiple:,.1f}×)"
    return text


# --- Version 1.2: rates, cash buying power and weight buttons ---
# These functions use fractions for rates: 0.10 means 10% per year.


def per_year(start_value: float, end_value: float, months: int) -> float | None:
    """How much a line changed per year: (end / start) ^ (12 / months) - 1.

    None (shown as "—") when the period is shorter than 12 months.
    Example: 100 -> 121 over 24 months is 0.10 (10% per year).
    """
    if months < 12:
        return None
    return (end_value / start_value) ** (12 / months) - 1


def cash_loss_per_year(basket_rate: float) -> float:
    """Share of buying power cash loses per year against a rising basket.

    1 - 1 / (1 + rate). Basket up 25% per year: cash loses 20% per year.
    A negative result means cash gains (basket falling 10%: gains 1/9).
    """
    return 1 - 1 / (1 + basket_rate)


def rate_versus(your_rate: float, other_rate: float) -> float:
    """Your money's change in buying power per year: (1 + yours) / (1 + other) - 1.

    Your rate 4%, basket 30%: (1.04 / 1.30) - 1 = -0.20 (you lose 20% per year).
    """
    return (1 + your_rate) / (1 + other_rate) - 1


def change_since_start(values: pd.Series) -> pd.Series:
    """% change of each month since the first month: 100, 150 -> 0%, +50%."""
    return 100 * (values / values.iloc[0] - 1)


def cash_line(values: pd.Series) -> pd.Series:
    """% change in how much cash buys, month by month: 100 × V_start / V_now - 100.

    With CPI it is cash in consumer goods (CPI 100 -> 125 gives -20%); with the
    basket index it is cash in your basket (100 -> 1,000 gives -90%).
    """
    return 100 * values.iloc[0] / values - 100


def worst_drop(values: pd.Series) -> float:
    """Worst drop from a previous high, as a fraction: min(V / highest so far - 1).

    100, 150, 75, 120 -> 75 / 150 - 1 = -0.50.
    """
    return (values / values.cummax() - 1).min()


def basket_and_total(checked: dict[str, float]) -> tuple[dict[str, float], float]:
    """From the checked assets' weights (in %), the basket and the total.

    The basket is only the assets above 0%; the total adds all checked
    weights. 50/50/0 -> basket of 2, total 100. Weights must total 100%
    (see weights_add_up) for basket results to be shown.
    """
    basket = {name: weight for name, weight in checked.items() if weight > 0}
    return basket, sum(checked.values())


def weights_add_up(total: float) -> bool:
    """True when the weights total 100% (allowing for tiny rounding, like 3 × 100/3)."""
    return abs(total - 100) < TOLERANCE * 100


def make_100(weights: dict[str, float], target: float = 100) -> dict[str, float]:
    """Scale weights to add up to `target` % (100 unless given), keeping their proportions.

    50/30/10 (total 90) -> 500/9, 100/3, 100/9. A section made into 20%:
    10/30 -> 5/15. If the weights add up to 0, nothing can be scaled, so they
    are returned unchanged.
    """
    total = sum(weights.values())
    if total == 0:
        return dict(weights)
    return {name: weight * target / total for name, weight in weights.items()}


def split_evenly(names: list[str], target: float = 100) -> dict[str, float]:
    """Give every name an equal share of `target` % (100 unless given).

    3 assets -> 100/3 each; a section of 4 assets split to 40% -> 10 each.
    """
    return {name: target / len(names) for name in names} if names else {}


def set_section_total(weights: dict[str, float], target: float) -> dict[str, float]:
    """New weights for a section so they add up to `target` %.

    The assets keep their proportions (10/30 set to 20 -> 5/15); if they are
    all at 0%, they share the target equally (0/0 set to 40 -> 20/20).
    """
    if sum(weights.values()) == 0:
        return split_evenly(list(weights), target)
    return make_100(weights, target)


def split_categories(categories: dict[str, dict[str, float]]) -> dict[str, float]:
    """Give every category that has a checked asset an equal share of 100%.

    categories: each category's checked assets and their current weights,
    for example {"Equities": {"S&P 500": 100}, "Commodities": {"Gold": 0}}.
    Categories with nothing checked are left out. Inside a category, the
    assets keep their current proportions; if they are all at 0%, they
    split the category's share equally. The example gives S&P 500 50, Gold 50.
    """
    used = [assets for assets in categories.values() if assets]
    if not used:
        return {}
    share = 100 / len(used)
    result = {}
    for assets in used:
        result.update(set_section_total(assets, share))
    return result


# --- The main result sentences (rates are fractions: 0.10 = 10%) ---


def rate_text(rate: float) -> str:
    """A rate as a % without its sign: 0.0763 -> "7.63%", -0.10 -> "10.00%",
    and from 1,000% without decimals: 12.345 -> "1,235%"."""
    percent = abs(rate) * 100
    return f"{percent:,.0f}%" if round(percent, 2) >= 1000 else f"{percent:,.2f}%"


def is_zero(rate: float) -> bool:
    """True when a rate would show as 0.00%, so "exactly 0" matches what is shown."""
    return round(rate * 100, 2) == 0


def your_rate_text(your_rate: float) -> str:
    """The rate the user typed, as typed: 0.04 -> "4%", 0.045 -> "4.5%", -0.02 -> "-2%"."""
    return f"{your_rate * 100:.2f}".rstrip("0").rstrip(".") + "%"


def basket_sentences(rate: float | None, start, end) -> list[str]:
    """The basket's main result: how fast its prices changed, and what that did to cash.

    No sentences when the rate is "—" (period under 12 months). Rising:
    "rose ... Cash lost ...". Falling: "fell ... Cash gained ...". Flat: only
    "didn't change (0% per year)".
    """
    if rate is None:
        return []
    if is_zero(rate):
        return ["Your basket's prices didn't change (0% per year)."]
    cash = cash_loss_per_year(rate)
    return [
        f"Your basket's prices {'rose' if rate > 0 else 'fell'} {rate_text(rate)} per year "
        f"({start:%B %Y} to {end:%B %Y}).",
        f"Cash {'lost' if cash > 0 else 'gained'} {rate_text(cash)} of its buying power "
        f"against your basket per year.",
    ]


def cpi_sentence(rate: float | None) -> str | None:
    """'Official inflation (CPI): 3.16% per year.' (a minus sign when prices fell)."""
    if rate is None:
        return None
    return f"Official inflation (CPI): {'-' if rate < 0 and not is_zero(rate) else ''}{rate_text(rate)} per year."


def keep_up_sentence(rate: float | None) -> str | None:
    """Shown only when the basket's prices rose."""
    if rate is None or rate <= 0 or is_zero(rate):
        return None
    return f"To keep up with your basket, your money must grow at least {rate_text(rate)} per year."


def buying_power_phrase(change: float, where: str) -> str:
    """'lose 20.00% of your buying power <where>', 'gain ...', or 'keep the same buying power'."""
    if is_zero(change):
        return "keep the same buying power"
    return f"{'lose' if change < 0 else 'gain'} {rate_text(change)} of your buying power {where}"


def your_rate_sentences(your_rate: float, basket_rate: float | None, cpi_rate: float | None) -> list[str]:
    """What the user's own rate (for example 4% in savings) means against the basket and CPI.

    A sentence is left out when the rate it depends on is "—".
    """
    sentences = []
    shown = your_rate_text(your_rate)
    if basket_rate is not None:
        phrase = buying_power_phrase(rate_versus(your_rate, basket_rate), "in your basket")
        sentences.append(
            f"If basket prices keep changing at their past rate, at {shown} per year "
            f"you'd {phrase} each year."
        )
    if cpi_rate is not None:
        phrase = buying_power_phrase(rate_versus(your_rate, cpi_rate), "at the store")
        sentences.append(f"Against CPI, at {shown} per year you'd {phrase} each year.")
    return sentences


def period_rates(prices: pd.DataFrame, cpi: pd.Series, weights: dict[str, float], end,
                 years=(1, 3, 5, 10, 20)) -> dict[str, dict[int, float | None]]:
    """Basket and CPI per year over the last 1, 3, 5, 10 and 20 years to `end`.

    Each period is calculated fresh: the basket restarts with `weights` (in %)
    at the period's start. The start is the same month `years` earlier; if
    that month has no data for every asset and CPI (such as October 2025),
    the month before is used with its true length. None (shown as "—") when
    an asset has no data that far back. With no basket (weights empty, for
    example while they don't add up to 100%), only CPI is calculated.
    """
    fractions = {name: weight / 100 for name, weight in weights.items()}
    available = cpi.dropna().index
    if fractions:
        available = prices.dropna().index.intersection(available)
    rates = {"basket": {}, "CPI": {}}
    for period in years:
        target = end - pd.DateOffset(years=period)
        candidates = available[available <= target]
        if len(candidates) == 0:
            rates["basket"][period] = rates["CPI"][period] = None
            continue
        start = candidates.max()
        months = months_between(start, end)
        if fractions:
            index = asset_index(prices.loc[[start, end], list(fractions)], fractions)
            rates["basket"][period] = per_year(index.iloc[0], index.iloc[-1], months)
        else:
            rates["basket"][period] = None
        rates["CPI"][period] = per_year(cpi[start], cpi[end], months)
    return rates


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


# --- Market size (for the "Weight by market size" button) ---
# Market values are in US dollars. A table has columns date, value; a year-end
# value is dated December of that year, a FRED quarter by its first month.

OUNCES_PER_TONNE = 32_150.7466  # troy ounces in one metric ton
DOLLARS_PER_MILLION = 1_000_000  # FRED's market values are in millions of dollars

# Why an asset gets 0% from the market-size button.
NO_DATA_REASON = "no market-size data for this date."
SILVER_PLATINUM_REASON = "no reliable estimate of how much exists above ground."


def value_at(table: pd.DataFrame, month) -> float | None:
    """The table's value in `month`, or None if it has none."""
    values = table.set_index("date")["value"]
    return float(values[month]) if month in values.index else None


def latest_at_or_before(table: pd.DataFrame, month) -> tuple[pd.Timestamp, float] | None:
    """The table's latest (date, value) at or before `month`, or None."""
    earlier = table[table["date"] <= month]
    if earlier.empty:
        return None
    row = earlier.loc[earlier["date"].idxmax()]
    return row["date"], float(row["value"])


def move_to_start(value: float, price_at_start: float, price_then: float) -> float:
    """Move a market value from its own date to the start month by the asset's
    price change: 100 with the price 10% higher at the start month -> 110."""
    return value * price_at_start / price_then


def stock_market_value(start, year_end_values: pd.DataFrame, sp500: pd.DataFrame) -> float | None:
    """US stocks: the latest year-end value (World Bank, dated December) at or
    before the start month, moved to it by the S&P 500's price change.
    None before December 1975, the first year-end."""
    latest = latest_at_or_before(year_end_values, start)
    if latest is None:
        return None
    month, value = latest
    price_at_start, price_then = value_at(sp500, start), value_at(sp500, month)
    if price_at_start is None or price_then is None:
        return None
    return move_to_start(value, price_at_start, price_then)


def home_market_value(start, quarterly_millions: pd.DataFrame, home_prices: pd.DataFrame) -> float | None:
    """US homes: the latest quarter-end value at or before the start month (FRED,
    in millions; a quarter dated by its first month ends two months later),
    moved to the start month by the home price index's change."""
    quarter_ends = quarterly_millions.assign(date=quarterly_millions["date"] + pd.DateOffset(months=2))
    latest = latest_at_or_before(quarter_ends, start)
    if latest is None:
        return None
    month, millions = latest
    price_at_start, price_then = value_at(home_prices, start), value_at(home_prices, month)
    if price_at_start is None or price_then is None:
        return None
    return move_to_start(millions * DOLLARS_PER_MILLION, price_at_start, price_then)


def crypto_market_value(start, monthly_caps: pd.DataFrame) -> float | None:
    """A coin: its average market cap in the start month (None if there is none)."""
    return value_at(monthly_caps, start)


def gold_stock_table(production: dict[int, float], anchor_tonnes: float, anchor_date,
                     first_price_month) -> dict[int, float]:
    """The world's above-ground gold stock at each year-end, in tonnes.

    Let Y be the latest year of mine production. For year-ends from Y up to the
    anchor date: anchor - production in Y × (months from that year-end to the
    anchor) / 12. Before Y: end of the previous year = end of this year minus
    this year's production, back to the year-end before the first price month.
    Example: anchor 222,600 t at 30 June 2026, Y = 2025 with 3,600 t:
    end-2025 = 222,600 - 3,600 × 6/12 = 220,800 t.
    """
    latest_year = max(production)
    stocks = {}
    for year in range(latest_year, anchor_date.year):
        months = (anchor_date.year - year) * 12 + (anchor_date.month - 12)
        stocks[year] = anchor_tonnes - production[latest_year] * months / 12
    for year in range(latest_year, first_price_month.year - 1, -1):
        stocks[year - 1] = stocks[year] - production[year]
    return dict(sorted(stocks.items()))


def investment_gold(stock_tonnes: float, investment_tonnes: float, anchor_tonnes: float) -> float:
    """Investment gold (bars and coins, ETFs, central banks) in a year's stock,
    using today's share for every year: 222,600 t -> 90,800 t."""
    return stock_tonnes * investment_tonnes / anchor_tonnes


def gold_market_value(start, investment_by_year_end: dict[int, float], gold_prices: pd.DataFrame) -> float | None:
    """Gold: investment tonnes at the latest year-end at or before the start month
    (a year-end counts as December) × ounces per tonne × the start month's price."""
    years = [year for year in investment_by_year_end if pd.Timestamp(year=year, month=12, day=1) <= start]
    price = value_at(gold_prices, start)
    if not years or price is None:
        return None
    return investment_by_year_end[max(years)] * OUNCES_PER_TONNE * price


def market_size_weights(checked: list[str], market_values: dict[str, float | None]) -> tuple[dict[str, float], dict[str, str]]:
    """Weights (in %) proportional to each checked asset's market value, and the
    reason for every asset set to 0%.

    market_values: the market value in dollars of each asset that has a market
    size at all (stocks, homes, gold, crypto); None means no data for this date.
    """
    reasons = {}
    for asset in checked:
        if asset == "Nasdaq":
            reasons[asset] = (
                "already included in the S&P 500 row, which stands for the whole US stock market."
                if "S&P 500" in checked else
                "no separate market-size data; check S&P 500 to include US stocks."
            )
        elif asset.startswith("Luxury homes"):
            reasons[asset] = (
                "already included in US home prices."
                if "US home prices" in checked else
                "no market-size data for individual cities; check US home prices to include US homes."
            )
        elif asset in ("Silver", "Platinum"):
            reasons[asset] = SILVER_PLATINUM_REASON
        elif market_values.get(asset) is None:
            reasons[asset] = NO_DATA_REASON
    sized = {asset: market_values[asset] for asset in checked if asset not in reasons}
    total = sum(sized.values())
    weights = {asset: (100 * sized[asset] / total if asset in sized else 0.0) for asset in checked}
    return weights, reasons
