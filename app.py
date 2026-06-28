from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from src.config import load_config
from src.dashboard_data import DashboardData, WatchRow, build_dashboard_data

_PROJECT_ROOT = Path(__file__).parent
_CONFIG_PATH = _PROJECT_ROOT / "conditions.yaml"

st.set_page_config(page_title="株リサーチャー", layout="wide")

st.markdown("""
<style>
  .stApp { background-color: #0d0d0d; color: #e8e8e8; }
  [data-testid="stHeader"] { background-color: #0d0d0d; }
  .stButton > button {
    background: #1a1a1a; color: #e8e8e8;
    border: 1px solid #333; border-radius: 8px; padding: 6px 14px;
  }
  .stButton > button:hover { background: #2a2a2a; border-color: #555; }
  hr { border-color: #1e1e1e !important; }
  .stCaption { color: #555 !important; }
  h1, h2, h3 { color: #ffffff !important; }
  a { color: inherit !important; text-decoration: none !important; }
</style>
""", unsafe_allow_html=True)

cfg      = load_config(_CONFIG_PATH)
_TTL     = cfg.dashboard.cache_ttl_minutes * 60
_WARNING = cfg.dashboard.warning_deviation_pct  # -7
_DANGER  = cfg.dashboard.danger_deviation_pct   # -10

_COLOR = {"normal": "#4a9eff", "warning": "#ff8c00", "danger": "#00e676", "no_data": "#555"}
_BG    = {"normal": "#0d1a2b", "warning": "#1a1200", "danger": "#001a0d", "no_data": "#141414"}
_BORDER= {"normal": "#1e3a5f", "warning": "#4a3000", "danger": "#005c2e", "no_data": "#2a2a2a"}


@st.cache_data(ttl=_TTL, show_spinner="データ取得中...")
def _get_data() -> DashboardData:
    return build_dashboard_data(cfg, today=date.today())


def _tradingview_url(symbol: str) -> str:
    code = symbol.replace(".T", "")
    return f"https://www.tradingview.com/chart/?symbol=TSE:{code}"


def _distance_bar(dev: float | None, h: int = 20) -> str:
    """買いシグナルまでの距離バー。左端=今、右端=買い場(-10%)。"""
    if dev is None:
        return ""
    # devが0%のとき0%埋まり、-10%のとき100%埋まり
    fill = max(0.0, min(dev / _DANGER * 100, 100.0))
    warn_pos = _WARNING / _DANGER * 100  # 警戒ラインの位置
    col = "#00e676" if dev <= _DANGER else "#ff8c00" if dev <= _WARNING else "#4a9eff"
    remaining = max(0.0, _DANGER - dev)  # あと何%下がれば買い場か
    return (
        f'<div style="position:relative;width:100%;height:{h}px;background:#111;border-radius:8px;overflow:hidden;">'
        f'<div style="width:{fill:.1f}%;height:100%;background:linear-gradient(90deg,#1a3a6a,{col});box-shadow:0 0 12px {col}55;transition:width 0.3s;"></div>'
        f'<div style="position:absolute;left:{warn_pos:.1f}%;top:0;height:100%;width:2px;background:#ff8c00;opacity:0.7;"></div>'
        f'</div>'
        f'<div style="display:flex;justify-content:space-between;font-size:10px;color:#444;margin-top:3px;">'
        f'<span style="color:#888;">現在位置</span>'
        f'<span style="color:#ff8c00;">注意 {_WARNING}%</span>'
        f'<span style="color:#00e676;">🎯 買い場 {_DANGER}%</span>'
        f'</div>'
    )


# ─── ヘッダー ─────────────────────────────────────────────────
c_ttl, c_btn = st.columns([7, 1])
with c_ttl:
    st.markdown("<h1 style='margin-bottom:0;'>📈 株リサーチャー</h1>", unsafe_allow_html=True)
with c_btn:
    st.write("")
    if st.button("🔄 更新"):
        st.cache_data.clear()
        st.rerun()

data = _get_data()
m    = data.market

# ─── メインステータス: 買いシグナルまでの距離 ────────────────
dev = m.current_deviation_pct

if dev is None:
    distance_str = "—"
    phase_label  = "データなし"
    phase_color  = "#555"
    phase_bg     = "#141414"
    phase_border = "#2a2a2a"
    phase_desc   = ""
