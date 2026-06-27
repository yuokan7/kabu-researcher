from pathlib import Path
from datetime import date, timedelta
import duckdb
import pandas as pd
import yfinance as yf


def _get_conn(db_path: str) -> duckdb.DuckDBPyConnection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(db_path)


def _ensure_price_table(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_prices (
            symbol VARCHAR,
            date DATE,
            close DOUBLE,
            PRIMARY KEY (symbol, date)
        )
    """)


def fetch_daily_close(
    symbol: str,
    start: date,
    end: date,
    db_path: str = "./data/cache.duckdb",
) -> pd.Series:
    """
    symbol の日次終値を返す pd.Series（index=date, name=symbol）。
    DuckDBにキャッシュされていない期間のみyfinanceで取得して補完する。
    """
    conn = _get_conn(db_path)
    _ensure_price_table(conn)

    cached = conn.execute(
        "SELECT date, close FROM daily_prices WHERE symbol = ? AND date BETWEEN ? AND ?",
        [symbol, start, end],
    ).df()

    cached_dates = set(pd.to_datetime(cached["date"]).dt.date) if not cached.empty else set()

    needed_start = start
    needed_end = end

    if cached_dates:
        # キャッシュの空白期間を検出して最小限のfetchに留める
        all_dates = set(
            pd.bdate_range(start=str(start), end=str(end)).date
        )
        missing = all_dates - cached_dates
        if not missing:
            series = cached.set_index("date")["close"].rename(symbol)
            series.index = pd.to_datetime(series.index)
            return series.sort_index()
        needed_start = min(missing)
        needed_end = max(missing)

    ticker = yf.Ticker(symbol)
    raw = ticker.history(
        start=str(needed_start),
        end=str(needed_end + timedelta(days=1)),
        auto_adjust=True,
    )["Close"].dropna()

    if not raw.empty:
        rows = [(symbol, d.date(), float(v)) for d, v in raw.items()]
        conn.executemany(
            "INSERT OR REPLACE INTO daily_prices VALUES (?, ?, ?)", rows
        )

    result = conn.execute(
        "SELECT date, close FROM daily_prices WHERE symbol = ? AND date BETWEEN ? AND ? ORDER BY date",
        [symbol, start, end],
    ).df()

    conn.close()

    if result.empty:
        return pd.Series([], name=symbol, dtype=float)

    series = result.set_index("date")["close"].rename(symbol)
    series.index = pd.to_datetime(series.index)
    return series.sort_index()
