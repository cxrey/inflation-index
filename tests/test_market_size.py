"""Tests for the "Weight by market size" math, using numbers you can check by hand."""

import pandas as pd
import pytest

from calc import (
    DOLLARS_PER_MILLION,
    NO_DATA_REASON,
    OUNCES_PER_TONNE,
    SILVER_PLATINUM_REASON,
    add_tables,
    cannot_measure,
    crypto_market_value,
    gold_market_value,
    gold_stock_table,
    home_market_value,
    investment_gold,
    market_caption,
    market_size_weights,
    move_to_start,
    stock_market_value,
    treasury_market_value,
    yearly_market_index,
)

ANCHOR_DATE = pd.Timestamp("2026-06-30")


def table(values: dict[str, float]) -> pd.DataFrame:
    """A (date, value) table from {"YYYY-MM": value}."""
    return pd.DataFrame({"date": pd.to_datetime(list(values)), "value": list(values.values())})


# --- Weights and reasons ---

def test_weights_in_proportion_to_market_size():
    # Stocks 83.05, homes 54.07, gold 11.8, Bitcoin 1.63 (trillions): total 150.55.
    values = {"S&P 500": 83.05e12, "US home prices": 54.07e12, "Gold": 11.8e12, "Bitcoin": 1.63e12}
    assert cannot_measure(list(values), values) == {}
    weights = market_size_weights(list(values), values)
    assert weights == pytest.approx({name: 100 * value / 150.55e12 for name, value in values.items()}, abs=1e-9)
    assert sum(weights.values()) == pytest.approx(100, abs=1e-9)


def test_untick_what_cannot_be_measured_then_weight_the_rest():
    # S&P 500, Gold and New York ticked: New York can't be measured (the pop-up lists it).
    checked = ["S&P 500", "Gold", "Luxury homes (New York)"]
    values = {"S&P 500": 50e12, "Gold": 25e12}  # stocks $50 trillion, gold $25 trillion
    reasons = cannot_measure(checked, values)
    assert list(reasons) == ["Luxury homes (New York)"]
    # After unticking New York: 50 : 25 = 2 : 1, so 66.67% and 33.33%.
    weights = market_size_weights(["S&P 500", "Gold"], values)
    assert weights == pytest.approx({"S&P 500": 200 / 3, "Gold": 100 / 3}, abs=1e-9)


def test_nasdaq_messages():
    # With S&P 500 checked: "already included".
    reasons = cannot_measure(["S&P 500", "Nasdaq"], {"S&P 500": 1e12})
    assert list(reasons) == ["Nasdaq"]
    assert reasons["Nasdaq"].startswith("already included in the S&P 500 row")
    # Nasdaq alone: "check S&P 500".
    assert "check S&P 500 to include US stocks" in cannot_measure(["Nasdaq"], {})["Nasdaq"]


def test_luxury_cities_messages():
    reasons = cannot_measure(["US home prices", "Luxury homes (Boston)"], {"US home prices": 1e12})
    assert reasons == {"Luxury homes (Boston)": "already included in US home prices."}
    reasons = cannot_measure(["Luxury homes (Boston)"], {})
    assert "check US home prices to include US homes" in reasons["Luxury homes (Boston)"]


def test_silver_gets_its_message():
    reasons = cannot_measure(["Gold", "Silver"], {"Gold": 1e12})
    assert reasons == {"Silver": SILVER_PLATINUM_REASON}
    assert SILVER_PLATINUM_REASON == "no reliable estimate of how much exists above ground."


def test_no_data_at_the_start_month():
    reasons = cannot_measure(["S&P 500", "Bitcoin"], {"S&P 500": 1e12, "Bitcoin": None})
    assert reasons == {"Bitcoin": NO_DATA_REASON}
    assert NO_DATA_REASON == "no market-size data for this date."


# --- Units and moving a value to the start month ---

def test_units():
    # 1 tonne of gold at $1 per ounce = $32,150.7466; FRED's 1,000 (millions) = $1,000,000,000.
    assert 1 * OUNCES_PER_TONNE * 1 == pytest.approx(32_150.7466, abs=1e-9)
    assert 1_000 * DOLLARS_PER_MILLION == 1_000_000_000


