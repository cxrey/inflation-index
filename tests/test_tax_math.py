"""Tests for the tax math with simple made-up brackets you can check by hand."""

import pytest

from calc import bracket_tax, federal_tax, marginal_rate, state_tax

# A made-up federal system: 10% to $10,000, 20% above; standard deduction
# $5,000; gains 0% to $20,000 of taxable income, 15% above; 3.8% over $50,000.
RULES = {
    "brackets": {"single": [[0, 0.10], [10_000, 0.20]]},
    "standard_deduction": {"single": 5_000},
    "gains_brackets": {"single": [[0, 0.0], [20_000, 0.15]]},
    "niit_rate": 0.038,
    "niit_threshold": {"single": 50_000},
}


def test_bracket_tax():
    # $15,000: 10% of 10,000 + 20% of 5,000 = 1,000 + 1,000 = 2,000.
    assert bracket_tax(15_000, RULES["brackets"]["single"]) == pytest.approx(2_000)
    assert bracket_tax(0, RULES["brackets"]["single"]) == 0


def test_federal_wages_only():
    # $20,000 wages: taxable 15,000 -> 2,000. $1,000 more interest: 20% bracket.
    assert federal_tax(20_000, 0, 0, "single", RULES) == pytest.approx(2_000)
    assert marginal_rate(lambda extra: federal_tax(20_000, 0, extra, "single", RULES)) == pytest.approx(20)


def test_interest_pushes_gains_into_a_higher_band():
    # Wages 10,000 + gains 15,000: taxable 20,000 = ordinary 5,000 + gains 15,000
    # (all gains below 20,000 -> 0%). $1,000 more interest: ordinary 6,000 (10%),
    # and $1,000 of gains moves above 20,000 (15%): 10% + 15% = 25%.
    assert marginal_rate(lambda extra: federal_tax(10_000, 15_000, extra, "single", RULES)) == pytest.approx(25)


def test_net_investment_income_tax():
    # Wages 60,000: income over 50,000, so interest also pays 3.8%: 20% + 3.8%.
    assert marginal_rate(lambda extra: federal_tax(60_000, 0, extra, "single", RULES)) == pytest.approx(23.8)


def test_state_tax():
    state = {"brackets": {"single": [[0, 0.05]], "married": [[0, 0.04]]},
             "standard_deduction": {"single": 2_000, "married": 4_000},
             "exemption": {"single": 1_000, "married": 2_000}}
    # Single $10,000: (10,000 − 2,000 − 1,000) × 5% = 350.
    assert state_tax(10_000, "single", state) == pytest.approx(350)
    # Head of household uses the single figures when the state has none.
    assert state_tax(10_000, "head", state) == pytest.approx(350)
    assert state_tax(10_000, "married", state) == pytest.approx(160)
    # No income tax: empty brackets.
    assert state_tax(10_000, "single", {"brackets": {"single": [], "married": []}}) == 0
