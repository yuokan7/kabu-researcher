# Webダッシュボード v1 実装プラン

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `streamlit run app.py` の1コマンドで、日経225の暴落ゲージと監視銘柄リストを表示するローカルダッシュボードを構築する

**Architecture:** 既存の fetch.py / trigger.py を活用した純粋ロジック層 `dashboard_data.py`（テスト可能）と、その結果を描画するだけの薄い Streamlit UI `app.py` に分離する。監視リストは `out/pool.csv` で管理し、J-Quants 不要で即動作する。

**Tech Stack:** Python 3.11+, streamlit>=1.30, 既存: yfinance / duckdb / pydantic / pandas

---

## ファイル構成

```
C:\Users\you-k\OneDrive\Desktop\株リサーチ\
├── conditions.yaml          # 変更: dashboardセクション追加
├── pyproject.toml           # 変更: streamlit依存追加
├── app.py                   # 新規: Streamlit UI（薄い描画層）
├── out/
│   └── pool.csv             # 新規: 監視銘柄シードデータ（手動編集用）
├── src/
│   ├── config.py            # 変更: DashboardConfig + ScreenerConfig.dashboard追加
│   └── dashboard_data.py    # 新規: 純粋ロジック（Streamlit非依存・テスト可能）
├── tests/
│   └── test_dashboard_data.py  # 新規: dashboard_data のユニットテスト
└── .claude/commands/
    └── dashboard.md         # 新規: /dashboardコマンド定義
```

---

### Task 1: DashboardConfig — conditions.yaml と config.py に追加

**Files:**
- Modify: `conditions.yaml`（末尾に dashboardセクション追加）
- Modify: `src/config.py`（DashboardConfig クラス追加 + ScreenerConfig に dashboard フィールド追加）
- Modify: `tests/test_config.py`（dashboard デフォルト値テスト追加）

- [ ] **Step 1: テストを追加する**

`tests/test_config.py` の末尾に以下を追加する:

```python
def test_dashboard_config_warning_deviation():
    cfg = load_config(YAML_PATH)
    assert cfg.dashboard.warning_deviation_pct == -7

def test_dashboard_config_danger_deviation():
    cfg = load_config(YAML_PATH)
    assert cfg.dashboard.danger_deviation_pct == -10

def test_dashboard_config_cache_ttl():
    cfg = load_config(YAML_PATH)
    assert cfg.dashboard.cache_ttl_minutes == 60
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
cd "C:\Users\you-k\OneDrive\Desktop\株リサーチ"
pytest tests/test_config.py -v -k "dashboard"
```

期待値: `AttributeError: 'ScreenerConfig' object has no attribute 'dashboard'`

- [ ] **Step 3: conditions.yaml に dashboard セクションを追加**

`conditions.yaml` の末尾（`output:` セクションの後）に以下を追加する:

```yaml
# =============================================================
#  Webダッシュボード
# =============================================================
dashboard:
  warning_deviation_pct: -7      # 黄信号ライン
  danger_deviation_pct: -10      # 赤信号ライン（trigger.market.threshold_pctと同値）
  price_lookback_days: 60        # 乖離率計算の価格取得日数
  cache_ttl_minutes: 60          # Streamlitキャッシュ有効期間（分）
  fresh_touch_highlight_days: 90 # 直近この日数以内の発火をバナー表示
```

- [ ] **Step 4: src/config.py に DashboardConfig を追加**

`src/config.py` の `DataSourcesConfig` クラスの直後（`ScreenerConfig` の前）に以下を追加する:

```python
class DashboardConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    warning_deviation_pct: float = -7
    danger_deviation_pct: float = -10
    price_lookback_days: int = 60
    cache_ttl_minutes: int = 60
    fresh_touch_highlight_days: int = 90
```

さらに `ScreenerConfig` に `dashboard` フィールドを追加する:

```python
class ScreenerConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    trigger: TriggerConfig
    output: OutputConfig
    data_sources: DataSourcesConfig = Field(default_factory=DataSourcesConfig)
    dashboard: DashboardConfig = Field(default_factory=DashboardConfig)
```

- [ ] **Step 5: テストが通ることを確認**

```bash
pytest tests/test_config.py -v
```

期待値: `8 passed`（既存5件 + 新規3件）

- [ ] **Step 6: コミット**

```bash
git add conditions.yaml src/config.py tests/test_config.py
git commit -m "feat: add DashboardConfig to config and conditions.yaml"
```

---

### Task 2: out/pool.csv シードデータ作成

**Files:**
- Create: `out/pool.csv`

> pool.csv はgitignore対象外（ユーザーの監視リスト設定ファイルとして扱う）。.gitignoreに `out/` と書いてあるが、pool.csv は意図的にコミットする。

- [ ] **Step 1: out/ ディレクトリが存在することを確認**