def test_move_to_start():
    # A value of 100 with the asset's price 10% higher at the start month -> 110.
    assert move_to_start(100, 11, 10) == pytest.approx(110, abs=1e-9)


# --- US stocks (World Bank year-ends, from December 1975) ---

WORLD_BANK = table({"1975-12": 100.0, "1976-12": 120.0})
SP500 = table({"1970-01": 5.0, "1975-06": 9.0, "1975-12": 10.0, "1976-03": 11.0})


def test_stocks_moved_by_sp500():
    # Year-end 1975 value 100, S&P 500 10% higher in March 1976 -> 110.
    assert stock_market_value(pd.Timestamp("1976-03-01"), WORLD_BANK, SP500) == pytest.approx(110, abs=1e-9)


def test_stocks_before_december_1975_have_no_data():
    for start in ("1975-06-01", "1970-01-01"):
        value = stock_market_value(pd.Timestamp(start), WORLD_BANK, SP500)
        assert cannot_measure(["S&P 500"], {"S&P 500": value}) == {"S&P 500": NO_DATA_REASON}
    # December 1975 itself has data, so it can be weighted.
    value = stock_market_value(pd.Timestamp("1975-12-01"), WORLD_BANK, SP500)
    assert cannot_measure(["S&P 500"], {"S&P 500": value}) == {}
    assert market_size_weights(["S&P 500"], {"S&P 500": value})["S&P 500"] == 100.0


# --- US homes (FRED quarters, in millions) ---

def test_homes_quarter_end_moved_to_start_month():
    # The quarter dated January 2024 ends in March 2024: 100 (millions) there,
    # home prices 10% higher in May 2024 -> $110 million.
    homes = table({"2024-01": 100.0})
    prices = table({"2024-03": 200.0, "2024-05": 220.0})
    assert home_market_value(pd.Timestamp("2024-05-01"), homes, prices) == pytest.approx(110e6, abs=1e-3)
    # February 2024 is before that quarter ends: no data.
    assert home_market_value(pd.Timestamp("2024-02-01"), homes, prices) is None


def test_all_us_homes_is_the_sum_of_both_series():
    # Households' homes 54,073,947 + landlords' homes 10,603,430 (millions, Q2 2026)
    # = 64,677,377 million = $64.68 trillion. A date only one series has is left out.
    households = table({"2026-01": 52_942_961.0, "2026-04": 54_073_947.0})
    landlords = table({"2026-04": 10_603_430.0})
    total = add_tables(households, landlords)
    assert total["value"].tolist() == [64_677_377.0]
    assert total["date"].tolist() == [pd.Timestamp("2026-04-01")]
    # With home prices unchanged since the quarter ended in June: $64.68 trillion in July 2026.
    prices = table({"2026-06": 300.0, "2026-07": 300.0})
    assert home_market_value(pd.Timestamp("2026-07-01"), total, prices) == pytest.approx(64_677_377e6)


# --- 10-year Treasury (Dallas Fed market value minus bills) ---

DALLAS = table({"1990-05": 2_000.0, "2024-01": 100.0, "2024-02": 101.0})  # billions
BILLS_MONTHLY = table({"2001-01": 500_000.0, "2024-01": 20_000.0})  # millions, from January 2001
BILLS_QUARTERLY = table({"1990-01": 400_000.0, "1990-04": 450_000.0})  # millions, quarter-ends Mar and Jun
NO_BILLS = table({})
# The 10-year Treasury index, unchanged in every month these tests use.
TREASURY = table({month: 100.0 for month in ["1989-12", "1990-05", "2024-01", "2024-02", "2024-03"]})


def test_treasury_market_size():
    # $100 billion minus $20,000 million of bills = $80 billion.
    value = treasury_market_value(pd.Timestamp("2024-01-01"), DALLAS, BILLS_MONTHLY, BILLS_QUARTERLY, TREASURY)
    assert value == pytest.approx(80e9, abs=1e-3)


def test_treasury_before_2001_uses_the_feds_quarter_end():
    # May 1990: the quarter dated January ends in March ($400,000 million);
    # the one dated April ends in June, after May. $2,000 billion - $400 billion = $1,600 billion.
    value = treasury_market_value(pd.Timestamp("1990-05-01"), DALLAS, BILLS_MONTHLY, BILLS_QUARTERLY, TREASURY)
    assert value == pytest.approx(1_600e9, abs=1e-3)


