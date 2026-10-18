"""Tests for the version 1.2 math in calc.py, using numbers you can check by hand.

Rates are fractions: 0.10 means 10% per year.
"""

import pandas as pd
import pytest

from calc import (
    cash_line,
    cash_loss_per_year,
    change_since_start,
    make_100,
    per_year,
    period_rates,
    rate_versus,
    split_evenly,
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
