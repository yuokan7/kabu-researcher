from datetime import date
from pathlib import Path

import streamlit as st

from src.config import load_config
from src.dashboard_data import DashboardData, build_dashboard_data

_PROJECT_ROOT = Path(__file__).parent
_CONFIG_PATH = _PROJECT_ROOT / "conditions.yaml"

st.set_page_config(page_title="まだ株ダッシュボード", layout="wide")

# ─────────────────────────────────────────────────────────────
#  ダークテーマ CSS
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
  /* ページ全体 */
  .stApp { background-color: #0d0d0d; color: #e8e8e8; }

  /* サイドバー・ヘッダー */
  [data-testid="stHeader"] { background-color: #0d0d0d; }
  [data-testid="stToolbar"] { background-color: #0d0d0d; }

  /* ボタン */
  .stButton > button {
    background: #1e1e1e; color: #e8e8e8;
    border: 1px solid #333; border-radius: 8px;
  }
  .stButton > button:hover { background: #2a2a2a; border-color: #555; }

  /* divider */
  hr { border-color: #222 !important; }

  /* caption */
  .stCaption { color: #555 !important; }

  /* subheader */
  h2 { color: #e8e8e8 !important; }
  h1 { color: #ffffff !important; }
</style>
""", unsafe_allow_html=True)

cfg = load_config(_CONFIG_PATH)
_TTL = cfg.dashboard.cache_ttl_minutes * 60
_WARNING = cfg.dashboard.warning_deviation_pct  # -7
_DANGER  = cfg.dashboard.danger_deviation_pct   # -10

# ステータスの定義（"danger" = 買いチャンス）
_ICON  = {"normal": "🔵", "warning": "🟠", "danger": "🎯", "no_data": "⚫"}
_LABEL = {"normal": "様子見", "warning": "接近中", "danger": "買いチャンス！", "no_data": "データなし"}
_COLOR = {"normal": "#4a9eff", "warning": "#ff8c00", "danger": "#00e676", "no_data": "#555"}
_BG    = {"normal": "#0d1a2b", "warning": "#1a1200", "danger": "#001a0d", "no_data": "#141414"}
_BORDER= {"normal": "#1e3a5f", "warning": "#4a3000", "danger": "#005c2e", "no_data": "#2a2a2a"}


@st.cache_data(ttl=_TTL, show_spinner="データ取得中...")
def _get_data() -> DashboardData:
    return build_dashboard_data(cfg, today=date.today())


def _bar_html(deviation_pct: float | None, height: int = 14) -> str:
    """0%=空(様子見)、-10%=満杯(買いチャンス)のカラーバー"""
    if deviation_pct is None:
        return "<div style='color:#444;font-size:12px;'>—</div>"

    fill_pct   = min(deviation_pct / _DANGER * 100, 115)
    fill_pct   = max(fill_pct, 0)
    warn_pos   = _WARNING / _DANGER * 100

    if deviation_pct <= _DANGER:
        color = "#00e676"
    elif deviation_pct <= _WARNING:
        color = "#ff8c00"
    else:
        color = "#4a9eff"

    return f"""
    <div style="position:relative;width:100%;height:{height}px;background:#1e1e1e;border-radius:6px;overflow:visible;margin:8px 0;">
      <div style="width:min({fill_pct}%,100%);height:100%;background:{color};border-radius:6px;box-shadow:0 0 8px {color}55;"></div>
      <div style="position:absolute;left:{warn_pos}%;top:-3px;height:{height+6}px;width:2px;background:#ff8c00;opacity:0.7;border-radius:1px;"></div>
    </div>
    <div style="display:flex;justify-content:space-between;font-size:10px;color:#444;margin-top:2px;">
      <span>0%</span>
      <span style="color:#ff8c00;">⚡ 接近{_WARNING}%</span>
      <span style="color:#00e676;">🎯 チャンス{_DANGER}%</span>
    </div>"""


# ─────────────────────────────────────────────────────────────
#  ヘッダー
# ─────────────────────────────────────────────────────────────
c_title, c_btn = st.columns([7, 1])
with c_title:
    st.markdown("<h1 style='margin-bottom:0;'>📈 まだ株ダッシュボード</h1>", unsafe_allow_html=True)
with c_btn:
    st.write("")
    if st.button("🔄 更新"):
        st.cache_data.clear()
        st.rerun()

data = _get_data()
m    = data.market

# ─────────────────────────────────────────────────────────────
#  日経225 暴落ゲージ
# ─────────────────────────────────────────────────────────────
clr  = _COLOR.get(m.status, "#555")
bg   = _BG.get(m.status, "#141414")
bdr  = _BORDER.get(m.status, "#2a2a2a")
dev_str   = f"{m.current_deviation_pct:+.2f}%" if m.current_deviation_pct is not None else "—"
price_str = f"¥{m.current_price:,.0f}"         if m.current_price          is not None else "—"

st.markdown(f"""
<div style="background:{bg};border:1px solid {bdr};border-left:5px solid {clr};
            padding:22px 28px;border-radius:12px;margin-bottom:16px;">
  <div style="font-size:12px;color:#555;letter-spacing:1px;text-transform:uppercase;margin-bottom:8px;">
    日経225 / 25日乖離率
  </div>
  <div style="display:flex;align-items:center;gap:24px;flex-wrap:wrap;">
    <span style="font-size:52px;font-weight:900;color:{clr};letter-spacing:-2px;line-height:1;">{dev_str}</span>
    <div>
      <div style="font-size:20px;color:#aaa;">{price_str}</div>
      <div style="font-size:18px;margin-top:4px;">{_ICON.get(m.status,'')} <span style="color:{clr};font-weight:700;">{_LABEL.get(m.status,'')}</span></div>
    </div>
  </div>
  {_bar_html(m.current_deviation_pct, height=18)}
</div>
""", unsafe_allow_html=True)

if m.fresh_touch_fired and m.last_signal_date:
    st.markdown(f"""
    <div style="background:#001a0d;border:1px solid #00e676;border-radius:10px;padding:16px 20px;margin-bottom:12px;">
      <span style="font-size:20px;">🎯</span>
      <span style="font-size:16px;font-weight:700;color:#00e676;margin-left:8px;">
        3か月ぶりの買いシグナル発火 — 最終発火日: {m.last_signal_date}
      </span><br>
      <span style="font-size:13px;color:#aaa;margin-left:32px;">
        下の監視リストから購入候補を確認してください
      </span>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# ─────────────────────────────────────────────────────────────
#  監視リスト
# ─────────────────────────────────────────────────────────────
st.markdown("<h2 style='margin-bottom:16px;'>📋 監視リスト<span style='font-size:14px;color:#555;font-weight:400;margin-left:12px;'>乖離率が深い順 — 🎯が今すぐ買い検討の銘柄</span></h2>", unsafe_allow_html=True)

if not data.rows:
    st.markdown("<div style='color:#555;padding:20px;'>out/pool.csv に銘柄を追加してください</div>", unsafe_allow_html=True)
else:
    for row in data.rows:
        clr_r = _COLOR.get(row.status, "#555")
        bg_r  = _BG.get(row.status, "#141414")
        bdr_r = _BORDER.get(row.status, "#2a2a2a")
        dev_r   = f"{row.current_deviation_pct:+.2f}%" if row.current_deviation_pct is not None else "—"
        price_r = f"¥{row.current_price:,.0f}"         if row.current_price          is not None else "—"
        label_r = _LABEL.get(row.status, "")

        st.markdown(f"""
        <div style="background:{bg_r};border:1px solid {bdr_r};border-left:4px solid {clr_r};
                    padding:14px 20px;border-radius:10px;margin-bottom:10px;display:flex;
                    align-items:center;gap:0;flex-wrap:wrap;">

          <!-- 銘柄名 -->
          <div style="min-width:180px;flex:1;">
            <div style="font-size:17px;font-weight:700;color:#e8e8e8;">
              {_ICON.get(row.status,'')} {row.name}
            </div>
            <div style="font-size:12px;color:#555;margin-top:2px;">{row.symbol}</div>
          </div>

          <!-- 現在値 -->
          <div style="min-width:120px;flex:1;text-align:right;padding-right:24px;">
            <div style="font-size:13px;color:#555;">現在値</div>
            <div style="font-size:18px;color:#aaa;">{price_r}</div>
          </div>

          <!-- 乖離率 + ステータス -->
          <div style="min-width:160px;flex:1;text-align:right;padding-right:24px;">
            <div style="font-size:30px;font-weight:900;color:{clr_r};line-height:1;">{dev_r}</div>
            <div style="font-size:12px;color:{clr_r};margin-top:2px;">{label_r}</div>
          </div>

          <!-- バー -->
          <div style="min-width:240px;flex:2;">
            {_bar_html(row.current_deviation_pct, height=10)}
          </div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)
st.caption(f"最終更新: {data.as_of}　|　接近ライン {_WARNING}%　買いチャンスライン {_DANGER}%")
