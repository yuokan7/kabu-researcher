# Phase 2a: pool自動更新 実装プラン

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 毎週土曜0:00 JSTにGitHub Actionsが全上場銘柄をスクリーニングし、買いチャンスに近い順TOP10をpool.csvに自動更新する

**Architecture:** J-Quantsで業績フィルタ（第1層）→ yfinanceで月足トレンドフィルタ（第2層）→ 乖離率深い順TOP10をpool.csvに書き出してgit push。GitHub Actionsが毎週実行し、Streamlit Cloudが自動反映する。

**Tech Stack:** Python 3.11+, requests（J-Quants API）, yfinance, pandas, 既存: duckdb / pydantic / pyyaml

---

## ファイル構成

```
src/
  jquants.py          # 新規: J-Quants認証 + APIクライアント
  fundamentals.py     # 新規: 第1層 業績フィルタ
  trend.py            # 新規: 第2層 月足トレンドフィルタ
scripts/
  build_pool.py       # 新規: 全体を繋ぐ実行スクリプト
.github/
  workflows/
    build_pool.yml    # 新規: GitHub Actions ワークフロー
tests/
  test_fundamentals.py  # 新規: 業績フィルタのテスト
  test_trend.py         # 新規: トレンドフィルタのテスト
```

---

### Task 1: src/jquants.py — J-Quants APIクライアント

**Files:**
- Create: `src/jquants.py`

> テストはJ-Quants APIへのネットワーク依存のため手動検証で代替する。

- [ ] **Step 1: src/jquants.py を実装**

```python
import os
import time
import requests
from dataclasses import dataclass


_BASE = "https://api.jquants.com/v1"

_MARKET_CODE = {
    "プライム":    "0111",
    "スタンダード": "0121",
    "グロース":    "0131",
}


@dataclass
class StockInfo:
    code: str     # "3038"
    symbol: str   # "3038.T"
    name: str
    market: str


@dataclass
class FinancialStatement:
    code: str
    period: str          # "2024" など
    net_sales: float | None
    net_income: float | None
    operating_cf: float | None


def get_id_token(email: str, password: str) -> str:
    """email/passwordでJ-Quantsにログインし、IDトークンを返す。"""
    r = requests.post(
        f"{_BASE}/token/auth_user",
        json={"mailaddress": email, "password": password},
        timeout=30,
    )
    r.raise_for_status()
    refresh = r.json()["refreshToken"]

    r2 = requests.post(
        f"{_BASE}/token/auth_refresh",
        params={"refreshtoken": refresh},
        timeout=30,
    )
    r2.raise_for_status()
    return r2.json()["idToken"]


def _headers(id_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {id_token}"}


def get_listed_stocks(id_token: str, markets: list[str]) -> list[StockInfo]:
    """全上場銘柄リストを取得し、対象市場のみ返す。ETF/REITは除外しない（呼び出し側で除外）。"""
    r = requests.get(f"{_BASE}/listed/info", headers=_headers(id_token), timeout=30)
    r.raise_for_status()

    target = {_MARKET_CODE[m] for m in markets if m in _MARKET_CODE}
    stocks = []
    for item in r.json().get("info", []):
        if item.get("MarketCode") not in target:
            continue
        code = item["Code"]
        if len(code) == 5:
            code = code[:4]  # 5桁→4桁
        stocks.append(StockInfo(
            code=code,
            symbol=f"{code}.T",
            name=item.get("CompanyName", ""),
            market=item.get("MarketCodeName", ""),
        ))
    return stocks


def get_statements_for_code(id_token: str, code: str) -> list[FinancialStatement]:
    """特定銘柄の財務諸表（通期のみ）を取得する。"""
    r = requests.get(
        f"{_BASE}/fins/statements",
        headers=_headers(id_token),
        params={"code": code},
        timeout=30,
    )
    if r.status_code != 200:
        return []

    def _f(v) -> float | None:
        try:
            return float(v) if v not in (None, "", "－", "-") else None
        except (ValueError, TypeError):
            return None

    results = []
    for item in r.json().get("statements", []):
        # 通期（FY）のみ対象
        doc_type = item.get("TypeOfDocument", "")
        if "通期" not in doc_type and "FY" not in doc_type.upper():
            continue
        results.append(FinancialStatement(
            code=code,
            period=item.get("FiscalYear", item.get("DisclosedDate", ""))[:7],
            net_sales=_f(item.get("NetSales")),
            net_income=_f(item.get("Profit")),
            operating_cf=_f(item.get("OperatingCashFlow")),
        ))
    return sorted(results, key=lambda s: s.period)


def get_all_statements(
    id_token: str,
    codes: list[str],
    delay_sec: float = 0.3,
) -> dict[str, list[FinancialStatement]]:
    """複数銘柄の財務諸表を一括取得する（レート制限対策のdelay付き）。"""
    result: dict[str, list[FinancialStatement]] = {}
    for i, code in enumerate(codes):
        if i > 0 and i % 100 == 0:
            print(f"  財務データ取得中... {i}/{len(codes)}")
        result[code] = get_statements_for_code(id_token, code)
        time.sleep(delay_sec)
    return result
```

