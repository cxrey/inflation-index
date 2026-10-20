"""Tests for market-size weights updated every January, using numbers you can check by hand.

Market value = quantity × price, so "no new supply" means a constant quantity.
"""

import pandas as pd
import pytest

from calc import asset_index, market_weights_unchanged, period_rates, waiting_lines, yearly_market_index

MONTHS = pd.to_datetime(["2020-01-01", "2020-07-01", "2021-01-01", "2021-07-01", "2022-01-01"])


def prices(**columns: list[float]) -> pd.DataFrame:
    """A price table: one row per month in MONTHS, one column per asset (None = no price)."""
    return pd.DataFrame(columns, index=MONTHS, dtype=float)


def market(quantities: dict[str, dict[str, float]], table: pd.DataFrame):
    """market_value(asset, month) = quantity × price; the quantity in force is the
    latest one listed at or before the month ({asset: {"YYYY-MM": quantity}})."""
    def market_value(asset, month):
        listed = {pd.Timestamp(m + "-01"): q for m, q in quantities.get(asset, {}).items()}
        earlier = [m for m in listed if m <= month]
        if not earlier:
            return None
        return listed[max(earlier)] * table.at[month, asset]
    return market_value


def test_no_new_supply_gives_the_same_index_as_no_reweighting():
    # A and B at 1/2 each. A doubles in year 1 (index 150; January weights 2/3 and 1/3),
    # B doubles in year 2: 150 × (2/3 × 1 + 1/3 × 2) = 200. Buy and hold: 0.5 × 2 + 0.5 × 2 = 2 -> 200.
    table = prices(A=[1, 1.5, 2, 2, 2], B=[1, 1, 1, 1.5, 2])
    index, reweights = yearly_market_index(table, MONTHS[0], market({"A": {"2020-01": 1}, "B": {"2020-01": 1}}, table))
    assert index.tolist() == pytest.approx(asset_index(table, {"A": 0.5, "B": 0.5}).tolist(), abs=1e-9)
    assert index.iloc[-1] == pytest.approx(200, abs=1e-9)
    assert reweights[pd.Timestamp("2021-01-01")] == pytest.approx({"A": 2 / 3, "B": 1 / 3}, abs=1e-9)


def test_new_supply_changes_the_weight_next_january():
    # Same prices, but B's quantity doubles during year 1. In January 2021 the
    # market values are A 1 × 2 = 2 and B 2 × 1 = 2: weights 1/2 and 1/2 (not 2/3 and 1/3).
    # Year 2: 150 × (1/2 × 1 + 1/2 × 2) = 225 (buy and hold: 200).
    table = prices(A=[1, 1.5, 2, 2, 2], B=[1, 1, 1, 1.5, 2])
    quantities = {"A": {"2020-01": 1}, "B": {"2020-01": 1, "2020-07": 2}}
    index, reweights = yearly_market_index(table, MONTHS[0], market(quantities, table))
    assert reweights[pd.Timestamp("2021-01-01")] == pytest.approx({"A": 0.5, "B": 0.5}, abs=1e-9)
    assert index.loc["2021-01-01"] == pytest.approx(150, abs=1e-9)
    assert index.iloc[-1] == pytest.approx(225, abs=1e-9)
    # The weights only change in January: July 2020 is still buy and hold (1/2 × 1.5 + 1/2 × 1 = 125).
    assert index.loc["2020-07-01"] == pytest.approx(125, abs=1e-9)


def test_asset_without_market_size_data_joins_the_first_january_with_full_data():
    # A has data from the start. B has a price but no market-size data until
    # 2021; C has no price until July 2020 and no market-size data until 2022.
    # 2020: A alone, 1 -> 1.5, index 150.
    # January 2021: A 1 × 1.5 = 1.5, B 0.5 × 1 = 0.5: weights 3/4 and 1/4 (C not yet).
    # January 2022: 150 × (3/4 × 1 + 1/4 × 3) = 225; C joins then.
    table = prices(A=[1, 1.2, 1.5, 1.5, 1.5], B=[1, 1, 1, 2, 3], C=[None, 1, 1, 1, 1])
    quantities = {"A": {"2020-01": 1}, "B": {"2021-01": 0.5}, "C": {"2022-01": 1}}
    index, reweights = yearly_market_index(table, MONTHS[0], market(quantities, table))
    assert reweights[MONTHS[0]] == {"A": 1.0}
    assert reweights[pd.Timestamp("2021-01-01")] == pytest.approx({"A": 0.75, "B": 0.25}, abs=1e-9)
    assert set(reweights[pd.Timestamp("2022-01-01")]) == {"A", "B", "C"}
    assert index.tolist() == pytest.approx([100, 120, 150, 150 * (0.75 + 0.25 * 2), 225], abs=1e-9)


