"""文献驱动的虚拟细胞培养模拟器 Streamlit 界面。"""

import html
import json
import time
from dataclasses import asdict
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from streamlit.runtime.scriptrunner import get_script_run_ctx

from profiles import CELL_PROFILES
from simulation import PRESETS, cell_status, new_simulation, run_steps


st.set_page_config(page_title="e-cell", page_icon="🧫", layout="wide")

st.markdown(
    """
    <style>
    .block-container {max-width: 1440px; padding-top: 1.4rem;}
    .vc-metric-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: .7rem;
        margin: .25rem 0 1rem;
    }
    .vc-metric-card {
        min-width: 0;
        padding: .8rem .9rem;
        border: 1px solid #dfe9e3;
        border-left: 4px solid var(--accent, #4d9f78);
        border-radius: .75rem;
        background: linear-gradient(145deg, #ffffff, #f6faf7);
        box-shadow: 0 2px 9px rgba(33, 53, 42, .06);
    }
    .vc-metric-label {
        color: #597065; font-size: .78rem; line-height: 1.2;
        white-space: normal;
    }
    .vc-metric-value {
        color: #173c2b; font-size: 1.18rem; font-weight: 700;
        line-height: 1.25; margin-top: .24rem; overflow-wrap: anywhere;
    }
    .vc-overview {
        display: grid; grid-template-columns: minmax(210px, .8fr) minmax(280px, 1.6fr);
        gap: 1rem; align-items: stretch; margin: .35rem 0 1.1rem;
    }
    .vc-panel {
        border: 1px solid #dfe9e3; border-radius: .9rem; padding: 1rem;
        background: #fbfdfb;
    }
    .vc-dish-wrap {display:flex; align-items:center; justify-content:center; gap:.8rem; overflow:hidden;}
    .vc-dish-stage {display:flex; flex-direction:column; align-items:center; gap:.45rem; width:100%;}
    .vc-dish {
        position:relative; width:min(270px, 92%); aspect-ratio:1.48; overflow:hidden;
        border:6px solid #4b9870; border-radius:50%;
        background:radial-gradient(circle at 42% 35%,#f7fff9 0,#d8f0df 62%,#b9dfc7 100%);
        box-shadow:inset 0 0 0 5px rgba(255,255,255,.7), 0 9px 13px rgba(39,91,65,.17);
    }
    .vc-dish::before {content:""; position:absolute; inset:9px; border:2px solid rgba(95,164,119,.45); border-radius:50%;}
    .vc-dish-label {font-size:.78rem; color:#597065; text-align:center; line-height:1.35;}
    .vc-cell-particle {
        position:absolute; width:15px; height:15px; margin:-7px; border-radius:48% 52% 46% 54%;
        background:#70c495; border:1px solid rgba(39,112,75,.35);
        box-shadow:0 2px 4px rgba(33,93,61,.2); animation:vc-cell-drift 3.8s ease-in-out infinite;
    }
    .vc-cell-particle::after {
        content:""; position:absolute; width:5px; height:5px; border-radius:50%;
        background:#246c4a; left:5px; top:4px; opacity:.82;
    }
    .vc-dish-center {
        position:absolute; left:50%; top:50%; transform:translate(-50%,-50%);
        padding:.22rem .45rem; border-radius:999px; background:rgba(255,255,255,.78);
        color:#214c36; font-weight:750; font-size:1.05rem; z-index:4;
    }
    .vc-html-bubble {
        position:absolute; bottom:17%; border:2px solid #63b7d5; border-radius:50%;
        background:rgba(210,244,255,.55); opacity:0; animation:vc-bubble-up 2.2s ease-out infinite;
    }
    .vc-html-sugar {
        position:absolute; top:-14px; width:14px; height:14px; border-radius:4px;
        background:linear-gradient(135deg,#fff6b1,#e7b53f); border:1px solid #b9851d;
        opacity:0; z-index:5; animation:vc-sugar-drop 1.8s cubic-bezier(.35,.05,.25,1) infinite;
    }
    .vc-cell-particle {transform-origin:center;}
    @keyframes vc-cell-drift {50% {transform:translate(3px,-2px) scale(1.04);}}
    @keyframes vc-bubble-up {
        0% {transform:translateY(0) scale(.55); opacity:0;}
        18% {opacity:.85;} 100% {transform:translateY(-90px) scale(1.15); opacity:0;}
    }
    @keyframes vc-sugar-drop {
        0% {transform:translateY(0) rotate(0); opacity:0;}
        15% {opacity:1;} 72% {transform:translateY(72px) rotate(230deg); opacity:1;}
        100% {transform:translateY(92px) rotate(300deg) scale(.55); opacity:0;}
    }
    .vc-live {
        display:inline-flex; align-items:center; gap:.45rem; padding:.32rem .62rem;
        border-radius:999px; background:#e8f7ed; color:#256644; font-size:.82rem; font-weight:650;
    }
    .vc-live-dot {width:.55rem; height:.55rem; border-radius:50%; background:#2dad65; animation:vc-pulse 1.2s infinite;}
    @keyframes vc-pulse {50% {box-shadow:0 0 0 6px rgba(45,173,101,0); opacity:.55;}}
    .vc-bars {display:grid; grid-template-columns: 1fr 1fr; gap:.75rem 1rem;}
    .vc-bar-head {display:flex; justify-content:space-between; gap:.5rem; font-size:.82rem; color:#40574b;}
    .vc-track {height:.55rem; background:#e7efe9; border-radius:999px; overflow:hidden; margin-top:.3rem;}
    .vc-fill {height:100%; border-radius:inherit; background:linear-gradient(90deg,#64b88b,#2f7d5b);}
    .vc-env {display:flex; flex-wrap:wrap; gap:.45rem; margin-top:.9rem;}
    .vc-chip {padding:.28rem .55rem; border-radius:999px; background:#eaf4ed; color:#315b45; font-size:.78rem;}
    div.stButton > button {
        min-height: 2.85rem; font-weight: 650; transition: transform .08s ease, box-shadow .15s ease;
    }
    div.stButton > button:hover {box-shadow: 0 4px 12px rgba(47,125,91,.18);}
    div.stButton > button:active {transform: translateY(2px) scale(.99);}
    @media (max-width: 900px) {
        .vc-metric-grid {grid-template-columns: repeat(2, minmax(0, 1fr));}
        .vc-overview {grid-template-columns: 1fr;}
    }
    @media (max-width: 560px) {
        .block-container {padding-left: .8rem; padding-right: .8rem;}
        .vc-metric-grid {grid-template-columns: repeat(2, minmax(0, 1fr)); gap:.5rem;}
        .vc-metric-card {padding:.68rem .7rem;}
        .vc-metric-value {font-size: 1rem;}
        .vc-bars {grid-template-columns: 1fr;}
    }
    </style>
    """,
    unsafe_allow_html=True,
)

