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
  .stApp { background-color: #0d0d0d; color: #e8e8e8; }
  [data-testid="stHeader"] { background-color: #0d0d0d; }
  .block-container { padding-top: 2rem; padding-bottom: 2rem; }
  .stButton > button {
    background: #1a1a1a; color: #e8e8e8;
    border: 1px solid #333; border-radius: 8px; padding: 6px 14px;
  }
  .stButton > button:hover { background: #2a2a2a; border-color: #555; }
  hr { border-color: #1e1e1e !important; }
  .stCaption { color: #555 !important; }
  h1, h2, h3 { color: #ffffff !important; }
  a { color: inherit !important; text-decoration: none !important; }

  .hero-num { font-size: clamp(40px, 13vw, 66px); font-weight: 900; line-height: 1; letter-spacing: -2px; }
  .card-row { display: flex; flex-wrap: wrap; align-items: center; gap: 14px; }
  .card-name   { flex: 3 1 160px; }
  .card-metric { flex: 1 1 95px; text-align: center; }
  .card-btn    { flex: 0 1 120px; text-align: center; }

  @media (max-width: 640px) {
    .card-name   { flex-basis: 100%; }
    .card-metric { flex-basis: 30%; text-align: left; }
    .card-btn    { flex-basis: 100%; text-align: left; margin-top: 6px; }
    .hero-flex   { flex-direction: column; align-items: flex-start !important; gap: 12px !important; }
  }
</style>
""", unsafe_allow_html=True)

cfg      = load_config(_CONFIG_PATH)
_TTL     = cfg.dashboard.cache_ttl_minutes * 60
_WARNING = cfg.dashboard.warning_deviation_pct  # -7
_DANGER  = cfg.dashboard.danger_deviation_pct   # -10

# 待機=青 / もうすぐ=シアン(警戒感のない色) / 買い場=緑
_COLOR = {"normal": "#4a9eff", "warning": "#00c9b7", "danger": "#00e676", "no_data": "#555"}
_BG    = {"normal": "#0d1a2b", "warning": "#06201e", "danger": "#001a0d", "no_data": "#141414"}
_BORDER= {"normal": "#1e3a5f", "warning": "#0a4a44", "danger": "#005c2e", "no_data": "#2a2a2a"}

_NIKKEI_TV = "https://www.tradingview.com/chart/?symbol=TVC:NI225"


@st.cache_data(ttl=_TTL, show_spinner="データ取得中...")
def _get_data() -> DashboardData:
    return build_dashboard_data(cfg, today=date.today())


def _tradingview_url(symbol: str) -> str:
    code = symbol.replace(".T", "")
    return f"https://www.tradingview.com/chart/?symbol=TSE:{code}"


def _distance_bar(dev: float | None, h: int = 18) -> str:
    """買い場までの距離バー。左端=現在水準、右端=買い場(-10%)。"""
    if dev is None:
        return ""
    fill = max(0.0, min(dev / _DANGER * 100, 100.0))
    warn_pos = _WARNING / _DANGER * 100
    col = "#00e676" if dev <= _DANGER else "#00c9b7" if dev <= _WARNING else "#4a9eff"
    return (
        f'<div style="position:relative;width:100%;height:{h}px;background:#111;border-radius:8px;overflow:hidden;">'
        f'<div style="width:{fill:.1f}%;height:100%;background:linear-gradient(90deg,#1a3a6a,{col});box-shadow:0 0 12px {col}55;"></div>'
        f'<div style="position:absolute;left:{warn_pos:.1f}%;top:0;height:100%;width:2px;background:#00c9b7;opacity:0.6;"></div>'
        f'</div>'
        f'<div style="display:flex;justify-content:space-between;font-size:10px;color:#444;margin-top:3px;">'
        f'<span style="color:#777;">いまの安さ</span>'
        f'<span style="color:#00e676;">🎯 買い場 ({_DANGER:.0f}%)</span>'
        f'</div>'
    )


def _yen(v: float | None) -> str:
    return f"¥{v:,.0f}" if v is not None else "—"


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
dev  = m.current_deviation_pct

# ─── メイン: 買い場までの距離（日経） ─────────────────────────
if dev is None:
    distance_str, phase_label, phase_desc = "—", "データなし", ""
    pc, pbg, pbd = "#555", "#141414", "#2a2a2a"
elif dev <= _DANGER:
    distance_str = "0.0%"
    phase_label  = "🎯 いまが買い場！"
    phase_desc   = "日経が割安水準に到達。下の銘柄のチャートを見て購入を検討しましょう。"
    pc, pbg, pbd = "#00e676", "#001a0d", "#005c2e"
elif dev <= _WARNING:
    distance_str = f"{_DANGER - dev:.1f}%"
    phase_label  = "👀 そろそろ買い場"
    phase_desc   = "日経が下がってきています。下の銘柄をチェックして準備しておきましょう。"
    pc, pbg, pbd = "#00c9b7", "#06201e", "#0a4a44"
else:
    distance_str = f"{_DANGER - dev:.1f}%"
    phase_label  = "⏳ いまは待機"
    phase_desc   = "まだ買い場ではありません。日経が下がるのを待ちましょう。"
    pc, pbg, pbd = "#4a9eff", "#0d1a2b", "#1e3a5f"

nikkei_info = (
    f'日経平均 {_yen(m.current_price)} ／ 25日平均からの差 {dev:+.1f}%'
    if dev is not None else "日経データ取得失敗"
)

st.markdown(
    f'<div style="background:{pbg};border:1px solid {pbd};border-left:6px solid {pc};padding:24px 26px;border-radius:14px;margin-bottom:16px;">'
    f'<div style="font-size:13px;color:#666;letter-spacing:1px;margin-bottom:12px;">📊 買い場まで あと…（日経平均）</div>'
    f'<div class="hero-flex" style="display:flex;align-items:center;gap:28px;flex-wrap:wrap;margin-bottom:16px;">'
    f'<div><span class="hero-num" style="color:{pc};">{distance_str}</span>'
    f'<span style="font-size:16px;color:#777;margin-left:8px;">下落で買い場</span></div>'
    f'<div style="flex:1;min-width:200px;">'
    f'<div style="font-size:22px;font-weight:800;color:{pc};margin-bottom:6px;">{phase_label}</div>'
    f'<div style="font-size:14px;color:#aaa;line-height:1.5;">{phase_desc}</div>'
    f'</div></div>'
    f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:6px;">'
    f'<span style="font-size:12px;color:#666;">{nikkei_info}</span>'
    f'<a href="{_NIKKEI_TV}" target="_blank"><span style="font-size:12px;color:#888;border:1px solid #333;border-radius:6px;padding:4px 10px;">📊 日経チャートを見る</span></a>'
    f'</div>'
    f'{_distance_bar(dev, h=18)}'
    f'</div>',
    unsafe_allow_html=True,
)

if m.fresh_touch_fired and m.last_signal_date:
    st.markdown(
        f'<div style="background:#001a0d;border:2px solid #00e676;border-radius:12px;padding:18px 22px;margin-bottom:16px;text-align:center;">'
        f'<div style="font-size:22px;font-weight:900;color:#00e676;">🎯 3か月ぶりの買いシグナル発火！</div>'
        f'<div style="font-size:13px;color:#aaa;margin-top:6px;">最終発火日: {m.last_signal_date} ／ 下の銘柄のチャートを確認して購入を検討しましょう</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

st.divider()

# ─── 使い方 ───────────────────────────────────────────────────
with st.expander("📖 はじめての方へ — 使い方と用語"):
    st.markdown(f"""
**この手法のキホン：好業績の株を「暴落で安くなった時」に仕込む**

#### 画面の見方
- **⏳ いまは待機（青）** … 何もしない。日経が下がるのを待つ
- **👀 そろそろ買い場（青緑）** … 日経が下落中。下の銘柄を見て準備
- **🎯 いまが買い場（緑）** … 日経が割安水準（{_DANGER:.0f}%）に到達。購入を検討

#### 用語の意味
- **25日平均からの差（乖離率）** … 株価が直近25日の平均より何%上下しているか。大きくマイナス＝急落して割安、ということ。この手法では **{_DANGER:.0f}%** が「買い場」の目安
- **売上 / 純利益（前年比）** … その会社が去年より何%成長したか。高いほど好業績
- **100株購入額** … 日本株は基本100株単位で買う。その購入に必要なおよその金額

#### 買うときの流れ
1. 日経が「🎯 いまが買い場」になる
2. 下の監視銘柄から気になるものを選ぶ
3. 「📊 チャートを見る」で上昇トレンドが崩れていないか最終確認
4. 問題なければ100株購入を検討

※ このアプリは投資助言ではありません。最終判断はご自身で。
    """)

# ─── 監視銘柄 ─────────────────────────────────────────────────
st.markdown(
    "<h2 style='margin-bottom:4px;'>📋 監視銘柄</h2>"
    "<div style='font-size:13px;color:#555;margin-bottom:16px;'>好業績で上昇トレンドの株を自動選定（毎週土曜更新）。安い順に表示。</div>",
    unsafe_allow_html=True,
)

if not data.rows:
    st.info("監視銘柄がありません。`out/pool.csv` に銘柄を追加してください。")
else:
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
        dev_r   = f"{row.current_deviation_pct:+.1f}%" if row.current_deviation_pct is not None else "—"
        price_r = _yen(row.current_price)
        unit_r  = _yen(row.current_price * 100) if row.current_price is not None else "—"
        tv_url  = _tradingview_url(row.symbol)
        gd      = growth_data.get(row.symbol, {})
        rev_str = f"売上 +{gd['rev']:.0f}%" if gd.get("rev") is not None else ""
        inc_str = f"純利益 +{gd['inc']:.0f}%" if gd.get("inc") is not None else ""
        growth_str = " ／ ".join(x for x in [rev_str, inc_str] if x)
        growth_html = (
            f'<div style="font-size:12px;color:#4a9eff;margin-top:4px;">📈 前年比 {growth_str}</div>'
            if growth_str else ""
        )

        st.markdown(
            f'<div style="background:{bg_r};border:1px solid {bdr_r};border-left:4px solid {clr_r};padding:16px 18px;border-radius:12px;margin-bottom:10px;">'
            f'<div class="card-row">'

            f'<div class="card-name">'
            f'<div style="font-size:18px;font-weight:700;color:#e8e8e8;">{row.name}</div>'
            f'<div style="font-size:12px;color:#555;margin-top:2px;">{row.symbol}</div>'
            f'{growth_html}'
            f'</div>'

            f'<div class="card-metric">'
            f'<div style="font-size:11px;color:#555;">現在値</div>'
            f'<div style="font-size:16px;color:#ddd;font-weight:600;">{price_r}</div>'
            f'<div style="font-size:10px;color:#666;margin-top:2px;">100株 {unit_r}</div>'
            f'</div>'

            f'<div class="card-metric">'
            f'<div style="font-size:11px;color:#555;">25日平均との差</div>'
            f'<div style="font-size:22px;font-weight:900;color:{clr_r};">{dev_r}</div>'
            f'</div>'

            f'<div class="card-btn">'
            f'<a href="{tv_url}" target="_blank">'
            f'<div style="background:#1e1e1e;border:1px solid #333;border-radius:8px;padding:9px 14px;font-size:13px;color:#bbb;white-space:nowrap;">📊 チャートを見る</div>'
            f'</a></div>'

            f'</div>'
            f'<div style="margin-top:10px;">{_distance_bar(row.current_deviation_pct, h=9)}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

st.markdown("<br>", unsafe_allow_html=True)
st.caption(f"最終更新: {data.as_of}　|　買い場の目安 {_DANGER:.0f}%　|　毎週土曜 0:00 JST 自動更新")
