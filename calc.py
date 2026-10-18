"""Calculations for the Wealth Inflation Tracker.

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


def power_of_ten_ticks(low: float, high: float) -> tuple[list[float], list[str]]:
    """Axis labels at every power of 10 from below low to above high.

    For example 55 to 10,031.9 gives 10, 100, 1k, 10k, 100k. Large values use
    k (thousand), M (million), B (billion) and T (trillion).
    """
    suffixes = {0: "", 3: "k", 6: "M", 9: "B", 12: "T"}
    values, labels = [], []
    for exponent in range(math.floor(math.log10(low)), math.ceil(math.log10(high)) + 1):
        values.append(10.0 ** exponent)
        if exponent < 3:
            labels.append(f"{10.0 ** exponent:g}")  # 0.1, 1, 10, 100
        else:
            group = min(exponent // 3 * 3, 12)
            labels.append(f"{10 ** (exponent - group)}{suffixes[group]}")  # 1k, 10k, 100k, 1M
    return values, labels


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
    an asset has no data that far back.
    """
    available = prices.dropna().index.intersection(cpi.dropna().index)
    fractions = {name: weight / 100 for name, weight in weights.items()}
    rates = {"basket": {}, "CPI": {}}
    for period in years:
        target = end - pd.DateOffset(years=period)
        candidates = available[available <= target]
        if len(candidates) == 0:
            rates["basket"][period] = rates["CPI"][period] = None
            continue
        start = candidates.max()
        months = months_between(start, end)
        index = asset_index(prices.loc[[start, end], list(fractions)], fractions)
        rates["basket"][period] = per_year(index.iloc[0], index.iloc[-1], months)
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
