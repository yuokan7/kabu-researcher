"""
毎週実行されるpool自動更新スクリプト。
全上場銘柄を3層スクリーニングし、買いチャンスに近い順TOP10をpool.csvに書き出す。

使い方:
  python scripts/build_pool.py

環境変数（.envまたはGitHub Secrets）:
  JQUANTS_API_KEY  J-Quants V2 APIキー
"""
import os
import sys
from pathlib import Path
from datetime import date, timedelta

# プロジェクトルートをPYTHONPATHに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass  # GitHub Actions環境ではdotenvは不要

import pandas as pd

from src.config import load_config
from src.jquants import get_id_token, get_listed_stocks, get_all_statements_bulk
from src.fundamentals import filter_by_fundamentals
from src.trend import apply_trend_filter
from src.fetch import fetch_daily_close
from src.trigger import calc_deviation

_PROJECT_ROOT = Path(__file__).parent.parent
_CONFIG_PATH  = _PROJECT_ROOT / "conditions.yaml"
_POOL_PATH    = _PROJECT_ROOT / "out" / "pool.csv"
_TOP_N        = 10


def _get_current_deviation(symbol: str, db_path: str, window: int = 25) -> float | None:
    """銘柄の現在の25日乖離率を返す。取得失敗時はNone。"""
    try:
        today = date.today()
        start = today - timedelta(days=90)
        prices = fetch_daily_close(symbol=symbol, start=start, end=today, db_path=db_path)
        if len(prices) < window:
            return None
        dev = calc_deviation(prices, window=window)
        clean = dev.dropna()
        return float(clean.iloc[-1]) if not clean.empty else None
    except Exception:
        return None


def main() -> None:
    cfg     = load_config(_CONFIG_PATH)
    db_path = str(_PROJECT_ROOT / cfg.data_sources.cache_db.lstrip("./").lstrip(".\\"))

    print("=== pool自動更新 開始 ===")

    # Step 1: J-Quants認証
    print("\n[1/5] J-Quants認証...")
    try:
        id_token = get_id_token()
        print("  認証OK")
    except Exception as e:
        print(f"  [ERROR] 認証失敗: {e}")
        print("  既存のpool.csvを維持します")
        return

    # Step 2: 全上場銘柄取得
    print("\n[2/5] 全上場銘柄リスト取得...")
    markets = ["プライム", "スタンダード", "グロース"]
    stocks = get_listed_stocks(id_token, markets)
    print(f"  {len(stocks)}銘柄取得")

    # Step 3: 財務データ取得（日付ベース一括取得 — APIコール数を大幅削減）
    print("\n[3/5] 財務データ取得中（過去3年分を月次一括取得）...")
    names = {s.code: s.name for s in stocks}
    statements = get_all_statements_bulk(id_token, lookback_months=36, delay_sec=1.0)
    print(f"  取得完了（{len(statements)}銘柄分）")

    # Step 4a: 第1層 業績フィルタ
    # ─── デバッグ: 財務データの中身を確認 ───
    valid_count = sum(
        1 for stmts in statements.values()
        if any(s.net_sales is not None for s in stmts)
    )
    print(f"\n[DEBUG] 財務データあり銘柄: {valid_count}/{len(statements)}")
    for code, stmts in list(statements.items())[:3]:
        print(f"  [DEBUG] {code} ({names.get(code, '?')}): {len(stmts)}期")
        for s in stmts[-3:]:
            print(f"    period={s.period} sales={s.net_sales} income={s.net_income} cf={s.operating_cf}")
    # ─────────────────────────────────────

    print("\n[4a/5] 第1層: 業績フィルタ...")
    l1_passed = filter_by_fundamentals(
        statements=statements,
        names=names,
        min_revenue_yoy_pct=15.0,
        min_income_yoy_pct=15.0,
        consecutive_periods=3,
        require_positive_cf=True,
    )
    print(f"  {len(l1_passed)}銘柄通過")

    if not l1_passed:
        print("  [WARNING] 0銘柄通過。既存のpool.csvを維持します")
        return

    # Step 4b: 第2層 月足トレンドフィルタ
    print(f"\n[4b/5] 第2層: 月足トレンドフィルタ（{len(l1_passed)}銘柄）...")
    l2_passed = apply_trend_filter(
        candidates=l1_passed,
        ma_periods=[6, 12, 24],
        swing_window=3,
        min_swings=2,
        max_distance_pct=25.0,
        require_rising_slope=True,
        lookback_days=800,
        db_path=db_path,
    )
    print(f"  {len(l2_passed)}銘柄通過")

    if not l2_passed:
        print("  [WARNING] 0銘柄通過。既存のpool.csvを維持します")
        return

    # Step 5: 乖離率計算 → TOP10
    print(f"\n[5/5] 乖離率計算 → TOP{_TOP_N}選定...")
    rows = []
    for stock in l2_passed:
        dev = _get_current_deviation(stock.symbol, db_path)
        rows.append({
            "symbol": stock.symbol,
            "name": stock.name,
            "revenue_growth_pct": round(stock.revenue_growth_pct, 1),
            "net_income_growth_pct": round(stock.net_income_growth_pct, 1),
            "current_deviation_pct": round(dev, 2) if dev is not None else None,
        })

    # 乖離率深い順（None は末尾）、TOP10
    rows.sort(key=lambda r: (r["current_deviation_pct"] is None, r["current_deviation_pct"] or 0.0))
    top10 = rows[:_TOP_N]

    # pool.csv 書き出し
    df = pd.DataFrame(top10)
    _POOL_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(_POOL_PATH, index=False, encoding="utf-8")

    print(f"\n=== 完了: {len(top10)}銘柄を pool.csv に書き出しました ===")
    for r in top10:
        dev_str = f"{r['current_deviation_pct']:+.2f}%" if r["current_deviation_pct"] is not None else "—"
        print(f"  {r['symbol']} {r['name']}  売上+{r['revenue_growth_pct']}%  利益+{r['net_income_growth_pct']}%  乖離率{dev_str}")


if __name__ == "__main__":
    main()