APP_STATE_VERSION = "1.0-alpha.3"
RUNTIME_STATE_PATH = Path(__file__).with_name(".runtime_state.json")

TIME_MULTIPLIERS = {
    1: "1× 实时（1 秒 = 1 秒）",
    60: "60×（1 秒 = 1 分钟）",
    600: "600×（1 秒 = 10 分钟）",
    3600: "3600×（1 秒 = 1 小时）",
    21600: "21600×（1 秒 = 6 小时）",
}

PERSISTED_CELL_FIELDS = (
    "culture_volume_ml", "surface_area_cm2", "viable_cells", "dead_cells",
    "time_h", "glucose_mm", "glutamine_mm", "lactate_mm", "oxygen_percent",
    "oxygen_setpoint_percent", "ph", "temperature_c", "co2_percent",
    "osmolality_mosm_kg", "drug_um", "energy_index",
    "last_growth_rate_per_h", "last_death_rate_per_h",
)


def persistence_enabled() -> bool:
    """测试运行不读写用户的连续培养状态。"""

    context = get_script_run_ctx(suppress_warning=True)
    return context is None or context.session_id != "test session id"

# 这些字段是当前界面的模型校准控件必须使用的参数。
# 除了版本号，还要检查对象结构，因为 Streamlit 热更新后可能出现：
# 新版本号已经写入，但旧版 Cell 对象仍留在当前浏览器会话中。
REQUIRED_PARAMETER_FIELDS = (
    "growth_scale",
    "uptake_scale",
    "death_rate_per_h",
    "drug_ic50_um",
    "drug_hill",
    "oxygen_transfer_per_h",
)

ENVIRONMENT_WIDGET_KEYS = (
    "environment_temperature_c",
    "environment_co2_percent",
    "environment_oxygen_setpoint_percent",
    "environment_osmolality_mosm_kg",
    "environment_ph",
)