elif dev <= _DANGER:
    remaining    = 0.0
    distance_str = "0.0%"
    phase_label  = "🎯 今が買い場！"
    phase_color  = "#00e676"
    phase_bg     = "#001a0d"
    phase_border = "#005c2e"
    phase_desc   = "下の監視銘柄のチャートを確認し、購入を検討してください。"
elif dev <= _WARNING:
    remaining    = _DANGER - dev
    distance_str = f"{remaining:.1f}%"
    phase_label  = "⚡ 買い場に接近中"
    phase_color  = "#ff8c00"
    phase_bg     = "#1a1200"
    phase_border = "#4a3000"
    phase_desc   = "市場が下落中です。銘柄の準備をしておきましょう。"
else:
    remaining    = _DANGER - dev
    distance_str = f"{remaining:.1f}%"
    phase_label  = "⏳ 待機中"
    phase_color  = "#4a9eff"
    phase_bg     = "#0d1a2b"
    phase_border = "#1e3a5f"
    phase_desc   = "日経が買いシグナルラインに達したら通知が出ます。"

st.markdown(
    f'<div style="background:{phase_bg};border:1px solid {phase_border};border-left:6px solid {phase_color};padding:24px 28px;border-radius:14px;margin-bottom:20px;">'
    f'<div style="font-size:13px;color:#666;letter-spacing:1px;margin-bottom:10px;">📊 買いシグナルまでの距離（日経225）</div>'
    f'<div style="display:flex;align-items:center;gap:28px;flex-wrap:wrap;margin-bottom:16px;">'
    f'<div>'
    f'<div style="font-size:11px;color:#555;margin-bottom:2px;">あと</div>'
    f'<div style="font-size:64px;font-weight:900;color:{phase_color};line-height:1;letter-spacing:-3px;">{distance_str}</div>'
    f'<div style="font-size:12px;color:#555;margin-top:2px;">下落で買いシグナル</div>'
    f'</div>'
    f'<div style="flex:1;">'
    f'<div style="font-size:20px;font-weight:700;color:{phase_color};margin-bottom:6px;">{phase_label}</div>'
    f'<div style="font-size:14px;color:#aaa;margin-bottom:12px;">{phase_desc}</div>'
    f'<div style="font-size:12px;color:#555;">日経現在値: ¥{m.current_price:,.0f} &nbsp;|&nbsp; 25日乖離率: {dev:+.2f}%</div>' if dev is not None else
    f'<div style="font-size:20px;font-weight:700;color:{phase_color};margin-bottom:6px;">{phase_label}</div>'
    f'</div></div>'
    f'{_distance_bar(dev, h=20)}'
    f'</div>',
    unsafe_allow_html=True,
)