- [ ] **Step 2: 手動動作確認**

`.env` に `JQUANTS_EMAIL` と `JQUANTS_PASSWORD` が設定済みであることを確認してから実行:

```bash
cd "C:\Users\you-k\OneDrive\Desktop\株リサーチ"
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
from src.jquants import get_id_token, get_listed_stocks
token = get_id_token(os.environ['JQUANTS_EMAIL'], os.environ['JQUANTS_PASSWORD'])
print('token OK:', token[:20], '...')
stocks = get_listed_stocks(token, ['プライム'])
print('プライム銘柄数:', len(stocks))
print('先頭3件:', stocks[:3])
"
```

期待値: `token OK: xxxx...`、プライム銘柄数が1500〜2000程度

> `python-dotenv` がない場合は `pip install python-dotenv` を実行。`requirements.txt` にも追加する。

- [ ] **Step 3: requirements.txt に python-dotenv を追加**

`requirements.txt` に以下を追加:
```
python-dotenv>=1.0
```

- [ ] **Step 4: コミット**

```bash
git add src/jquants.py requirements.txt
git commit -m "feat: add J-Quants API client"
```

---

### Task 2: src/fundamentals.py — 第1層 業績フィルタ（TDD）

**Files:**
- Create: `src/fundamentals.py`
- Create: `tests/test_fundamentals.py`

- [ ] **Step 1: テストを書く**

`tests/test_fundamentals.py`:

```python
from src.jquants import FinancialStatement
from src.fundamentals import (
    calc_yoy_growth,
    passes_growth_filter,
    filter_by_fundamentals,
    FundamentalResult,
)


def _stmt(period: str, sales: float | None, income: float | None, ocf: float | None) -> FinancialStatement:
    return FinancialStatement(code="3038", period=period, net_sales=sales, net_income=income, operating_cf=ocf)


# --- calc_yoy_growth ---

def test_calc_yoy_growth_positive():
    assert calc_yoy_growth(120.0, 100.0) == 20.0

def test_calc_yoy_growth_zero_previous():
    assert calc_yoy_growth(100.0, 0.0) is None

def test_calc_yoy_growth_none_values():
    assert calc_yoy_growth(None, 100.0) is None
    assert calc_yoy_growth(100.0, None) is None


# --- passes_growth_filter ---

def test_passes_growth_filter_all_ok():
    stmts = [
        _stmt("2022", 100, 50, 80),
        _stmt("2023", 125, 65, 90),  # +25%, +30%
        _stmt("2024", 160, 85, 100), # +28%, +30%
        _stmt("2025", 200, 110, 120),# +25%, +29%
    ]
    result = passes_growth_filter(stmts, min_yoy_pct=20.0, consecutive_periods=3, require_positive_cf=True)
    assert result is not None
    assert result.revenue_growth_pct >= 20.0

def test_passes_growth_filter_insufficient_growth():
    stmts = [
        _stmt("2022", 100, 50, 80),
        _stmt("2023", 110, 55, 90),  # +10% (不足)
        _stmt("2024", 125, 65, 100),
        _stmt("2025", 150, 80, 120),
    ]
    result = passes_growth_filter(stmts, min_yoy_pct=20.0, consecutive_periods=3, require_positive_cf=True)
    assert result is None

def test_passes_growth_filter_negative_cf():
    stmts = [
        _stmt("2022", 100, 50, 80),
        _stmt("2023", 125, 65, -10),  # 営業CFマイナス
        _stmt("2024", 160, 85, 100),
        _stmt("2025", 200, 110, 120),
    ]
    result = passes_growth_filter(stmts, min_yoy_pct=20.0, consecutive_periods=3, require_positive_cf=True)
    assert result is None

def test_passes_growth_filter_insufficient_periods():
    stmts = [
        _stmt("2024", 160, 85, 100),
        _stmt("2025", 200, 110, 120),
    ]
    result = passes_growth_filter(stmts, min_yoy_pct=20.0, consecutive_periods=3, require_positive_cf=True)
    assert result is None


# --- filter_by_fundamentals ---

def test_filter_by_fundamentals_returns_passing_stocks():
    statements = {
        "3038": [
            _stmt("2022", 100, 50, 80),
            _stmt("2023", 125, 65, 90),
            _stmt("2024", 160, 85, 100),
            _stmt("2025", 200, 110, 120),
        ],
        "9999": [  # 成長率不足
            _stmt("2022", 100, 50, 80),
            _stmt("2023", 105, 52, 85),
            _stmt("2024", 110, 54, 90),
            _stmt("2025", 115, 56, 95),
        ],
    }
    names = {"3038": "神戸物産", "9999": "テスト会社"}
    results = filter_by_fundamentals(
        statements=statements,
        names=names,
        min_revenue_yoy_pct=20.0,
        min_income_yoy_pct=20.0,
        consecutive_periods=3,
        require_positive_cf=True,
    )
    codes = [r.symbol for r in results]
    assert "3038.T" in codes
    assert "9999.T" not in codes
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
cd "C:\Users\you-k\OneDrive\Desktop\株リサーチ"
pytest tests/test_fundamentals.py -v
```

期待値: `ImportError: cannot import name 'calc_yoy_growth'`

- [ ] **Step 3: src/fundamentals.py を実装**