def test_january_skipped_when_an_asset_in_the_basket_has_no_market_data():
    # B's market-size data stops after 2020: January 2021 is skipped and the
    # basket is held on (same as no reweighting), so B isn't dropped.
    table = prices(A=[1, 1.5, 2, 2, 2], B=[1, 1, 1, 1.5, 2])

    def market_value(asset, month):
        if asset == "B" and month >= pd.Timestamp("2021-01-01"):
            return None
        return table.at[month, asset]

    index, reweights = yearly_market_index(table, MONTHS[0], market_value)
    assert list(reweights) == [MONTHS[0]]
    assert index.iloc[-1] == pytest.approx(200, abs=1e-9)


def test_no_market_size_data_at_the_start_is_an_error():
    table = prices(A=[1, 1, 1, 1, 1])
    with pytest.raises(ValueError, match="January 2020"):
        yearly_market_index(table, MONTHS[0], lambda asset, month: None)


# --- When updating every January is allowed, and the lines about waiting assets ---

PRESSED = {"start": pd.Timestamp("2024-01-01"), "weights": {"S&P 500": 60.0, "Gold": 40.0}}


def test_updating_turns_off_after_an_edit_or_a_new_start_month():
    january = pd.Timestamp("2024-01-01")
    # Right after pressing "Weight by market size": allowed.
    assert market_weights_unchanged(PRESSED, {"S&P 500": 60.0, "Gold": 40.0}, january)
    # Typing a weight, or pressing another weight button ("edited"): off.
    assert not market_weights_unchanged(PRESSED, {"S&P 500": 70.0, "Gold": 30.0}, january)
    assert not market_weights_unchanged({**PRESSED, "edited": True}, {"S&P 500": 60.0, "Gold": 40.0}, january)
    # Another start month: off.
    assert not market_weights_unchanged(PRESSED, {"S&P 500": 60.0, "Gold": 40.0}, pd.Timestamp("2020-01-01"))
    # Never pressed, or Reset: off.
    assert not market_weights_unchanged(None, {"S&P 500": 100.0}, january)
    # Pressing the button again stores a fresh state for the new month: allowed again.
    pressed_again = {"start": pd.Timestamp("2020-01-01"), "weights": {"S&P 500": 55.0, "Gold": 45.0}}
    assert market_weights_unchanged(pressed_again, {"S&P 500": 55.0, "Gold": 45.0}, pd.Timestamp("2020-01-01"))


def test_waiting_lines():
    reweights = {
        pd.Timestamp("1975-06-01"): {"Gold": 1.0},
        pd.Timestamp("1976-01-01"): {"Gold": 0.4, "S&P 500": 0.6},
    }
    assert waiting_lines(["S&P 500"], reweights, yearly=True) == [
        "S&P 500: 0% until January 1976, when its market-size data starts."
    ]
    # Not updated every January: it stays at 0%.
    assert waiting_lines(["S&P 500"], reweights, yearly=False) == [
        "S&P 500: 0% (no market-size data at the start month)."
    ]
    # Updated every January, but never joined before the end month.
    assert waiting_lines(["Bitcoin"], reweights, yearly=True) == [
        "Bitcoin: 0% (no market-size data at the start month)."
    ]


def test_period_rates_updated_every_january():
    # Two assets each growing exactly 10% a year, no new supply: every period shows 10%.
    months = pd.date_range("2006-09-01", "2026-09-01", freq="MS")
    elapsed = (months.year - 2006) * 12 + (months.month - 9)
    growing = pd.Series(100 * 1.1 ** (elapsed / 12), index=months)
    table = pd.DataFrame({"A": growing, "B": 2 * growing})
    rates = period_rates(table, growing, {"A": 50, "B": 50}, months[-1],
                         market_value=lambda asset, month: table.at[month, asset])
    for period in (1, 3, 5, 10, 20):
        assert rates["basket"][period] == pytest.approx(0.10, abs=1e-9)