def save_runtime_state() -> None:
    """保存连续培养状态，使页面离开后仍可按真实经过时间补算。"""

    if not persistence_enabled():
        return
    cell = st.session_state.get("cell")
    if cell is None:
        return
    payload = {
        "version": APP_STATE_VERSION,
        "profile_key": cell.profile_key,
        "preset_name": st.session_state.get("preset_name", "标准培养"),
        "cell": {name: getattr(cell, name) for name in PERSISTED_CELL_FIELDS},
        "parameters": asdict(cell.parameters),
        "history": st.session_state.get("history", []),
        "running": st.session_state.get("running", False),
        "run_message": st.session_state.get("run_message", "尚未运行"),
        "last_wall_time": st.session_state.get("last_wall_time", time.time()),
        "time_multiplier": st.session_state.get("time_multiplier", 60),
    }
    temporary_path = RUNTIME_STATE_PATH.with_suffix(".json.tmp")
    temporary_path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    temporary_path.replace(RUNTIME_STATE_PATH)


def load_runtime_state() -> bool:
    """恢复上次连续培养；文件无效时安全回退为新实验。"""

    if not persistence_enabled() or not RUNTIME_STATE_PATH.exists():
        return False
    try:
        payload = json.loads(RUNTIME_STATE_PATH.read_text(encoding="utf-8"))
        if payload.get("version") != APP_STATE_VERSION:
            return False
        cell, _ = new_simulation(payload.get("profile_key", "hela"))
        for name, value in payload.get("cell", {}).items():
            if name in PERSISTED_CELL_FIELDS:
                setattr(cell, name, value)
        for name, value in payload.get("parameters", {}).items():
            if hasattr(cell.parameters, name):
                setattr(cell.parameters, name, value)
        history = payload.get("history")
        st.session_state.cell = cell
        st.session_state.history = history if isinstance(history, list) and history else [cell.snapshot()]
        st.session_state.profile_key = cell.profile_key
        st.session_state.preset_name = payload.get("preset_name", "标准培养")
        st.session_state.running = bool(payload.get("running", False)) and cell.alive
        st.session_state.run_message = payload.get("run_message", "尚未运行")
        st.session_state.last_wall_time = float(payload.get("last_wall_time", time.time()))
        multiplier = int(payload.get("time_multiplier", 60))
        st.session_state.time_multiplier = multiplier if multiplier in TIME_MULTIPLIERS else 60
        return True
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return False


def trigger_effect(effect: str, duration_s: float = 6.0) -> None:
    """触发培养皿中的短时粒子动画。"""

    st.session_state.visual_effect = effect
    st.session_state.effect_until = time.time() + duration_s
    st.session_state.effect_cycles_remaining = max(1, round(duration_s))
    st.session_state.effect_nonce = st.session_state.get("effect_nonce", 0) + 1


def advance_realtime(now: float | None = None) -> float:
    """按墙上时钟推进连续培养，并返回本次推进的模拟小时数。"""

    if not st.session_state.get("running", False):
        return 0.0
    cell = st.session_state.cell
    if not cell.alive:
        st.session_state.running = False
        save_runtime_state()
        return 0.0

    current = time.time() if now is None else float(now)
    last = float(st.session_state.get("last_wall_time", current))
    elapsed_seconds = max(0.0, current - last)
    st.session_state.last_wall_time = current
    simulated_hours = elapsed_seconds * st.session_state.time_multiplier / 3600.0
    if simulated_hours <= 0:
        return 0.0

    # 最多约 500 个历史点；长时间离开页面时使用不超过模型上限 6 h 的步长补算。
    step_h = min(6.0, max(1.0 / 3600.0, simulated_hours / 500.0))
    remaining = simulated_hours
    iterations = 0
    while remaining > 1e-9 and cell.alive and iterations < 20000:
        cell.step(min(step_h, remaining))
        st.session_state.history.append(cell.snapshot())
        remaining -= step_h
        iterations += 1
    if not cell.alive:
        st.session_state.running = False
        st.session_state.run_message = "连续培养已停止：培养物失活"
    save_runtime_state()
    return simulated_hours - max(0.0, remaining)


def format_simulation_time(hours: float) -> str:
    """把小时转换成连续培养时钟。"""

    total_seconds = max(0, round(hours * 3600))
    days, remainder = divmod(total_seconds, 86400)
    hour, remainder = divmod(remainder, 3600)
    minute, second = divmod(remainder, 60)
    prefix = f"{days} d " if days else ""
    return f"{prefix}{hour:02d}:{minute:02d}:{second:02d}"


def state_needs_migration() -> bool:
    """判断缓存会话是否与当前模型结构兼容。"""

    if st.session_state.get("app_state_version") != APP_STATE_VERSION:
        return True

    cell = st.session_state.get("cell")
    parameters = getattr(cell, "parameters", None)
    if parameters is None:
        return True

    return any(
        not hasattr(parameters, field_name)
        for field_name in REQUIRED_PARAMETER_FIELDS
    )


