from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from src.config import load_config
from src.dashboard_data import DashboardData, build_dashboard_data

_PROJECT_ROOT = Path(__file__).parent
_CONFIG_PATH = _PROJECT_ROOT / "conditions.yaml"

st.set_page_config(page_title="まだ株ダッシュボード", layout="wide")

cfg = load_config(_CONFIG_PATH)
_TTL = cfg.dashboard.cache_ttl_minutes * 60

_STATUS_LABEL = {
    "normal": "✅ 平常",
    "warning": "⚠️ 注意",
    "danger": "🚨 暴落点タッチ",
    "no_data": "❓ データなし",
}

_STATUS_BADGE = {
    "danger":  "🚨 暴落点",
    "warning": "⚠️ 注意",
    "normal":  "　平常",
    "no_data": "❓ データなし",
}


@st.cache_data(ttl=_TTL, show_spinner="データ取得中...")
def _get_data() -> DashboardData:
    return build_dashboard_data(cfg, today=date.today())


# ── ヘッダー ──────────────────────────────────────────────────
col_title, col_btn = st.columns([6, 1])
with col_title:
    st.title("📈 まだ株ダッシュボード")
with col_btn:
    st.write("")  # 縦位置合わせ
    if st.button("🔄 更新"):
        st.cache_data.clear()
        st.rerun()

data = _get_data()

# ── 暴落ゲージ ────────────────────────────────────────────────
st.subheader("日経225 暴落ゲージ")

m = data.market
c1, c2, c3 = st.columns(3)
c1.metric("現在値", f"¥{m.current_price:,.0f}" if m.current_price is not None else "—")
c2.metric("25日乖離率", f"{m.current_deviation_pct:.2f}%" if m.current_deviation_pct is not None else "—")
c3.metric("状態", _STATUS_LABEL.get(m.status, m.status))

if m.fresh_touch_fired and m.last_signal_date:
    st.error(
        f"⚠️ 3か月ぶりの暴落シグナル発火（最終: {m.last_signal_date}）"
        "— 監視リストを確認してください"
    )
elif m.status == "danger":
    st.warning("暴落点付近です。監視リストの乖離率を確認してください。")
elif m.status == "warning":
    st.info("乖離率が警戒水準に近づいています。")

st.divider()

# ── 監視リスト ────────────────────────────────────────────────
st.subheader("監視リスト（乖離率 深い順）")

if not data.rows:
    st.info(
        "監視銘柄がありません。"
        "`out/pool.csv` に symbol（例: 3038.T）と name を追加してください。"
    )
else:
    records = []
    for row in data.rows:
        records.append({
            "銘柄名": row.name,
            "コード": row.symbol,
            "現在値": f"¥{row.current_price:,.0f}" if row.current_price is not None else "—",
            "乖離率(%)": f"{row.current_deviation_pct:.2f}" if row.current_deviation_pct is not None else "—",
            "状態": _STATUS_BADGE.get(row.status, row.status),
        })
    df = pd.DataFrame(records)
    st.dataframe(df, use_container_width=True, hide_index=True)

st.caption(
    f"最終更新: {data.as_of}　|　"
    f"注意ライン: {cfg.dashboard.warning_deviation_pct}%　"
    f"暴落ライン: {cfg.dashboard.danger_deviation_pct}%"
)