def test_treasury_without_data():
    # Before the first market value or bills figure: no data.
    value = treasury_market_value(pd.Timestamp("1989-12-01"), DALLAS, BILLS_MONTHLY, BILLS_QUARTERLY, TREASURY)
    assert value is None
    assert cannot_measure(["10-year Treasury"], {"10-year Treasury": value}) == {"10-year Treasury": NO_DATA_REASON}
    # February 2024 (and March, which falls back to February): the Dallas Fed
    # has it, but the Treasury's bills figure doesn't.
    for start in ("2024-02-01", "2024-03-01"):
        assert treasury_market_value(pd.Timestamp(start), DALLAS, BILLS_MONTHLY, BILLS_QUARTERLY, TREASURY) is None


def test_lagged_value_moved_forward_and_stale_value_skips_january():
    # The Dallas Fed's latest month is December 2024: $100 billion - $20,000 million = $80 billion.
    dallas, bills = table({"2024-12": 100.0}), table({"2024-12": 20_000.0})
    treasury = table({"2024-12": 100.0, "2025-01": 101.0, "2026-01": 101.0})
    # January 2025: last month's value with the 10-year Treasury up 1% since -> $80.8 billion (101%).
    january_2025 = treasury_market_value(pd.Timestamp("2025-01-01"), dallas, bills, NO_BILLS, treasury)
    assert january_2025 == pytest.approx(80.8e9, abs=1e-3)
    # January 2026: the latest value is 13 months old -> no data.
    assert treasury_market_value(pd.Timestamp("2026-01-01"), dallas, bills, NO_BILLS, treasury) is None

    # In the yearly basket: January 2025 is reweighted (no skip), January 2026 is skipped.
    months = pd.to_datetime(["2024-12-01", "2025-01-01", "2026-01-01"])
    prices = pd.DataFrame({"10-year Treasury": [100.0, 101.0, 101.0], "A": [1.0, 1.0, 1.0]}, index=months)

    def market_value(asset, month):
        if asset == "A":
            return 80e9
        return treasury_market_value(month, dallas, bills, NO_BILLS, treasury)

    _, reweights = yearly_market_index(prices, months[0], market_value)
    assert list(reweights) == [months[0], months[1]]
    # January 2025: $80.8 billion against A's $80 billion.
    assert reweights[months[1]]["10-year Treasury"] == pytest.approx(80.8 / 160.8, abs=1e-9)


def test_stale_after_12_months():
    # A year-end value from December 2023 still counts in December 2024 (12 months),
    # but not in January 2025 (13 months).
    year_ends = table({"2023-12": 100.0})
    sp500 = table({"2023-12": 10.0, "2024-12": 11.0, "2025-01": 11.0})
    assert stock_market_value(pd.Timestamp("2024-12-01"), year_ends, sp500) == pytest.approx(110, abs=1e-9)
    assert stock_market_value(pd.Timestamp("2025-01-01"), year_ends, sp500) is None


# --- Crypto (monthly average market caps) ---

def test_solana_from_may_2020():
    caps = table({"2020-05": 5.3e6, "2020-06": 10.8e6})
    prices = table({"2020-04": 0.9, "2020-05": 1.0, "2020-06": 2.0, "2020-07": 2.2})
    assert crypto_market_value(pd.Timestamp("2020-05-01"), caps, prices) == pytest.approx(5.3e6)
    assert market_size_weights(["S&P 500", "Solana"], {"S&P 500": 1e12, "Solana": 5.3e6})["Solana"] > 0
    assert crypto_market_value(pd.Timestamp("2020-04-01"), caps, prices) is None
    # July 2020 has no market cap yet: June's, moved forward by the price (2.0 -> 2.2): 10.8 × 1.1 = 11.88 million.
    assert crypto_market_value(pd.Timestamp("2020-07-01"), caps, prices) == pytest.approx(11.88e6)


