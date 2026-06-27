from dataclasses import dataclass
from datetime import date
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
