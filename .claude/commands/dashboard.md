# /dashboard

ローカルでダッシュボードを起動します。

## 実行

以下のコマンドを実行します:
cd "C:\Users\you-k\OneDrive\Desktop\株リサーチ"
streamlit run app.py

ブラウザが自動で開きます（http://localhost:8501）。

## 監視銘柄の追加・削除

out/pool.csv をテキストエディタで編集します:

symbol,name
3038.T,神戸物産
7203.T,トヨタ自動車

symbol は yfinance 形式（日本株は末尾に .T）。
編集後、ダッシュボードの「更新」ボタンを押すと反映されます。

## 閾値の変更

conditions.yaml の dashboard セクションを編集します:

dashboard:
  warning_deviation_pct: -7   # 黄信号（注意）
  danger_deviation_pct: -10   # 赤信号（暴落点）