def test_bitcoin_basket_starting_in_2015():
    caps = table({"2015-01": 3.5e9})
    value = crypto_market_value(pd.Timestamp("2015-01-01"), caps, table({"2015-01": 250.0}))
    assert market_size_weights(["Bitcoin"], {"Bitcoin": value})["Bitcoin"] == 100.0


# --- Gold ---

def test_gold_anchor_latest_year_2025():
    # Y = 2025 with 3,600 t: end-2025 = 222,600 - 3,600 × 6/12 = 220,800 t.
    stocks = gold_stock_table({2025: 3600}, 222_600, ANCHOR_DATE, pd.Timestamp("2025-01-01"))
    assert stocks[2025] == pytest.approx(220_800, abs=1e-9)


def test_gold_anchor_latest_year_2024():
    # Y = 2024 with 3,600 t: end-2024 = 222,600 - 3,600 × 18/12 = 217,200 t, end-2025 = 220,800 t.
    stocks = gold_stock_table({2024: 3600}, 222_600, ANCHOR_DATE, pd.Timestamp("2024-01-01"))
    assert stocks[2024] == pytest.approx(217_200, abs=1e-9)
    assert stocks[2025] == pytest.approx(220_800, abs=1e-9)


def test_gold_history():
    # A stock of 100 t at end-2025 with 2 t mined in 2025 gives 98 t at end-2024.
    # (Anchor 101 t: end-2025 = 101 - 2 × 6/12 = 100.)
    stocks = gold_stock_table({2025: 2}, 101, ANCHOR_DATE, pd.Timestamp("2025-01-01"))
    assert stocks[2025] == pytest.approx(100, abs=1e-9)
    assert stocks[2024] == pytest.approx(98, abs=1e-9)


def test_gold_coverage_from_first_price_month():
    # Gold prices start in January 1971: the table reaches back to end-1970,
    # and January 1971 uses that year-end.
    production = {year: 1000 for year in range(1971, 2026)}
    stocks = gold_stock_table(production, 222_600, ANCHOR_DATE, pd.Timestamp("1971-01-01"))
    assert min(stocks) == 1970
    prices = table({"1971-01": 38.0})
    value = gold_market_value(pd.Timestamp("1971-01-01"), stocks, prices)
    assert value == pytest.approx(stocks[1970] * OUNCES_PER_TONNE * 38.0, abs=1e-3)


def test_gold_investment_share():
    # The investment share of 222,600 t is 90,800 t.
    assert investment_gold(222_600, 90_800, 222_600) == pytest.approx(90_800, abs=1e-9)


# --- The caption under the weights ---

PRESSED = {"start": pd.Timestamp("2024-01-01"), "weights": {"S&P 500": 60.0, "Gold": 40.0}}


def test_caption_after_pressing():
    lines = market_caption(PRESSED, {"S&P 500": 60.0, "Gold": 40.0}, pd.Timestamp("2024-01-01"))
    assert lines == ["Market-size weights as of January 2024."]


def test_caption_edited_after_make_it_100_and_removed_by_reset():
    # Pressing Make it 100% after the button marks it edited, even though the
    # weights already added up to 100% and stay the same: "(edited)".
    after_make_100 = {"S&P 500": 60.0, "Gold": 40.0}
    assert market_caption({**PRESSED, "edited": True}, after_make_100, pd.Timestamp("2024-01-01")) == [
        "Started from market-size weights (edited)."
    ]
    # Typing a different weight is a change too.
    assert market_caption(PRESSED, {"S&P 500": 75.0, "Gold": 25.0}, pd.Timestamp("2024-01-01")) == [
        "Started from market-size weights (edited)."
    ]
    # Checking another asset (it joins at 0%) is a change too.
    assert market_caption(PRESSED, {"S&P 500": 60.0, "Gold": 40.0, "Silver": 0.0},
                          pd.Timestamp("2024-01-01"))[0].endswith("(edited).")
    # Reset clears what the button set: no caption.
    assert market_caption(None, after_make_100, pd.Timestamp("2024-01-01")) == []


def test_caption_when_start_month_changes():
    lines = market_caption(PRESSED, {"S&P 500": 60.0, "Gold": 40.0}, pd.Timestamp("2020-01-01"))
    assert lines == ["Market-size weights as of January 2024.", "Start month changed; press again to update."]
