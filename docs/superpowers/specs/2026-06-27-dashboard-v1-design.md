# Webダッシュボード v1 設計書

**作成日:** 2026-06-27
**対象:** まだ株・奥義継承スクリーナー / サブプロジェクト① Webダッシュボード v1

---

## 0. このサブプロジェクトの位置づけ

全体は4つのサブプロジェクトに分割し、価値が早く出る順に構築する:

| # | サブプロジェクト | 内容 | 依存 |
|---|---|---|---|
| **①** | **Webダッシュボード v1（本書）** | ローカル起動の1画面。日経暴落ゲージ＋監視リスト（乖離率順） | Phase 1のみ（J-Quants不要） |
| ② | J-Quants基盤 | 認証＋業績データ取得・キャッシュ | J-Quants無料登録 |
| ③ | Phase 2 自動pool | 第1層業績＋第2層月足で自動スクリーニング→pool.csv | ② |
| ④ | 個別トリガー＋ランキング | 個別下限キャリブレ＋買い候補ハイライト | ③ |

**設計の核:** データの受け渡しは `out/pool.csv` で固定する。①では人間が手動で中身を書き、③が完成すると自動で書き換わる。これによりダッシュボードのコードは①→③の切替で作り直しが発生しない。

---

## 1. このサブプロジェクトのゴール

`streamlit run app.py`（または `/dashboard` コマンド）の1コマンドで、ブラウザに以下を表示するローカルダッシュボードを作る:

1. **日経225 暴落ゲージ** — 25日乖離率を視覚化。-7%で黄信号、-10%で赤信号。直近に「3か月ぶりタッチ」が発火していれば明示。
2. **監視リスト** — `out/pool.csv` に登録された銘柄を、各銘柄の現在25日乖離率の深い順（マイナスが大きい順）に並べて表示。

J-Quants登録を待たずに、既存のPhase 1ロジック（fetch.py / trigger.py / config.py）だけで動く。

---

## 2. アーキテクチャ

```
app.py (Streamlit UI・薄い表示層)
   │ 呼び出す
   ▼
src/dashboard_data.py (純粋ロジック・テスト可能)
   │ 使う
   ├─ src/config.py        (conditions.yaml ローダ)
   ├─ src/fetch.py         (yfinance + DuckDBキャッシュ)
   └─ src/trigger.py       (calc_deviation / detect_fresh_touches)
        │ 読む
        ▼
   out/pool.csv (監視リスト・データ契約)
```

**設計原則:** Streamlit依存のコード（`app.py`）と、データ構築ロジック（`dashboard_data.py`）を分離する。ロジックはStreamlitを一切importせず単体テスト可能にする。`app.py` は `dashboard_data` が返すデータ構造を描画するだけの薄い層に保つ。

---

## 3. データ契約: `out/pool.csv`

監視リストの実体。①では手動編集、③で自動生成。

**v1で必須の列:**

| 列名 | 型 | 説明 |
|---|---|---|
| `symbol` | str | yfinanceシンボル（例: `7203.T`） |
| `name` | str | 表示用銘柄名（例: トヨタ自動車） |

将来③が `revenue_growth_pct` 等の業績列を追加するが、ダッシュボードは `symbol` / `name` のみ参照し、余分な列は無視する（前方互換）。

**初期シード:** リポジトリに手動の見本 `out/pool.csv` を1つ用意する（数銘柄。例として神戸物産 `3038.T`、MonotaRO `3064.T`、ニトリHD `9843.T` 等の好業績株を入れておく。あくまで動作確認用の例であり投資推奨ではない旨をコメント不可のCSVなので、README/仕様書側に明記）。

---

## 4. conditions.yaml への追加

CLAUDE.mdの「閾値は一切ハードコードせず conditions.yaml から読む」原則に従い、ダッシュボード用の閾値を新セクションとして追加する:

```yaml
# =============================================================
#  Webダッシュボード（サブプロジェクト①）
# =============================================================
dashboard:
  warning_deviation_pct: -7      # 黄信号ライン（注意）
  danger_deviation_pct: -10      # 赤信号ライン（暴落点。trigger.market.threshold_pct と一致させる）
  price_lookback_days: 60        # 各銘柄の25日乖離率計算に使う取得日数
  cache_ttl_minutes: 60          # データ再取得の間隔（Streamlitキャッシュ）
  fresh_touch_highlight_days: 90 # 直近この日数以内の日経発火をハイライト
```

`src/config.py` に対応する `DashboardConfig` を追加し、`ScreenerConfig.dashboard` として読めるようにする（全フィールドにデフォルト値を持たせ、conditions.yamlに `dashboard` セクションが無くても動くこと）。

---

## 5. コンポーネント詳細

### 5-1. `src/dashboard_data.py`（純粋ロジック）

以下のデータクラスと関数を提供する。Streamlitは一切importしない。

```python
@dataclass
class MarketStatus:
    symbol: str                # "^N225"
    current_price: float
    current_deviation_pct: float
    status: str                # "normal" | "warning" | "danger"
    fresh_touch_fired: bool    # 直近 fresh_touch_highlight_days 以内に発火したか
    last_signal_date: date | None

@dataclass
class WatchRow:
    symbol: str
    name: str
    current_price: float
    current_deviation_pct: float | None   # データ不足時はNone
    status: str                # "normal" | "warning" | "danger" | "no_data"

@dataclass
class DashboardData:
    market: MarketStatus
    rows: list[WatchRow]       # current_deviation_pct 昇順（深い順）。Noneは末尾
    as_of: date
```