def initialize_state() -> None:
    """初始化 Streamlit 会话。"""

    # Streamlit Cloud 在热更新代码时可能保留旧版本 session_state。
    # V0.3 的 Cell/参数对象与 V1.0 不兼容，因此版本变化时统一重建会话。
    if state_needs_migration():
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.session_state.app_state_version = APP_STATE_VERSION

    if "profile_key" not in st.session_state:
        st.session_state.profile_key = "hela"
    if "preset_name" not in st.session_state:
        st.session_state.preset_name = "标准培养"
    if "cell" not in st.session_state or "history" not in st.session_state:
        if not load_runtime_state():
            st.session_state.cell, st.session_state.history = new_simulation()
    if "run_message" not in st.session_state:
        st.session_state.run_message = "尚未运行"
    if "running" not in st.session_state:
        st.session_state.running = False
    if "last_wall_time" not in st.session_state:
        st.session_state.last_wall_time = time.time()
    if "time_multiplier" not in st.session_state:
        st.session_state.time_multiplier = 60
    if st.session_state.running and st.session_state.run_message == "尚未运行":
        st.session_state.run_message = (
            f"连续培养中 · {TIME_MULTIPLIERS[st.session_state.time_multiplier]}"
        )
    if "speed_choice" not in st.session_state:
        st.session_state.speed_choice = st.session_state.time_multiplier
    if "visual_effect" not in st.session_state:
        st.session_state.visual_effect = ""
    if "effect_until" not in st.session_state:
        st.session_state.effect_until = 0.0
    if "effect_cycles_remaining" not in st.session_state:
        st.session_state.effect_cycles_remaining = 0


def reset_simulation(profile_key: str, preset_name: str, volume: float, area: float) -> None:
    """按当前设置创建新的培养模拟。"""

    st.session_state.cell, st.session_state.history = new_simulation(
        profile_key, preset_name, volume, area
    )
    # 环境控件拥有独立的 widget state。重置时必须清除旧值，否则旧实验的
    # 温度、pH、氧等设置会在下一次渲染时覆盖新场景的初始条件。
    for key in ENVIRONMENT_WIDGET_KEYS:
        st.session_state.pop(key, None)
    st.session_state.profile_key = profile_key
    st.session_state.preset_name = preset_name
    st.session_state.running = False
    st.session_state.last_wall_time = time.time()
    st.session_state.run_message = "已创建新实验"
    st.session_state.pending_toast = ("实验已重置，新场景参数已生效", "🔄")
    save_runtime_state()


def update_environment(attribute: str, widget_key: str) -> None:
    """在页面主体渲染前把环境控件的新值同步到当前培养物。"""

    setattr(st.session_state.cell, attribute, st.session_state[widget_key])
    if attribute == "oxygen_setpoint_percent":
        trigger_effect("oxygen")
    save_runtime_state()


def update_time_multiplier() -> None:
    """切换倍率前先按旧倍率结算已经过的真实时间。"""

    advance_realtime()
    st.session_state.time_multiplier = st.session_state.speed_choice
    st.session_state.last_wall_time = time.time()
    st.session_state.run_message = f"培养速度切换为 {TIME_MULTIPLIERS[st.session_state.time_multiplier]}"
    save_runtime_state()


def sidebar() -> None:
    """显示细胞类型、培养器皿和可校准参数。"""

    st.sidebar.header("实验设计")
    keys = list(CELL_PROFILES)
    labels = {key: CELL_PROFILES[key].display_name for key in keys}
    profile_key = st.sidebar.selectbox(
        "细胞类型", keys, format_func=lambda key: labels[key],
        index=keys.index(st.session_state.profile_key),
    )
    preset_name = st.sidebar.selectbox("实验场景", list(PRESETS))
    st.sidebar.caption(PRESETS[preset_name]["description"])
    volume = st.sidebar.number_input("培养液体积（mL）", 0.1, 500.0, 10.0, 0.5)
    area = st.sidebar.number_input("培养面积（cm²）", 0.1, 500.0, 25.0, 1.0)
    if st.sidebar.button("创建/重置实验", type="primary", width="stretch"):
        reset_simulation(profile_key, preset_name, volume, area)
        st.rerun()

    cell = st.session_state.cell
    p = cell.parameters
    st.sidebar.subheader("模型校准参数")
    st.sidebar.caption("以下参数应使用本实验室数据拟合；修改后下一步生效。")
    p.growth_scale = st.sidebar.slider("生长速率缩放", 0.1, 2.0, p.growth_scale, 0.05)
    p.uptake_scale = st.sidebar.slider("代谢摄取缩放", 0.1, 3.0, p.uptake_scale, 0.05)
    p.death_rate_per_h = st.sidebar.number_input(
        "基础死亡率（1/h）", 0.0, 0.10, p.death_rate_per_h, 0.001, format="%.3f"
    )
    p.drug_ic50_um = st.sidebar.number_input(
        "药物 IC50（µM）", 0.001, 10000.0, p.drug_ic50_um, 1.0
    )
    p.drug_hill = st.sidebar.slider("Hill 系数", 0.2, 4.0, p.drug_hill, 0.1)
    p.oxygen_transfer_per_h = st.sidebar.slider(
        "氧传递系数（1/h）", 0.01, 2.0, p.oxygen_transfer_per_h, 0.01
    )


