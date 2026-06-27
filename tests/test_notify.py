import csv
import io
from datetime import date
from pathlib import Path
import tempfile
import pytest
from src.trigger import MarketSignal
from src.notify import format_console_line, write_csv


def _make_signal(d: str = "2020-03-09", pct: float = -10.5) -> MarketSignal:
    return MarketSignal(
        signal_date=date.fromisoformat(d),
        deviation_pct=pct,
        index_symbol="^N225",
    )


def test_format_console_line_contains_date():
    sig = _make_signal()
    line = format_console_line(sig)
    assert "2020-03-09" in line


def test_format_console_line_contains_deviation():
    sig = _make_signal(pct=-10.5)
    line = format_console_line(sig)
    assert "-10.5" in line or "-10.50" in line


def test_format_console_line_contains_symbol():
    sig = _make_signal()
    line = format_console_line(sig)
    assert "N225" in line


def test_write_csv_creates_file():
    signals = [_make_signal("2020-03-09", -10.5), _make_signal("2016-01-20", -11.2)]
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "out" / "candidates.csv"
        write_csv(signals, path)
        assert path.exists()
        rows = list(csv.DictReader(open(path, encoding="utf-8")))
        assert len(rows) == 2
        assert rows[0]["signal_date"] == "2020-03-09"
        assert rows[0]["symbol"] == "^N225"


def test_write_csv_empty_signals():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "candidates.csv"
        write_csv([], path)
        assert path.exists()
        rows = list(csv.DictReader(open(path, encoding="utf-8")))
        assert len(rows) == 0
