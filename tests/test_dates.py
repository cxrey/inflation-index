"""Tests for which months the chart uses, and for the comparison lines (version 1.2, Step 4)."""

import math

import pandas as pd
import pytest

from calc import basket_and_total, change_table, comparison_line, valid_months


def monthly(first: str, last: str, value: float = 100.0, missing=()) -> pd.DataFrame:
    """A table (date, value) with one row per month, leaving out the `missing` months."""
    dates = pd.date_range(first, last, freq="MS").difference(pd.to_datetime(list(missing)))
    return pd.DataFrame({"date": dates, "value": value})


def test_dates_come_from_basket_and_cpi():
    # Asset A has 2000; CPI has 1999-2001 but no June 2000: the months are
    # January-December 2000 without June.
    months = valid_months({"A": monthly("2000-01-01", "2000-12-01")},
                          monthly("1999-01-01", "2001-12-01", missing=["2000-06-01"]))
    assert months[0] == pd.Timestamp("2000-01-01") and months[-1] == pd.Timestamp("2000-12-01")
    assert pd.Timestamp("2000-06-01") not in months
    assert len(months) == 11


def test_asset_at_0_percent_does_not_change_the_start():
    # "Young" starts in 2010 but is checked at 0%, so it is not in the basket
    # and the earliest start stays January 2000.
    tables = {"A": monthly("2000-01-01", "2020-12-01"), "Young": monthly("2010-01-01", "2020-12-01")}
    basket, _ = basket_and_total({"A": 100, "Young": 0})
    months = valid_months({name: tables[name] for name in basket}, monthly("1990-01-01", "2020-12-01"))
    assert months[0] == pd.Timestamp("2000-01-01")


def test_wages_before_1964_are_hidden_with_a_note():
    # Start month 1950: wages (from 1964) have no value then, so no line and a note.
    wages = monthly("1964-01-01", "2026-09-01")
    line, note = comparison_line("Wages", wages, pd.Timestamp("1950-01-01"), pd.Timestamp("2026-09-01"))
    assert line is None
    assert note == "Wages data starts in January 1964."


def test_turning_wages_or_m2_on_or_off_changes_nothing_else():
    # The months come only from the basket and CPI, and each comparison line is
    # calculated on its own: CPI is identical whether wages and M2 are shown or not.
    basket = {"A": monthly("2000-01-01", "2020-12-01")}
    cpi = monthly("1990-01-01", "2020-12-01")
    months = valid_months(basket, cpi)  # wages and M2 are not even an input
    start, end = months[0], months[-1]
    cpi_line, _ = comparison_line("CPI", cpi, start, end)
    _ = comparison_line("Wages", monthly("2005-01-01", "2020-12-01"), start, end)  # hidden (starts later)
    _ = comparison_line("Money supply (M2)", monthly("1959-01-01", "2020-11-01"), start, end)
    assert valid_months(basket, cpi) == months
    assert comparison_line("CPI", cpi, start, end)[0].equals(cpi_line)


def test_cpi_gap_shows_as_a_break():
    # CPI has no October 2025: the month is still on the chart, with no value,
    # so the line shows a break instead of joining September to November.
    cpi = monthly("2025-01-01", "2026-09-01", missing=["2025-10-01"])
    line, note = comparison_line("CPI", cpi, pd.Timestamp("2025-01-01"), pd.Timestamp("2026-09-01"))
    assert note is None
    assert pd.Timestamp("2025-10-01") in line.index and math.isnan(line[pd.Timestamp("2025-10-01")])


def test_line_ending_early_stops_and_table_uses_its_own_last_month():
    # M2 ends in August while the chart ends in September: the line stops, and
    # its change is measured to August (100 -> 121 over 24 months = 21%, 10% per year).
    m2 = pd.DataFrame({"date": pd.to_datetime(["2024-08-01", "2026-08-01"]), "value": [100.0, 121.0]})
    m2 = pd.concat([m2, monthly("2024-09-01", "2026-07-01", value=110.0)]).sort_values("date")
    line, _ = comparison_line("Money supply (M2)", m2, pd.Timestamp("2024-08-01"), pd.Timestamp("2026-09-01"))
    assert math.isnan(line[pd.Timestamp("2026-09-01")])
    table = change_table(pd.DataFrame({"M2": line}))
    assert table.loc["M2", "Total change"] == pytest.approx(21, abs=1e-9)
    assert table.loc["M2", "Yearly change"] == pytest.approx(10, abs=1e-9)
