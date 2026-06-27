import logging
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

_logger = logging.getLogger(__name__)

import pandas as pd

from src.config import ScreenerConfig
from src.fetch import fetch_daily_close
from src.trigger import calc_deviation, detect_fresh_touches

_PROJECT_ROOT = Path(__file__).parent.parent


def _resolve(raw: str) -> Path:
    p = Path(raw)
    return p if p.is_absolute() else _PROJECT_ROOT / raw.lstrip("./").lstrip(".\\")


@dataclass
class MarketStatus:
    symbol: str
    current_price: float | None
    current_deviation_pct: float | None
    status: str  # "normal" | "warning" | "danger" | "no_data"
    fresh_touch_fired: bool
    last_signal_date: date | None


@dataclass
class WatchRow:
    symbol: str
    name: str
    current_price: float | None
    current_deviation_pct: float | None
    status: str  # "normal" | "warning" | "danger" | "no_data"


@dataclass
class DashboardData:
    market: MarketStatus
    rows: list[WatchRow]
    as_of: date


def classify_deviation(
    deviation_pct: float | None,
    warning: float,
    danger: float,
) -> str:
    if deviation_pct is None:
        return "no_data"
    if deviation_pct <= danger:
        return "danger"
    if deviation_pct <= warning:
        return "warning"
    return "normal"


def load_watchlist(pool_path: str | Path) -> list[tuple[str, str]]:
    path = Path(pool_path)
    if not path.exists():
        return []
    df = pd.read_csv(path, usecols=["symbol", "name"])
    return list(zip(df["symbol"], df["name"]))


def build_market_status(
    cfg: ScreenerConfig,
    today: date,
    fetch_fn=fetch_daily_close,
) -> MarketStatus:
    symbol = cfg.trigger.market.index_symbol
    window = cfg.trigger.deviation_window
    threshold = cfg.trigger.market.threshold_pct
    fresh_days = cfg.trigger.market.fresh_touch_min_days
    highlight_days = cfg.dashboard.fresh_touch_highlight_days
    db_path = str(_resolve(cfg.data_sources.cache_db))
    start = today - timedelta(days=cfg.dashboard.price_lookback_days + window * 3)

    prices = fetch_fn(symbol=symbol, start=start, end=today, db_path=db_path)

    if len(prices) < window:
        return MarketStatus(
            symbol=symbol,
            current_price=None,
            current_deviation_pct=None,
            status="no_data",
            fresh_touch_fired=False,
            last_signal_date=None,
        )

    deviation = calc_deviation(prices, window=window)
    current_price = float(prices.iloc[-1])
    dev_clean = deviation.dropna()
    current_dev = float(dev_clean.iloc[-1]) if not dev_clean.empty else None
    status = classify_deviation(
        current_dev,
        cfg.dashboard.warning_deviation_pct,
        cfg.dashboard.danger_deviation_pct,
    )

    signals = detect_fresh_touches(
        deviation, threshold_pct=threshold, fresh_touch_min_days=fresh_days
    )
    last_signal_date = signals[-1].signal_date if signals else None
    fresh_touch_fired = (
        last_signal_date is not None
        and (today - last_signal_date).days <= highlight_days
    )

    return MarketStatus(
        symbol=symbol,
        current_price=current_price,
        current_deviation_pct=current_dev,
        status=status,
        fresh_touch_fired=fresh_touch_fired,
        last_signal_date=last_signal_date,
    )


def build_watch_rows(
    watchlist: list[tuple[str, str]],
    cfg: ScreenerConfig,
    today: date,
    fetch_fn=fetch_daily_close,
) -> list[WatchRow]:
    window = cfg.trigger.deviation_window
    db_path = str(_resolve(cfg.data_sources.cache_db))
    start = today - timedelta(days=cfg.dashboard.price_lookback_days + window * 3)

    rows: list[WatchRow] = []
    for symbol, name in watchlist:
        try:
            prices = fetch_fn(symbol=symbol, start=start, end=today, db_path=db_path)
            if len(prices) < window:
                rows.append(WatchRow(
                    symbol=symbol, name=name,
                    current_price=None, current_deviation_pct=None, status="no_data",
                ))
                continue
            deviation = calc_deviation(prices, window=window)
            current_price = float(prices.iloc[-1])
            dev_clean = deviation.dropna()
            current_dev = float(dev_clean.iloc[-1]) if not dev_clean.empty else None
            status = classify_deviation(
                current_dev,
                cfg.dashboard.warning_deviation_pct,
                cfg.dashboard.danger_deviation_pct,
            )
            rows.append(WatchRow(
                symbol=symbol, name=name,
                current_price=current_price,
                current_deviation_pct=current_dev,
                status=status,
            ))
        except Exception:
            _logger.warning("fetch failed for %s", symbol, exc_info=True)
            rows.append(WatchRow(
                symbol=symbol, name=name,
                current_price=None, current_deviation_pct=None, status="no_data",
            ))

    rows.sort(key=lambda r: (r.current_deviation_pct is None, r.current_deviation_pct or 0.0))
    return rows


def build_dashboard_data(
    cfg: ScreenerConfig,
    today: date | None = None,
    fetch_fn=fetch_daily_close,
    pool_path: str | Path | None = None,
) -> DashboardData:
    today = today or date.today()
    pool = _resolve(cfg.output.pool_path) if pool_path is None else Path(pool_path)
    market = build_market_status(cfg, today, fetch_fn)
    watchlist = load_watchlist(pool)
    rows = build_watch_rows(watchlist, cfg, today, fetch_fn)
    return DashboardData(market=market, rows=rows, as_of=today)