```bash
ls "C:\Users\you-k\OneDrive\Desktop\株リサーチ\out\"
```

期待値: `candidates.csv` が表示される（out/ は既存）

- [ ] **Step 2: pool.csv を作成**

`out/pool.csv`:

```csv
symbol,name
3038.T,神戸物産
3064.T,MonotaRO
9843.T,ニトリHD
6861.T,キーエンス
4755.T,楽天グループ
```

> 注: これは動作確認用のサンプルデータ。好業績・上昇トレンドの選定は手法マニュアルに従って人間が判断して編集すること。投資推奨ではない。

- [ ] **Step 3: .gitignore を修正して pool.csv だけ追跡対象に戻す**

`.gitignore` の `out/` の行を以下に変更する:

```gitignore
# 出力ファイル（pool.csv は除く）
out/candidates.csv
out/*.csv.bak
```

- [ ] **Step 4: git の追跡状態を確認**

```bash
cd "C:\Users\you-k\OneDrive\Desktop\株リサーチ"
git status
```

期待値: `out/pool.csv` が `Untracked files` に表示される

- [ ] **Step 5: コミット**

```bash
git add .gitignore out/pool.csv
git commit -m "feat: add pool.csv seed watchlist and fix gitignore"
```

---

### Task 3: src/dashboard_data.py — 純粋ロジック（TDD）

**Files:**
- Create: `src/dashboard_data.py`
- Create: `tests/test_dashboard_data.py`

- [ ] **Step 1: テストを書く**

`tests/test_dashboard_data.py`:

```python
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
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
cd "C:\Users\you-k\OneDrive\Desktop\株リサーチ"
pytest tests/test_dashboard_data.py -v
```

期待値: `ImportError: cannot import name 'classify_deviation' from 'src.dashboard_data'`

- [ ] **Step 3: src/dashboard_data.py を実装**

`src/dashboard_data.py`:

```python
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

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
    current_price: float
    current_deviation_pct: float
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
            current_price=0.0,
            current_deviation_pct=0.0,
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
        current_deviation_pct=current_dev if current_dev is not None else 0.0,
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
```

- [ ] **Step 4: テストが通ることを確認**

```bash
pytest tests/test_dashboard_data.py -v
```

期待値: `16 passed`

- [ ] **Step 5: 全テストが通ることを確認**

```bash
pytest tests/ -v --tb=short
```

期待値: 既存テスト含め全件 PASS（失敗ゼロ）

- [ ] **Step 6: コミット**

```bash
git add src/dashboard_data.py tests/test_dashboard_data.py
git commit -m "feat: add dashboard_data pure logic with full test coverage"
```

---

### Task 4: app.py — Streamlit UI と依存追加

**Files:**
- Modify: `pyproject.toml`（streamlit 依存追加）
- Create: `app.py`

- [ ] **Step 1: pyproject.toml に streamlit を追加**

`pyproject.toml` の `dependencies` リストに `"streamlit>=1.30"` を追加する:

```toml
dependencies = [
    "yfinance>=0.2.40",
    "duckdb>=0.10.0",
    "pydantic>=2.0",
    "pyyaml>=6.0",
    "pandas>=2.0",
    "streamlit>=1.30",
]
```

- [ ] **Step 2: streamlit をインストール**

```bash
cd "C:\Users\you-k\OneDrive\Desktop\株リサーチ"
pip install -e ".[dev]"
```

期待値: `Successfully installed streamlit-...` を含む出力

- [ ] **Step 3: app.py を作成**

`app.py`（プロジェクトルート直下）:

