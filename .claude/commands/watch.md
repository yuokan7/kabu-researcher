# /watch

日経225の25日乖離率を監視し、3か月ぶりの閾値タッチを検出して通知します。

## 実行

```bash
cd "C:\Users\you-k\OneDrive\Desktop\株リサーチ"
python -m src.watch_runner
```

## 出力

- コンソール: シグナル一覧
- CSV: `./out/candidates.csv`