def show_profile(cell) -> None:
    """显示所选细胞系的培养条件和参数来源状态。"""

    profile = cell.profile
    st.subheader(profile.display_name)
    with st.expander("查看细胞系资料与推荐培养条件"):
        info = pd.DataFrame(
            {
                "项目": ["来源组织", "疾病/类型", "形态", "推荐培养基", "温度", "CO₂", "倍增时间先验"],
                "值": [profile.tissue, profile.disease, profile.morphology, profile.medium,
                       f"{profile.temperature_c:.1f} °C", f"{profile.co2_percent:.1f}%",
                       f"{profile.doubling_time_h:.1f} h"],
            }
        )
        st.dataframe(info, hide_index=True, width="stretch")
        st.info(profile.reference_status)


def controls(cell) -> None:
    """提供可对应真实培养操作的控制项。"""

    st.subheader("培养操作")
    speed_col, start_col, pause_col = st.columns([2, 1, 1])
    speed_col.selectbox(
        "培养时间倍率",
        list(TIME_MULTIPLIERS),
        key="speed_choice",
        format_func=lambda value: TIME_MULTIPLIERS[value],
        on_change=update_time_multiplier,
    )
    if start_col.button(
        "▶ 开始连续培养", type="primary", width="stretch",
        disabled=st.session_state.running or not cell.alive,
    ):
        st.session_state.running = True
        st.session_state.last_wall_time = time.time()
        st.session_state.run_message = f"连续培养中 · {TIME_MULTIPLIERS[st.session_state.time_multiplier]}"
        st.session_state.pending_toast = ("连续培养已开始；离开页面后仍按真实时间补算", "▶️")
        save_runtime_state()
        st.rerun()
    if pause_col.button(
        "⏸ 暂停培养", width="stretch", disabled=not st.session_state.running,
    ):
        advance_realtime()
        st.session_state.running = False
        st.session_state.run_message = "连续培养已暂停"
        st.session_state.pending_toast = ("培养时钟已暂停", "⏸️")
        save_runtime_state()
        st.rerun()

    if st.session_state.running:
        st.markdown(
            f'<span class="vc-live"><span class="vc-live-dot"></span>'
            f'连续培养中 · {html.escape(TIME_MULTIPLIERS[st.session_state.time_multiplier])}</span>',
            unsafe_allow_html=True,
        )
    else:
        st.caption("培养时钟当前已暂停；开始后即使页面休眠，返回时也会补算经过时间。")

    st.markdown("##### 单步操作")
    col1, col2, col3, col4 = st.columns(4)
    dt_h = col1.selectbox("每步时长（h）", [0.25, 0.5, 1.0, 2.0, 4.0], index=2)
    steps = col2.selectbox("运行步数", [1, 6, 12, 24, 48, 72], index=0)
    if col3.button("单步推进", width="stretch", disabled=not cell.alive):
        advance_realtime()
        completed = run_steps(cell, st.session_state.history, steps, dt_h)
        st.session_state.run_message = f"已运行 {completed} 步，共 {completed * dt_h:g} h"
        st.session_state.pending_toast = (
            f"模拟推进 {completed * dt_h:g} 小时，图表和指标已更新", "▶️"
        )
        st.session_state.last_wall_time = time.time()
        save_runtime_state()
        st.rerun()
    if col4.button("全量换液", width="stretch", disabled=not cell.alive):
        advance_realtime()
        cell.exchange_medium(1.0)
        st.session_state.history.append(cell.snapshot())
        st.session_state.run_message = "已全量换液"
        st.session_state.pending_toast = ("换液完成，营养与环境指标已刷新", "✅")
        save_runtime_state()
        st.rerun()

    if st.session_state.run_message != "尚未运行":
        st.success(f"操作完成 · {st.session_state.run_message}", icon="✅")

    with st.expander("环境与药物设置", expanded=True):
        a, b, c, d = st.columns(4)
        cell.temperature_c = a.number_input(
            "温度（°C）", 30.0, 42.0, cell.temperature_c, 0.1,
            key="environment_temperature_c",
            on_change=update_environment,
            args=("temperature_c", "environment_temperature_c"),
        )
        cell.co2_percent = b.number_input(
            "CO₂（%）", 0.0, 20.0, cell.co2_percent, 0.5,
            key="environment_co2_percent",
            on_change=update_environment,
            args=("co2_percent", "environment_co2_percent"),
        )
        cell.oxygen_setpoint_percent = c.number_input(
            "氧设定值（%）", 0.1, 21.0, cell.oxygen_setpoint_percent, 0.5,
            key="environment_oxygen_setpoint_percent",
            on_change=update_environment,
            args=("oxygen_setpoint_percent", "environment_oxygen_setpoint_percent"),
        )
        cell.osmolality_mosm_kg = d.number_input(
            "渗透压（mOsm/kg）", 200.0, 450.0, cell.osmolality_mosm_kg, 5.0,
            key="environment_osmolality_mosm_kg",
            on_change=update_environment,
            args=("osmolality_mosm_kg", "environment_osmolality_mosm_kg"),
        )
        e, f, g = st.columns(3)
        cell.ph = e.number_input(
            "当前 pH", 6.2, 8.0, cell.ph, 0.05,
            key="environment_ph",
            on_change=update_environment,
            args=("ph", "environment_ph"),
        )
        dose = f.number_input("设置药物浓度（µM）", 0.0, 10000.0, cell.drug_um, 0.5)
        if g.button("应用药物浓度", width="stretch"):
            advance_realtime()
            cell.add_drug(dose)
            st.session_state.history.append(cell.snapshot())
            st.session_state.run_message = f"药物浓度设为 {dose:g} µM"
            st.session_state.pending_toast = (
                f"药物浓度已设为 {dose:g} µM，下一步模拟时生效", "💊"
            )
            save_runtime_state()
            st.rerun()

