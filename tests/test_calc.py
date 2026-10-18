"""Tests for calc.py, using small numbers you can check by hand."""

import pandas as pd
import pytest

from calc import asset_index, rebase

# Two months, stored as the first day of each month.
MONTHS = pd.to_datetime(["2024-01-01", "2024-02-01"])


def test_check_example_from_brief():
    # Two assets at 50% each. A goes 10 -> 12 (up 20%), B goes 20 -> 22 (up 10%).
    # Start: 100 × (1/2 × 10/10 + 1/2 × 20/20) = 100
    # Later: 100 × (1/2 × 12/10 + 1/2 × 22/20) = 100 × 23/20 = 115
    prices = pd.DataFrame({"A": [10, 12], "B": [20, 22]}, index=MONTHS)
    index = asset_index(prices, {"A": 0.5, "B": 0.5})
    assert index.tolist() == pytest.approx([100, 115], abs=1e-6)


def test_rebase_starts_at_100():
    # CPI 200, 210, 250 -> 100, 105, 125 (210/200 = 1.05, 250/200 = 1.25)
    cpi = pd.Series([200, 210, 250], index=pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"]))
    assert rebase(cpi).tolist() == pytest.approx([100, 105, 125], abs=1e-6)


def test_weights_not_adding_to_one_are_refused():
    prices = pd.DataFrame({"A": [10, 12], "B": [20, 22]}, index=MONTHS)
    with pytest.raises(ValueError, match="add up to 1"):
        asset_index(prices, {"A": 0.6, "B": 0.6})
