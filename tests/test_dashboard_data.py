import csv
import tempfile
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from src.config import load_config
from src.dashboard_data import (
    MarketStatus,
    WatchRow,
    classify_deviation,
    load_watchlist,
    build_market_status,
    build_watch_rows,
    build_dashboard_data,
)

YAML_PATH = Path(__file__).parent.parent / "conditions.yaml"


# --- classify_deviation ---

def test_classify_normal():
    assert classify_deviation(-5.0, -7.0, -10.0) == "normal"

def test_classify_warning_at_boundary():
    assert classify_deviation(-7.0, -7.0, -10.0) == "warning"

def test_classify_warning_between():
    assert classify_deviation(-8.5, -7.0, -10.0) == "warning"

def test_classify_danger_at_boundary():
    assert classify_deviation(-10.0, -7.0, -10.0) == "danger"

def test_classify_danger_below():
    assert classify_deviation(-12.0, -7.0, -10.0) == "danger"

def test_classify_no_data():
    assert classify_deviation(None, -7.0, -10.0) == "no_data"


# --- load_watchlist ---

def test_load_watchlist_normal():
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, encoding="utf-8", newline=""
    ) as f:
        writer = csv.DictWriter(f, fieldnames=["symbol", "name"])
        writer.writeheader()
        writer.writerow({"symbol": "3038.T", "name": "神戸物産"})
        writer.writerow({"symbol": "3064.T", "name": "MonotaRO"})
        path = f.name
    result = load_watchlist(path)
    assert result == [("3038.T", "神戸物産"), ("3064.T", "MonotaRO")]

def test_load_watchlist_file_not_found():
    result = load_watchlist("/nonexistent/path/pool.csv")
    assert result == []

def test_load_watchlist_ignores_extra_columns():
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, encoding="utf-8", newline=""
    ) as f:
        writer = csv.DictWriter(f, fieldnames=["symbol", "name", "revenue_growth"])
        writer.writeheader()
        writer.writerow({"symbol": "3038.T", "name": "神戸物産", "revenue_growth": "25"})
        path = f.name
    result = load_watchlist(path)
    assert result == [("3038.T", "神戸物産")]


# --- build_market_status (mock fetch_fn) ---

def _make_prices(values: list[float], end_date: str = "2020-03-10") -> pd.Series:
    idx = pd.bdate_range(end=end_date, periods=len(values))
    return pd.Series(values, index=idx, name="^N225")

def test_build_market_status_normal():
    cfg = load_config(YAML_PATH)
    prices = _make_prices([100.0] * 50)
    result = build_market_status(
        cfg,
        today=date(2020, 3, 10),
        fetch_fn=lambda symbol, start, end, db_path: prices,
    )
    assert result.status == "normal"
    assert isinstance(result.current_price, float)
    assert result.fresh_touch_fired is False

def test_build_market_status_danger():
    cfg = load_config(YAML_PATH)
    # 最後の値が SMA より 11% 以上低い → danger
    base = [100.0] * 49
    last = [88.0]
    prices = _make_prices(base + last)
    result = build_market_status(
        cfg,
        today=date(2020, 3, 10),
        fetch_fn=lambda symbol, start, end, db_path: prices,
    )
    assert result.status == "danger"

def test_build_market_status_insufficient_data():
    cfg = load_config(YAML_PATH)
    prices = _make_prices([100.0] * 10)  # window=25 未満
    result = build_market_status(
        cfg,
        today=date(2020, 3, 10),
        fetch_fn=lambda symbol, start, end, db_path: prices,
    )
    assert result.status == "no_data"
    assert result.fresh_touch_fired is False


# --- build_watch_rows ---

def test_build_watch_rows_sorted_deepest_first():
    cfg = load_config(YAML_PATH)
    watchlist = [("A.T", "A株"), ("B.T", "B株")]
    prices_a = _make_prices([100.0] * 49 + [96.0])   # 乖離率 ≈ -4% (normal)
    prices_b = _make_prices([100.0] * 49 + [88.0])   # 乖離率 ≈ -12% (danger)

    def mock_fetch(symbol, start, end, db_path):
        return prices_a if symbol == "A.T" else prices_b

    rows = build_watch_rows(watchlist, cfg, today=date(2020, 3, 10), fetch_fn=mock_fetch)
    assert len(rows) == 2
    assert rows[0].symbol == "B.T"   # より深い B が先頭
    assert rows[1].symbol == "A.T"

def test_build_watch_rows_no_data_at_end():
    cfg = load_config(YAML_PATH)
    watchlist = [("A.T", "A株"), ("BAD.T", "BAD株")]
    prices_a = _make_prices([100.0] * 50)

    def mock_fetch(symbol, start, end, db_path):
        if symbol == "A.T":
            return prices_a
        raise ValueError("fetch failed")

    rows = build_watch_rows(watchlist, cfg, today=date(2020, 3, 10), fetch_fn=mock_fetch)
    assert rows[-1].symbol == "BAD.T"
    assert rows[-1].status == "no_data"
    assert rows[-1].current_price is None

def test_build_watch_rows_empty_watchlist():
    cfg = load_config(YAML_PATH)
    rows = build_watch_rows(
        [],
        cfg,
        today=date(2020, 3, 10),
        fetch_fn=lambda symbol, start, end, db_path: pd.Series([], dtype=float),
    )
    assert rows == []


# --- build_dashboard_data (integration) ---

def test_build_dashboard_data_returns_correct_date():
    cfg = load_config(YAML_PATH)
    prices = _make_prices([100.0] * 50)
    today = date(2020, 3, 10)
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, encoding="utf-8", newline=""
    ) as f:
        writer = csv.DictWriter(f, fieldnames=["symbol", "name"])
        writer.writeheader()
        path = f.name

    data = build_dashboard_data(
        cfg,
        today=today,
        fetch_fn=lambda symbol, start, end, db_path: prices,
        pool_path=path,
    )
    assert data.as_of == today
    assert data.rows == []           # pool が空
    assert data.market.symbol == "^N225"
