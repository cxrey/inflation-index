"""Tests for tax on "Your rate", using numbers you can check by hand (rates in %)."""

import pytest

from calc import TAX_TOO_HIGH, after_tax_rate, state_tax_applies


def test_federal_and_state():
    # 4 × (1 − 0.24 − 0.09) = 4 × 0.67 = 2.68%.
    rate, taxed, message = after_tax_rate(4.0, 24.0, 9.0, state_applies=True)
    assert rate == pytest.approx(2.68, abs=1e-9) and taxed and message is None


def test_state_checkbox_off():
    # 4 × (1 − 0.24) = 4 × 0.76 = 3.04%.
    rate, taxed, _ = after_tax_rate(4.0, 24.0, 9.0, state_applies=False)
    assert rate == pytest.approx(3.04, abs=1e-9) and taxed


def test_rates_adding_up_to_100_or_more():
    # 60% + 40% = 100% with state on: message, your rate unchanged.
    assert after_tax_rate(4.0, 60.0, 40.0, state_applies=True) == (4.0, False, TAX_TOO_HIGH)
    assert TAX_TOO_HIGH == "Tax rates must add up to less than 100%"
    # With state off, only 60% applies: 4 × 0.40 = 1.60%.
    rate, taxed, message = after_tax_rate(4.0, 60.0, 40.0, state_applies=False)
    assert rate == pytest.approx(1.60, abs=1e-9) and taxed and message is None


def test_empty_boxes_leave_the_rate_unchanged():
    assert after_tax_rate(4.0, None, None, state_applies=True) == (4.0, False, None)
    assert after_tax_rate(4.0, 0.0, 0.0, state_applies=True) == (4.0, False, None)


def test_negative_or_zero_rate_never_taxed():
    assert after_tax_rate(-2.0, 24.0, 9.0, state_applies=True) == (-2.0, False, None)
    assert after_tax_rate(0.0, 24.0, 9.0, state_applies=True) == (0.0, False, None)


def test_state_checkbox_follows_where_the_rate_came_from():
    # A Treasury shortcut button turns it off; typing a rate afterward turns it back on.
    assert state_tax_applies("treasury") is False
    assert state_tax_applies("typed") is True
