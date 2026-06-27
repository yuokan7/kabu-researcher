import pandas as pd
from datetime import date, timedelta
from src.fundamentals import FundamentalResult
from src.fetch import fetch_daily_close


def resample_monthly(daily: pd.Series) -> pd.Series:
    """日足を月末終値にリサンプルする。"""
    return daily.resample("ME").last().dropna()


def calc_monthly_smas(monthly: pd.Series, periods: list[int]) -> dict[int, pd.Series]:
    """月足SMAsを計算して辞書で返す。"""
    return {
        p: monthly.rolling(window=p, min_periods=p).mean()
        for p in periods
    }


def check_perfect_order(
    monthly: pd.Series,
    smas: dict[int, pd.Series],
    require_rising_slope: bool = True,
) -> bool:
    """
    パーフェクトオーダー判定。
    SMA短 > SMA中 > SMA長 かつ 終値 > SMA短 かつ（オプション）全SMA上向き。
    """
    periods = sorted(smas.keys())
    if len(periods) < 2:
        return False

    latest_smas = {}
    for p in periods:
        clean = smas[p].dropna()
        if len(clean) < 2:
            return False
        latest_smas[p] = clean

    last_vals = {p: latest_smas[p].iloc[-1] for p in periods}
    last_close = monthly.iloc[-1]

    # 終値 > SMA短期
    short = periods[0]
    if last_close <= last_vals[short]:
        return False

    # SMA短 > SMA中 > SMA長
    for i in range(len(periods) - 1):
        if last_vals[periods[i]] <= last_vals[periods[i + 1]]:
            return False

    # 全SMA上向き（前月比プラス）
    if require_rising_slope:
        for p in periods:
            s = latest_smas[p]
            if s.iloc[-1] <= s.iloc[-2]:
                return False

    return True


def check_higher_highs_lows(
    monthly: pd.Series,
    swing_window: int = 3,
    min_swings: int = 2,
) -> bool:
    """
    高値・安値の切り上げ判定。
    局所的な高値・安値がそれぞれ単調増加していればTrue。
    """
    if len(monthly) < swing_window * 2 + 1:
        return False

    highs, lows = [], []
    arr = monthly.values
    w = swing_window

    # swing_window 月分の窓で局所高値・安値を検出
    for i in range(w, len(arr) - w):
        window = arr[i - w: i + w + 1]
        if arr[i] == max(window):
            highs.append(arr[i])
        if arr[i] == min(window):
            lows.append(arr[i])

    if len(highs) < min_swings or len(lows) < min_swings:
        return False

    recent_highs = highs[-min_swings:]
    recent_lows  = lows[-min_swings:]

    return all(recent_highs[i] < recent_highs[i + 1] for i in range(len(recent_highs) - 1)) and \
           all(recent_lows[i]  < recent_lows[i + 1]  for i in range(len(recent_lows) - 1))


def check_alltime_high_proximity(
    monthly: pd.Series,
    max_distance_pct: float = 25.0,
) -> bool:
    """上場来高値から max_distance_pct% 以内にいればTrue。"""
    if monthly.empty:
        return False
    alltime_high = float(monthly.max())
    current      = float(monthly.iloc[-1])
    distance_pct = (alltime_high - current) / alltime_high * 100
    return bool(distance_pct <= max_distance_pct)


def apply_trend_filter(
    candidates: list[FundamentalResult],
    ma_periods: list[int],
    swing_window: int,
    min_swings: int,
    max_distance_pct: float,
    require_rising_slope: bool,
    lookback_days: int = 800,
    db_path: str = "./data/cache.duckdb",
) -> list[FundamentalResult]:
    """
    第1層通過銘柄に月足トレンドフィルタを適用して通過した銘柄リストを返す。
    """
    today = date.today()
    start = today - timedelta(days=lookback_days)
    passed = []

    for i, stock in enumerate(candidates):
        if i > 0 and i % 50 == 0:
            print(f"  トレンドフィルタ中... {i}/{len(candidates)}")
        try:
            daily = fetch_daily_close(
                symbol=stock.symbol,
                start=start,
                end=today,
                db_path=db_path,
            )
            if len(daily) < max(ma_periods) * 22:  # 月足 SMA最長期 × 約22営業日
                continue

            monthly = resample_monthly(daily)
            if len(monthly) < max(ma_periods) + 1:
                continue

            smas = calc_monthly_smas(monthly, periods=ma_periods)

            if not check_perfect_order(monthly, smas, require_rising_slope=require_rising_slope):
                continue
            if not check_higher_highs_lows(monthly, swing_window=swing_window, min_swings=min_swings):
                continue
            if not check_alltime_high_proximity(monthly, max_distance_pct=max_distance_pct):
                continue

            passed.append(stock)
        except Exception as e:
            print(f"  {stock.symbol} スキップ: {e}")
            continue

    return passed
