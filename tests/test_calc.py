"""Tests for calc.py (and data.py helpers), using small numbers you can check by hand."""

import pandas as pd
import pytest

from calc import asset_index, last_month_set_by, line_up, monthly_average, rebase
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


def test_line_up():
    # Only months where every series has a value are kept:
    # Jan (no asset), Mar (no CPI) and Jun (no CPI) are dropped.
    def table(months, values):
        return pd.DataFrame({"date": pd.to_datetime([f"2024-{m}-01" for m in months]), "value": values})

    cpi = table(["01", "02", "04", "05"], [100, 101, 103, 104])
    wages = table(["01", "02", "03", "04", "05", "06"], [10, 11, 12, 13, 14, 15])
    asset = table(["02", "03", "04", "05", "06"], [50, 55, 60, 65, 70])
    lined_up = line_up({"CPI": cpi, "Wages": wages, "Asset": asset})
    assert lined_up.index.tolist() == pd.to_datetime(["2024-02-01", "2024-04-01", "2024-05-01"]).tolist()
    assert lined_up.columns.tolist() == ["CPI", "Wages", "Asset"]
    assert lined_up.loc["2024-02-01"].tolist() == [101, 11, 50]


def test_line_up_matches_by_month_not_exact_date():
    # B is dated at month-end; it must still line up with A.
    a = pd.DataFrame({"date": pd.to_datetime(["2024-01-01", "2024-02-01"]), "value": [1, 2]})
    b = pd.DataFrame({"date": pd.to_datetime(["2024-01-31", "2024-02-29"]), "value": [10, 20]})
    lined_up = line_up({"A": a, "B": b})
    assert lined_up.index.tolist() == pd.to_datetime(["2024-01-01", "2024-02-01"]).tolist()
    assert lined_up["A"].tolist() == [1, 2]
    assert lined_up["B"].tolist() == [10, 20]


def test_line_up_no_shared_months_gives_empty_table():
    a = pd.DataFrame({"date": pd.to_datetime(["2024-01-01", "2024-02-01"]), "value": [1, 2]})
    b = pd.DataFrame({"date": pd.to_datetime(["2024-03-01", "2024-04-01"]), "value": [3, 4]})
    lined_up = line_up({"A": a, "B": b})
    assert lined_up.empty
    assert lined_up.columns.tolist() == ["A", "B"]


def test_line_up_refuses_two_values_in_one_month():
    a = pd.DataFrame({"date": pd.to_datetime(["2024-01-01", "2024-01-31"]), "value": [1, 2]})
    with pytest.raises(ValueError, match="more than one value"):
        line_up({"A": a})


def test_last_month_set_by():
    # A and C end in March 2024, B in May 2024: A and C decide the last month.
    def ends(last):
        return pd.DataFrame({"date": pd.to_datetime(["2024-01-01", last]), "value": [1, 2]})

    assert last_month_set_by({"A": ends("2024-03-01"), "B": ends("2024-05-01"), "C": ends("2024-03-01")}) == ["A", "C"]


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