def metrics(cell) -> None:
    """显示实验常用的状态指标。"""

    st.subheader("实时培养状态")
    values = [
        ("⏱", "培养时间", format_simulation_time(cell.time_h)),
        ("🧫", "活细胞数", f"{cell.viable_cells:,.0f}"),
        ("♥", "存活率", f"{cell.viability_percent:.1f}%"),
        ("◉", "汇合度", f"{cell.confluence_percent:.1f}%"),
        ("⚡", "能量指数", f"{cell.energy_index:.1f}"),
        ("⬡", "葡萄糖", f"{cell.glucose_mm:.3f} mM"),
        ("◇", "谷氨酰胺", f"{cell.glutamine_mm:.3f} mM"),
        ("●", "乳酸", f"{cell.lactate_mm:.3f} mM"),
        ("○", "溶氧", f"{cell.oxygen_percent:.2f}%"),
        ("pH", "酸碱度", f"{cell.ph:.2f}"),
        ("✦", "药物", f"{cell.drug_um:.3f} µM"),
        ("≈", "渗透压", f"{cell.osmolality_mosm_kg:.0f} mOsm/kg"),
    ]
    cards = "".join(
        f'<div class="vc-metric-card"><div class="vc-metric-label">'
        f'{icon} {html.escape(label)}</div><div class="vc-metric-value">'
        f'{html.escape(value)}</div></div>'
        for icon, label, value in values
    )
    st.markdown(f'<div class="vc-metric-grid">{cards}</div>', unsafe_allow_html=True)