if m.fresh_touch_fired and m.last_signal_date:
    st.markdown(
        f'<div style="background:#001a0d;border:2px solid #00e676;border-radius:12px;padding:18px 24px;margin-bottom:16px;text-align:center;">'
        f'<div style="font-size:24px;font-weight:900;color:#00e676;">🎯 3か月ぶりの買いシグナル発火！</div>'
        f'<div style="font-size:14px;color:#aaa;margin-top:6px;">最終発火日: {m.last_signal_date} &nbsp;|&nbsp; 下の銘柄のチャートを確認してから購入を検討してください</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

st.divider()

# ─── 使い方説明 ───────────────────────────────────────────────
with st.expander("📖 このアプリの使い方"):
    st.markdown("""
**このアプリは「まだ株・奥義継承」手法に基づくスクリーナーです。**

1. **待機中（青）** → 今は動かない。日経が下がるのを待つだけ
2. **接近中（オレンジ）** → 買い場が近い。下の銘柄リストを確認しておく
3. **買い場！（緑）** → 日経の25日乖離率が -10% に到達。下の銘柄を購入検討

**購入手順:**
- 📋 下のリストから気になる銘柄を選ぶ
- 📊 「チャートを見る」で月足チャートを最終確認
- ✅ 上昇トレンドが崩れていなければ購入

※ 最終判断は必ず自分で行ってください。このアプリは投資助言ではありません。
    """)

# ─── 監視銘柄リスト ───────────────────────────────────────────
st.markdown(
    "<h2 style='margin-bottom:4px;'>📋 監視銘柄</h2>"
    "<div style='font-size:13px;color:#555;margin-bottom:16px;'>毎週土曜に自動更新 — 買いシグナル発火時に購入を検討する銘柄</div>",
    unsafe_allow_html=True,
)

if not data.rows:
    st.info("監視銘柄がありません。`out/pool.csv` に銘柄を追加してください。")
else:
    # pool.csvに業績データがあれば読み込む
    pool_path = _PROJECT_ROOT / "out" / "pool.csv"
    growth_data: dict[str, dict] = {}
    if pool_path.exists():
        try:
            pool_df = pd.read_csv(pool_path)
            for _, prow in pool_df.iterrows():
                growth_data[str(prow["symbol"])] = {
                    "rev": prow.get("revenue_growth_pct"),
                    "inc": prow.get("net_income_growth_pct"),
                }
        except Exception:
            pass

    for row in data.rows:
        clr_r = _COLOR.get(row.status, "#555")
        bg_r  = _BG.get(row.status, "#141414")
        bdr_r = _BORDER.get(row.status, "#2a2a2a")
        dev_r   = f"{row.current_deviation_pct:+.2f}%" if row.current_deviation_pct is not None else "—"
        price_r = f"¥{row.current_price:,.0f}" if row.current_price is not None else "—"
        tv_url  = _tradingview_url(row.symbol)
        gd      = growth_data.get(row.symbol, {})
        rev_str = f"売上 +{gd['rev']:.0f}%" if gd.get("rev") is not None else ""
        inc_str = f"利益 +{gd['inc']:.0f}%" if gd.get("inc") is not None else ""
        growth_str = " &nbsp;|&nbsp; ".join(x for x in [rev_str, inc_str] if x)

        # 個別銘柄の「買い場まであと」
        if row.current_deviation_pct is not None:
            stock_remaining = max(0.0, _DANGER - row.current_deviation_pct)
            stock_dist = f"個別：あと {stock_remaining:.1f}% で買い場" if stock_remaining > 0 else "個別：買い場レベル"
        else:
            stock_dist = ""

        st.markdown(
            f'<div style="background:{bg_r};border:1px solid {bdr_r};border-left:4px solid {clr_r};padding:16px 20px;border-radius:12px;margin-bottom:10px;">'
            f'<div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;">'

            # 銘柄名・コード・業績
            f'<div style="flex:3;min-width:160px;">'
            f'<div style="font-size:18px;font-weight:700;color:#e8e8e8;">{row.name}</div>'
            f'<div style="font-size:12px;color:#555;margin-top:2px;">{row.symbol}</div>'
            f'<div style="font-size:12px;color:#4a9eff;margin-top:4px;">{growth_str}</div>'
            f'</div>'

            # 現在値
            f'<div style="flex:1;min-width:90px;text-align:center;">'
            f'<div style="font-size:11px;color:#555;">現在値</div>'
            f'<div style="font-size:16px;color:#aaa;font-weight:600;">{price_r}</div>'
            f'</div>'

            # 乖離率
            f'<div style="flex:1;min-width:90px;text-align:center;">'
            f'<div style="font-size:11px;color:#555;">25日乖離率</div>'
            f'<div style="font-size:22px;font-weight:900;color:{clr_r};">{dev_r}</div>'
            f'<div style="font-size:10px;color:#555;margin-top:1px;">{stock_dist}</div>'
            f'</div>'

            # チャートボタン
            f'<div style="flex:0;min-width:110px;text-align:center;">'
            f'<a href="{tv_url}" target="_blank">'
            f'<div style="background:#1e1e1e;border:1px solid #333;border-radius:8px;padding:8px 14px;font-size:13px;color:#aaa;cursor:pointer;white-space:nowrap;">'
            f'📊 チャートを見る</div></a>'
            f'</div>'

            f'</div>'
            f'<div style="margin-top:10px;">{_distance_bar(row.current_deviation_pct, h=10)}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

st.markdown("<br>", unsafe_allow_html=True)
st.caption(f"最終更新: {data.as_of}　|　注意ライン {_WARNING}%　買いシグナルライン {_DANGER}%　|　毎週土曜 0:00 JST 自動更新")
