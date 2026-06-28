from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from src.config import load_config
from src.dashboard_data import DashboardData, build_dashboard_data

_PROJECT_ROOT = Path(__file__).parent
_CONFIG_PATH = _PROJECT_ROOT / "conditions.yaml"

st.set_page_config(page_title="株リサーチャー", layout="wide")

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@700;900&display=swap');

  .stApp {
    background: linear-gradient(180deg, #5ec8f0 0%, #a8e6fa 35%, #d4f3ff 60%, #e8fbff 100%);
    font-family: 'Noto Sans JP', sans-serif;
  }
  [data-testid="stHeader"] { background: transparent; }
  .block-container { padding-top: 1.4rem; padding-bottom: 2rem; max-width: 1100px; }

  /* ふきだし風ボタン */
  .stButton > button {
    background: linear-gradient(180deg, #ffe066 0%, #ffb800 100%);
    color: #6b3a00; font-weight: 900; font-size: 14px;
    border: 3px solid #d48000; border-radius: 30px;
    padding: 8px 20px; box-shadow: 0 4px 0 #a06000, 0 6px 12px #00000033;
    text-shadow: 0 1px 0 #fff8;
  }
  .stButton > button:hover {
    background: linear-gradient(180deg, #fff080 0%, #ffc820 100%);
    transform: translateY(2px); box-shadow: 0 2px 0 #a06000, 0 4px 8px #00000033;
  }
  hr { border-color: #b8e8f8 !important; }
  a { color: inherit !important; text-decoration: none !important; }

  /* 汎用カード */
  .puyo-card {
    border-radius: 20px; padding: 18px 20px; margin-bottom: 14px;
    border: 3px solid; position: relative; overflow: hidden;
  }
  .puyo-card::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 40%;
    background: linear-gradient(180deg, #ffffff33 0%, transparent 100%);
    border-radius: 18px 18px 0 0; pointer-events: none;
  }

  /* タイトル */
  .app-title {
    font-size: clamp(20px, 5vw, 34px); font-weight: 900; color: #fff;
    text-shadow: 0 3px 0 #1a88c0, 0 5px 12px #0060a044;
    letter-spacing: -0.5px; margin: 0;
  }

  /* ヒーロー数字 */
  .hero-num {
    font-size: clamp(44px, 14vw, 74px); font-weight: 900; line-height: 1; letter-spacing: -2px;
  }

  /* ラベルバッジ */
  .badge {
    display: inline-block; font-size: 12px; font-weight: 900;
    padding: 3px 12px; border-radius: 20px; border: 2px solid;
  }

  /* カードレイアウト */
  .card-row { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; }
  .card-name   { flex: 3 1 160px; }
  .card-metric { flex: 1 1 90px; text-align: center; }
  .card-btn    { flex: 0 1 126px; text-align: center; }

  @media (max-width: 640px) {
    .card-name   { flex-basis: 100%; }
    .card-metric { flex-basis: 30%; text-align: left; }
    .card-btn    { flex-basis: 100%; margin-top: 8px; }
    .hero-flex   { flex-direction: column; align-items: flex-start !important; gap: 14px !important; }
  }
</style>
""", unsafe_allow_html=True)

cfg      = load_config(_CONFIG_PATH)
_TTL     = cfg.dashboard.cache_ttl_minutes * 60
_WARNING = cfg.dashboard.warning_deviation_pct  # -7
_DANGER  = cfg.dashboard.danger_deviation_pct   # -10

# ぷよぷよ配色: 待機=紫っぽい青 / もうすぐ=緑 / 買い場=赤（ぷよの発火色）
_THEME = {
    "normal":  {"col":"#5b6ef5", "bg":"#eef0ff", "brd":"#8090f8", "badge_bg":"#d8dcff", "txt":"#2030c0"},
    "warning": {"col":"#19c07a", "bg":"#e8faf2", "brd":"#52d89e", "badge_bg":"#c4f5de", "txt":"#0a7a4a"},
    "danger":  {"col":"#f53c5b", "bg":"#fff0f3", "brd":"#f87090", "badge_bg":"#ffd0db", "txt":"#c0001e"},
    "no_data": {"col":"#aaaaaa", "bg":"#f5f5f5", "brd":"#cccccc", "badge_bg":"#e8e8e8", "txt":"#777"},
}
_ROW_LABEL = {"normal": "⏳ 待機中", "warning": "👀 そろそろ！", "danger": "🎯 買い場！", "no_data": "—"}
_NIKKEI_TV = "https://www.tradingview.com/chart/?symbol=TVC:NI225"


@st.cache_data(ttl=_TTL, show_spinner="データ読み込み中…")
def _get_data() -> DashboardData:
    return build_dashboard_data(cfg, today=date.today())


def _tradingview_url(symbol: str) -> str:
    return f"https://www.tradingview.com/chart/?symbol=TSE:{symbol.replace('.T','')}"


def _yen(v: float | None) -> str:
    return f"¥{v:,.0f}" if v is not None else "—"


def _recovery_profit_100(price: float | None, dev: float | None) -> float | None:
    if price is None or dev is None or dev >= 0:
        return None
    return (price / (1 + dev / 100.0) - price) * 100.0


def _dist_bar(dev: float | None, theme: dict, h: int = 16) -> str:
    if dev is None:
        return ""
    fill = max(0.0, min(dev / _DANGER * 100, 100.0))
    warn = _WARNING / _DANGER * 100
    col  = theme["col"]
    return (
        f'<div style="position:relative;width:100%;height:{h}px;background:#e0eef8;border-radius:99px;overflow:hidden;'
        f'border:2px solid #c0d8ea;box-shadow:inset 0 2px 4px #0002;">'
        f'<div style="width:{fill:.1f}%;height:100%;background:linear-gradient(90deg,#a0c4ff,{col});border-radius:99px;'
        f'box-shadow:0 0 8px {col}88;"></div>'
        f'<div style="position:absolute;left:{warn:.1f}%;top:0;height:100%;width:2px;background:#19c07a;opacity:0.7;"></div>'
        f'</div>'
        f'<div style="display:flex;justify-content:space-between;font-size:10px;color:#88aac0;margin-top:3px;">'
        f'<span>いまの安さ</span><span style="color:{col};font-weight:700;">🎯 買い場 ({_DANGER:.0f}%)</span>'
        f'</div>'
    )


# ─── ヘッダー ─────────────────────────────────────────────────
c_ttl, c_btn = st.columns([5, 1])
with c_ttl:
    st.markdown(
        '<div style="display:flex;align-items:center;gap:12px;">'
        '<div style="width:42px;height:42px;background:linear-gradient(135deg,#5ec8f0,#2a8fd4);'
        'border-radius:12px;border:3px solid #fff;box-shadow:0 3px 8px #00608044;'
        'display:flex;align-items:center;justify-content:center;font-size:22px;">📈</div>'
        '<div class="app-title">株リサーチャー</div>'
        '</div>',
        unsafe_allow_html=True,
    )
with c_btn:
    if st.button("🔄 更新"):
        st.cache_data.clear()
        st.rerun()

st.write("")
data = _get_data()
m    = data.market
dev  = m.current_deviation_pct

# ─── ステータス判定 ────────────────────────────────────────────
if dev is None:
    status_key, distance_str, phase_label, phase_desc = "no_data", "—", "データなし", ""
elif dev <= _DANGER:
    status_key, distance_str = "danger", "0.0%"
    phase_label  = "🎯 いまが買い場！"
    phase_desc   = "日経が割安水準に到達！下の銘柄のチャートを確認して購入を検討しよう！"
elif dev <= _WARNING:
    status_key   = "warning"
    distance_str = f"{_DANGER - dev:.1f}%"
    phase_label  = "👀 そろそろ買い場！"
    phase_desc   = "日経が下落中！下の銘柄をチェックして準備しておこう！"
else:
    status_key   = "normal"
    distance_str = f"{_DANGER - dev:.1f}%"
    phase_label  = "⏳ いまは待機"
    phase_desc   = "まだ買い場ではないよ。日経が下がるのをゆっくり待とう！"

th = _THEME[status_key]
nikkei_txt = (f'日経平均 {_yen(m.current_price)} ／ 25日平均との差 {dev:+.1f}%' if dev is not None else "取得失敗")

# ─── メインカード ──────────────────────────────────────────────
st.markdown(
    f'<div class="puyo-card" style="background:{th["bg"]};border-color:{th["brd"]};'
    f'box-shadow:0 6px 0 {th["brd"]},0 8px 24px #00000018;">'

    f'<div style="font-size:13px;font-weight:700;color:{th["col"]};letter-spacing:1px;margin-bottom:12px;">'
    f'📊 買い場まであと…（日経平均）</div>'

    f'<div class="hero-flex" style="display:flex;align-items:center;gap:24px;flex-wrap:wrap;margin-bottom:16px;">'
    f'<div style="text-align:center;">'
    f'<span class="hero-num" style="color:{th["col"]};text-shadow:0 4px 0 {th["brd"]};">{distance_str}</span>'
    f'<div style="font-size:14px;font-weight:700;color:{th["txt"]};margin-top:2px;">下落で買い場</div>'
    f'</div>'
    f'<div style="flex:1;min-width:180px;">'
    f'<div style="font-size:22px;font-weight:900;color:{th["txt"]};margin-bottom:6px;">{phase_label}</div>'
    f'<div style="font-size:14px;color:#556677;line-height:1.6;">{phase_desc}</div>'
    f'</div></div>'

    f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:8px;">'
    f'<span style="font-size:12px;color:#778899;">{nikkei_txt}</span>'
    f'<a href="{_NIKKEI_TV}" target="_blank">'
    f'<span style="font-size:13px;font-weight:700;color:{th["txt"]};background:{th["badge_bg"]};'
    f'border:2px solid {th["brd"]};border-radius:20px;padding:5px 14px;">📊 日経チャート</span></a>'
    f'</div>'
    f'{_dist_bar(dev, th, h=16)}'
    f'</div>',
    unsafe_allow_html=True,
)

if m.fresh_touch_fired and m.last_signal_date:
    rt = _THEME["danger"]
    st.markdown(
        f'<div class="puyo-card" style="background:{rt["bg"]};border-color:{rt["brd"]};'
        f'box-shadow:0 6px 0 {rt["brd"]},0 0 40px #f53c5b44;text-align:center;">'
        f'<div style="font-size:24px;font-weight:900;color:{rt["txt"]};">🎯 3か月ぶりの買いシグナル発火！！</div>'
        f'<div style="font-size:13px;color:#667788;margin-top:6px;">最終発火日: {m.last_signal_date} ／ 下の銘柄のチャートを確認して購入を検討しよう！</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

# ─── 使い方 ────────────────────────────────────────────────────
with st.expander("📖 はじめての方へ — 使い方と用語"):
    st.markdown(f"""
**この手法のキホン：好業績の株を「暴落で安くなった時」に仕込む**

- **⏳ いまは待機（青）** … 何もしない。日経が下がるのを待つ
- **👀 そろそろ！（緑）** … 日経が下落中。下の銘柄をチェックして準備
- **🎯 いまが買い場（赤）** … 日経が割安水準（{_DANGER:.0f}%）に到達。購入を検討！

**用語の意味**
- **25日平均との差（乖離率）** … 株価が直近25日の平均より何%上下しているか。大きくマイナス＝急落で割安。{_DANGER:.0f}%が買い場の目安
- **売上 / 純利益（前年比）** … 去年より何%成長したか。高いほど好業績
- **100株購入額** … 日本株は基本100株単位。購入に必要なおよその金額
- **回復益（目安）** … 現在の株価から25日平均まで戻った場合の100株あたり利益見込み

**買うときの流れ**
日経が「🎯 いまが買い場」になる → 下の銘柄から選ぶ → 「📊 チャートを見る」で最終確認 → 100株購入を検討

※ このアプリは投資助言ではありません。最終判断はご自身で。
    """)

st.markdown(
    '<div style="font-size:18px;font-weight:900;color:#2060a0;margin:12px 0 4px;">'
    '📋 監視銘柄</div>'
    '<div style="font-size:13px;color:#6688aa;margin-bottom:14px;">好業績で上昇トレンドの株を自動選定（毎週土曜更新）。安い順に表示。</div>',
    unsafe_allow_html=True,
)

# ─── 監視銘柄リスト ────────────────────────────────────────────
if not data.rows:
    st.info("監視銘柄がありません。`out/pool.csv` に銘柄を追加してください。")
else:
    pool_path = _PROJECT_ROOT / "out" / "pool.csv"
    growth_data: dict[str, dict] = {}
    if pool_path.exists():
        try:
            pdf = pd.read_csv(pool_path)
            for _, prow in pdf.iterrows():
                growth_data[str(prow["symbol"])] = {
                    "rev": prow.get("revenue_growth_pct"),
                    "inc": prow.get("net_income_growth_pct"),
                }
        except Exception:
            pass

    for row in data.rows:
        th_r = _THEME.get(row.status, _THEME["no_data"])
        dev_r   = f"{row.current_deviation_pct:+.1f}%" if row.current_deviation_pct is not None else "—"
        price_r = _yen(row.current_price)
        unit_r  = _yen(row.current_price * 100) if row.current_price is not None else "—"
        tv_url  = _tradingview_url(row.symbol)
        gd = growth_data.get(row.symbol, {})
        rev = f"売上 +{gd['rev']:.0f}%" if gd.get("rev") is not None else ""
        inc = f"純利益 +{gd['inc']:.0f}%" if gd.get("inc") is not None else ""
        growth_str = " ／ ".join(x for x in [rev, inc] if x)
        growth_html = (
            f'<div style="font-size:12px;color:#4488cc;font-weight:700;margin-top:4px;">📈 前年比 {growth_str}</div>'
            if growth_str else ""
        )

        profit = _recovery_profit_100(row.current_price, row.current_deviation_pct)
        if profit is not None and profit > 0:
            profit_html = (
                f'<div class="card-metric">'
                f'<div style="font-size:11px;color:#778899;font-weight:700;">回復益(目安)</div>'
                f'<div style="font-size:16px;font-weight:900;color:#e07800;">+{_yen(profit)}</div>'
                f'<div style="font-size:10px;color:#99aacc;">平均まで戻れば</div>'
                f'</div>'
            )
        else:
            profit_html = (
                f'<div class="card-metric">'
                f'<div style="font-size:11px;color:#778899;font-weight:700;">回復益(目安)</div>'
                f'<div style="font-size:15px;color:#aabbcc;">—</div>'
                f'</div>'
            )

        st.markdown(
            f'<div class="puyo-card" style="background:{th_r["bg"]};border-color:{th_r["brd"]};'
            f'box-shadow:0 5px 0 {th_r["brd"]},0 7px 18px #00000014;">'
            f'<div class="card-row">'

            f'<div class="card-name">'
            f'<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">'
            f'<span style="font-size:17px;font-weight:900;color:#1a2a3a;">{row.name}</span>'
            f'<span class="badge" style="background:{th_r["badge_bg"]};color:{th_r["txt"]};border-color:{th_r["brd"]};">'
            f'{_ROW_LABEL.get(row.status,"")}</span>'
            f'</div>'
            f'<div style="font-size:12px;color:#8899aa;margin-top:2px;">{row.symbol}</div>'
            f'{growth_html}'
            f'</div>'

            f'<div class="card-metric">'
            f'<div style="font-size:11px;color:#778899;font-weight:700;">現在値</div>'
            f'<div style="font-size:16px;color:#2a3a4a;font-weight:800;">{price_r}</div>'
            f'<div style="font-size:10px;color:#99aacc;margin-top:2px;">100株 {unit_r}</div>'
            f'</div>'

            f'<div class="card-metric">'
            f'<div style="font-size:11px;color:#778899;font-weight:700;">25日平均との差</div>'
            f'<div style="font-size:22px;font-weight:900;color:{th_r["col"]};text-shadow:0 2px 0 {th_r["brd"]};">{dev_r}</div>'
            f'</div>'

            f'{profit_html}'

            f'<div class="card-btn">'
            f'<a href="{tv_url}" target="_blank">'
            f'<div style="background:linear-gradient(180deg,#5ec8f0,#2a8fd4);color:#fff;font-weight:900;font-size:13px;'
            f'border-radius:20px;padding:10px 14px;border:2px solid #1a70b0;'
            f'box-shadow:0 3px 0 #1a60a0;text-shadow:0 1px 0 #0006;white-space:nowrap;">📊 チャートを見る</div>'
            f'</a></div>'

            f'</div>'
            f'<div style="margin-top:12px;">{_dist_bar(row.current_deviation_pct, th_r, h=10)}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

st.markdown("<br>", unsafe_allow_html=True)
st.markdown(
    f'<div style="text-align:center;font-size:12px;color:#6688aa;padding:8px;">'
    f'最終更新: {data.as_of}　|　買い場の目安 {_DANGER:.0f}%　|　毎週土曜 0:00 JST 自動更新'
    f'</div>',
    unsafe_allow_html=True,
)