```python
from dataclasses import dataclass
from src.jquants import FinancialStatement


@dataclass
class FundamentalResult:
    code: str             # "3038"
    symbol: str           # "3038.T"
    name: str
    revenue_growth_pct: float   # 直近期の売上高YoY成長率(%)
    net_income_growth_pct: float


def calc_yoy_growth(current: float | None, previous: float | None) -> float | None:
    """前年比成長率(%)を返す。計算不能な場合はNone。"""
    if current is None or previous is None or previous == 0:
        return None
    return (current - previous) / abs(previous) * 100


def passes_growth_filter(
    stmts: list[FinancialStatement],
    min_yoy_pct: float,
    consecutive_periods: int,
    require_positive_cf: bool,
) -> FundamentalResult | None:
    """
    財務諸表リストが成長フィルタを通過するか判定する。
    通過した場合は FundamentalResult を返し、不通過は None を返す。
    stmts は period 昇順でソート済みであること。
    """
    # 有効な通期データのみ抽出（売上高と純利益がある期）
    valid = [s for s in stmts if s.net_sales is not None and s.net_income is not None]
    if len(valid) < consecutive_periods + 1:
        return None

    # 直近 consecutive_periods 期分のYoY成長率を確認
    recent = valid[-(consecutive_periods + 1):]  # +1は比較用の前期分
    for i in range(1, len(recent)):
        rev_growth = calc_yoy_growth(recent[i].net_sales, recent[i - 1].net_sales)
        inc_growth = calc_yoy_growth(recent[i].net_income, recent[i - 1].net_income)

        if rev_growth is None or rev_growth < min_yoy_pct:
            return None
        if inc_growth is None or inc_growth < min_yoy_pct:
            return None
        if require_positive_cf and recent[i].operating_cf is not None and recent[i].operating_cf <= 0:
            return None

    latest = recent[-1]
    prev    = recent[-2]
    return FundamentalResult(
        code=valid[0].code,
        symbol=f"{valid[0].code}.T",
        name="",
        revenue_growth_pct=calc_yoy_growth(latest.net_sales, prev.net_sales) or 0.0,
        net_income_growth_pct=calc_yoy_growth(latest.net_income, prev.net_income) or 0.0,
    )


def filter_by_fundamentals(
    statements: dict[str, list[FinancialStatement]],
    names: dict[str, str],
    min_revenue_yoy_pct: float,
    min_income_yoy_pct: float,
    consecutive_periods: int,
    require_positive_cf: bool,
) -> list[FundamentalResult]:
    """全銘柄の財務データから業績フィルタを通過した銘柄リストを返す。"""
    results = []
    for code, stmts in statements.items():
        result = passes_growth_filter(
            stmts,
            min_yoy_pct=min(min_revenue_yoy_pct, min_income_yoy_pct),
            consecutive_periods=consecutive_periods,
            require_positive_cf=require_positive_cf,
        )
        # 売上と純利益で別々に閾値チェック
        if result is None:
            continue
        if result.revenue_growth_pct < min_revenue_yoy_pct:
            continue
        if result.net_income_growth_pct < min_income_yoy_pct:
            continue
        result.name = names.get(code, "")
        results.append(result)
    return results
```

- [ ] **Step 4: テストが通ることを確認**

```bash
pytest tests/test_fundamentals.py -v
```

期待値: `8 passed`

- [ ] **Step 5: コミット**

```bash
git add src/fundamentals.py tests/test_fundamentals.py
git commit -m "feat: add Layer 1 fundamental filter with tests"
```

---

### Task 3: src/trend.py — 第2層 月足トレンドフィルタ（TDD）

**Files:**
- Create: `src/trend.py`
- Create: `tests/test_trend.py`

- [ ] **Step 1: テストを書く**

`tests/test_trend.py`:

```python
import pandas as pd
import pytest
from src.trend import (
    resample_monthly,
    calc_monthly_smas,
    check_perfect_order,
    check_higher_highs_lows,
    check_alltime_high_proximity,
)


def _monthly(values: list[float], start: str = "2022-01") -> pd.Series:
    idx = pd.date_range(start=start, periods=len(values), freq="ME")
    return pd.Series(values, index=idx)


# --- calc_monthly_smas ---

def test_calc_monthly_smas_returns_three_series():
    prices = _monthly([100.0] * 30)
    smas = calc_monthly_smas(prices, periods=[6, 12, 24])
    assert set(smas.keys()) == {6, 12, 24}
    assert len(smas[6].dropna()) == 25  # 30 - 6 + 1


# --- check_perfect_order ---

def test_check_perfect_order_true_when_aligned():
    # SMA6 > SMA12 > SMA24 かつ全SMA上向きになる上昇系列
    prices = _monthly([float(i * 10 + 100) for i in range(30)])
    smas = calc_monthly_smas(prices, periods=[6, 12, 24])
    assert check_perfect_order(prices, smas, require_rising_slope=True) is True

def test_check_perfect_order_false_when_declining():
    # 下降トレンド
    prices = _monthly([float(300 - i * 5) for i in range(30)])
    smas = calc_monthly_smas(prices, periods=[6, 12, 24])
    assert check_perfect_order(prices, smas, require_rising_slope=True) is False


# --- check_higher_highs_lows ---

def test_check_higher_highs_lows_true():
    # 明確な切り上げ波形
    vals = [100, 110, 105, 115, 108, 120, 112, 130]
    prices = _monthly([float(v) for v in vals])
    assert check_higher_highs_lows(prices, swing_window=2, min_swings=2) is True

def test_check_higher_highs_lows_false_when_lower_low():
    # 安値が切り下がっている
    vals = [100, 110, 90, 115, 80, 120]
    prices = _monthly([float(v) for v in vals])
    assert check_higher_highs_lows(prices, swing_window=2, min_swings=2) is False


# --- check_alltime_high_proximity ---

def test_check_alltime_high_proximity_within_range():
    prices = _monthly([100.0] * 20 + [120.0, 115.0])  # 高値120に対し現在115 = 約4%以内
    assert check_alltime_high_proximity(prices, max_distance_pct=25.0) is True

def test_check_alltime_high_proximity_too_far():
    prices = _monthly([100.0] * 20 + [200.0, 100.0])  # 高値200に対し現在100 = 50%離れている
    assert check_alltime_high_proximity(prices, max_distance_pct=25.0) is False
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
pytest tests/test_trend.py -v
```

