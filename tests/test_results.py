"""Tests for the main result sentences (version 1.2, Step 5), using rates you can check by hand."""

import pandas as pd

from calc import (
    basket_sentences,
    cpi_sentence,
    keep_up_sentence,
    per_year,
    percent_ticks,
    your_rate_sentences,
)

START, END = pd.Timestamp("2024-01-01"), pd.Timestamp("2026-01-01")  # 24 months


def test_rising_basket():
    # 100 -> 121 over 24 months: 10% per year; cash loses 1 - 1/1.1 = 9.09% per year.
    rate = per_year(100, 121, 24)
    assert basket_sentences(rate, START, END) == [
        "Your basket's prices rose 10.00% per year (January 2024 to January 2026).",
        "Cash lost 9.09% of its buying power against your basket per year.",
    ]
    assert keep_up_sentence(rate) == "To keep up with your basket, your money must grow at least 10.00% per year."


def test_falling_basket():
    # 100 -> 81 over 24 months: falls 10% per year; cash gains 1/9 = 11.11% per year.
    rate = per_year(100, 81, 24)
    assert basket_sentences(rate, START, END) == [
        "Your basket's prices fell 10.00% per year (January 2024 to January 2026).",
        "Cash gained 11.11% of its buying power against your basket per year.",
    ]
    assert keep_up_sentence(rate) is None  # only shown when prices rose


def test_flat_basket():
    # 100 -> 100: "didn't change (0% per year)" and no cash sentence.
    rate = per_year(100, 100, 24)
    assert basket_sentences(rate, START, END) == ["Your basket's prices didn't change (0% per year)."]
    assert keep_up_sentence(rate) is None


def test_your_rate_against_basket_and_cpi():
    # Your rate 4%, basket 30%: 1.04 / 1.30 - 1 = -20%, "lose 20%".
    # Your rate 4%, CPI 4%: "keep the same buying power".
    assert your_rate_sentences(0.04, 0.30, 0.04) == [
        "If basket prices keep changing at their past rate, at 4% per year "
        "you'd lose 20.00% of your buying power in your basket each year.",
        "Against CPI, at 4% per year you'd keep the same buying power each year.",
    ]
    # Your rate 10%, basket 10%: "keep the same buying power".
    assert your_rate_sentences(0.10, 0.10, None)[0].endswith("you'd keep the same buying power each year.")
    # Your rate 10%, CPI 0%: 10% more, "gain 10.00%".
    assert your_rate_sentences(0.10, None, 0.0) == [
        "Against CPI, at 10% per year you'd gain 10.00% of your buying power at the store each year."
    ]


def test_under_12_months_hides_the_sentences():
    # 11 months: per year is "—" (None), and every sentence that uses it is hidden.
    rate = per_year(100, 110, 11)
    assert rate is None
    assert basket_sentences(rate, START, END) == []
    assert cpi_sentence(rate) is None
    assert keep_up_sentence(rate) is None
    assert your_rate_sentences(0.04, rate, rate) == []


def test_cpi_sentence():
    assert cpi_sentence(0.0316) == "Official inflation (CPI): 3.16% per year."
    assert cpi_sentence(-0.02) == "Official inflation (CPI): -2.00% per year."


def test_percent_axis_labels():
    # Narrow chart (60 to 1,000 as levels, under 3 powers of ten): -50% and +100% are added.
    levels, labels = percent_ticks(60, 1000)
    assert levels == [10, 50, 100, 200, 1000]
    assert labels == ["-90%", "-50%", "0%", "+100%", "+900%"]
    # Wide chart (Bitcoin-like, 0.5 to 2 million): only powers of ten, more decimals below -99%.
    levels, labels = percent_ticks(0.5, 2_000_000)
    assert labels == ["-99.9%", "-99%", "-90%", "0%", "+900%", "+9,900%", "+99,900%",
                      "+999,900%", "+9,999,900%"]