```python
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from src.config import load_config
from src.dashboard_data import DashboardData, build_dashboard_data

_PROJECT_ROOT = Path(__file__).parent
_CONFIG_PATH = _PROJECT_ROOT / "conditions.yaml"

st.set_page_config(page_title="まだ株ダッシュボード", layout="wide")

cfg = load_config(_CONFIG_PATH)
_TTL = cfg.dashboard.cache_ttl_minutes * 60

_STATUS_LABEL = {
    "normal": "✅ 平常",
    "warning": "⚠️ 注意",
    "danger": "🚨 暴落点タッチ",
    "no_data": "❓ データなし",
}

_STATUS_BADGE = {
    "danger":  "🚨 暴落点",
    "warning": "⚠️ 注意",
    "normal":  "　平常",
    "no_data": "❓ データなし",
}


@st.cache_data(ttl=_TTL, show_spinner="データ取得中...")
def _get_data() -> DashboardData:
    return build_dashboard_data(cfg, today=date.today())


# ── ヘッダー ──────────────────────────────────────────────────
col_title, col_btn = st.columns([6, 1])
with col_title:
    st.title("📈 まだ株ダッシュボード")
with col_btn:
    st.write("")  # 縦位置合わせ
    if st.button("🔄 更新"):
        st.cache_data.clear()
        st.rerun()

data = _get_data()

# ── 暴落ゲージ ────────────────────────────────────────────────
st.subheader("日経225 暴落ゲージ")

m = data.market
c1, c2, c3 = st.columns(3)
c1.metric("現在値", f"¥{m.current_price:,.0f}" if m.current_price else "—")
c2.metric("25日乖離率", f"{m.current_deviation_pct:.2f}%" if m.status != "no_data" else "—")
c3.metric("状態", _STATUS_LABEL.get(m.status, m.status))

if m.fresh_touch_fired and m.last_signal_date:
    st.error(
        f"⚠️ 3か月ぶりの暴落シグナル発火（最終: {m.last_signal_date}）"
        "— 監視リストを確認してください"
    )
elif m.status == "danger":
    st.warning("暴落点付近です。監視リストの乖離率を確認してください。")
elif m.status == "warning":
    st.info("乖離率が警戒水準に近づいています。")

st.divider()

# ── 監視リスト ────────────────────────────────────────────────
st.subheader("監視リスト（乖離率 深い順）")

if not data.rows:
    st.info(
        "監視銘柄がありません。"
        "`out/pool.csv` に symbol（例: 3038.T）と name を追加してください。"
    )
else:
    records = []
    for row in data.rows:
        records.append({
            "銘柄名": row.name,
            "コード": row.symbol,
            "現在値": f"¥{row.current_price:,.0f}" if row.current_price else "—",
            "乖離率(%)": f"{row.current_deviation_pct:.2f}" if row.current_deviation_pct is not None else "—",
            "状態": _STATUS_BADGE.get(row.status, row.status),
        })
    df = pd.DataFrame(records)
    st.dataframe(df, use_container_width=True, hide_index=True)

st.caption(
    f"最終更新: {data.as_of}　|　"
    f"注意ライン: {cfg.dashboard.warning_deviation_pct}%　"
    f"暴落ライン: {cfg.dashboard.danger_deviation_pct}%"
)
```

- [ ] **Step 4: 起動して手動確認**

```bash
cd "C:\Users\you-k\OneDrive\Desktop\株リサーチ"
streamlit run app.py
```

ブラウザが自動で開く。以下を確認する:
- 「日経225 暴落ゲージ」に現在値・乖離率・状態が表示される
- 「監視リスト」に神戸物産・MonotaRO・ニトリHD・キーエンス・楽天が乖離率順で表示される
- 「🔄 更新」ボタンを押すと再取得される
- ブラウザを閉じ、ターミナルで Ctrl+C で停止する

- [ ] **Step 5: コミット**

```bash
git add pyproject.toml app.py
git commit -m "feat: add streamlit dashboard UI"
```

---

### Task 5: /dashboardコマンドと最終確認

**Files:**
- Create: `.claude/commands/dashboard.md`

- [ ] **Step 1: .claude/commands/dashboard.md を作成**

`.claude/commands/dashboard.md`:

```markdown
# /dashboard

ローカルでダッシュボードを起動します。

## 実行

```bash
cd "C:\Users\you-k\OneDrive\Desktop\株リサーチ"
streamlit run app.py
```

ブラウザが自動で開きます（http://localhost:8501）。

## 監視銘柄の追加・削除

`out/pool.csv` をテキストエディタで編集:

```csv
symbol,name
3038.T,神戸物産
7203.T,トヨタ自動車
```

symbol は yfinance 形式（日本株は末尾に `.T`）。
編集後、ダッシュボードの「🔄 更新」ボタンを押すと反映されます。

## 閾値の変更

`conditions.yaml` の `dashboard` セクションを編集:

```yaml
dashboard:
  warning_deviation_pct: -7   # 黄信号（注意）
  danger_deviation_pct: -10   # 赤信号（暴落点）
```
```

- [ ] **Step 2: 全テストを実行して最終確認**

```bash
cd "C:\Users\you-k\OneDrive\Desktop\株リサーチ"
pytest tests/ -v --tb=short
```

期待値: 全件 PASS（test_config: 8件 + test_trigger: 8件 + test_notify: 5件 + test_dashboard_data: 16件 = 37件以上）

- [ ] **Step 3: 完了チェックリスト確認**

手動で以下を確認する:
- [ ] `streamlit run app.py` でダッシュボードが起動する
- [ ] 日経225の現在値・乖離率・状態が表示される
- [ ] `out/pool.csv` の5銘柄が乖離率の深い順に表示される
- [ ] `out/pool.csv` に1行追加→「🔄 更新」→監視リストに反映される
- [ ] データ取得エラー銘柄（存在しないシンボルを追加）がリスト末尾に「❓ データなし」で表示され、他の銘柄の表示が継続する

- [ ] **Step 4: コミット**

```bash
git add .claude/commands/dashboard.md
git commit -m "feat: add /dashboard command and complete Phase 1 dashboard"
```
