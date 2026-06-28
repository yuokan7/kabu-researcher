from dataclasses import dataclass
from datetime import date, timedelta
import numpy as np
import pandas as pd


@dataclass
class MarketSignal:
    signal_date: date
    deviation_pct: float
    index_symbol: str


def calc_deviation(prices: pd.Series, window: int = 25) -> pd.Series:
    """
    乖離率 = (終値 - SMA(window)) / SMA(window) * 100
    SMAが計算できない先頭は NaN。
    """
    sma = prices.rolling(window=window, min_periods=window).mean()
    return (prices - sma) / sma * 100


def detect_fresh_touches(
    deviation: pd.Series,
    threshold_pct: float,
    fresh_touch_min_days: int,
) -> list[MarketSignal]:
    """
    乖離率系列から「フレッシュなタッチ」を検出して返す。

    フレッシュなタッチ = 乖離率が上から下へ閾値を初めてクロスした日、
    かつ直前のタッチから fresh_touch_min_days 以上経過している日。
    """
    signals: list[MarketSignal] = []
    last_touch_date: date | None = None
    prev_above = True  # 最初は閾値より上にいると仮定

    for ts, val in deviation.items():
        if pd.isna(val):
            continue

        currently_below = val <= threshold_pct

        # 上から下へのクロス検出
        if currently_below and prev_above:
            current_date = ts.date() if hasattr(ts, "date") else ts

            if last_touch_date is None or (current_date - last_touch_date).days >= fresh_touch_min_days:
                signals.append(
                    MarketSignal(
                        signal_date=current_date,
                        deviation_pct=float(val),
                        index_symbol=str(deviation.name or ""),
                    )
                )
                last_touch_date = current_date

        prev_above = not currently_below

    return signals


def calibrate_individual_threshold(
    symbol: str,
    lookback_years: int = 10,
    window: int = 25,
    base_percentile: float = 3.0,
    target_touch_min: int = 10,
    target_touch_max: int = 20,
    fresh_touch_min_days: int = 90,
    fallback: float = -10.0,
    db_path: str = "./data/cache.duckdb",
) -> float:
    """
    個別銘柄の「歴史的な買い場下限」を過去データから算出する。

    アルゴリズム:
    1. 過去 lookback_years 年の25日乖離率を計算
    2. 分布の下位 base_percentile% を初期閾値とする
    3. その閾値で3か月ルールを適用したとき 10〜20回タッチするか検証
    4. 範囲外ならパーセンタイルを調整して再試行
    5. それでも収まらなければ fallback を返す
    """
    from src.fetch import fetch_daily_close

    today = date.today()
    start = today - timedelta(days=int(lookback_years * 365.25) + 60)

    try:
        prices = fetch_daily_close(symbol=symbol, start=start, end=today, db_path=db_path)
    except Exception:
        return fallback

    if len(prices) < window * 20:  # 最低500日程度必要
        return fallback

    deviation = calc_deviation(prices, window=window)
    dev_clean = deviation.dropna()

    if len(dev_clean) < 100:
        return fallback

    dev_values = dev_clean.values

    # パーセンタイルの候補リスト（緩→厳の順で試す）
    percentiles = [base_percentile, 5.0, 7.0, 2.0, 1.0, 10.0, 0.5]

    for p in percentiles:
        threshold = float(np.percentile(dev_values, p))
        if threshold >= 0:
            continue  # 閾値がプラスは無意味
        signals = detect_fresh_touches(
            dev_clean, threshold_pct=threshold, fresh_touch_min_days=fresh_touch_min_days
        )
        if target_touch_min <= len(signals) <= target_touch_max:
            return round(threshold, 2)

    return fallback
