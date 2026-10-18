"""Tests for the version 1.2 math in calc.py, using numbers you can check by hand.

Rates are fractions: 0.10 means 10% per year.
"""

import pandas as pd
import pytest

from calc import (
    basket_and_total,
    cash_line,
    cash_loss_per_year,
    change_since_start,
    make_100,
    per_year,
    period_rates,
    rate_versus,
    set_section_total,
    split_categories,
    split_evenly,
    weights_add_up,
    worst_drop,
)


def test_per_year():
    # 100 -> 121 over 24 months: 1.21 ^ (12 / 24) = 1.10, so 10% per year.
    assert per_year(100, 121, 24) == pytest.approx(0.10, abs=1e-9)
    # Falling: 100 -> 81 over 24 months: 0.81 ^ 0.5 = 0.90, so -10% per year.
    assert per_year(100, 81, 24) == pytest.approx(-0.10, abs=1e-9)
    # Flat: 0% per year.
    assert per_year(100, 100, 24) == pytest.approx(0, abs=1e-9)
    # Under 12 months: no per-year rate ("—").
    assert per_year(100, 120, 11) is None


def test_cash_loss_per_year():
    # Basket rising 25% per year: 1 - 1 / 1.25 = 0.20, cash loses 20%.
    assert cash_loss_per_year(0.25) == pytest.approx(0.20, abs=1e-9)
    # Basket falling 10% per year: 1 - 1 / 0.9 = -1/9, cash gains about 11.1%.
    assert cash_loss_per_year(-0.10) == pytest.approx(-1 / 9, abs=1e-9)


def test_rate_versus():
    # Your rate 4%, basket 30%: 1.04 / 1.30 - 1 = -0.20 ("lose 20%").
    assert rate_versus(0.04, 0.30) == pytest.approx(-0.20, abs=1e-9)
    # Your rate 10%, basket 10%: 0 ("keep the same buying power").
    assert rate_versus(0.10, 0.10) == pytest.approx(0, abs=1e-9)


def test_change_since_start():
    assert change_since_start(pd.Series([100, 150, 80])).tolist() == pytest.approx([0, 50, -20], abs=1e-9)


def test_cash_lines():
    # Cash in consumer goods: CPI 100 -> 125, cash buys 100/125 = 80%: -20%.
    assert cash_line(pd.Series([100, 125])).tolist() == pytest.approx([0, -20], abs=1e-9)
    # Cash in your basket: basket 100 -> 1,000, cash buys 10%: -90%.
    assert cash_line(pd.Series([100, 1000])).tolist() == pytest.approx([0, -90], abs=1e-9)


def test_worst_drop():
    # 100, 150, 75, 120: the worst is 75 after the high of 150, 75/150 - 1 = -50%.
    assert worst_drop(pd.Series([100, 150, 75, 120])) == pytest.approx(-0.50, abs=1e-9)


def test_make_100():
    # 50/30/10 (total 90) scaled to 100: 500/9, 100/3, 100/9.
    scaled = make_100({"A": 50, "B": 30, "C": 10})
    assert list(scaled.values()) == pytest.approx([500 / 9, 100 / 3, 100 / 9], abs=1e-9)
    assert sum(scaled.values()) == pytest.approx(100, abs=1e-9)
    # Nothing to scale when every weight is 0.
    assert make_100({"A": 0, "B": 0}) == {"A": 0, "B": 0}


def test_split_evenly():
    assert list(split_evenly(["A", "B", "C"]).values()) == pytest.approx([100 / 3] * 3, abs=1e-9)
    assert split_evenly([]) == {}


def test_section_buttons():
    # Real estate set to 40%, split among US home prices and 3 cities: 10% each.
    split = split_evenly(["US home prices", "New York", "Boston", "Washington DC"], 40)
    assert list(split.values()) == pytest.approx([10, 10, 10, 10], abs=1e-9)
    # A section made into 20%, keeping proportions: 10 / 30 -> 5 / 15.
    assert list(make_100({"A": 10, "B": 30}, 20).values()) == pytest.approx([5, 15], abs=1e-9)
    # No section total typed: split the section's current total (2 + 3 + 7 = 12) evenly.
    current = {"A": 2, "B": 3, "C": 7}
    assert list(split_evenly(list(current), sum(current.values())).values()) == pytest.approx([4, 4, 4], abs=1e-9)


def test_set_section_total():
    # Typing a section total keeps the proportions: 10/30 set to 20 -> 5/15.
    assert set_section_total({"A": 10, "B": 30}, 20) == pytest.approx({"A": 5, "B": 15}, abs=1e-9)
    # Typing the total it already has changes nothing: 10/30 set to 40 -> 10/30.
    assert set_section_total({"A": 10, "B": 30}, 40) == pytest.approx({"A": 10, "B": 30}, abs=1e-9)
    # All at 0%: they share the new total equally, 0/0 set to 40 -> 20/20.
    assert set_section_total({"A": 0, "B": 0}, 40) == pytest.approx({"A": 20, "B": 20}, abs=1e-9)