def culture_overview(cell) -> None:
    """用培养皿、进度条和环境标签直观呈现当前培养状态。"""

    # 百分比坐标全部位于椭圆培养液的安全区内，避免细胞贴边或被裁切。
    dot_positions = (
        (30, 30), (42, 26), (55, 32), (68, 28), (76, 40), (26, 45),
        (39, 46), (52, 44), (66, 48), (75, 57), (29, 62), (42, 65),
        (55, 61), (68, 66), (35, 74), (50, 74), (63, 74), (72, 70),
        (23, 54), (78, 50), (32, 52), (60, 54), (46, 38), (58, 68),
    )
    dot_count = max(1, round(len(dot_positions) * cell.confluence_percent / 100.0))
    dots = "".join(
        f'<span class="vc-cell-particle" style="left:{x}%;top:{y}%;'
        f'animation-delay:{index * -.31:.2f}s;'
        f'animation-duration:{3.2 + (index % 5) * .45:.2f}s"></span>'
        for index, (x, y) in enumerate(dot_positions[:dot_count])
    )

    active_effect = (
        st.session_state.get("visual_effect", "")
        if st.session_state.get("effect_cycles_remaining", 0) > 0
        else ""
    )
    if active_effect:
        st.session_state.effect_cycles_remaining -= 1
    bubbles = ""
    sugars = ""
    if active_effect == "oxygen":
        bubbles = "".join(
            f'<span class="vc-html-bubble" style="left:{26 + index * 8}%;'
            f'width:{8 + index % 3 * 3}px;height:{8 + index % 3 * 3}px;'
            f'animation-delay:{index * .16:.2f}s"></span>'
            for index in range(7)
        )
    elif active_effect == "glucose":
        sugars = "".join(
            f'<span class="vc-html-sugar" style="left:{27 + index * 9}%;'
            f'animation-delay:{index * .13:.2f}s"></span>'
            for index in range(6)
        )

    glucose_percent = 100.0 * cell.glucose_mm / max(0.001, cell.profile.initial_glucose_mm)
    bars = (
        ("存活率", cell.viability_percent),
        ("汇合度", cell.confluence_percent),
        ("能量状态", cell.energy_index),
        ("葡萄糖储备", glucose_percent),
    )
    bar_html = "".join(
        '<div><div class="vc-bar-head"><span>{}</span><strong>{:.0f}%</strong></div>'
        '<div class="vc-track"><div class="vc-fill" style="width:{:.1f}%"></div></div></div>'.format(
            html.escape(label), max(0.0, min(100.0, value)), max(0.0, min(100.0, value))
        )
        for label, value in bars
    )
    overview = f"""
    <div class="vc-overview">
      <div class="vc-panel vc-dish-wrap">
        <div class="vc-dish-stage" role="img" aria-label="动态培养皿视图" data-effect="{html.escape(active_effect)}-{st.session_state.get('effect_nonce', 0)}">
          <div class="vc-dish">{dots}{bubbles}{sugars}<div class="vc-dish-center">{cell.confluence_percent:.0f}%</div></div>
          <div class="vc-dish-label"><strong>动态培养皿</strong><br><span>细胞漂移 · 氧气气泡 · 葡萄糖颗粒</span></div>
        </div>
      </div>
      <div class="vc-panel">
        <div class="vc-bars">{bar_html}</div>
        <div class="vc-env">
          <span class="vc-chip">pH {cell.ph:.2f}</span>
          <span class="vc-chip">O₂ {cell.oxygen_percent:.1f}%</span>
          <span class="vc-chip">{cell.temperature_c:.1f} °C</span>
          <span class="vc-chip">CO₂ {cell.co2_percent:.1f}%</span>
          <span class="vc-chip">乳酸 {cell.lactate_mm:.2f} mM</span>
          <span class="vc-chip">速度 {st.session_state.time_multiplier}×</span>
        </div>
      </div>
    </div>
    """
    # st.html 直接渲染 SVG/CSS 动画，避免 Markdown 解析器把动态 SVG 标签当成文字。
    st.html(overview)


def dish_quick_actions(cell) -> None:
    """把产生动画的操作放在培养皿正下方，保证同屏可见。"""

    st.markdown("##### 培养皿快捷操作")
    st.session_state.setdefault("dish_glucose_addition", 1.0)
    st.session_state.setdefault("dish_oxygen_addition", 1.0)
    sugar_button, oxygen_button = st.columns(2)
    if sugar_button.button("🍬 投入葡萄糖", width="stretch"):
        advance_realtime()
        glucose_addition = st.session_state.dish_glucose_addition
        cell.add_glucose(glucose_addition)
        st.session_state.history.append(cell.snapshot())
        trigger_effect("glucose")
        st.session_state.run_message = f"已补充葡萄糖 {glucose_addition:g} mM"
        st.toast(f"已向培养皿投入 {glucose_addition:g} mM 葡萄糖", icon="🍬")
        save_runtime_state()

    if oxygen_button.button("🫧 补充溶氧", width="stretch"):
        advance_realtime()
        oxygen_addition = st.session_state.dish_oxygen_addition
        cell.oxygen_percent = min(21.0, cell.oxygen_percent + oxygen_addition)
        st.session_state.history.append(cell.snapshot())
        trigger_effect("oxygen")
        st.session_state.run_message = f"已补充溶氧 {oxygen_addition:g} 个百分点"
        st.toast(f"溶氧已提高 {oxygen_addition:g} 个百分点", icon="🫧")
        save_runtime_state()

    sugar_input, oxygen_input = st.columns(2)
    sugar_input.number_input(
        "单次葡萄糖（mM）", min_value=0.1, max_value=20.0, step=0.5,
        key="dish_glucose_addition",
    )
    oxygen_input.number_input(
        "单次溶氧（百分点）", min_value=0.5, max_value=10.0, step=0.5,
        key="dish_oxygen_addition",
    )


