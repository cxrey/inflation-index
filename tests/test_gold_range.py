"""Tests for gold's range in the main results, using numbers you can check by hand."""

import pandas as pd
import pytest

from calc import (
    OUNCES_PER_TONNE,
    basket_sentences,
    gold_counts,
    keep_up_sentence,
    range_text,
    us_government_gold_value,
)

START, END = pd.Timestamp("2000-01-01"), pd.Timestamp("2026-09-01")
REASON = "depending on whether gold is counted worldwide or as US government gold only"


def test_us_government_gold_uses_8133_5_tonnes():
    # 8,133.5 t × 32,150.7466 oz per tonne × $2,000 = $523 billion.
    prices = pd.DataFrame({"date": [START], "value": [2_000.0]})
    assert us_government_gold_value(START, prices) == pytest.approx(8_133.5 * OUNCES_PER_TONNE * 2_000, abs=1e-3)
    assert us_government_gold_value(START, prices) == pytest.approx(523.0e9, rel=1e-3)
    assert us_government_gold_value(END, prices) is None  # no price that month


def test_range_smaller_first():
    # World gold 7%, US government gold 5%: "range 5.00% to 7.00%".
    sentences = basket_sentences(0.07, START, END, other=0.05)
    assert sentences[0] == (
        f"Your basket's prices rose 7.00% per year (January 2000 to September 2026; range 5.00% to 7.00%, {REASON})."
    )
    # The world figure lower (5%, US government 7%): still the smaller first.
    assert "range 5.00% to 7.00%" in basket_sentences(0.05, START, END, other=0.07)[0]


def test_cash_and_keep_up_sentences_get_their_own_range():
    # Cash loss: 1 - 1/1.07 = 6.54%, 1 - 1/1.05 = 4.76%.
    sentences = basket_sentences(0.07, START, END, other=0.05)
    assert sentences[1] == "Cash lost 6.54% of its buying power against your basket per year (range 4.76% to 6.54%)."
    assert keep_up_sentence(0.07, other=0.05) == (
        "To keep up with your basket, your money must grow at least 7.00% per year (range 5.00% to 7.00%)."
    )


def test_range_crossing_zero_keeps_signs():
    assert range_text(0.012, -0.005) == "range -0.50% to 1.20%"
    assert range_text(-0.005, 0.012) == "range -0.50% to 1.20%"


def test_no_range_when_equal_after_rounding_or_no_gold():
    # 5.001% and 5.002% both show as 5.00%: no range.
    assert range_text(0.05001, 0.05002) is None
    assert basket_sentences(0.05001, START, END, other=0.05002)[0] == (
        "Your basket's prices rose 5.00% per year (January 2000 to September 2026)."
    )
    assert keep_up_sentence(0.05001, other=0.05002).endswith("5.00% per year.")
    # No second result (gold not in the basket): no range.
    assert range_text(0.05, None) is None
    # Gold at 0%: no range is computed.
    assert not gold_counts({"S&P 500": 100.0, "Gold": 0.0}, {})
    assert gold_counts({"S&P 500": 60.0, "Gold": 40.0}, {})
    # Gold joining in a January (updated every January) counts too.
    assert gold_counts({"S&P 500": 100.0}, {pd.Timestamp("1972-01-01"): {"S&P 500": 0.9, "Gold": 0.1}})
