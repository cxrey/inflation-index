"""Tests for the 10-year Treasury price index, using numbers you can check by hand."""

import pandas as pd
import pytest

from calc import bond_price, treasury_index


def yields(values: list[float], start: str = "1953-04-01") -> pd.DataFrame:
    """Monthly yields in % (columns date, value) from `start`."""
    return pd.DataFrame({"date": pd.date_range(start, periods=len(values), freq="MS"), "value": values})


def test_bond_price():
    # c = 4%, y = 5%, T = 10: 1.025 ^ 20 = 1.638616, so 0.8 × (1 − 0.610271) + 0.610271 = 0.922054.
    assert bond_price(0.04, 0.05, 10) == pytest.approx(0.922054, abs=1e-6)
    # Yield equal to the coupon: exactly $1.
    assert bond_price(0.05, 0.05, 119 / 12) == 1.0
    # Yield below the coupon: above $1.
    assert bond_price(0.05, 0.04, 119 / 12) > 1


def test_unchanged_yields_keep_the_index_at_100():
    # 4.00% for 13 months (12 monthly steps): every month's price is exactly 1.
    index = treasury_index(yields([4.0] * 13))
    assert index["value"].tolist() == [100.0] * 13
    assert index["date"].iloc[0] == pd.Timestamp("1953-04-01")


def test_yield_rise_then_flat():
    # 4% then 5%: the bond bought at 4% is worth 0.922558 with 10 years minus
    # 1 month left (1.025 ^ −19.8333 = 0.612788; 0.8 + 0.2 × 0.612788 = 0.922558),
    # so the index falls to 92.2558.
    # Then 5% again: the new bond pays 5%, price 1, the index stays at 92.2558.
    index = treasury_index(yields([4.0, 5.0, 5.0]))["value"]
    assert index.tolist() == pytest.approx([100, 92.2558, 92.2558], abs=1e-4)


def test_gap_in_yields_is_an_error():
    table = yields([4.0, 4.0, 4.0]).drop(index=1)  # May 1953 missing
    with pytest.raises(ValueError, match="gap before June 1953"):
        treasury_index(table)