**関数:**

- `load_watchlist(pool_path: str | Path) -> list[tuple[str, str]]`
  - pool.csv を読み、`(symbol, name)` のリストを返す。ファイルが無ければ空リスト。

- `classify_deviation(deviation_pct: float | None, warning: float, danger: float) -> str`
  - `None` → `"no_data"`、`<= danger` → `"danger"`、`<= warning` → `"warning"`、それ以外 → `"normal"`

- `build_market_status(cfg, today, fetch_fn=fetch_daily_close) -> MarketStatus`
  - 日経の価格を取得→`calc_deviation`で最新乖離率→`classify_deviation`でstatus判定。
  - `detect_fresh_touches` を全期間に適用し、最後のシグナル日を取得。
    `(today - last_signal_date).days <= fresh_touch_highlight_days` なら `fresh_touch_fired=True`。

- `build_watch_rows(watchlist, cfg, today, fetch_fn=fetch_daily_close) -> list[WatchRow]`
  - 各銘柄について価格取得→最新乖離率→status。取得失敗/データ不足は `current_deviation_pct=None, status="no_data"`。
  - `current_deviation_pct` 昇順でソート（None は末尾）。

- `build_dashboard_data(cfg, today=None, fetch_fn=fetch_daily_close) -> DashboardData`
  - 上記を束ねて `DashboardData` を返す。`today` 省略時は `date.today()`。
  - `fetch_fn` を引数で差し替え可能にし、テストでモックする。

### 5-2. `app.py`（Streamlit UI）

- ページ設定: タイトル「まだ株ダッシュボード」、wide レイアウト。
- `@st.cache_data(ttl=...)` で `build_dashboard_data` の結果をキャッシュ（TTLは `dashboard.cache_ttl_minutes`）。
- 「🔄 更新」ボタンでキャッシュクリア＋再取得。
- **上部（暴落ゲージ）:**
  - `st.metric` で日経の現在値と乖離率を表示。
  - status に応じて色つきメッセージ: normal=緑「平常」/ warning=黄「注意」/ danger=赤「暴落点タッチ」。
  - `fresh_touch_fired=True` のとき目立つ警告バナー「⚠️ 3か月ぶりの暴落シグナル発火（最終: YYYY-MM-DD）」。
- **下部（監視リスト）:**
  - `st.dataframe` で WatchRow を表形式表示。列: 銘柄名 / コード / 現在値 / 乖離率(%) / 状態。
  - 乖離率は深い順。状態をバッジ的に色分け（danger=赤, warning=黄, normal=灰, no_data=「データなし」）。
  - リストが空のとき: 「out/pool.csv に銘柄を登録してください」の案内を表示。
- 最終更新日（`as_of`）をフッターに表示。

### 5-3. `.claude/commands/dashboard.md`

```markdown
# /dashboard

ローカルでダッシュボードを起動します。

## 実行
cd "C:\Users\you-k\OneDrive\Desktop\株リサーチ"
streamlit run app.py

ブラウザが自動で開きます。監視リストは out/pool.csv を編集して増減できます。
```

### 5-4. `pyproject.toml`

`dependencies` に `streamlit>=1.30` を追加する。

---

## 6. エラーハンドリング

- **pool.csv が存在しない:** 空の監視リストとして扱い、UIで登録を促す（例外を投げない）。
- **個別銘柄の取得失敗（無効なシンボル・通信エラー）:** その行だけ `status="no_data"` にし、他の銘柄の表示は継続する。1銘柄の失敗で全体を落とさない。
- **日経データ取得失敗:** ゲージ部分にエラーメッセージを表示し、監視リストは可能な範囲で表示する。
- **データ不足（25日未満）:** 乖離率 `None` 扱い。

---

## 7. テスト方針

`dashboard_data.py` の純粋ロジックを `tests/test_dashboard_data.py` でTDD:

- `classify_deviation`: normal / warning / danger / no_data 各境界（-6.9→normal, -7→warning, -10→danger, None→no_data）
- `load_watchlist`: 正常CSV読み込み / ファイル無し→空リスト / 余分な列を無視
- `build_watch_rows`: `fetch_fn` をモックし、乖離率の深い順ソート・no_data末尾を検証
- `build_market_status`: `fetch_fn` モックで status 判定と fresh_touch_fired 判定を検証

`app.py`（Streamlit UI）は手動起動で動作確認する（自動テスト対象外）。

---

## 8. スコープ外（このサブプロジェクトでやらないこと）

- 業績フィルタ・自動pool構築（→③）
- 個別下限のキャリブレ・買い候補ランキング（→④）
- J-Quants連携（→②）
- 認証・外部公開・スマホ対応（全体スコープ外。ローカル専用）
- 自動発注（プロジェクト全体のスコープ外）

---

## 9. 完了の定義

- `streamlit run app.py` でダッシュボードが起動する。
- 日経の暴落ゲージが現在の乖離率と状態（平常/注意/暴落点）を表示する。
- `out/pool.csv` に登録した銘柄が乖離率の深い順に表示される。
- `out/pool.csv` を編集して「🔄 更新」すると監視リストが変わる。
- `tests/test_dashboard_data.py` が全グリーン。
