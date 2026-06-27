import pandas as pd
import pytest
from src.trigger import calc_deviation, detect_fresh_touches, MarketSignal


def _make_series(values: list[float], start: str = "2020-01-02") -> pd.Series:
    idx = pd.bdate_range(start=start, periods=len(values))
    return pd.Series(values, index=idx, name="^N225")


def test_calc_deviation_flat_series():
    # 全値が同じなら乖離率は0
    prices = _make_series([100.0] * 30)
    dev = calc_deviation(prices, window=25)
    assert (dev.dropna().abs() < 1e-10).all()


def test_calc_deviation_above_sma():
    # 最後の値がSMAより上なら正の乖離率
    prices = _make_series([100.0] * 24 + [120.0])
    dev = calc_deviation(prices, window=25)
    assert dev.iloc[-1] > 0


def test_calc_deviation_below_sma():
    # 最後の値がSMAより下なら負の乖離率
    prices = _make_series([100.0] * 24 + [80.0])
    dev = calc_deviation(prices, window=25)
    assert dev.iloc[-1] < 0


def test_detect_no_touch_when_above_threshold():
    # 乖離率が-10%以上なら発火しない
    dev = pd.Series([-5.0, -4.0, -3.0], index=pd.bdate_range("2020-01-02", periods=3))
    signals = detect_fresh_touches(dev, threshold_pct=-10.0, fresh_touch_min_days=90)
    assert len(signals) == 0


def test_detect_touch_on_first_cross():
    # -10%を初めて下回る日をシグナルとして検出
    values = [-5.0] * 10 + [-11.0]  # 11日目に初タッチ
    idx = pd.bdate_range("2020-01-02", periods=11)
    dev = pd.Series(values, index=idx)
    signals = detect_fresh_touches(dev, threshold_pct=-10.0, fresh_touch_min_days=90)
    assert len(signals) == 1
    assert isinstance(signals[0], MarketSignal)
    assert signals[0].deviation_pct == pytest.approx(-11.0)


def test_detect_no_second_touch_within_90_days():
    # 2回目のタッチが90日以内なら無視
    values = [-5.0] * 5 + [-11.0] + [-5.0] * 3 + [-12.0]  # 10日目に2回目
    idx = pd.bdate_range("2020-01-02", periods=10)
    dev = pd.Series(values, index=idx)
    signals = detect_fresh_touches(dev, threshold_pct=-10.0, fresh_touch_min_days=90)
    assert len(signals) == 1


def test_detect_second_touch_after_90_days():
    # 2回目のタッチが90日超なら有効
    first = pd.bdate_range("2020-01-02", periods=1)
    gap = pd.bdate_range("2020-01-03", periods=90)
    second = pd.bdate_range("2020-06-01", periods=1)
    idx = first.union(gap).union(second)
    values = [-11.0] + [-5.0] * 90 + [-12.0]
    dev = pd.Series(values, index=idx)
    signals = detect_fresh_touches(dev, threshold_pct=-10.0, fresh_touch_min_days=90)
    assert len(signals) == 2


def test_known_nikkei_dates():
    """
    仕様書の検証日付: 日経-10%基準で 2016-01-20, 2018-12-25, 2020-03-09 が抽出されること。
    このテストはネットワーク不要のフィクスチャデータ版は省略し、
    integration テストとして別途 /watch コマンドで確認する。
    """
    pass  # integration確認はTask 6で実施
