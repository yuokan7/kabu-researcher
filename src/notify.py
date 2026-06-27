import csv
from pathlib import Path
from src.trigger import MarketSignal


def format_console_line(signal: MarketSignal) -> str:
    return (
        f"[シグナル] {signal.signal_date}  {signal.index_symbol}"
        f"  乖離率: {signal.deviation_pct:.2f}%"
        f"  ← 3か月ぶりの閾値タッチ"
    )


def print_signals(signals: list[MarketSignal]) -> None:
    if not signals:
        print("[情報] 本日は発火シグナルなし")
        return
    for sig in signals:
        print(format_console_line(sig))


def write_csv(signals: list[MarketSignal], path: Path | str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["signal_date", "symbol", "deviation_pct"])
        writer.writeheader()
        for sig in signals:
            writer.writerow(
                {
                    "signal_date": str(sig.signal_date),
                    "symbol": sig.index_symbol,
                    "deviation_pct": f"{sig.deviation_pct:.4f}",
                }
            )
