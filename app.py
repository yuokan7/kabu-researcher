from datetime import date
from pathlib import Path

import streamlit as st

from src.config import load_config
from src.dashboard_data import DashboardData, WatchRow, build_dashboard_data

_PROJECT_ROOT = Path(__file__).parent
_CONFIG_PATH = _PROJECT_ROOT / "conditions.yaml"

st.set_page_config(page_title="まだ株ダッシュボード", layout="wide")

cfg = load_config(_CONFIG_PATH)
_TTL = cfg.dashboard.cache_ttl_minutes * 60
_WARNING = cfg.dashboard.warning_deviation_pct  # -7
_DANGER = cfg.dashboard.danger_deviation_pct    # -10


@st.cache_data(ttl=_TTL, show_spinner="データ取得中...")
def _get_data() -> DashboardData:
    return build_dashboard_data(cfg, today=date.today())


def _bar_html(deviation_pct: float | None, height: int = 12) -> str:
    """乖離率の深さをカラーバーで表現。0%=空(安全), -10%=満杯(危険)。"""
    if deviation_pct is None:
        return "<div style='color:#aaa; font-size:12px;'>データなし</div>"

    # 0% → 0%, -10% → 100%, それ以上は100%超え（クランプ）
    fill_pct = min(deviation_pct / _DANGER * 100, 120)
    fill_pct = max(fill_pct, 0)

    warn_pos = _WARNING / _DANGER * 100  # 警戒ラインの位置

    if deviation_pct <= _DANGER:
        color = "#ff4b4b"
    elif deviation_pct <= _WARNING:
        color = "#ffa500"
    else:
        color = "#21c354"

    return f"""
    <div style="position:relative;width:100%;height:{height}px;background:#e8e8e8;border-radius:6px;overflow:hidden;margin:6px 0;">
      <div style="width:{fill_pct}%;height:100%;background:{color};border-radius:6px;transition:width 0.3s;"></div>
      <div style="position:absolute;left:{warn_pos}%;top:0;height:100%;width:2px;background:#ffa500;opacity:0.9;"></div>
    </div>
    <div style="display:flex;justify-content:space-between;font-size:10px;color:#999;margin-top:1px;">
      <span>0%</span><span style="color:#ffa500;">注意{_WARNING}%</span><span style="color:#ff4b4b;">危険{_DANGER}%</span>
    </div>"""


def _status_icon(status: str) -> str:
    return {"normal": "🟢", "warning": "🟡", "danger": "🔴", "no_data": "⚫"}.get(status, "⚫")


def _status_label(status: str) -> str:
    return {"normal": "平常", "warning": "注意", "danger": "🚨 暴落点タッチ", "no_data": "データなし"}.get(status, "")


def _card_css(status: str) -> tuple[str, str]:
    return {
        "normal":  ("#f0fff4", "#21c354"),
        "warning": ("#fffbeb", "#ffa500"),
        "danger":  ("#fff0f0", "#ff4b4b"),
        "no_data": ("#f5f5f5", "#cccccc"),
    }.get(status, ("#f5f5f5", "#ccc"))


# ─────────────────────────────────────────────────────────────
#  ヘッダー
# ─────────────────────────────────────────────────────────────
col_title, col_btn = st.columns([6, 1])
with col_title:
    st.title("📈 まだ株ダッシュボード")
with col_btn:
    st.write("")
    if st.button("🔄 更新"):
        st.cache_data.clear()
        st.rerun()

data = _get_data()
m = data.market

# ─────────────────────────────────────────────────────────────
#  日経225 暴落ゲージ
# ─────────────────────────────────────────────────────────────
bg, border = _card_css(m.status)
dev_str   = f"{m.current_deviation_pct:+.2f}%" if m.current_deviation_pct is not None else "—"
price_str = f"¥{m.current_price:,.0f}"         if m.current_price          is not None else "—"

st.markdown(f"""
<div style="background:{bg};border-left:6px solid {border};padding:20px 24px;border-radius:10px;margin-bottom:12px;">
  <div style="font-size:13px;color:#777;font-weight:500;margin-bottom:6px;">日経225 / 25日乖離率</div>
  <div style="display:flex;align-items:baseline;gap:20px;flex-wrap:wrap;">
    <span style="font-size:42px;font-weight:800;color:{border};letter-spacing:-1px;">{dev_str}</span>
    <span style="font-size:22px;color:#555;">{price_str}</span>
    <span style="font-size:18px;">{_status_icon(m.status)} {_status_label(m.status)}</span>
  </div>
  {_bar_html(m.current_deviation_pct, height=18)}
</div>
""", unsafe_allow_html=True)

if m.fresh_touch_fired and m.last_signal_date:
    st.error(f"⚠️ 3か月ぶりの暴落シグナル発火（最終: {m.last_signal_date}）— 監視リストを確認してください")

st.divider()

# ─────────────────────────────────────────────────────────────
#  監視リスト
# ─────────────────────────────────────────────────────────────
st.subheader("📋 監視リスト（乖離率 深い順）")

if not data.rows:
    st.info("`out/pool.csv` に symbol（例: 3038.T）と name を追加してください。")
else:
    for row in data.rows:
        bg_r, border_r = _card_css(row.status)
        dev_r   = f"{row.current_deviation_pct:+.2f}%" if row.current_deviation_pct is not None else "—"
        price_r = f"¥{row.current_price:,.0f}"         if row.current_price          is not None else "—"

        c_info, c_price, c_dev, c_bar = st.columns([3, 2, 2, 5])

        with c_info:
            st.markdown(
                f"<div style='padding:4px 0;'>"
                f"<span style='font-size:16px;font-weight:700;'>{_status_icon(row.status)} {row.name}</span><br>"
                f"<span style='font-size:12px;color:#888;'>{row.symbol}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
        with c_price:
            st.markdown(
                f"<div style='padding:6px 0;font-size:15px;color:#555;'>{price_r}</div>",
                unsafe_allow_html=True,
            )
        with c_dev:
            st.markdown(
                f"<div style='padding:4px 0;font-size:22px;font-weight:800;color:{border_r};'>{dev_r}</div>",
                unsafe_allow_html=True,
            )
        with c_bar:
            st.markdown(_bar_html(row.current_deviation_pct, height=10), unsafe_allow_html=True)

        st.markdown("<hr style='margin:4px 0;border:none;border-top:1px solid #eee;'>", unsafe_allow_html=True)

st.caption(f"最終更新: {data.as_of}　|　注意ライン {_WARNING}%　危険ライン {_DANGER}%")
