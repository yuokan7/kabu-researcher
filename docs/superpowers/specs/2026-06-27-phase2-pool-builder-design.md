# Phase 2a: pool自動更新 設計書

**作成日:** 2026-06-27
**対象:** まだ株・奥義継承スクリーナー / サブプロジェクト② pool自動更新

---

## 0. このサブプロジェクトの位置づけ

| # | サブプロジェクト | 状態 |
|---|---|---|
| ① | Webダッシュボード v1 | ✅ 完了 |
| **②** | **pool自動更新（本書）** | 実装中 |
| ③ | チャート表示 | 未着手 |
| ④ | 個別トリガー＋ランキング | 未着手 |

---

## 1. ゴール

毎週土曜0:00 JSTに GitHub Actions が自動実行し、全上場銘柄を3層スクリーニングして「買いチャンスに近い順TOP10」を `out/pool.csv` に書き出す。Streamlit ダッシュボードは次のアクセス時に自動反映される。

---

## 2. 全体アーキテクチャ

```
毎週土曜0:00 JST（GitHub Actions自動起動）
         ↓
src/jquants.py
 email + password → リフレッシュトークン → IDトークン
 GET /listed/info → 全上場銘柄リスト
 GET /fins/statements → 財務諸表（12週遅延・無料プラン）
         ↓
src/fundamentals.py【第1層 業績フィルタ】
 売上高YoY ≥ 20% × 直近3期連続
 純利益YoY ≥ 20% × 直近3期連続
 営業CF > 0
 ETF・REIT除外
 → 数百社に圧縮。各銘柄の成長率を記録。
         ↓
src/trend.py【第2層 月足トレンドフィルタ】(yfinance)
 月足パーフェクトオーダー（SMA6 > SMA12 > SMA24、全SMA上向き）
 高値・安値切り上げ継続（直近2スイング以上）
 上場来高値から25%以内
 → pool確定
         ↓
src/trigger.py【乖離率計算】（既存・流用）
 各pool銘柄の現在25日乖離率を計算
 乖離率の深い順（買いチャンスに近い順）でソート
         ↓
TOP10を out/pool.csv に書き出し
         ↓
git commit & push → Streamlit Cloud 自動反映
```

---

## 3. 新規ファイル構成

```
src/
  jquants.py          # J-Quants認証 + データ取得クライアント
  fundamentals.py     # 第1層: 業績フィルタ
  trend.py            # 第2層: 月足トレンドフィルタ（yfinance）
scripts/
  build_pool.py       # 全体を繋ぐ実行スクリプト
.github/
  workflows/
    build_pool.yml    # GitHub Actions ワークフロー
```

変更ファイル:
```
out/pool.csv          # 列を追加（売上成長率・純利益成長率・乖離率）
```

---

## 4. J-Quants連携（src/jquants.py）

### 4-1. 認証

毎回実行のたびにメール・パスワードで認証してトークンを取得する。リフレッシュトークンの失効問題を根本回避。

```
POST /token/auth_user（email + password）→ refresh_token
POST /token/auth_refresh（refresh_token）→ id_token（24時間有効）
全APIコール: Authorization: Bearer {id_token}
```

### 4-2. 使用API

| API | 用途 | 遅延 |
|---|---|---|
| `GET /listed/info` | 全上場銘柄リスト（コード・銘柄名・市場区分） | なし |
| `GET /fins/statements` | 財務諸表（売上高・純利益・営業CF） | 12週（無料プラン） |

### 4-3. GitHub Secrets

| Secret名 | 内容 |
|---|---|
| `JQUANTS_EMAIL` | J-Quantsのログインメールアドレス |
| `JQUANTS_PASSWORD` | J-Quantsのログインパスワード |

ローカルでは `.env` から読む（既存の仕組みを踏襲）:
```
JQUANTS_EMAIL=xxx@gmail.com
JQUANTS_PASSWORD=xxxxxx
```

---

## 5. 第1層: 業績フィルタ（src/fundamentals.py）

入力: J-Quants財務データ（全銘柄）
出力: `list[FundamentalResult]`（通過銘柄 + 成長率データ）

```python
@dataclass
class FundamentalResult:
    symbol: str           # yfinance形式 (例: "3038.T")
    name: str
    revenue_growth_pct: float    # 直近期の売上高YoY成長率(%)
    net_income_growth_pct: float # 直近期の純利益YoY成長率(%)
```

フィルタ条件（すべて `conditions.yaml` から読む）:
- `fundamentals.revenue_growth.min_yoy_pct` (=20) × `consecutive_periods` (=3) 期連続
- `fundamentals.net_income_growth.min_yoy_pct` (=20) × 同上
- `fundamentals.require_positive_operating_cf` (=true)
- `universe.exclude_etf_reit` (=true) でETF・REIT除外
- `universe.markets` で対象市場を絞る

---

## 6. 第2層: 月足トレンドフィルタ（src/trend.py）

入力: `list[FundamentalResult]`
出力: `list[FundamentalResult]`（さらに絞り込み）

yfinanceで各銘柄の日足を取得 → 月末終値にリサンプル → 以下を判定:

| 条件 | 設定値（conditions.yaml） |
|---|---|
| 月足パーフェクトオーダー | `trend.ma_periods: [6, 12, 24]` |
| 全SMA上向き | `trend.perfect_order.require_rising_slope: true` |
| 高値・安値切り上げ | `trend.higher_highs_lows.min_swings: 2` |
| 上場来高値接近 | `trend.all_time_high.max_distance_pct: 25` |

yfinanceレート制限対策: 既存 `fetch.py` のリトライロジックを流用。

---

## 7. ランキングと出力

pool銘柄ごとに既存 `src/trigger.py` の `calc_deviation` で現在の25日乖離率を計算。

ソート: `current_deviation_pct` 昇順（マイナスが大きいほど買いチャンスに近い）

TOP10を選択して `out/pool.csv` を上書き:

```csv
symbol,name,revenue_growth_pct,net_income_growth_pct,current_deviation_pct
3038.T,神戸物産,28.5,35.2,-4.1
3064.T,MonotaRO,22.1,24.8,-3.7
...
```

**エラー時の安全弁:**
- J-Quants認証失敗 → 既存 `pool.csv` を維持して終了（アプリ継続）
- 0銘柄通過 → 既存 `pool.csv` を維持して終了
- yfinanceレート制限 → リトライ後も失敗した銘柄はスキップ

---

## 8. GitHub Actions（.github/workflows/build_pool.yml）

```yaml
name: Build Pool

on:
  schedule:
    - cron: '0 15 * * 5'  # 毎週金曜15:00 UTC = 土曜0:00 JST
  workflow_dispatch:        # GitHub UIから手動実行可能

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: write       # pool.csvをpushするために必要

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python scripts/build_pool.py
        env:
          JQUANTS_EMAIL:    ${{ secrets.JQUANTS_EMAIL }}
          JQUANTS_PASSWORD: ${{ secrets.JQUANTS_PASSWORD }}
      - name: Commit pool.csv if changed
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add out/pool.csv
          git diff --staged --quiet || git commit -m "chore: update pool.csv [skip ci]"
          git push
```

---

## 9. 完了の定義

- [ ] GitHub Actionsが土曜0:00 JSTに自動実行される
- [ ] 手動実行（workflow_dispatch）でも動作する
- [ ] `out/pool.csv` が売上成長率・純利益成長率・乖離率の列を含む
- [ ] TOP10銘柄が乖離率深い順に並んでいる
- [ ] J-Quants認証失敗時に既存pool.csvを維持する
- [ ] Streamlitダッシュボードにpool更新が反映される（既存コードで自動対応済み）
