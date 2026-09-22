"""文献驱动的虚拟细胞培养模拟器 Streamlit 界面。"""

import html
import json
import time
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from streamlit.runtime.scriptrunner import get_script_run_ctx

from intracellular import IntracellularState, intracellular_status
from profiles import CELL_PROFILES
from simulation import PRESETS, cell_status, new_simulation


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
    .vc-cell-map {
        width:100%; max-width:1080px; margin:.5rem auto 1rem; padding:.7rem;
        overflow:hidden; border:1px solid rgba(91,142,162,.32); border-radius:1.1rem;
        background:linear-gradient(145deg,#f9fdff 0%,#eef8fb 58%,#f6f2ff 100%);
        box-shadow:0 12px 30px rgba(45,91,112,.11),inset 0 1px 0 #fff;
    }
    .vc-cell-map svg {display:block;width:100%;height:auto;min-height:340px;}
    .vc-cell-caption {display:flex;justify-content:space-between;gap:.8rem;align-items:center;padding:.1rem .5rem .35rem;color:#4b6672;font-size:.78rem;}
    .vc-state-ribbon {display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:.5rem;margin:.35rem auto 1rem;max-width:1080px;}
    .vc-state-pill {padding:.52rem .65rem;border:1px solid #dbe9ee;border-radius:.65rem;background:rgba(255,255,255,.84);color:#45606b;font-size:.72rem;text-align:center;}
    .vc-state-pill strong {display:block;color:#173f50;font-size:.9rem;margin-top:.12rem;}
    .vc-mode-note {padding:.75rem 1rem;border-left:4px solid #4d9f78;background:#f2faf5;border-radius:.35rem;margin:.35rem 0 1rem;}
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
        .vc-cell-map {padding:.2rem;border-radius:.75rem;overflow-x:auto;}
        .vc-cell-map svg {width:760px;max-width:none;min-height:0;}
        .vc-cell-caption {align-items:flex-start;flex-direction:column;padding:.4rem .55rem;}
        .vc-state-ribbon {grid-template-columns:repeat(2,minmax(0,1fr));}
    }
    </style>
    """,
    unsafe_allow_html=True,
)

APP_STATE_VERSION = "1.0-alpha.5"
RUNTIME_STATE_PATH = Path(__file__).with_name(".runtime_state.json")
MAX_HISTORY_POINTS = 2000

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
        "history": st.session_state.get("history", [])[-MAX_HISTORY_POINTS:],
        "running": st.session_state.get("running", False),
        "run_message": st.session_state.get("run_message", "尚未运行"),
        "last_wall_time": st.session_state.get("last_wall_time", time.time()),
        "time_multiplier": st.session_state.get("time_multiplier", 60),
        "app_mode": st.session_state.get("app_mode", "细胞培养"),
        "intracellular": asdict(st.session_state.get("intracellular", IntracellularState())),
        "intracellular_history": st.session_state.get("intracellular_history", [])[-MAX_HISTORY_POINTS:],
    }
    # Streamlit 的定时 fragment 和按钮回调可能并发保存。同名临时文件会被
    # 另一个执行流先移动，从而在 Cloud 上触发 FileNotFoundError。
    temporary_path = RUNTIME_STATE_PATH.with_name(
        f"{RUNTIME_STATE_PATH.name}.{uuid4().hex}.tmp"
    )
    try:
        temporary_path.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        temporary_path.replace(RUNTIME_STATE_PATH)
    except OSError:
        # 云端文件系统是临时存储；保存失败不应中断正在运行的培养界面。
        return
    finally:
        temporary_path.unlink(missing_ok=True)


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
        st.session_state.history = (
            history[-MAX_HISTORY_POINTS:]
            if isinstance(history, list) and history
            else [cell.snapshot()]
        )
        st.session_state.profile_key = cell.profile_key
        st.session_state.preset_name = payload.get("preset_name", "标准培养")
        st.session_state.running = bool(payload.get("running", False)) and cell.alive
        st.session_state.run_message = payload.get("run_message", "尚未运行")
        st.session_state.last_wall_time = float(payload.get("last_wall_time", time.time()))
        multiplier = int(payload.get("time_multiplier", 60))
        st.session_state.time_multiplier = multiplier if multiplier in TIME_MULTIPLIERS else 60
        intracellular_payload = payload.get("intracellular", {})
        allowed_fields = IntracellularState.__dataclass_fields__
        st.session_state.intracellular = IntracellularState(**{
            name: value for name, value in intracellular_payload.items()
            if name in allowed_fields
        })
        intracellular_history = payload.get("intracellular_history")
        st.session_state.intracellular_history = (
            intracellular_history[-MAX_HISTORY_POINTS:]
            if isinstance(intracellular_history, list) and intracellular_history
            else [st.session_state.intracellular.snapshot()]
        )
        st.session_state.app_mode = payload.get("app_mode", "细胞培养")
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
        actual_step = min(step_h, remaining)
        cell.step(actual_step)
        st.session_state.intracellular.step(cell, actual_step)
        st.session_state.history.append(cell.snapshot())
        st.session_state.intracellular_history.append(
            st.session_state.intracellular.snapshot()
        )
        remaining -= actual_step
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
    if "app_mode" not in st.session_state:
        st.session_state.app_mode = "细胞培养"
    if "intracellular" not in st.session_state:
        st.session_state.intracellular = IntracellularState()
    if "intracellular_history" not in st.session_state:
        st.session_state.intracellular_history = [
            st.session_state.intracellular.snapshot()
        ]
    # 连续模拟可能运行数天；界面只保留最近采样点，防止曲线和状态文件无限增长。
    st.session_state.history = st.session_state.history[-MAX_HISTORY_POINTS:]
    st.session_state.intracellular_history = (
        st.session_state.intracellular_history[-MAX_HISTORY_POINTS:]
    )


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
    st.session_state.intracellular = IntracellularState()
    st.session_state.intracellular_history = [
        st.session_state.intracellular.snapshot()
    ]
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
    st.sidebar.radio(
        "模拟模式",
        ["细胞培养", "细胞生命活动"],
        key="app_mode",
        help="两个模式共享同一培养环境和模拟时钟。",
    )
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

    intracellular_mode = st.session_state.get("app_mode") == "细胞生命活动"
    st.subheader("共享模拟时钟与环境操作" if intracellular_mode else "培养操作")
    speed_col, start_col, pause_col = st.columns([2, 1, 1])
    speed_col.selectbox(
        "培养时间倍率",
        list(TIME_MULTIPLIERS),
        key="speed_choice",
        format_func=lambda value: TIME_MULTIPLIERS[value],
        on_change=update_time_multiplier,
    )
    if start_col.button(
        "▶ 开始连续模拟" if intracellular_mode else "▶ 开始连续培养",
        type="primary", width="stretch",
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
        completed = 0
        for _ in range(steps):
            if not cell.alive:
                break
            cell.step(dt_h)
            st.session_state.intracellular.step(cell, dt_h)
            st.session_state.history.append(cell.snapshot())
            st.session_state.intracellular_history.append(
                st.session_state.intracellular.snapshot()
            )
            completed += 1
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


def intracellular_metrics(state: IntracellularState) -> None:
    """显示细胞内部功能指标。"""

    values = [
        ("⚡", "ATP 水平", f"{state.atp_percent:.1f}%"),
        ("◈", "线粒体膜电位", f"{state.mitochondrial_potential_percent:.1f}%"),
        ("⬡", "糖酵解活性", f"{state.glycolysis_percent:.1f}%"),
        ("✹", "ROS", f"{state.ros_percent:.1f}%"),
        ("Ca", "胞质 Ca²⁺", f"{state.cytosolic_calcium_nm:.0f} nM"),
        ("DNA", "DNA 损伤", f"{state.dna_damage_percent:.1f}%"),
        ("ER", "内质网应激", f"{state.er_stress_percent:.1f}%"),
        ("♻", "自噬活性", f"{state.autophagy_percent:.1f}%"),
        ("●", "蛋白质合成", f"{state.protein_synthesis_percent:.1f}%"),
        ("↗", "生长信号", f"{state.growth_signal_percent:.1f}%"),
        ("!", "凋亡信号", f"{state.apoptosis_signal_percent:.1f}%"),
        ("◷", "细胞周期", f"{state.cycle_phase} · {state.cycle_progress_percent:.0f}%"),
    ]
    cards = "".join(
        f'<div class="vc-metric-card"><div class="vc-metric-label">'
        f'{icon} {html.escape(label)}</div><div class="vc-metric-value">'
        f'{html.escape(value)}</div></div>'
        for icon, label, value in values
    )
    st.markdown(f'<div class="vc-metric-grid">{cards}</div>', unsafe_allow_html=True)


def _intracellular_svg_fallback(state: IntracellularState) -> None:
    """图片资源缺失时使用的离线矢量备用视图。"""

    mito = state.mitochondrial_potential_percent
    mito_color = "#35c9b1" if mito >= 65 else "#e8ae54" if mito >= 35 else "#dc6475"
    mito_label = "活跃" if mito >= 65 else "受抑" if mito >= 35 else "低功能"
    er_color = "#54a7d5" if state.er_stress_percent < 40 else "#e2a44d" if state.er_stress_percent < 70 else "#d85d72"
    dna_color = "#7767c9" if state.dna_damage_percent < 25 else "#e2a44d" if state.dna_damage_percent < 60 else "#d85d72"
    ros_color = "#5bbbd0" if state.ros_percent < 30 else "#efad45" if state.ros_percent < 60 else "#e25268"
    apoptosis_color = "#45bfa8" if state.apoptosis_signal_percent < 30 else "#e4a449" if state.apoptosis_signal_percent < 70 else "#db5269"
    membrane_glow = 0.12 + state.apoptosis_signal_percent / 260.0
    ros_positions = (
        (310, 190), (615, 213), (290, 365), (650, 370), (520, 150),
        (396, 405), (700, 295), (230, 275), (575, 410), (360, 130),
    )
    ros_count = max(1, min(len(ros_positions), round(state.ros_percent / 10.0)))
    ros_particles = "".join(
        f'<circle class="ros-particle" cx="{x}" cy="{y}" r="{4 + index % 3}" '
        f'fill="{ros_color}" style="animation-delay:{index * -.23:.2f}s"/>'
        for index, (x, y) in enumerate(ros_positions[:ros_count])
    )
    ribosomes = "".join(
        f'<circle cx="{x}" cy="{y}" r="3.2" fill="#485e91" opacity=".86"/>'
        for x, y in (
            (304, 252), (322, 242), (340, 258), (318, 275), (349, 285),
            (290, 290), (337, 306), (369, 280), (270, 330), (620, 180),
            (655, 330), (535, 425), (240, 220), (690, 250),
        )
    )
    cell_html = f"""
    <style>
      html,body {{margin:0;padding:0;background:transparent;font-family:system-ui,-apple-system,"Segoe UI",sans-serif;}}
      .vc-cell-map {{width:calc(100% - 2px);box-sizing:border-box;margin:0 auto .65rem;padding:.55rem;overflow:hidden;border:1px solid rgba(91,142,162,.32);border-radius:1.1rem;background:linear-gradient(145deg,#f9fdff 0%,#eef8fb 58%,#f6f2ff 100%);box-shadow:0 10px 25px rgba(45,91,112,.1),inset 0 1px 0 #fff;}}
      .vc-cell-map svg {{display:block;width:100%;height:auto;}}
      .vc-cell-caption {{display:flex;justify-content:space-between;gap:.8rem;align-items:center;padding:.15rem .5rem .3rem;color:#4b6672;font-size:.78rem;}}
      .vc-state-ribbon {{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:.45rem;}}
      .vc-state-pill {{padding:.48rem .55rem;border:1px solid #dbe9ee;border-radius:.65rem;background:rgba(255,255,255,.88);color:#45606b;font-size:.7rem;text-align:center;}}
      .vc-state-pill strong {{display:block;color:#173f50;font-size:.86rem;margin-top:.12rem;}}
      @media (max-width:600px) {{.vc-cell-map {{overflow-x:auto;padding:.2rem}} .vc-cell-map svg {{width:680px;max-width:none}} .vc-cell-caption {{flex-direction:column;align-items:flex-start;padding:.35rem .5rem}} .vc-state-ribbon {{grid-template-columns:repeat(2,minmax(0,1fr))}}}}
    </style>
    <div class="vc-cell-map" role="img" aria-label="状态联动的真核细胞结构图"
         data-atp="{state.atp_percent:.1f}" data-ros="{state.ros_percent:.1f}">
      <svg viewBox="0 0 920 560" xmlns="http://www.w3.org/2000/svg" aria-labelledby="cell-title cell-desc">
        <title id="cell-title">真核细胞生命活动仪表盘</title>
        <desc id="cell-desc">展示细胞膜、细胞核、核仁、线粒体、粗面和滑面内质网、高尔基体、溶酶体、核糖体和囊泡，并与当前模拟状态联动。</desc>
        <defs>
          <radialGradient id="cytoplasm" cx="42%" cy="35%" r="72%">
            <stop offset="0" stop-color="#f7fdff"/><stop offset=".55" stop-color="#d9f2f5"/><stop offset="1" stop-color="#bcdde7"/>
          </radialGradient>
          <radialGradient id="nucleus" cx="38%" cy="30%" r="72%">
            <stop offset="0" stop-color="#ebe7ff"/><stop offset=".68" stop-color="#b9afe8"/><stop offset="1" stop-color="#8f82ce"/>
          </radialGradient>
          <linearGradient id="mito" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stop-color="#ecfffb"/><stop offset=".45" stop-color="{mito_color}"/><stop offset="1" stop-color="#477d91"/>
          </linearGradient>
          <linearGradient id="membrane" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stop-color="#6ed3dc"/><stop offset=".5" stop-color="#527fb4"/><stop offset="1" stop-color="#8f74cb"/>
          </linearGradient>
          <filter id="softShadow" x="-30%" y="-30%" width="160%" height="160%">
            <feDropShadow dx="0" dy="7" stdDeviation="8" flood-color="#375b75" flood-opacity=".18"/>
          </filter>
          <filter id="mitoGlow" x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur stdDeviation="5" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
          </filter>
          <style>
            .label {{font:600 15px system-ui,sans-serif;fill:#294c5b}}
            .sub {{font:500 11px system-ui,sans-serif;fill:#69818b}}
            .leader {{fill:none;stroke:#789aa7;stroke-width:1.5;stroke-dasharray:3 3}}
            .node {{fill:#fff;stroke:#6c97a7;stroke-width:1.5}}
            .organelle-title {{font:700 13px system-ui,sans-serif;fill:#233f4c}}
            .ros-particle {{opacity:.75;animation:rosPulse 1.8s ease-in-out infinite;filter:url(#softShadow)}}
            .vesicle {{animation:vesicleDrift 3.4s ease-in-out infinite}}
            @keyframes rosPulse {{50% {{opacity:.28;transform:scale(1.45);transform-origin:center}}}}
            @keyframes vesicleDrift {{50% {{transform:translate(3px,-4px)}}}}
          </style>
        </defs>

        <!-- 标题与状态 -->
        <text x="24" y="30" class="organelle-title" font-size="16">代表性真核细胞 · 实时结构视图</text>
        <rect x="716" y="12" width="180" height="28" rx="14" fill="#ffffff" stroke="#d6e5ea"/>
        <circle cx="733" cy="26" r="5" fill="{apoptosis_color}"/>
        <text x="745" y="30" class="label" font-size="12">细胞周期 {state.cycle_phase} · {state.cycle_progress_percent:.0f}%</text>

        <!-- 细胞膜与细胞质 -->
        <path d="M181 281 C173 153 279 75 437 69 C607 60 753 130 760 277 C766 423 635 493 458 489 C286 486 190 414 181 281Z"
              fill="url(#cytoplasm)" stroke="{apoptosis_color}" stroke-opacity="{membrane_glow:.2f}" stroke-width="15"/>
        <path d="M181 281 C173 153 279 75 437 69 C607 60 753 130 760 277 C766 423 635 493 458 489 C286 486 190 414 181 281Z"
              fill="none" stroke="url(#membrane)" stroke-width="5" filter="url(#softShadow)"/>
        <path d="M193 279 C187 161 287 88 439 82 C599 75 740 139 747 279 C752 411 627 479 458 476 C297 473 201 404 193 279Z"
              fill="none" stroke="#fff" stroke-opacity=".68" stroke-width="2" stroke-dasharray="3 7"/>

        <!-- 细胞核、核仁和染色质 -->
        <g filter="url(#softShadow)">
          <ellipse cx="467" cy="267" rx="122" ry="108" fill="url(#nucleus)" stroke="{dna_color}" stroke-width="4"/>
          <ellipse cx="467" cy="267" rx="112" ry="98" fill="none" stroke="#f8f5ff" stroke-opacity=".68" stroke-width="2" stroke-dasharray="4 6"/>
          <path d="M392 235 C426 203 448 246 476 222 S533 230 548 202 M388 293 C420 272 438 316 474 288 S526 307 545 276 M415 337 C447 308 478 348 515 326"
                fill="none" stroke="{dna_color}" stroke-opacity=".55" stroke-width="3"/>
          <circle cx="481" cy="264" r="33" fill="#7060ae" opacity=".88" stroke="#ede9ff" stroke-width="3"/>
          <circle cx="471" cy="254" r="9" fill="#a99be0" opacity=".72"/>
        </g>

        <!-- 线粒体及嵴 -->
        <g filter="url(#mitoGlow)" opacity="{0.45 + mito / 180.0:.2f}">
          <path d="M231 180 C254 148 322 155 333 185 C343 214 305 239 267 229 C232 220 216 202 231 180Z" fill="url(#mito)" stroke="{mito_color}" stroke-width="4"/>
          <path d="M245 184 C258 169 270 213 284 182 S307 207 321 185" fill="none" stroke="#fff" stroke-opacity=".8" stroke-width="3"/>
          <path d="M584 371 C607 341 672 347 684 378 C695 407 657 432 619 421 C584 412 569 393 584 371Z" fill="url(#mito)" stroke="{mito_color}" stroke-width="4"/>
          <path d="M598 374 C611 359 623 403 637 372 S660 397 674 375" fill="none" stroke="#fff" stroke-opacity=".8" stroke-width="3"/>
        </g>

        <!-- 粗面内质网和核糖体 -->
        <g fill="none" stroke="{er_color}" stroke-width="7" stroke-linecap="round" opacity=".9">
          <path d="M330 226 C292 214 270 232 278 251 C287 269 319 259 345 270"/>
          <path d="M336 282 C302 274 272 290 282 309 C292 327 321 312 351 325"/>
          <path d="M365 344 C334 341 309 353 319 371 C330 389 361 369 387 376"/>
        </g>
        {ribosomes}

        <!-- 滑面内质网 -->
        <g fill="none" stroke="#64c3c7" stroke-width="6" stroke-linecap="round" opacity=".78">
          <path d="M555 182 C584 154 619 163 612 190 C605 216 651 213 656 187"/>
          <path d="M565 205 C591 188 610 223 635 220 C661 217 670 235 650 250"/>
          <path d="M570 230 C597 217 612 249 641 246"/>
        </g>

        <!-- 高尔基体 -->
        <g fill="none" stroke="#9b7dd2" stroke-width="7" stroke-linecap="round" opacity=".9">
          <path d="M572 281 C612 260 665 268 688 290"/>
          <path d="M578 300 C617 282 658 287 678 306"/>
          <path d="M584 319 C618 306 648 309 666 323"/>
          <path d="M593 337 C616 330 637 332 650 340"/>
        </g>

        <!-- 溶酶体、囊泡、自噬体 -->
        <g filter="url(#softShadow)">
          <circle cx="280" cy="385" r="28" fill="#e896b5" fill-opacity=".82" stroke="#a6537b" stroke-width="3"/>
          <circle cx="272" cy="378" r="5" fill="#fff" opacity=".7"/><circle cx="288" cy="392" r="7" fill="#b85f86" opacity=".55"/>
          <circle cx="704" cy="230" r="13" fill="#f6d3ef" stroke="#a974b6" stroke-width="2" class="vesicle"/>
          <circle cx="690" cy="354" r="10" fill="#d7f2ef" stroke="#5aaea8" stroke-width="2" class="vesicle" style="animation-delay:-1s"/>
          <circle cx="233" cy="307" r="9" fill="#d7f2ef" stroke="#5aaea8" stroke-width="2" class="vesicle" style="animation-delay:-2s"/>
          <circle cx="346" cy="419" r="20" fill="none" stroke="#55a990" stroke-width="4" stroke-dasharray="5 3"/>
          <circle cx="346" cy="419" r="10" fill="#93d2bd" opacity=".55"/>
        </g>
        {ros_particles}

        <!-- 左侧标注 -->
        <path class="leader" d="M181 155 L126 116 L34 116"/><circle class="node" cx="181" cy="155" r="4"/>
        <text x="34" y="108" class="label">细胞膜</text><text x="34" y="127" class="sub">选择性屏障 · 信号转导</text>
        <path class="leader" d="M358 217 L132 188 L34 188"/><circle class="node" cx="358" cy="217" r="4"/>
        <text x="34" y="180" class="label">粗面内质网</text><text x="34" y="199" class="sub">折叠蛋白 · 应激 {state.er_stress_percent:.0f}%</text>
        <path class="leader" d="M280 385 L127 392 L34 392"/><circle class="node" cx="280" cy="385" r="4"/>
        <text x="34" y="384" class="label">溶酶体</text><text x="34" y="403" class="sub">降解 · 自噬 {state.autophagy_percent:.0f}%</text>
        <path class="leader" d="M304 252 L140 272 L34 272"/><circle class="node" cx="304" cy="252" r="4"/>
        <text x="34" y="264" class="label">核糖体</text><text x="34" y="283" class="sub">蛋白合成 {state.protein_synthesis_percent:.0f}%</text>

        <!-- 右侧标注 -->
        <path class="leader" d="M545 210 L786 103 L891 103"/><circle class="node" cx="545" cy="210" r="4"/>
        <text x="891" y="95" text-anchor="end" class="label">细胞核与核仁</text><text x="891" y="114" text-anchor="end" class="sub">DNA 损伤 {state.dna_damage_percent:.0f}%</text>
        <path class="leader" d="M620 181 L797 169 L891 169"/><circle class="node" cx="620" cy="181" r="4"/>
        <text x="891" y="161" text-anchor="end" class="label">滑面内质网</text><text x="891" y="180" text-anchor="end" class="sub">脂质代谢 · Ca²⁺ 储存</text>
        <path class="leader" d="M652 300 L797 266 L891 266"/><circle class="node" cx="652" cy="300" r="4"/>
        <text x="891" y="258" text-anchor="end" class="label">高尔基体</text><text x="891" y="277" text-anchor="end" class="sub">修饰 · 分选 · 运输</text>
        <path class="leader" d="M684 378 L800 366 L891 366"/><circle class="node" cx="684" cy="378" r="4"/>
        <text x="891" y="358" text-anchor="end" class="label">线粒体 · {mito_label}</text><text x="891" y="377" text-anchor="end" class="sub">膜电位 {mito:.0f}% · ATP {state.atp_percent:.0f}%</text>
        <path class="leader" d="M690 354 L795 433 L891 433"/><circle class="node" cx="690" cy="354" r="4"/>
        <text x="891" y="425" text-anchor="end" class="label">运输囊泡</text><text x="891" y="444" text-anchor="end" class="sub">胞内货物运输</text>

        <rect x="277" y="510" width="366" height="31" rx="15.5" fill="#fff" stroke="#d8e8ed"/>
        <circle cx="297" cy="525.5" r="5" fill="{ros_color}"/><text x="309" y="530" class="sub">ROS {state.ros_percent:.0f}%</text>
        <circle cx="393" cy="525.5" r="5" fill="{er_color}"/><text x="405" y="530" class="sub">ER 应激 {state.er_stress_percent:.0f}%</text>
        <circle cx="508" cy="525.5" r="5" fill="{dna_color}"/><text x="520" y="530" class="sub">DNA {state.dna_damage_percent:.0f}%</text>
        <circle cx="587" cy="525.5" r="5" fill="{apoptosis_color}"/><text x="599" y="530" class="sub">凋亡</text>
      </svg>
      <div class="vc-cell-caption"><span>颜色从青蓝 → 琥珀 → 红色表示功能受抑或应激升高</span><span>结构位置为示意，不代表真实比例</span></div>
    </div>
    <div class="vc-state-ribbon">
      <div class="vc-state-pill">线粒体膜电位<strong style="color:{mito_color}">{mito:.1f}% · {mito_label}</strong></div>
      <div class="vc-state-pill">活性氧 ROS<strong style="color:{ros_color}">{state.ros_percent:.1f}%</strong></div>
      <div class="vc-state-pill">内质网应激<strong style="color:{er_color}">{state.er_stress_percent:.1f}%</strong></div>
      <div class="vc-state-pill">DNA 损伤<strong style="color:{dna_color}">{state.dna_damage_percent:.1f}%</strong></div>
      <div class="vc-state-pill">凋亡信号<strong style="color:{apoptosis_color}">{state.apoptosis_signal_percent:.1f}%</strong></div>
    </div>
    """
    # st.html 会通过 DOMPurify 移除复杂 SVG；st.iframe 可完整渲染可信的本地矢量图。
    st.iframe(cell_html, height=700, tab_index=-1)


def intracellular_map(state: IntracellularState) -> None:
    """在 3D 生物医学细胞剖面图上叠加实时状态与细胞器标签。"""

    atlas_path = Path(__file__).with_name("assets") / "cell-atlas-v1.png"
    if not atlas_path.exists():
        st.warning("3D 细胞图资源缺失，已切换到离线矢量备用视图。")
        _intracellular_svg_fallback(state)
        return

    mito = state.mitochondrial_potential_percent
    mito_color = "#45e0c1" if mito >= 65 else "#f3bc61" if mito >= 35 else "#ee7181"
    mito_label = "活跃" if mito >= 65 else "受抑" if mito >= 35 else "低功能"
    ros_color = "#58c9da" if state.ros_percent < 30 else "#f3b44f" if state.ros_percent < 60 else "#ee6378"
    er_color = "#5fbcea" if state.er_stress_percent < 40 else "#f0b65a" if state.er_stress_percent < 70 else "#e9667c"
    dna_color = "#aa91ef" if state.dna_damage_percent < 25 else "#f0b65a" if state.dna_damage_percent < 60 else "#e9667c"
    auto_color = "#76d7bd" if state.autophagy_percent < 45 else "#f0b65a"
    apoptosis_color = "#63d8bd" if state.apoptosis_signal_percent < 30 else "#f0b65a" if state.apoptosis_signal_percent < 70 else "#e95672"
    alert_strength = min(1.0, max(
        state.ros_percent / 100.0,
        state.dna_damage_percent / 100.0,
        state.er_stress_percent / 100.0,
        state.apoptosis_signal_percent / 100.0,
    ))
    ros_spots = (
        (24, 22), (56, 17), (83, 35), (72, 54), (42, 71),
        (18, 65), (89, 68), (60, 82), (34, 43), (78, 22),
    )
    ros_count = max(0, min(len(ros_spots), round(state.ros_percent / 10.0)))
    ros_html = "".join(
        f'<i class="ros" style="left:{x}%;top:{y}%;animation-delay:{index * -.2:.1f}s"></i>'
        for index, (x, y) in enumerate(ros_spots[:ros_count])
    )
    mito_glows = "".join(
        f'<i class="mito-glow m{index}"></i>' for index in range(1, 8)
    )
    cell_html = f"""
    <style>
      html,body {{margin:0;padding:0;background:transparent;font-family:system-ui,-apple-system,"Segoe UI",sans-serif;color:#eaf8ff}}
      * {{box-sizing:border-box}}
      .atlas-card {{width:100%;padding:10px;border:1px solid #cce1ea;border-radius:18px;background:linear-gradient(145deg,#f8fdff,#eef7fb 58%,#f6f1ff);box-shadow:0 12px 30px rgba(34,75,98,.13)}}
      .cell-stage {{position:relative;width:100%;aspect-ratio:3/2;overflow:hidden;border-radius:14px;background:#103e4c;box-shadow:inset 0 0 42px rgba(233,86,114,{alert_strength * .45:.2f})}}
      .cell-stage>img {{display:block;width:100%;height:100%;object-fit:cover}}
      .cell-stage::after {{content:"";position:absolute;inset:0;pointer-events:none;border:2px solid {apoptosis_color};border-radius:14px;opacity:{.18 + alert_strength * .62:.2f};box-shadow:inset 0 0 {12 + alert_strength * 28:.0f}px {apoptosis_color}}}
      .tag {{position:absolute;z-index:4;min-width:88px;padding:5px 8px;border:1px solid rgba(255,255,255,.45);border-radius:8px;background:rgba(7,31,48,.74);box-shadow:0 4px 13px rgba(0,18,32,.28);backdrop-filter:blur(5px);font-size:clamp(9px,1.15vw,13px);line-height:1.22;text-shadow:0 1px 2px #001}}
      .tag b {{display:block;font-size:1.05em;color:#fff}}
      .tag small {{display:block;margin-top:2px;color:var(--signal,#bfeef5);white-space:nowrap}}
      .tag::after {{content:"";position:absolute;width:28px;border-top:1px solid rgba(255,255,255,.72);transform-origin:left center}}
      .nucleus {{left:35%;top:38%;--signal:{dna_color}}} .nucleus::after {{left:100%;top:50%;transform:rotate(-18deg)}}
      .mitochondria {{right:4%;top:15%;--signal:{mito_color}}} .mitochondria::after {{right:100%;top:50%;transform:rotate(165deg)}}
      .rer {{left:4%;top:20%;--signal:{er_color}}} .rer::after {{left:100%;top:50%;transform:rotate(18deg)}}
      .ser {{right:4%;top:39%;--signal:{er_color}}} .ser::after {{right:100%;top:50%;transform:rotate(165deg)}}
      .golgi {{right:5%;bottom:16%;--signal:#f1a7cf}} .golgi::after {{right:100%;top:50%;transform:rotate(185deg)}}
      .lysosome {{left:5%;bottom:16%;--signal:{auto_color}}} .lysosome::after {{left:100%;top:50%;transform:rotate(-12deg)}}
      .cycle {{position:absolute;z-index:5;right:12px;top:12px;padding:6px 10px;border-radius:999px;background:rgba(245,242,255,.9);color:#503c8d;font-size:clamp(9px,1.2vw,13px);font-weight:750;box-shadow:0 4px 16px rgba(28,17,80,.2)}}
      .mito-glow {{position:absolute;z-index:2;width:12%;height:8%;border-radius:50%;border:2px solid {mito_color};opacity:{.14 + mito / 180:.2f};filter:blur(3px);box-shadow:0 0 18px {mito_color};pointer-events:none}}
      .m1{{left:24%;top:13%}} .m2{{left:51%;top:10%}} .m3{{left:72%;top:21%}} .m4{{left:83%;top:39%}} .m5{{left:68%;top:70%}} .m6{{left:43%;top:78%}} .m7{{left:16%;top:64%}}
      .ros {{position:absolute;z-index:3;width:8px;height:8px;border-radius:50%;background:{ros_color};box-shadow:0 0 12px 4px {ros_color};opacity:.72;animation:rosPulse 1.8s ease-in-out infinite}}
      @keyframes rosPulse {{50%{{opacity:.25;transform:scale(1.65)}}}}
      .status-grid {{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:6px;margin-top:8px}}
      .status {{padding:7px 5px;border:1px solid #d9e8ee;border-radius:9px;background:#fff;color:#607681;text-align:center;font-size:11px}}
      .status strong {{display:block;margin-top:2px;font-size:13px;color:var(--signal,#274d5d)}}
      .note {{display:flex;justify-content:space-between;gap:8px;padding:7px 5px 0;color:#667e89;font-size:11px}}
      @media(max-width:620px) {{.atlas-card{{padding:5px;border-radius:12px}} .tag{{min-width:64px;padding:3px 5px}} .tag::after{{width:14px}} .status-grid{{grid-template-columns:repeat(3,minmax(0,1fr))}} .note{{flex-direction:column}}}}
    </style>
    <div class="atlas-card" data-atp="{state.atp_percent:.1f}" data-ros="{state.ros_percent:.1f}">
      <div class="cell-stage" role="img" aria-label="3D 真核细胞横截面及实时细胞器状态">
        <img src="/app/static/cell-atlas-v1.png" alt="无文字的 3D 真核细胞横截面：含细胞膜、细胞核、线粒体、内质网、高尔基体、溶酶体、囊泡和核糖体">
        {mito_glows}{ros_html}
        <div class="cycle">细胞周期 {state.cycle_phase} · {state.cycle_progress_percent:.0f}%</div>
        <div class="tag nucleus"><b>细胞核 · 核仁</b><small>DNA 损伤 {state.dna_damage_percent:.1f}%</small></div>
        <div class="tag mitochondria"><b>线粒体</b><small>膜电位 {mito:.1f}% · {mito_label}</small></div>
        <div class="tag rer"><b>粗面内质网</b><small>应激 {state.er_stress_percent:.1f}%</small></div>
        <div class="tag ser"><b>滑面内质网</b><small>Ca²⁺ {state.cytosolic_calcium_nm:.0f} nM</small></div>
        <div class="tag golgi"><b>高尔基体</b><small>加工 · 分选 · 囊泡运输</small></div>
        <div class="tag lysosome"><b>溶酶体</b><small>自噬 {state.autophagy_percent:.1f}%</small></div>
      </div>
      <div class="status-grid">
        <div class="status">ATP<strong style="--signal:{mito_color}">{state.atp_percent:.1f}%</strong></div>
        <div class="status">ROS<strong style="--signal:{ros_color}">{state.ros_percent:.1f}%</strong></div>
        <div class="status">内质网应激<strong style="--signal:{er_color}">{state.er_stress_percent:.1f}%</strong></div>
        <div class="status">DNA 损伤<strong style="--signal:{dna_color}">{state.dna_damage_percent:.1f}%</strong></div>
        <div class="status">自噬<strong style="--signal:{auto_color}">{state.autophagy_percent:.1f}%</strong></div>
        <div class="status">凋亡信号<strong style="--signal:{apoptosis_color}">{state.apoptosis_signal_percent:.1f}%</strong></div>
      </div>
      <div class="note"><span>状态色：青蓝稳定 · 琥珀预警 · 珊瑚红高应激</span><span>3D 结构位置为科研可视化示意</span></div>
    </div>
    """
    st.iframe(cell_html, height=720, tab_index=-1)


def intracellular_actions(state: IntracellularState) -> None:
    """提供用于观察细胞响应链的最小干预。"""

    st.markdown("##### 细胞刺激实验")
    stress_col, recovery_col = st.columns(2)
    if stress_col.button("⚡ 施加氧化刺激", width="stretch"):
        state.apply_oxidative_stress(20.0)
        st.session_state.intracellular_history.append(state.snapshot())
        st.session_state.run_message = "已施加氧化刺激：ROS 与 DNA 损伤上升"
        st.toast("氧化刺激已施加，继续推进时间可观察下游响应", icon="⚡")
        save_runtime_state()
    if recovery_col.button("🛡️ 增强抗氧化响应", width="stretch"):
        state.apply_antioxidant_response(15.0)
        st.session_state.intracellular_history.append(state.snapshot())
        st.session_state.run_message = "抗氧化响应增强：ROS 降低"
        st.toast("ROS 清除增强；DNA 损伤仍需随时间修复", icon="🛡️")
        save_runtime_state()
    st.caption("环境仍由左侧实验设计和培养操作控制；氧、葡萄糖、pH、药物会传递到细胞内部模型。")


def plot_intracellular_history(history) -> None:
    """绘制细胞内部能量、应激与命运变化。"""

    data = pd.DataFrame(history)
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8))
    for column, label in (
        ("ATP_percent", "ATP"),
        ("mitochondrial_potential_percent", "Mito potential"),
        ("glycolysis_percent", "Glycolysis"),
    ):
        axes[0].plot(data["time_h"], data[column], label=label)
    for column, label in (
        ("ROS_percent", "ROS"),
        ("DNA_damage_percent", "DNA damage"),
        ("ER_stress_percent", "ER stress"),
        ("apoptosis_signal_percent", "Apoptosis"),
    ):
        axes[1].plot(data["time_h"], data[column], label=label)
    axes[0].set_title("Energy metabolism")
    axes[1].set_title("Stress and cell fate")
    for axis in axes:
        axis.set_xlabel("Time (h)")
        axis.set_ylabel("Relative index (%)")
        axis.set_ylim(0, 105)
        axis.grid(alpha=0.2)
        axis.legend(fontsize=8)
    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)


@st.fragment(run_every=1.0)
def intracellular_live_panel() -> None:
    """随共享时钟刷新细胞器功能状态。"""

    advance_realtime()
    state = st.session_state.intracellular
    status_text, status_level = intracellular_status(state)
    getattr(st, status_level)(
        f"当前状态：{html.escape(status_text)}｜细胞周期 {state.cycle_phase}"
    )
    intracellular_metrics(state)
    intracellular_map(state)
    intracellular_actions(state)


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
st.caption("细胞培养与细胞生命活动模拟器 · V1.0-alpha.5 · 双模式、共享环境与时间")
st.error("研究原型：可用于假设探索和实验设计辅助；尚未经过实验验证，不能替代湿实验。")

pending_toast = st.session_state.pop("pending_toast", None)
if pending_toast:
    message, icon = pending_toast
    st.toast(message, icon=icon)

if st.session_state.app_mode == "细胞培养":
    show_profile(cell)
    live_status_panel()
    controls(cell)
    st.subheader("培养动力学曲线")
    plot_history(st.session_state.history)
    data = pd.DataFrame(st.session_state.history)
    st.subheader("实验数据与导出")
    export_name = f"{cell.profile_key}_culture_{cell.time_h:.1f}h.csv"
else:
    st.markdown(
        '<div class="vc-mode-note"><strong>代表性单细胞视角</strong> · '
        '培养环境会影响膜运输、能量代谢、细胞器应激、细胞周期和凋亡信号；'
        '两个模式使用同一个时钟。</div>',
        unsafe_allow_html=True,
    )
    intracellular_live_panel()
    controls(cell)
    st.subheader("细胞内部状态曲线")
    plot_intracellular_history(st.session_state.intracellular_history)
    data = pd.DataFrame(st.session_state.intracellular_history)
    st.subheader("细胞内部数据与导出")
    export_name = f"{cell.profile_key}_intracellular_{cell.time_h:.1f}h.csv"

st.download_button(
    "下载带单位的 CSV",
    data=data.to_csv(index=False).encode("utf-8-sig"),
    file_name=export_name,
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
