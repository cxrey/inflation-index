"""Tests for "Estimate my tax rates" with the real 2026 tax rules (rates in %)."""

import pytest

from calc import can_compare, compare_states, estimate_tax_rates, selected_state_rate, tax_rules_note
from tax_rules import TAX_RULES


def rates(status, state, wages, gains=0, local=None):
    return estimate_tax_rates(status, state, local, wages, gains, TAX_RULES)


def test_federal_rates():
    # Single, $100,000 wages: taxable 100,000 − 16,100 = 83,900, in the 22% bracket (50,400–105,700).
    assert rates("single", "Texas", 100_000) == pytest.approx((22, 0))
    # Single, $250,000: taxable 233,900, 32% bracket (201,775–256,225), plus 3.8%
    # Net Investment Income Tax because income is over $200,000: 35.8%.
    assert rates("single", "Texas", 250_000)[0] == pytest.approx(35.8)
    # Single, $150,000 wages + $80,000 dividends and gains: wages taxable 133,900, 24% bracket;
    # the gains above it stay in the 15% band; income 230,000 is over $200,000: 24% + 3.8% = 27.8%.
    assert rates("single", "Texas", 150_000, gains=80_000)[0] == pytest.approx(27.8)
    # Married filing jointly, $150,000: taxable 117,800, 22% bracket (100,800–211,400); no state tax.
    assert rates("married", "Texas", 150_000) == pytest.approx((22, 0))


def test_state_rates():
    # California single $100,000: 100,000 − 5,706 = 94,294, in the 9.3% bracket (72,724–371,479).
    assert rates("single", "California", 100_000)[1] == pytest.approx(9.3)
    assert rates("single", "Texas", 100_000)[1] == 0


def test_new_york_city_and_yonkers():
    # Single $100,000: New York taxable 100,000 − 8,000 = 92,000: state 5.9% (80,650–215,400)
    # and NYC 3.876% (over $50,000, from the official NYC rate schedule): 9.776%.
    assert rates("single", "New York", 100_000)[1] == pytest.approx(5.9)
    assert rates("single", "New York", 100_000, local="New York City")[1] == pytest.approx(9.776)
    # Yonkers: 5.9% plus 16.75% of it = 6.88825%.
    assert rates("single", "New York", 100_000, local="Yonkers")[1] == pytest.approx(5.9 * 1.1675)


def test_compare_all_states():
    table = compare_states("single", 100_000, 0, 4.0, True, TAX_RULES)
    assert len(table) == 53  # 50 states + DC, with New York three times
    names = table["State"].tolist()
    assert "New York (New York City)" in names and "New York (Yonkers)" in names
    assert "Maryland + county tax (2.25–3.30%)" in names
    assert "Indiana + county tax (0.50–3.00%)" in names
    # The New York City row: state plus city rate.
    nyc = table.set_index("State").loc["New York (New York City)"]
    assert nyc["State rate (%)"] == pytest.approx(5.9 + 3.876)
    # California: 4% × (1 − 0.22 − 0.093) = 2.748%.
    assert table.set_index("State").loc["California", "Keeps after tax (%)"] == pytest.approx(2.748)


def test_compare_with_state_tax_off_and_without_your_rate():
    # State tax off (Treasury interest): "keeps after tax" is the same in every state, 4% × 0.78.
    table = compare_states("single", 100_000, 0, 4.0, False, TAX_RULES)
    assert table["Keeps after tax (%)"].tolist() == pytest.approx([3.12] * 53)
    # No "Your rate": no such column.
    assert "Keeps after tax (%)" not in compare_states("single", 100_000, 0, None, True, TAX_RULES)


def test_compare_needs_wages():
    assert not can_compare(None) and not can_compare(0)
    assert can_compare(50_000)


def test_out_of_date_warning():
    assert tax_rules_note(2026, 2026) is None
    assert tax_rules_note(2027, 2026) == "Tax rules are from 2026; this year's may differ."


def test_selecting_a_row_fills_the_state_box():
    table = compare_states("single", 100_000, 0, None, True, TAX_RULES)
    nyc_row = table.index[table["State"] == "New York (New York City)"][0]
    assert selected_state_rate(table, [nyc_row]) == pytest.approx(5.9 + 3.876)
    assert selected_state_rate(table, []) is None  # nothing selected


def test_georgia_and_south_carolina_2026_laws():
    # Georgia: flat 4.99% (H.B. 463). South Carolina single $100,000: 100,000 − 15,000 = 85,000,
    # over $30,000, so 5.21% (H. 4216). Below $30,000 of taxable income: 1.99%.
    assert rates("single", "Georgia", 100_000)[1] == pytest.approx(4.99)
    assert rates("single", "South Carolina", 100_000)[1] == pytest.approx(5.21)
    assert rates("single", "South Carolina", 40_000)[1] == pytest.approx(1.99)  # 40,000 − 15,000 = 25,000