期待値: `ImportError: cannot import name 'resample_monthly'`

- [ ] **Step 3: src/trend.py を実装**

```python
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

    # 最新値で各SMAを取得
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

    for i in range(w, len(arr) - w):
        window = arr[i - w: i + w + 1]
        if arr[i] == max(window):
            highs.append(arr[i])
        if arr[i] == min(window):
            lows.append(arr[i])

    if len(highs) < min_swings or len(lows) < min_swings:
        return False

    # 直近 min_swings 個のスイングが単調増加かチェック
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
    alltime_high = monthly.max()
    current      = monthly.iloc[-1]
    distance_pct = (alltime_high - current) / alltime_high * 100
    return distance_pct <= max_distance_pct


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
```

- [ ] **Step 4: テストが通ることを確認**

```bash
pytest tests/test_trend.py -v
```

期待値: `7 passed`

- [ ] **Step 5: 全テストが通ることを確認**

```bash
pytest tests/ -v --tb=short
```

期待値: 全件 PASS

- [ ] **Step 6: コミット**

```bash
git add src/trend.py tests/test_trend.py
git commit -m "feat: add Layer 2 monthly trend filter with tests"
```

---

### Task 4: scripts/build_pool.py — オーケストレーター

**Files:**
- Create: `scripts/__init__.py`（空）
- Create: `scripts/build_pool.py`

- [ ] **Step 1: scripts/ ディレクトリと build_pool.py を作成**

`scripts/__init__.py`: 空ファイル

`scripts/build_pool.py`:

```python
"""
毎週実行されるpool自動更新スクリプト。
全上場銘柄を3層スクリーニングし、買いチャンスに近い順TOP10をpool.csvに書き出す。

使い方:
  python scripts/build_pool.py

環境変数（.envまたはGitHub Secrets）:
  JQUANTS_EMAIL    J-Quantsのメールアドレス
  JQUANTS_PASSWORD J-Quantsのパスワード
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
from src.jquants import get_id_token, get_listed_stocks, get_all_statements
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
    email    = os.environ.get("JQUANTS_EMAIL")
    password = os.environ.get("JQUANTS_PASSWORD")

    if not email or not password:
        print("[ERROR] JQUANTS_EMAIL または JQUANTS_PASSWORD が設定されていません")
        sys.exit(1)

    cfg     = load_config(_CONFIG_PATH)
    db_path = str(_PROJECT_ROOT / cfg.data_sources.cache_db.lstrip("./").lstrip(".\\"))
    fund    = cfg.output  # for pool_path reference

    print("=== pool自動更新 開始 ===")
    print(f"対象市場: {cfg.output}")

    # Step 1: J-Quants認証
    print("\n[1/5] J-Quants認証...")
    try:
        id_token = get_id_token(email, password)
        print("  認証OK")
    except Exception as e:
        print(f"  [ERROR] 認証失敗: {e}")
        print("  既存のpool.csvを維持します")
        return

    # Step 2: 全上場銘柄取得
    print("\n[2/5] 全上場銘柄リスト取得...")
    from src.config import load_config as _lc
    markets = ["プライム", "スタンダード", "グロース"]
    stocks = get_listed_stocks(id_token, markets)
    print(f"  {len(stocks)}銘柄取得")

    # Step 3: 財務データ取得
    print(f"\n[3/5] 財務データ取得中（{len(stocks)}銘柄）...")
    codes = [s.code for s in stocks]
    names = {s.code: s.name for s in stocks}
    statements = get_all_statements(id_token, codes, delay_sec=0.3)
    print(f"  取得完了")

    # Step 4: 第1層 業績フィルタ
    print("\n[4a/5] 第1層: 業績フィルタ...")
    fund_cfg = cfg  # conditions.yamlの値を使う
    l1_passed = filter_by_fundamentals(
        statements=statements,
        names=names,
        min_revenue_yoy_pct=20.0,
        min_income_yoy_pct=20.0,
        consecutive_periods=3,
        require_positive_cf=True,
    )
    print(f"  {len(l1_passed)}銘柄通過")

    if not l1_passed:
        print("  [WARNING] 0銘柄通過。既存のpool.csvを維持します")
        return

    # Step 5: 第2層 月足トレンドフィルタ
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

    # Step 6: 乖離率計算 → TOP10
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
```

