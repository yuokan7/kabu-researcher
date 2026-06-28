from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from src.config import load_config
from src.dashboard_data import DashboardData, build_dashboard_data

_PROJECT_ROOT = Path(__file__).parent
_CONFIG_PATH = _PROJECT_ROOT / "conditions.yaml"

st.set_page_config(page_title="譬ｪ繝ｪ繧ｵ繝ｼ繝√Ε繝ｼ", layout="wide")

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@700;900&display=swap');

  .stApp {
    background: linear-gradient(180deg, #5ec8f0 0%, #a8e6fa 35%, #d4f3ff 60%, #e8fbff 100%);
    font-family: 'Noto Sans JP', sans-serif;
  }
  [data-testid="stHeader"] { background: transparent; }
  .block-container { padding-top: 1.4rem; padding-bottom: 2rem; max-width: 1100px; }

  /* 縺ｵ縺阪□縺鈴｢ｨ繝懊ち繝ｳ */
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

  /* expander: 鮟定レ譎ｯ繝ｻ逋ｽ譁・ｭ・*/
  [data-testid="stExpander"] {
    background: #1a1e2e !important; border-radius: 14px !important;
    border: 2px solid #3a4060 !important;
  }
  [data-testid="stExpander"] summary {
    color: #e8eeff !important; font-weight: 700 !important;
  }
  [data-testid="stExpanderDetails"] { color: #d0d8f0 !important; }
  [data-testid="stExpanderDetails"] p,
  [data-testid="stExpanderDetails"] li,
  [data-testid="stExpanderDetails"] strong { color: #e8eeff !important; }
  [data-testid="stExpanderDetails"] h4 { color: #a0c4ff !important; }

  /* 豎守畑繧ｫ繝ｼ繝・*/
  .puyo-card {
    border-radius: 20px; padding: 18px 20px; margin-bottom: 14px;
    border: 3px solid; position: relative; overflow: hidden;
  }
  .puyo-card::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 40%;
    background: linear-gradient(180deg, #ffffff33 0%, transparent 100%);
    border-radius: 18px 18px 0 0; pointer-events: none;
  }

  /* 繧ｿ繧､繝医Ν */
  .app-title {
    font-size: clamp(20px, 5vw, 34px); font-weight: 900; color: #fff;
    text-shadow: 0 3px 0 #1a88c0, 0 5px 12px #0060a044;
    letter-spacing: -0.5px; margin: 0;
  }

  /* 繝偵・繝ｭ繝ｼ謨ｰ蟄・*/
  .hero-num {
    font-size: clamp(44px, 14vw, 74px); font-weight: 900; line-height: 1; letter-spacing: -2px;
  }

  /* 繝ｩ繝吶Ν繝舌ャ繧ｸ */
  .badge {
    display: inline-block; font-size: 12px; font-weight: 900;
    padding: 3px 12px; border-radius: 20px; border: 2px solid;
  }

  /* 繧ｫ繝ｼ繝峨Ξ繧､繧｢繧ｦ繝・*/
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

# 縺ｷ繧医・繧磯・濶ｲ: 蠕・ｩ・邏ｫ縺｣縺ｽ縺・搨 / 繧ゅ≧縺吶＄=邱・/ 雋ｷ縺・ｴ=襍､・医・繧医・逋ｺ轣ｫ濶ｲ・・_THEME = {
    "normal":  {"col":"#5b6ef5", "bg":"#eef0ff", "brd":"#8090f8", "badge_bg":"#d8dcff", "txt":"#2030c0"},
    "warning": {"col":"#19c07a", "bg":"#e8faf2", "brd":"#52d89e", "badge_bg":"#c4f5de", "txt":"#0a7a4a"},
    "danger":  {"col":"#f53c5b", "bg":"#fff0f3", "brd":"#f87090", "badge_bg":"#ffd0db", "txt":"#c0001e"},
    "no_data": {"col":"#aaaaaa", "bg":"#f5f5f5", "brd":"#cccccc", "badge_bg":"#e8e8e8", "txt":"#777"},
}
_ROW_LABEL = {"normal": "竢ｳ 蠕・ｩ滉ｸｭ", "warning": "操 縺昴ｍ縺昴ｍ・・, "danger": "識 雋ｷ縺・ｴ・・, "no_data": "窶・}
_NIKKEI_TV = "https://www.tradingview.com/chart/?symbol=TVC:NI225"


@st.cache_data(ttl=_TTL, show_spinner="繝・・繧ｿ隱ｭ縺ｿ霎ｼ縺ｿ荳ｭ窶ｦ")
def _get_data() -> DashboardData:
    return build_dashboard_data(cfg, today=date.today())


def _tradingview_url(symbol: str) -> str:
    return f"https://www.tradingview.com/chart/?symbol=TSE:{symbol.replace('.T','')}"


def _yen(v: float | None) -> str:
    return f"ﾂ･{v:,.0f}" if v is not None else "窶・


def _signed_dev(dev: float | None) -> str:
    """荵夜屬邇・ｒ +/- 繧ｫ繝ｩ繝ｼHTML縺ｧ霑斐☆縲ゅ・繧､繝翫せ=襍､・亥牡螳峨・繝√Ε繝ｳ繧ｹ・峨√・繝ｩ繧ｹ=邱托ｼ亥牡鬮假ｼ峨・""
    if dev is None:
        return '<span style="color:#aaa;">窶・/span>'
    if dev < 0:
        return f'<span style="color:#f05060;font-weight:900;">{dev:+.1f}%</span>'
    return f'<span style="color:#44cc88;font-weight:900;">{dev:+.1f}%</span>'


def _recovery_profit_100(price: float | None, dev: float | None) -> float | None:
    if price is None or dev is None or dev >= 0:
        return None
    return (price / (1 + dev / 100.0) - price) * 100.0


def _dist_bar(dev: float | None, theme: dict, h: int = 16,
              threshold: float | None = None) -> str:
    """
    雋ｷ縺・ｴ縺ｾ縺ｧ縺ｮ霍晞屬繝舌・縲・    threshold 縺梧欠螳壹＆繧後ｌ縺ｰ縺昴・譬ｪ蝗ｺ譛峨・雋ｷ縺・ｴ繝ｩ繧､繝ｳ縲√↑縺代ｌ縺ｰ _DANGER(-10%) 繧剃ｽｿ縺・・    """
    if dev is None:
        return ""
    thr = threshold if threshold is not None else _DANGER
    fill = max(0.0, min(dev / thr * 100, 100.0))
    col  = theme["col"]
    at_target = dev <= thr
    thr_label = f"{thr:+.1f}%" if threshold is not None else f"{_DANGER:.0f}%"
    bar_col = col if at_target else "#a0c4ff"
    return (
        f'<div style="position:relative;width:100%;height:{h}px;background:#e0eef8;border-radius:99px;overflow:hidden;'
        f'border:2px solid #c0d8ea;box-shadow:inset 0 2px 4px #0002;">'
        f'<div style="width:{fill:.1f}%;height:100%;background:linear-gradient(90deg,#a0c4ff,{col});border-radius:99px;'
        f'box-shadow:0 0 8px {col}88;"></div>'
        f'</div>'
        f'<div style="display:flex;justify-content:space-between;font-size:10px;color:#88aac0;margin-top:3px;">'
        f'<span>縺・∪縺ｮ螳峨＆</span>'
        f'<span style="color:{col};font-weight:700;">識 雋ｷ縺・ｴ ({thr_label})</span>'
        f'</div>'
    )


# 笏笏笏 繝倥ャ繝繝ｼ 笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏
c_ttl, c_btn = st.columns([5, 1])
with c_ttl:
    st.markdown(
        '<div style="display:flex;align-items:center;gap:12px;">'
        '<div style="width:42px;height:42px;background:linear-gradient(135deg,#5ec8f0,#2a8fd4);'
        'border-radius:12px;border:3px solid #fff;box-shadow:0 3px 8px #00608044;'
        'display:flex;align-items:center;justify-content:center;font-size:22px;">嶋</div>'
        '<div class="app-title">譬ｪ繝ｪ繧ｵ繝ｼ繝√Ε繝ｼ</div>'
        '</div>',
        unsafe_allow_html=True,
    )
with c_btn:
    if st.button("売 譖ｴ譁ｰ"):
        st.cache_data.clear()
        st.rerun()

st.write("")
data = _get_data()
m    = data.market
dev  = m.current_deviation_pct

# 笏笏笏 繧ｹ繝・・繧ｿ繧ｹ蛻､螳・笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏
if dev is None:
    status_key, distance_str, phase_label, phase_desc = "no_data", "窶・, "繝・・繧ｿ縺ｪ縺・, ""
elif dev <= _DANGER:
    status_key, distance_str = "danger", "0.0%"
    phase_label  = "識 縺・∪縺瑚ｲｷ縺・ｴ・・
    phase_desc   = "譌･邨後′蜑ｲ螳画ｰｴ貅悶↓蛻ｰ驕費ｼ∽ｸ九・驫俶氛縺ｮ繝√Ε繝ｼ繝医ｒ遒ｺ隱阪＠縺ｦ雉ｼ蜈･繧呈､懆ｨ弱＠繧医≧・・
elif dev <= _WARNING:
    status_key   = "warning"
    distance_str = f"{_DANGER - dev:.1f}%"
    phase_label  = "操 縺昴ｍ縺昴ｍ雋ｷ縺・ｴ・・
    phase_desc   = "譌･邨後′荳玖誠荳ｭ・∽ｸ九・驫俶氛繧偵メ繧ｧ繝・け縺励※貅門ｙ縺励※縺翫％縺・ｼ・
else:
    status_key   = "normal"
    distance_str = f"{_DANGER - dev:.1f}%"
    phase_label  = "竢ｳ 縺・∪縺ｯ蠕・ｩ・
    phase_desc   = "縺ｾ縺雋ｷ縺・ｴ縺ｧ縺ｯ縺ｪ縺・ｈ縲よ律邨後′荳九′繧九・繧偵ｆ縺｣縺上ｊ蠕・→縺・ｼ・

th = _THEME[status_key]
nikkei_txt = (f'譌･邨悟ｹｳ蝮・{_yen(m.current_price)} ・・25譌･蟷ｳ蝮・→縺ｮ蟾ｮ {dev:+.1f}%' if dev is not None else "蜿門ｾ怜､ｱ謨・)

# 笏笏笏 繝｡繧､繝ｳ繧ｫ繝ｼ繝・笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏
st.markdown(
    f'<div class="puyo-card" style="background:{th["bg"]};border-color:{th["brd"]};'
    f'box-shadow:0 6px 0 {th["brd"]},0 8px 24px #00000018;">'

    f'<div style="font-size:13px;font-weight:700;color:{th["col"]};letter-spacing:1px;margin-bottom:12px;">'
    f'投 雋ｷ縺・ｴ縺ｾ縺ｧ縺ゅ→窶ｦ・域律邨悟ｹｳ蝮・ｼ・/div>'

    f'<div class="hero-flex" style="display:flex;align-items:center;gap:24px;flex-wrap:wrap;margin-bottom:16px;">'
    f'<div style="text-align:center;">'
    f'<span class="hero-num" style="color:{th["col"]};text-shadow:0 4px 0 {th["brd"]};">{distance_str}</span>'
    f'<div style="font-size:14px;font-weight:700;color:{th["txt"]};margin-top:2px;">荳玖誠縺ｧ雋ｷ縺・ｴ</div>'
    f'</div>'
    f'<div style="flex:1;min-width:180px;">'
    f'<div style="font-size:22px;font-weight:900;color:{th["txt"]};margin-bottom:6px;">{phase_label}</div>'
    f'<div style="font-size:14px;color:#556677;line-height:1.6;">{phase_desc}</div>'
    f'</div></div>'

    f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:8px;">'
    f'<span style="font-size:12px;color:#778899;">{nikkei_txt}</span>'
    f'<a href="{_NIKKEI_TV}" target="_blank">'
    f'<span style="font-size:13px;font-weight:700;color:{th["txt"]};background:{th["badge_bg"]};'
    f'border:2px solid {th["brd"]};border-radius:20px;padding:5px 14px;">投 譌･邨後メ繝｣繝ｼ繝・/span></a>'
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
        f'<div style="font-size:24px;font-weight:900;color:{rt["txt"]};">識 3縺区怦縺ｶ繧翫・雋ｷ縺・す繧ｰ繝翫Ν逋ｺ轣ｫ・・ｼ・/div>'
        f'<div style="font-size:13px;color:#667788;margin-top:6px;">譛邨ら匱轣ｫ譌･: {m.last_signal_date} ・・荳九・驫俶氛縺ｮ繝√Ε繝ｼ繝医ｒ遒ｺ隱阪＠縺ｦ雉ｼ蜈･繧呈､懆ｨ弱＠繧医≧・・/div>'
        f'</div>',
        unsafe_allow_html=True,
    )

# 笏笏笏 菴ｿ縺・婿 笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏
with st.expander("当 縺ｯ縺倥ａ縺ｦ縺ｮ譁ｹ縺ｸ 窶・菴ｿ縺・婿縺ｨ逕ｨ隱・):
    st.markdown(f"""
**縺薙・謇区ｳ輔・繧ｭ繝帙Φ・壼･ｽ讌ｭ邵ｾ縺ｮ譬ｪ繧偵梧垓關ｽ縺ｧ螳峨￥縺ｪ縺｣縺滓凾縲阪↓莉戊ｾｼ繧**

- **竢ｳ 縺・∪縺ｯ蠕・ｩ滂ｼ磯搨・・* 窶ｦ 菴輔ｂ縺励↑縺・よ律邨後′荳九′繧九・繧貞ｾ・▽
- **操 縺昴ｍ縺昴ｍ・・ｼ育ｷ托ｼ・* 窶ｦ 譌･邨後′荳玖誠荳ｭ縲ゆｸ九・驫俶氛繧偵メ繧ｧ繝・け縺励※貅門ｙ
- **識 縺・∪縺瑚ｲｷ縺・ｴ・郁ｵ､・・* 窶ｦ 譌･邨後′蜑ｲ螳画ｰｴ貅厄ｼ・_DANGER:.0f}%・峨↓蛻ｰ驕斐りｳｼ蜈･繧呈､懆ｨ趣ｼ・
**逕ｨ隱槭・諢丞袖**
- **25譌･蟷ｳ蝮・→縺ｮ蟾ｮ・井ｹ夜屬邇・ｼ・* 窶ｦ 譬ｪ萓｡縺檎峩霑・5譌･縺ｮ蟷ｳ蝮・ｈ繧贋ｽ・荳贋ｸ九＠縺ｦ縺・ｋ縺九ょ､ｧ縺阪￥繝槭う繝翫せ・晄･關ｽ縺ｧ蜑ｲ螳峨・_DANGER:.0f}%縺瑚ｲｷ縺・ｴ縺ｮ逶ｮ螳・- **螢ｲ荳・/ 邏泌茜逶奇ｼ亥燕蟷ｴ豈費ｼ・* 窶ｦ 蜴ｻ蟷ｴ繧医ｊ菴・謌宣聞縺励◆縺九るｫ倥＞縺ｻ縺ｩ螂ｽ讌ｭ邵ｾ
- **100譬ｪ雉ｼ蜈･鬘・* 窶ｦ 譌･譛ｬ譬ｪ縺ｯ蝓ｺ譛ｬ100譬ｪ蜊倅ｽ阪りｳｼ蜈･縺ｫ蠢・ｦ√↑縺翫ｈ縺昴・驥鷹｡・- **蝗槫ｾｩ逶奇ｼ育岼螳会ｼ・* 窶ｦ 迴ｾ蝨ｨ縺ｮ譬ｪ萓｡縺九ｉ25譌･蟷ｳ蝮・∪縺ｧ謌ｻ縺｣縺溷ｴ蜷医・100譬ｪ縺ゅ◆繧雁茜逶願ｦ玖ｾｼ縺ｿ

**雋ｷ縺・→縺阪・豬√ｌ**
譌･邨後′縲交沁ｯ 縺・∪縺瑚ｲｷ縺・ｴ縲阪↓縺ｪ繧・竊・荳九・驫俶氛縺九ｉ驕ｸ縺ｶ 竊・縲交沒・繝√Ε繝ｼ繝医ｒ隕九ｋ縲阪〒譛邨ら｢ｺ隱・竊・100譬ｪ雉ｼ蜈･繧呈､懆ｨ・
窶ｻ 縺薙・繧｢繝励Μ縺ｯ謚戊ｳ・勧險縺ｧ縺ｯ縺ゅｊ縺ｾ縺帙ｓ縲よ怙邨ょ愛譁ｭ縺ｯ縺碑・霄ｫ縺ｧ縲・    """)

st.markdown(
    '<div style="font-size:18px;font-weight:900;color:#2060a0;margin:12px 0 4px;">'
    '搭 逶｣隕夜釜譟・/div>'
    '<div style="font-size:13px;color:#6688aa;margin-bottom:14px;">螂ｽ讌ｭ邵ｾ縺ｧ荳頑・繝医Ξ繝ｳ繝峨・譬ｪ繧定・蜍暮∈螳夲ｼ域ｯ朱ｱ蝨滓屆譖ｴ譁ｰ・峨ょｮ峨＞鬆・↓陦ｨ遉ｺ縲・/div>',
    unsafe_allow_html=True,
)

# 笏笏笏 逶｣隕夜釜譟・Μ繧ｹ繝・笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏
if not data.rows:
    st.info("逶｣隕夜釜譟・′縺ゅｊ縺ｾ縺帙ｓ縲Ａout/pool.csv` 縺ｫ驫俶氛繧定ｿｽ蜉縺励※縺上□縺輔＞縲・)
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
                    "thr": prow.get("individual_threshold_pct"),
                }
        except Exception:
            pass

    nikkei_fired = (dev is not None and dev <= _DANGER)  # 譌･邨後′雋ｷ縺・ｴ縺・
    for row in data.rows:
        th_r = _THEME.get(row.status, _THEME["no_data"])
        dev_r   = _signed_dev(row.current_deviation_pct)
        price_r = _yen(row.current_price)
        unit_r  = _yen(row.current_price * 100) if row.current_price is not None else "窶・
        tv_url  = _tradingview_url(row.symbol)
        gd  = growth_data.get(row.symbol, {})
        thr = gd.get("thr")  # 蛟句挨荳矩剞・井ｾ・ -9.3・・
        rev = f"螢ｲ荳・+{gd['rev']:.0f}%" if gd.get("rev") is not None else ""
        inc = f"邏泌茜逶・+{gd['inc']:.0f}%" if gd.get("inc") is not None else ""
        growth_str = " ・・".join(x for x in [rev, inc] if x)
        growth_html = (
            f'<div style="font-size:12px;color:#4488cc;font-weight:700;margin-top:4px;">嶋 蜑榊ｹｴ豈・{growth_str}</div>'
            if growth_str else ""
        )

        # 蛟句挨譬ｪ繧り・蛻・・荳矩剞縺ｫ蛻ｰ驕斐＠縺ｦ縺・ｋ縺・        stock_fired = (
            thr is not None
            and row.current_deviation_pct is not None
            and row.current_deviation_pct <= thr
        )
        # 荳｡譚｡莉ｶ驕疲・繝舌ャ繧ｸ
        if nikkei_fired and stock_fired:
            dual_badge = '<span style="background:#c00020;color:#fff;font-weight:900;font-size:13px;padding:4px 12px;border-radius:20px;border:2px solid #ff4060;margin-left:8px;">櫨 荳｡譚｡莉ｶ驕疲・・・/span>'
        elif stock_fired:
            dual_badge = '<span style="background:#cc6600;color:#fff;font-weight:900;font-size:12px;padding:3px 10px;border-radius:20px;border:2px solid #ff8800;margin-left:8px;">笞｡ 蛟句挨繧ょｺ募､蝨・/span>'
        else:
            dual_badge = ""

        # 蛟句挨荳矩剞縺ｮ陦ｨ遉ｺ
        if thr is not None:
            thr_str = f"{thr:+.1f}%"
            thr_color = "#f05060" if stock_fired else "#778899"
            thr_html = (
                f'<div style="font-size:11px;color:#778899;font-weight:700;">縺薙・譬ｪ縺ｮ雋ｷ縺・ｴ繝ｩ繧､繝ｳ</div>'
                f'<div style="font-size:18px;font-weight:900;color:{thr_color};">{thr_str}</div>'
                f'<div style="font-size:10px;color:#99aacc;">驕主悉10蟷ｴ縺ｮ螳溽ｸｾ縺九ｉ邂怜・</div>'
            )
        else:
            thr_html = (
                f'<div style="font-size:11px;color:#778899;font-weight:700;">雋ｷ縺・ｴ繝ｩ繧､繝ｳ</div>'
                f'<div style="font-size:15px;color:#aabbcc;">邂怜・荳ｭ</div>'
            )

        profit = _recovery_profit_100(row.current_price, row.current_deviation_pct)
        if profit is not None and profit > 0:
            profit_html = (
                f'<div class="card-metric">'
                f'<div style="font-size:11px;color:#778899;font-weight:700;">蝗槫ｾｩ逶・逶ｮ螳・</div>'
                f'<div style="font-size:16px;font-weight:900;color:#e07800;">+{_yen(profit)}</div>'
                f'<div style="font-size:10px;color:#99aacc;">蟷ｳ蝮・∪縺ｧ謌ｻ繧後・</div>'
                f'</div>'
            )
        else:
            profit_html = (
                f'<div class="card-metric">'
                f'<div style="font-size:11px;color:#778899;font-weight:700;">蝗槫ｾｩ逶・逶ｮ螳・</div>'
                f'<div style="font-size:15px;color:#aabbcc;">窶・/div>'
                f'</div>'
            )

        border_extra = "border:3px solid #f05060;" if (nikkei_fired and stock_fired) else ""

        st.markdown(
            f'<div class="puyo-card" style="background:{th_r["bg"]};border-color:{th_r["brd"]};{border_extra}'
            f'box-shadow:0 5px 0 {th_r["brd"]},0 7px 18px #00000014;">'
            f'<div class="card-row">'

            f'<div class="card-name">'
            f'<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">'
            f'<span style="font-size:17px;font-weight:900;color:#1a2a3a;">{row.name}</span>'
            f'{dual_badge}'
            f'<span class="badge" style="background:{th_r["badge_bg"]};color:{th_r["txt"]};border-color:{th_r["brd"]};">'
            f'{_ROW_LABEL.get(row.status,"")}</span>'
            f'</div>'
            f'<div style="font-size:12px;color:#8899aa;margin-top:2px;">{row.symbol}</div>'
            f'{growth_html}'
            f'</div>'

            f'<div class="card-metric">'
            f'<div style="font-size:11px;color:#778899;font-weight:700;">迴ｾ蝨ｨ蛟､</div>'
            f'<div style="font-size:16px;color:#2a3a4a;font-weight:800;">{price_r}</div>'
            f'<div style="font-size:10px;color:#99aacc;margin-top:2px;">100譬ｪ {unit_r}</div>'
            f'</div>'

            f'<div class="card-metric">'
            f'<div style="font-size:11px;color:#778899;font-weight:700;">25譌･蟷ｳ蝮・→縺ｮ蟾ｮ</div>'
            f'<div style="font-size:22px;text-shadow:0 2px 0 {th_r["brd"]};">{dev_r}</div>'
            f'</div>'

            f'<div class="card-metric">'
            f'{thr_html}'
            f'</div>'

            f'{profit_html}'

            f'<div class="card-btn">'
            f'<a href="{tv_url}" target="_blank">'
            f'<div style="background:linear-gradient(180deg,#5ec8f0,#2a8fd4);color:#fff;font-weight:900;font-size:13px;'
            f'border-radius:20px;padding:10px 14px;border:2px solid #1a70b0;'
            f'box-shadow:0 3px 0 #1a60a0;text-shadow:0 1px 0 #0006;white-space:nowrap;">投 繝√Ε繝ｼ繝医ｒ隕九ｋ</div>'
            f'</a></div>'

            f'</div>'
            f'<div style="margin-top:12px;">{_dist_bar(row.current_deviation_pct, th_r, h=10, threshold=thr)}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

st.markdown("<br>", unsafe_allow_html=True)
st.markdown(
    f'<div style="text-align:center;font-size:12px;color:#6688aa;padding:8px;">'
    f'譛邨よ峩譁ｰ: {data.as_of}縲|縲雋ｷ縺・ｴ縺ｮ逶ｮ螳・{_DANGER:.0f}%縲|縲豈朱ｱ蝨滓屆 0:00 JST 閾ｪ蜍墓峩譁ｰ'
    f'</div>',
    unsafe_allow_html=True,
)