def test_split_categories():
    # Two categories: S&P 500 (Equities) and Gold at 0% (Commodities) -> 50 / 50.
    # Empty categories (nothing checked) are left out.
    result = split_categories({"Equities": {"S&P 500": 100}, "Commodities": {"Gold": 0}, "Crypto": {}})
    assert result == pytest.approx({"S&P 500": 50, "Gold": 50}, abs=1e-9)
    # Three categories with one asset each -> 100/3 each (33.33%).
    result = split_categories({"A": {"a": 10}, "B": {"b": 20}, "C": {"c": 0}})
    assert list(result.values()) == pytest.approx([100 / 3] * 3, abs=1e-9)
    # Real estate keeps its proportions (10 : 5 : 5) inside its 50% share: 25 / 12.5 / 12.5.
    result = split_categories({
        "Equities": {"S&P 500": 80},
        "Real estate": {"US home prices": 10, "New York": 5, "Boston": 5},
    })
    assert result == pytest.approx(
        {"S&P 500": 50, "US home prices": 25, "New York": 12.5, "Boston": 12.5}, abs=1e-9
    )
    # Nothing checked anywhere: nothing to split.
    assert split_categories({"Equities": {}}) == {}


def test_checking_and_unchecking_assets():
    # 50/50, then check a new asset: it joins at 0%, total still 100%.
    basket, total = basket_and_total({"A": 50, "B": 50, "C": 0})
    assert basket == {"A": 50, "B": 50}  # C at 0% is not in the basket
    assert total == 100 and weights_add_up(total)
    # Uncheck B: A 50% and C 0%, total 50%, so no basket results.
    basket, total = basket_and_total({"A": 50, "C": 0})
    assert total == 50 and not weights_add_up(total)
    # Split evenly gives 3 × 100/3, which counts as 100%.
    assert weights_add_up(sum(split_evenly(["A", "B", "C"]).values()))


def test_luxury_cities_are_separate_assets():
    # Two cities at 50% each are two assets in the basket; a third city at 0% is not in it.
    basket, total = basket_and_total({
        "Luxury homes (New York)": 50,
        "Luxury homes (Boston)": 50,
        "Luxury homes (Chicago)": 0,
    })
    assert basket == {"Luxury homes (New York)": 50, "Luxury homes (Boston)": 50}
    assert weights_add_up(total)


# --- Rates over different periods ---

END = pd.Timestamp("2026-09-01")
MONTHS = pd.date_range("2006-09-01", END, freq="MS")  # 20 years + 1 month of data


def growing_10_percent_a_year(months):
    """A price that grows exactly 10% per year: 100 × 1.1 ^ (months since start / 12)."""
    elapsed = (months.year - months[0].year) * 12 + (months.month - months[0].month)
    return pd.Series(100 * 1.1 ** (elapsed / 12), index=months)


def test_period_rates_exact_10_percent():
    # Something growing exactly 10% a year shows 10% in every period column.
    prices = pd.DataFrame({"A": growing_10_percent_a_year(MONTHS)})
    cpi = growing_10_percent_a_year(MONTHS)
    rates = period_rates(prices, cpi, {"A": 100}, END)
    for period in (1, 3, 5, 10, 20):
        assert rates["basket"][period] == pytest.approx(0.10, abs=1e-9)
        assert rates["CPI"][period] == pytest.approx(0.10, abs=1e-9)


def test_period_rates_missing_start_month_uses_month_before():
    # CPI has no September 2025 (like the October 2025 gap). The 1-year period
    # starts in August 2025 instead, over its true 13 months: still 10%.
    prices = pd.DataFrame({"A": growing_10_percent_a_year(MONTHS)})
    cpi = growing_10_percent_a_year(MONTHS).drop(pd.Timestamp("2025-09-01"))
    rates = period_rates(prices, cpi, {"A": 100}, END)
    assert rates["CPI"][1] == pytest.approx(0.10, abs=1e-9)
    assert rates["basket"][1] == pytest.approx(0.10, abs=1e-9)


def test_period_rates_dash_when_asset_too_new():
    # Asset B only has 4 years of data: 5, 10 and 20 years show "—" (None).
    young = pd.date_range("2022-09-01", END, freq="MS")
    prices = pd.DataFrame({"A": growing_10_percent_a_year(MONTHS), "B": growing_10_percent_a_year(young)})
    cpi = growing_10_percent_a_year(MONTHS)
    rates = period_rates(prices, cpi, {"A": 50, "B": 50}, END)
    assert rates["basket"][3] == pytest.approx(0.10, abs=1e-9)
    assert rates["basket"][5] is None and rates["basket"][10] is None and rates["basket"][20] is None
    assert rates["CPI"][5] is None  # same months as the basket, so CPI is "—" too
