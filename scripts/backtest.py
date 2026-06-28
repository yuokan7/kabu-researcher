"""
バックテスト: 2010年〜現在の日経シグナルで仮想売買し、1年後リターンを集計する。

使い方:
  python scripts/backtest.py

出力:
  out/backtest.csv  … 全トレードの詳細
  コンソールにサマリーを表示
"""
import sys
from pathlib import Path
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

import pandas as pd

from src.config import load_config
from src.fetch import fetch_daily_close
from src.trigger import calc_deviation, detect_fresh_touches

_PROJECT_ROOT = Path(__file__).parent.parent
_CONFIG_PATH  = _PROJECT_ROOT / "conditions.yaml"
_POOL_PATH    = _PROJECT_ROOT / "out" / "pool.csv"
_OUT_PATH     = _PROJECT_ROOT / "out" / "backtest.csv"

HOLD_DAYS     = 365   # 保有期間（1年固定）
BACKTEST_FROM = date(2010, 1, 1)


def _nearest_price(prices: pd.Series, target: date) -> float | None:
    """ターゲット日付に最も近い取引日の株価を返す（±10営業日以内）。"""
    ts = pd.Timestamp(target)
    for delta in range(0, 15):
        for sign in [0, 1, -1]:
            d = ts + pd.Timedelta(days=delta * sign)
            if d in prices.index:
                return float(prices.loc[d])
    return None


def main() -> None:
    cfg = load_config(_CONFIG_PATH)
    db_path = str(_PROJECT_ROOT / cfg.data_sources.cache_db.lstrip("./").lstrip(".\\"))

    # pool.csv から銘柄リストを取得
    if not _POOL_PATH.exists():
        print("[ERROR] out/pool.csv が見つかりません。先に build_pool を実行してください。")
        return
    pool = pd.read_csv(_POOL_PATH)
    symbols = list(pool["symbol"])
    names   = dict(zip(pool["symbol"], pool["name"]))
    print(f"対象銘柄: {len(symbols)}銘柄 / {', '.join(symbols)}")

    # ─── 日経225のシグナル日を取得 ────────────────────────────
    today  = date.today()
    print(f"\n日経225データ取得中 ({BACKTEST_FROM} 〜 {today})...")
    nikkei = fetch_daily_close("^N225", start=BACKTEST_FROM, end=today, db_path=db_path)
    nikkei_dev = calc_deviation(nikkei, window=cfg.trigger.deviation_window)
    signals = detect_fresh_touches(
        nikkei_dev,
        threshold_pct=cfg.trigger.market.threshold_pct,
        fresh_touch_min_days=cfg.trigger.market.fresh_touch_min_days,
    )
    print(f"シグナル検出: {len(signals)}回")
    for s in signals:
        print(f"  {s.signal_date}  日経乖離率: {s.deviation_pct:.2f}%")

    if not signals:
        print("シグナルが0件のため終了します。")
        return

    # ─── 各銘柄の10年分価格データを取得 ─────────────────────
    print("\n個別株データ取得中...")
    stock_prices: dict[str, pd.Series] = {}
    for symbol in symbols:
        prices = fetch_daily_close(symbol, start=BACKTEST_FROM, end=today, db_path=db_path)
        stock_prices[symbol] = prices
        print(f"  {symbol}: {len(prices)}日分")

    # ─── 仮想売買 ─────────────────────────────────────────────
    print("\n仮想売買シミュレーション中...")
    records = []
    for sig in signals:
        buy_date  = sig.signal_date
        sell_date = buy_date + timedelta(days=HOLD_DAYS)
        if sell_date > today:
            print(f"  {buy_date}: 売却日({sell_date})が未来のためスキップ")
            continue

        for symbol in symbols:
            prices = stock_prices.get(symbol)
            if prices is None or len(prices) == 0:
                continue

            buy_price  = _nearest_price(prices, buy_date)
            sell_price = _nearest_price(prices, sell_date)

            if buy_price is None or sell_price is None or buy_price == 0:
                continue

            ret_pct    = (sell_price - buy_price) / buy_price * 100
            profit_100 = (sell_price - buy_price) * 100  # 100株あたり損益

            records.append({
                "signal_date":  str(buy_date),
                "nikkei_dev":   round(sig.deviation_pct, 2),
                "symbol":       symbol,
                "name":         names.get(symbol, ""),
                "buy_price":    round(buy_price, 0),
                "sell_price":   round(sell_price, 0),
                "return_pct":   round(ret_pct, 2),
                "profit_100":   round(profit_100, 0),
                "hold_days":    HOLD_DAYS,
            })

    if not records:
        print("有効なトレードが0件でした。")
        return

    df = pd.DataFrame(records)
    df.to_csv(_OUT_PATH, index=False, encoding="utf-8")

    # ─── サマリー出力 ─────────────────────────────────────────
    total      = len(df)
    wins       = (df["return_pct"] > 0).sum()
    win_rate   = wins / total * 100
    avg_ret    = df["return_pct"].mean()
    median_ret = df["return_pct"].median()
    best       = df.loc[df["return_pct"].idxmax()]
    worst      = df.loc[df["return_pct"].idxmin()]
    avg_profit = df["profit_100"].mean()

    print("\n" + "=" * 55)
    print(f"  バックテスト結果（{BACKTEST_FROM} 〜 {today}）")
    print(f"  売買条件: 日経{cfg.trigger.market.threshold_pct:.0f}%タッチで買い → {HOLD_DAYS}日後売り")
    print("=" * 55)
    print(f"  総トレード数    : {total}回")
    print(f"  勝率            : {win_rate:.1f}%  （{wins}勝 {total - wins}敗）")
    print(f"  平均リターン    : {avg_ret:+.1f}%")
    print(f"  中央値リターン  : {median_ret:+.1f}%")
    print(f"  100株平均損益   : {'+' if avg_profit >= 0 else ''}{avg_profit:,.0f}円")
    print(f"  最高トレード    : {best['name']}({best['signal_date']}) {best['return_pct']:+.1f}%")
    print(f"  最悪トレード    : {worst['name']}({worst['signal_date']}) {worst['return_pct']:+.1f}%")
    print("=" * 55)

    print("\nシグナル別サマリー:")
    for sig_date, grp in df.groupby("signal_date"):
        avg = grp["return_pct"].mean()
        w   = (grp["return_pct"] > 0).sum()
        print(f"  {sig_date}  平均{avg:+.1f}%  ({w}/{len(grp)}勝)")

    print(f"\n詳細は {_OUT_PATH} に保存しました。")


if __name__ == "__main__":
    main()
