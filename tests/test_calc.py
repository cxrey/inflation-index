"""Tests for calc.py (and data.py helpers), using small numbers you can check by hand."""

import pandas as pd
import pytest

from calc import asset_index, monthly_average, rebase
from data import TemporaryDownloadError, download_with_backup, pink_date, shiller_date

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


def test_monthly_average():
    # January 2024: price = day number 1..31 -> average (1 + 31) / 2 = 16
    # February 2024: 100 every day for all 29 days (leap year) -> 100
    # March 2024: only March 1-10 -> incomplete, left out
    january = pd.DataFrame({"date": pd.date_range("2024-01-01", "2024-01-31"), "value": range(1, 32)})
    february = pd.DataFrame({"date": pd.date_range("2024-02-01", "2024-02-29"), "value": 100})
    march = pd.DataFrame({"date": pd.date_range("2024-03-01", "2024-03-10"), "value": 50})
    monthly = monthly_average(pd.concat([january, february, march]))
    assert monthly["date"].tolist() == [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-02-01")]
    assert monthly["value"].tolist() == pytest.approx([16, 100], abs=1e-6)


def test_shiller_date():
    # Shiller writes October as 2026.1 (not 2026.10); it must become October.
    assert shiller_date(1871.01) == pd.Timestamp("1871-01-01")
    assert shiller_date(2026.1) == pd.Timestamp("2026-10-01")
    assert shiller_date(2026.12) == pd.Timestamp("2026-12-01")


def test_pink_date():
    assert pink_date("1960M01") == pd.Timestamp("1960-01-01")
    assert pink_date("1999M12") == pd.Timestamp("1999-12-01")
    assert pink_date("2026M09") == pd.Timestamp("2026-09-01")


# --- Retries and backup copies (no internet: pretend downloads) ---

TABLE = pd.DataFrame({"date": MONTHS, "value": [10.0, 12.0]})


def pretend_download(results):
    """Make a pretend download that returns or raises results[0], results[1], ... in turn.

    Also returns a list that gets one item per call, to count the calls.
    """
    calls = []

    def download():
        result = results[len(calls)]
        calls.append(1)
        if isinstance(result, Exception):
            raise result
        return result

    return download, calls


def save_copy(folder):
    # A saved copy whose latest month is February 2024.
    TABLE.to_csv(folder / "TEST.csv", index=False)


def test_temporary_failures_then_success(tmp_path):
    download, calls = pretend_download([
        TemporaryDownloadError("timed out"),
        TemporaryDownloadError("timed out"),
        TABLE,
    ])
    table, note = download_with_backup("TEST", download, folder=tmp_path, wait_seconds=0)
    assert table["value"].tolist() == [10.0, 12.0]
    assert note is None
    assert len(calls) == 3
    assert (tmp_path / "TEST.csv").exists()  # the success was saved


def test_backup_used_after_three_temporary_failures(tmp_path):
    save_copy(tmp_path)
    download, calls = pretend_download([TemporaryDownloadError("timed out")] * 3)
    table, note = download_with_backup("TEST", download, folder=tmp_path, wait_seconds=0)
    assert table["value"].tolist() == [10.0, 12.0]
    assert "February 2024" in note
    assert len(calls) == 3


def test_error_when_nothing_saved(tmp_path):
    download, calls = pretend_download([TemporaryDownloadError("timed out")] * 3)
    with pytest.raises(TemporaryDownloadError):
        download_with_backup("TEST", download, folder=tmp_path, wait_seconds=0)


def test_permanent_failure_not_retried_and_backup_used(tmp_path):
    save_copy(tmp_path)
    download, calls = pretend_download([ValueError("error 404 (Not Found)")])
    table, note = download_with_backup("TEST", download, folder=tmp_path, wait_seconds=0)
    assert len(calls) == 1  # no retries
    assert "404" in note
    assert table["value"].tolist() == [10.0, 12.0]