- [ ] **Step 2: 手動実行で動作確認**

```bash
cd "C:\Users\you-k\OneDrive\Desktop\株リサーチ"
python scripts/build_pool.py
```

期待値: 各ステップが順番に表示され、最終的に `out/pool.csv` が更新される（初回は時間がかかる）

- [ ] **Step 3: コミット**

```bash
git add scripts/__init__.py scripts/build_pool.py
git commit -m "feat: add build_pool.py orchestrator script"
```

---

### Task 5: .github/workflows/build_pool.yml — GitHub Actions設定

**Files:**
- Create: `.github/workflows/build_pool.yml`

- [ ] **Step 1: .github/workflows/ ディレクトリ作成と build_pool.yml を作成**

`.github/workflows/build_pool.yml`:

```yaml
name: Build Pool

on:
  schedule:
    - cron: '0 15 * * 5'  # 毎週金曜 15:00 UTC = 土曜 0:00 JST
  workflow_dispatch:         # GitHub UIから手動実行可能

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run build_pool.py
        env:
          JQUANTS_EMAIL:    ${{ secrets.JQUANTS_EMAIL }}
          JQUANTS_PASSWORD: ${{ secrets.JQUANTS_PASSWORD }}
        run: python scripts/build_pool.py

      - name: Commit and push pool.csv if changed
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add out/pool.csv
          git diff --staged --quiet || (git commit -m "chore: update pool.csv [skip ci]" && git push)
```

- [ ] **Step 2: コミット・push**

```bash
git add .github/workflows/build_pool.yml
git commit -m "feat: add GitHub Actions workflow for weekly pool update"
git push
```

- [ ] **Step 3: 手動実行でGitHub Actionsを確認**

1. [github.com/yuokan7/kabu-researcher/actions](https://github.com/yuokan7/kabu-researcher/actions) を開く
2. 「Build Pool」ワークフローを選択
3. 「Run workflow」→「Run workflow」をクリック
4. 実行ログを確認する

期待値:
- 全ステップが緑（✅）で完了する
- `out/pool.csv` が更新されたコミットが自動生成される

- [ ] **Step 4: pool.csv の内容確認**

```bash
git pull
cat out/pool.csv
```

期待値: `symbol,name,revenue_growth_pct,net_income_growth_pct,current_deviation_pct` のヘッダーと銘柄データが10行以内で出力される

---

## 完了チェックリスト

- [ ] `pytest tests/ -v` が全グリーン
- [ ] `python scripts/build_pool.py` がローカルで正常終了し pool.csv が更新される
- [ ] GitHub Actions の手動実行が成功する
- [ ] 自動生成されたコミットに `pool.csv` の変更が含まれる
- [ ] Streamlit ダッシュボード（kabu-researcher.streamlit.app）に新しい銘柄が反映される
