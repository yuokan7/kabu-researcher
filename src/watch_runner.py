"""
/watch コマンドの実処理。
日経225の乖離率を算出し、フレッシュタッチを検出して通知する。
"""
from datetime import date, timedelta
from pathlib import Path

from src.config import load_config
from src.fetch import fetch_daily_close
from src.trigger import calc_deviation, detect_fresh_touches
from src.notify import print_signals, write_csv

_PROJECT_ROOT = Path(__file__).parent.parent


def _resolve_path(raw: str) -> Path:
    p = Path(raw)
    if p.is_absolute():
        return p
    return _PROJECT_ROOT / raw.lstrip("./").lstrip(".\\")


def run_watch(
    config_path: str | Path | None = None,
    lookback_days: int = 400,
    today: date | None = None,
) -> None:
    config_path = Path(config_path) if config_path else _PROJECT_ROOT / "conditions.yaml"
    cfg = load_config(config_path)
    today = today or date.today()
    start = today - timedelta(days=lookback_days)

    symbol = cfg.trigger.market.index_symbol
    threshold = cfg.trigger.market.threshold_pct
    fresh_days = cfg.trigger.market.fresh_touch_min_days
    window = cfg.trigger.deviation_window
    db_path = _resolve_path(cfg.data_sources.cache_db)
    csv_path = _resolve_path(cfg.output.csv_path)

    print(f"[watch] {symbol} の終値を取得中... ({start} 〜 {today})")
    prices = fetch_daily_close(
        symbol=symbol,
        start=start,
        end=today,
        db_path=str(db_path),
    )

    if len(prices) < window:
        print(f"[エラー] データ不足: {len(prices)}件（{window}件必要）")
        return

    deviation = calc_deviation(prices, window=window)
    signals = detect_fresh_touches(deviation, threshold_pct=threshold, fresh_touch_min_days=fresh_days)

    print(f"[watch] 検出シグナル数: {len(signals)}")
    print_signals(signals)

    if "csv" in cfg.output.format:
        write_csv(signals, csv_path)
        print(f"[watch] CSV出力: {csv_path}")


if __name__ == "__main__":
    run_watch()