def plot_history(history) -> None:
    """绘制细胞数量、代谢物和环境条件曲线。"""

    data = pd.DataFrame(history)
    fig, axes = plt.subplots(2, 2, figsize=(11, 7))
    axes[0, 0].plot(
        data["time_h"], data["viable_cells"], label="Viable cells",
        marker="o", markersize=3,
    )
    axes[0, 0].plot(data["time_h"], data["dead_cells"], label="Dead cells", marker="o", markersize=3)
    axes[0, 0].set_ylabel("Cell count")
    axes[0, 0].legend()
    axes[0, 1].plot(data["time_h"], data["glucose_mM"], label="Glucose", marker="o", markersize=3)
    axes[0, 1].plot(data["time_h"], data["lactate_mM"], label="Lactate", marker="o", markersize=3)
    axes[0, 1].set_ylabel("mM")
    axes[0, 1].legend()
    axes[1, 0].plot(data["time_h"], data["viability_percent"], label="Viability", marker="o", markersize=3)
    axes[1, 0].plot(data["time_h"], data["confluence_percent"], label="Confluence", marker="o", markersize=3)
    axes[1, 0].set_ylabel("Percent")
    axes[1, 0].legend()
    axes[1, 1].plot(data["time_h"], data["pH"], label="pH", marker="o", markersize=3)
    axes[1, 1].plot(data["time_h"], data["oxygen_percent"], label="Oxygen %", marker="o", markersize=3)
    axes[1, 1].legend()
    for ax in axes.flat:
        ax.set_xlabel("Time (h)")
        ax.grid(alpha=0.2)
    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)


def references(cell) -> None:
    """显示当前配置使用的来源和局限。"""

    with st.expander("参数来源与可追溯性", expanded=True):
        for reference in cell.profile.references:
            st.markdown(f"- [{reference.title}]({reference.url})：{reference.note}")
        st.warning(
            "培养条件来自细胞库/论文；代谢摄取速率、死亡率和部分倍增时间是可校准先验。"
            "在没有同批次实验数据拟合和外部验证前，输出不能作为定量实验结论。"
        )


@st.fragment(run_every=1.0)
def live_status_panel() -> None:
    """每秒刷新连续培养时钟、状态卡片和动态培养皿。"""

    advance_realtime()
    current_cell = st.session_state.cell
    status_text, status_level = cell_status(current_cell)
    getattr(st, status_level)(
        f"当前状态：{html.escape(status_text)}｜{st.session_state.run_message}"
    )
    metrics(current_cell)
    overview_slot = st.empty()
    dish_quick_actions(current_cell)
    with overview_slot:
        culture_overview(current_cell)


initialize_state()
sidebar()
cell = st.session_state.cell

st.title("e-cell")
st.caption("虚拟细胞培养与代谢模拟器 · V1.0-alpha.4 · 文献驱动、真实单位、可校准参数")
st.error("研究原型：可用于假设探索和实验设计辅助；尚未经过实验验证，不能替代湿实验。")

pending_toast = st.session_state.pop("pending_toast", None)
if pending_toast:
    message, icon = pending_toast
    st.toast(message, icon=icon)

show_profile(cell)
live_status_panel()

controls(cell)
st.subheader("培养动力学曲线")
plot_history(st.session_state.history)

data = pd.DataFrame(st.session_state.history)
st.subheader("实验数据与导出")
st.download_button(
    "下载带单位的 CSV",
    data=data.to_csv(index=False).encode("utf-8-sig"),
    file_name=f"{cell.profile_key}_culture_{cell.time_h:.1f}h.csv",
    mime="text/csv",
)
with st.expander("查看原始数据"):
    st.dataframe(data, hide_index=True, width="stretch")

references(cell)

with st.expander("模型方程和校准说明"):
    st.markdown(
        """
        - 最大比生长率由群体倍增时间换算：`μmax = ln(2) / doubling_time`。
        - 实际生长率由葡萄糖、氧、pH、温度、渗透压、乳酸、药物和汇合度共同修正。
        - 葡萄糖采用 Monod 饱和项；药物采用 Hill/IC50 抑制项；汇合度采用承载量限制。
        - 葡萄糖消耗与乳酸生成使用细胞特异性先验，并按细胞数、体积和时间积分。
        - 建议用至少 3 个生物学重复、多个时间点的细胞数、存活率、葡萄糖和乳酸数据拟合参数，
          再用独立实验批次验证预测误差。
        """
    )
