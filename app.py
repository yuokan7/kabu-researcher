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
  .stApp { background: radial-gradient(1200px 600px at 50% -10%, #16161c 0%, #0b0b0d 60%) fixed; color: #e8e8e8; }
  [data-testid="stHeader"] { background: transparent; }
  .block-container { padding-top: 1.6rem; padding-bottom: 2rem; max-width: 1100px; }
  .stButton > button {
    background: #1a1a1f; color: #e8e8e8;
    border: 1px solid #333; border-radius: 10px; padding: 8px 16px; font-weight: 600;
  }
  .stButton > button:hover { background: #26262e; border-color: #555; }
  hr { border-color: #1c1c20 !important; }
  .stCaption { color: #555 !important; }
  a { color: inherit !important; text-decoration: none !important; }

  .app-title { font-size: clamp(22px, 6vw, 38px); font-weight: 900; letter-spacing: -1px;
               background: linear-gradient(90deg,#fff,#9fc4ff); -webkit-background-clip: text;
               -webkit-text-fill-color: transparent; margin: 0; }
  .hero-num  { font-size: clamp(42px, 14vw, 72px); font-weight: 900; line-height: 1; letter-spacing: -3px; }

  .card { border-radius: 14px; padding: 16px 18px; margin-bottom: 12px;
          transition: transform .15s ease, box-shadow .15s ease; }
  .card:hover { transform: translateY(-2px); }
  .card-row { display: flex; flex-wrap: wrap; align-items: center; gap: 14px; }
  .card-name   { flex: 3 1 170px; }
  .card-metric { flex: 1 1 95px; text-align: center; }
  .card-btn    { flex: 0 1 130px; text-align: center; }
  .pill { display:inline-block; font-size:11px; font-weight:700; padding:3px 10px; border-radius:20px; }

  @media (max-width: 640px) {
    .card-name   { flex-basis: 100%; }
    .card-metric { flex-basis: 30%; text-align: left; }
    .card-btn    { flex-basis: 100%; text-align: left; margin-top: 8px; }
    .hero-flex   { flex-direction: column; align-items: flex-start !important; gap: 14px !important; }
  }
</style>
""", unsafe_allow_html=True)

cfg      = load_config(_CONFIG_PATH)
_TTL     = cfg.dashboard.cache_ttl_minutes * 60
_WARNING = cfg.dashboard.warning_deviation_pct  # -7
_DANGER  = cfg.dashboard.danger_deviation_pct   # -10

_COLOR = {"normal": "#4a9eff", "warning": "#00c9b7", "danger": "#00e676", "no_data": "#555"}
_BG    = {"normal": "#0d1a2b", "warning": "#06201e", "danger": "#001a0d", "no_data": "#141414"}
_BORDER= {"normal": "#1e3a5f", "warning": "#0a4a44", "danger": "#005c2e", "no_data": "#2a2a2a"}
_ROW_LABEL = {"normal": "⏳ 待機", "warning": "👀 そろそろ", "danger": "🎯 買い場", "no_data": "—"}

_NIKKEI_TV = "https://www.tradingview.com/chart/?symbol=TVC:NI225"


@st.cache_data(ttl=_TTL, show_spinner="データ取得中...")
def _get_data() -> DashboardData:
    return build_dashboard_data(cfg, today=date.today())


def _tradingview_url(symbol: str) -> str:
    return f"https://www.tradingview.com/chart/?symbol=TSE:{symbol.replace('.T', '')}"


def _yen(v: float | None) -> str:
    return f"¥{v:,.0f}" if v is not None else "—"


def _recovery_profit_100(price: float | None, dev: float | None) -> float | None:
    """25日平均まで戻った場合の100株あたり回復益。下落時(dev<0)のみ。"""
    if price is None or dev is None or dev >= 0:
        return None
    sma = price / (1 + dev / 100.0)   # 25日平均を逆算
    return (sma - price) * 100.0


def _distance_bar(dev: float | None, h: int = 18) -> str:
    if dev is None:
        return ""
    fill = max(0.0, min(dev / _DANGER * 100, 100.0))
    warn_pos = _WARNING / _DANGER * 100
    col = "#00e676" if dev <= _DANGER else "#00c9b7" if dev <= _WARNING else "#4a9eff"
    return (
        f'<div style="position:relative;width:100%;height:{h}px;background:#0a0a0c;border-radius:8px;overflow:hidden;border:1px solid #1c1c20;">'
        f'<div style="width:{fill:.1f}%;height:100%;background:linear-gradient(90deg,#1a3a6a,{col});box-shadow:0 0 14px {col}66;"></div>'
        f'<div style="position:absolute;left:{warn_pos:.1f}%;top:0;height:100%;width:2px;background:#00c9b7;opacity:0.5;"></div>'
        f'</div>'
        f'<div style="display:flex;justify-content:space-between;font-size:10px;color:#555;margin-top:3px;">'
        f'<span>いまの安さ</span><span style="color:#00e676;">🎯 買い場 ({_DANGER:.0f}%)</span>'
        f'</div>'
    )


# ─── ヘッダー ─────────────────────────────────────────────────
c_ttl, c_btn = st.columns([5, 1])
with c_ttl:
    st.markdown("<div class='app-title'>📈 株リサーチャー</div>", unsafe_allow_html=True)
with c_btn:
    if st.button("🔄 更新"):
        st.cache_data.clear()
        st.rerun()

st.write("")
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
    pc, pbg, pbd = "#00e676", "#021c0f", "#005c2e"
elif dev <= _WARNING:
    distance_str = f"{_DANGER - dev:.1f}%"
    phase_label  = "👀 そろそろ買い場"
    phase_desc   = "日経が下がってきています。下の銘柄をチェックして準備しておきましょう。"
    pc, pbg, pbd = "#00c9b7", "#07211f", "#0a4a44"
else:
    distance_str = f"{_DANGER - dev:.1f}%"
    phase_label  = "⏳ いまは待機"
    phase_desc   = "まだ買い場ではありません。日経が下がるのを待ちましょう。"
    pc, pbg, pbd = "#4a9eff", "#0c1a2c", "#1e3a5f"

nikkei_info = (
    f'日経平均 {_yen(m.current_price)} ／ 25日平均からの差 {dev:+.1f}%'
    if dev is not None else "日経データ取得失敗"
)

st.markdown(
    f'<div style="background:linear-gradient(135deg,{pbg},#0b0b0d);border:1px solid {pbd};'
    f'border-left:6px solid {pc};padding:26px 28px;border-radius:18px;margin-bottom:16px;'
    f'box-shadow:0 0 40px {pc}22, inset 0 1px 0 #ffffff08;">'
    f'<div style="font-size:13px;color:#888;letter-spacing:2px;margin-bottom:14px;text-transform:uppercase;">📊 買い場まで あと…（日経平均）</div>'
    f'<div class="hero-flex" style="display:flex;align-items:center;gap:30px;flex-wrap:wrap;margin-bottom:18px;">'
    f'<div><span class="hero-num" style="color:{pc};text-shadow:0 0 30px {pc}55;">{distance_str}</span>'
    f'<span style="font-size:15px;color:#888;margin-left:8px;">下落で買い場</span></div>'
    f'<div style="flex:1;min-width:200px;">'
    f'<div style="font-size:23px;font-weight:800;color:{pc};margin-bottom:6px;">{phase_label}</div>'
    f'<div style="font-size:14px;color:#aaa;line-height:1.6;">{phase_desc}</div>'
    f'</div></div>'
    f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:8px;">'
    f'<span style="font-size:12px;color:#777;">{nikkei_info}</span>'
    f'<a href="{_NIKKEI_TV}" target="_blank"><span style="font-size:12px;color:#bbb;border:1px solid #333;border-radius:8px;padding:5px 12px;background:#15151a;">📊 日経チャート</span></a>'
    f'</div>'
    f'{_distance_bar(dev, h=18)}'
    f'</div>',
    unsafe_allow_html=True,
)

if m.fresh_touch_fired and m.last_signal_date:
    st.markdown(
        f'<div style="background:linear-gradient(135deg,#021c0f,#0b0b0d);border:2px solid #00e676;border-radius:14px;'
        f'padding:20px;margin-bottom:16px;text-align:center;box-shadow:0 0 50px #00e67633;">'
        f'<div style="font-size:24px;font-weight:900;color:#00e676;">🎯 3か月ぶりの買いシグナル発火！</div>'
        f'<div style="font-size:13px;color:#aaa;margin-top:6px;">最終発火日: {m.last_signal_date} ／ 下の銘柄のチャートを確認して購入を検討しましょう</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

st.divider()

with st.expander("📖 はじめての方へ — 使い方と用語"):
    st.markdown(f"""
**この手法のキホン：好業績の株を「暴落で安くなった時」に仕込む**

#### 画面の見方
- **⏳ いまは待機（青）** … 何もしない。日経が下がるのを待つ
- **👀 そろそろ買い場（青緑）** … 日経が下落中。下の銘柄を見て準備
- **🎯 いまが買い場（緑）** … 日経が割安水準（{_DANGER:.0f}%）に到達。購入を検討

#### 用語の意味
- **25日平均からの差（乖離率）** … 株価が直近25日平均より何%上下しているか。大きくマイナス＝急落して割安。**{_DANGER:.0f}%** が買い場の目安
- **売上 / 純利益（前年比）** … 去年より何%成長したか。高いほど好業績
- **100株購入額** … 日本株は基本100株単位。購入に必要なおよその金額
- **回復益（目安）** … いまの暴落価格から株価が25日平均まで戻った場合の、100株あたりの利益見込み（あくまで目安）

#### 買うときの流れ
1. 日経が「🎯 いまが買い場」になる → 2. 下の銘柄から選ぶ → 3.「📊 チャートを見る」で最終確認 → 4. 100株購入を検討

※ このアプリは投資助言ではありません。最終判断はご自身で。
    """)

# ─── 監視銘柄 ─────────────────────────────────────────────────
st.markdown(
    "<h2 style='margin-bottom:4px;font-size:22px;'>📋 監視銘柄</h2>"
    "<div style='font-size:13px;color:#666;margin-bottom:16px;'>好業績で上昇トレンドの株を自動選定（毎週土曜更新）。安い順に表示。</div>",
    unsafe_allow_html=True,
)

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
        clr_r = _COLOR.get(row.status, "#555")
        bg_r  = _BG.get(row.status, "#141414")
        bdr_r = _BORDER.get(row.status, "#2a2a2a")
        dev_r   = f"{row.current_deviation_pct:+.1f}%" if row.current_deviation_pct is not None else "—"
        price_r = _yen(row.current_price)
        unit_r  = _yen(row.current_price * 100) if row.current_price is not None else "—"
        tv_url  = _tradingview_url(row.symbol)
        glow    = f"box-shadow:0 0 30px {clr_r}33;" if row.status == "danger" else ""

        gd = growth_data.get(row.symbol, {})
        rev = f"売上 +{gd['rev']:.0f}%" if gd.get("rev") is not None else ""
        inc = f"純利益 +{gd['inc']:.0f}%" if gd.get("inc") is not None else ""
        growth_str = " ／ ".join(x for x in [rev, inc] if x)
        growth_html = (f'<div style="font-size:12px;color:#5aa9ff;margin-top:4px;">📈 前年比 {growth_str}</div>'
                       if growth_str else "")

        profit = _recovery_profit_100(row.current_price, row.current_deviation_pct)
        if profit is not None and profit > 0:
            profit_html = (
                f'<div class="card-metric">'
                f'<div style="font-size:11px;color:#555;">回復益(目安)</div>'
                f'<div style="font-size:16px;font-weight:800;color:#ffd24c;">+{_yen(profit)}</div>'
                f'<div style="font-size:10px;color:#666;margin-top:2px;">25日平均まで戻れば</div>'
                f'</div>'
            )
        else:
            profit_html = (
                f'<div class="card-metric">'
                f'<div style="font-size:11px;color:#555;">回復益(目安)</div>'
                f'<div style="font-size:15px;color:#666;">—</div>'
                f'</div>'
            )

        st.markdown(
            f'<div class="card" style="background:linear-gradient(135deg,{bg_r},#0b0b0d);border:1px solid {bdr_r};border-left:4px solid {clr_r};{glow}">'
            f'<div class="card-row">'

            f'<div class="card-name">'
            f'<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">'
            f'<span style="font-size:18px;font-weight:700;color:#fff;">{row.name}</span>'
            f'<span class="pill" style="background:{clr_r}22;color:{clr_r};">{_ROW_LABEL.get(row.status,"")}</span>'
            f'</div>'
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

            f'{profit_html}'

            f'<div class="card-btn">'
            f'<a href="{tv_url}" target="_blank">'
            f'<div style="background:#17171c;border:1px solid #333;border-radius:9px;padding:9px 14px;font-size:13px;color:#bbb;white-space:nowrap;">📊 チャートを見る</div>'
            f'</a></div>'

            f'</div>'
            f'<div style="margin-top:12px;">{_distance_bar(row.current_deviation_pct, h=9)}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

st.markdown("<br>", unsafe_allow_html=True)
st.caption(f"最終更新: {data.as_of}　|　買い場の目安 {_DANGER:.0f}%　|　毎週土曜 0:00 JST 自動更新")
