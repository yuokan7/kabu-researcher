import pandas as pd
import pytest
from src.trend import (
    resample_monthly,
    calc_monthly_smas,
    check_perfect_order,
    check_higher_highs_lows,
    check_alltime_high_proximity,
)


def _monthly(values: list[float], start: str = "2022-01") -> pd.Series:
    idx = pd.date_range(start=start, periods=len(values), freq="ME")
    return pd.Series(values, index=idx)


# --- calc_monthly_smas ---

def test_calc_monthly_smas_returns_three_series():
    prices = _monthly([100.0] * 30)
    smas = calc_monthly_smas(prices, periods=[6, 12, 24])
    assert set(smas.keys()) == {6, 12, 24}
    assert len(smas[6].dropna()) == 25  # 30 - 6 + 1


# --- check_perfect_order ---

def test_check_perfect_order_true_when_aligned():
    # SMA6 > SMA12 > SMA24 かつ全SMA上向きになる上昇系列
    prices = _monthly([float(i * 10 + 100) for i in range(30)])
    smas = calc_monthly_smas(prices, periods=[6, 12, 24])
    assert check_perfect_order(prices, smas, require_rising_slope=True) is True

def test_check_perfect_order_false_when_declining():
    # 下降トレンド
    prices = _monthly([float(300 - i * 5) for i in range(30)])
    smas = calc_monthly_smas(prices, periods=[6, 12, 24])
    assert check_perfect_order(prices, smas, require_rising_slope=True) is False


# --- check_higher_highs_lows ---

def test_check_higher_highs_lows_true():
    # 明確な切り上げ波形
    vals = [100, 110, 105, 115, 108, 120, 112, 130]
    prices = _monthly([float(v) for v in vals])
    assert check_higher_highs_lows(prices, swing_window=2, min_swings=2) is True

def test_check_higher_highs_lows_false_when_lower_low():
    # 安値が切り下がっている
    vals = [100, 110, 90, 115, 80, 120]
    prices = _monthly([float(v) for v in vals])
    assert check_higher_highs_lows(prices, swing_window=2, min_swings=2) is False


# --- check_alltime_high_proximity ---

def test_check_alltime_high_proximity_within_range():
    prices = _monthly([100.0] * 20 + [120.0, 115.0])  # 高値120に対し現在115 = 約4%以内
    assert check_alltime_high_proximity(prices, max_distance_pct=25.0) is True

def test_check_alltime_high_proximity_too_far():
    prices = _monthly([100.0] * 20 + [200.0, 100.0])  # 高値200に対し現在100 = 50%離れている
    assert check_alltime_high_proximity(prices, max_distance_pct=25.0) is False
