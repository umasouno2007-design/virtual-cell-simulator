"""虚拟细胞能量代谢模拟器的 Streamlit 用户界面。"""

import html

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from simulation import PRESETS, cell_status, new_simulation, run_steps


st.set_page_config(page_title="虚拟细胞能量代谢模拟器", page_icon="🧫", layout="wide")


def initialize_state() -> None:
    """只在首次加载页面时建立 session_state。"""
    if "cell" not in st.session_state or "history" not in st.session_state:
        st.session_state.cell, st.session_state.history = new_simulation()
    if "run_mode" not in st.session_state:
        st.session_state.run_mode = "已暂停"
    if "active_preset" not in st.session_state:
        st.session_state.active_preset = "正常培养环境"


def parameter_panel() -> None:
    """显示实验预设与代谢参数，并把修改写入当前细胞。"""
    st.sidebar.header("实验设置")
    preset_name = st.sidebar.selectbox("实验预设", list(PRESETS), key="preset_choice")
    st.sidebar.caption(PRESETS[preset_name]["description"])

    if st.sidebar.button("应用预设并重新开始", type="primary", width="stretch"):
        st.session_state.cell, st.session_state.history = new_simulation(preset_name)
        st.session_state.active_preset = preset_name
        st.session_state.run_mode = f"已应用预设：{preset_name}"
        for key in PARAMETER_WIDGET_KEYS:
            st.session_state.pop(key, None)
        st.rerun()

    cell = st.session_state.cell
    params = cell.parameters
    st.sidebar.subheader("模型参数")
    st.sidebar.caption("修改后从下一步开始生效。数值均为教学用相对参数。")
    params.maintenance_base = st.sidebar.slider(
        "基础 ATP 消耗", 2.0, 10.0, params.maintenance_base, 0.5, key="param_maintenance"
    )
    params.aerobic_yield = st.sidebar.slider(
        "有氧 ATP 产率", 2.0, 4.5, params.aerobic_yield, 0.1, key="param_aerobic"
    )
    params.anaerobic_yield = st.sidebar.slider(
        "无氧 ATP 产率", 0.5, 2.0, params.anaerobic_yield, 0.05, key="param_anaerobic"
    )
    params.hypoxia_threshold = st.sidebar.slider(
        "缺氧阈值", 10.0, 40.0, params.hypoxia_threshold, 1.0, key="param_hypoxia"
    )
    params.lactate_rate = st.sidebar.slider(
        "乳酸生成速率", 0.5, 3.0, params.lactate_rate, 0.1, key="param_lactate"
    )
    st.sidebar.subheader("每次补充量")
    st.sidebar.slider("葡萄糖补充量", 5.0, 40.0, 20.0, 5.0, key="glucose_dose")
    st.sidebar.slider("氧气补充量", 5.0, 50.0, 25.0, 5.0, key="oxygen_dose")
    st.sidebar.subheader("环境干预量")
    st.sidebar.slider("每次 pH 调节", 0.05, 0.50, 0.10, 0.05, key="ph_step")
    st.sidebar.slider("每次毒素调节", 5.0, 30.0, 10.0, 5.0, key="toxin_dose")
    st.sidebar.slider("每次渗透压调节", 5.0, 40.0, 15.0, 5.0, key="osmolarity_step")


def draw_cell(cell) -> None:
    """用 HTML/CSS 绘制教学示意图；图形大小不代表真实比例。"""
    mito_count = min(cell.mitochondria, 12)
    mitochondria = "".join(
        f'<span class="mito m{i}">ϟ</span>' for i in range(mito_count)
    )
    opacity = max(0.28, cell.health / 100)
    st.markdown(
        f"""
        <style>
        .cell-wrap {{height: 350px; display:flex; align-items:center; justify-content:center;}}
        .cell {{position:relative; width:300px; height:300px; border-radius:50%;
          border:8px solid #4d9f78; background:rgba(141,224,181,{opacity:.2f});
          box-shadow:inset 0 0 32px #75c99b;}}
        .nucleus {{position:absolute; width:100px; height:100px; left:92px; top:92px;
          border-radius:50%; background:#8e79c6; border:6px solid #62508f;
          display:flex; align-items:center; justify-content:center; color:white; font-weight:700;}}
        .mito {{position:absolute; width:40px; height:22px; border-radius:50%;
          background:#f1a45b; border:3px solid #c66a2b; color:#71390e;
          display:flex; align-items:center; justify-content:center; font-weight:800;}}
        .m0{{left:45px;top:52px}} .m1{{left:195px;top:48px}} .m2{{left:30px;top:140px}}
        .m3{{left:220px;top:140px}} .m4{{left:70px;top:225px}} .m5{{left:180px;top:230px}}
        .m6{{left:105px;top:25px}} .m7{{left:150px;top:185px}} .m8{{left:110px;top:255px}}
        .m9{{left:235px;top:90px}} .m10{{left:35px;top:195px}} .m11{{left:180px;top:92px}}
        </style>
        <div class="cell-wrap"><div class="cell"><div class="nucleus">细胞核</div>{mitochondria}</div></div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("教学示意图：橙色符号代表线粒体；透明度随健康度变化。")


def show_metric(label: str, value: float, maximum: float = 100.0, suffix: str = "") -> None:
    """显示数值和安全范围内的进度条。"""
    st.metric(label, f"{value:.1f}{suffix}")
    st.progress(max(0.0, min(1.0, value / maximum)))


def plot_history(history) -> None:
    """绘制资源、ATP、健康度和乳酸的历史曲线。"""
    data = pd.DataFrame(history)
    fig, ax = plt.subplots(figsize=(10, 4.8))
    colors = {
        "atp": "#7b61ff",
        "glucose": "#e6a23c",
        "oxygen": "#409eff",
        "health": "#2da66d",
        "lactate": "#e45555",
    }
    labels = {
        "atp": "ATP",
        "glucose": "Glucose",
        "oxygen": "Oxygen",
        "health": "Health",
        "lactate": "Lactate",
    }
    for column in colors:
        ax.plot(data["time"], data[column], label=labels[column], color=colors[column], linewidth=2)
    # 使用英文坐标文字，避免某些新安装的系统缺少中文绘图字体。
    ax.set(xlabel="Simulation time", ylabel="Relative units", ylim=(0, 105))
    ax.grid(alpha=0.2)
    ax.legend(ncol=5, loc="upper center")
    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)


def plot_environment_history(history) -> None:
    """分别绘制 pH、毒素、渗透压和细胞水分状态。"""
    data = pd.DataFrame(history)
    fig, axes = plt.subplots(2, 2, figsize=(10, 6.5), sharex=True)
    charts = [
        ("ph", "pH", "#8e79c6", (6.0, 8.5)),
        ("toxin", "Toxin", "#d15b63", (0, 105)),
        ("osmolarity", "Osmolarity", "#3f88c5", (195, 405)),
        ("water_balance", "Cell water", "#36a67a", (0, 105)),
    ]
    for ax, (column, label, color, limits) in zip(axes.flat, charts):
        ax.plot(data["time"], data[column], color=color, linewidth=2)
        ax.set(title=label, ylim=limits)
        ax.grid(alpha=0.2)
    axes[1, 0].set_xlabel("Simulation time")
    axes[1, 1].set_xlabel("Simulation time")
    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)


initialize_state()
PARAMETER_WIDGET_KEYS = [
    "param_maintenance",
    "param_aerobic",
    "param_anaerobic",
    "param_hypoxia",
    "param_lactate",
]
parameter_panel()
cell = st.session_state.cell

st.title("虚拟细胞能量代谢模拟器")
st.caption("V0.3 · pH、毒素、渗透压与细胞水分（教学简化模型）")

status_text, status_level = cell_status(cell)
message = f"当前状态：{html.escape(status_text)}　｜　{st.session_state.run_mode}"
getattr(st, status_level)(message)

st.subheader("实验控制台")
resource_cols = st.columns(4)
if resource_cols[0].button("加入葡萄糖", width="stretch", disabled=not cell.alive):
    cell.add_glucose(st.session_state.glucose_dose)
if resource_cols[1].button("移除葡萄糖", width="stretch", disabled=not cell.alive):
    cell.remove_glucose(st.session_state.glucose_dose)
if resource_cols[2].button("补充氧气", width="stretch", disabled=not cell.alive):
    cell.add_oxygen(st.session_state.oxygen_dose)
if resource_cols[3].button("减少氧气", width="stretch", disabled=not cell.alive):
    cell.remove_oxygen(st.session_state.oxygen_dose)

if st.button("增加线粒体", width="stretch", disabled=not cell.alive):
    cell.add_mitochondrion()

with st.expander("环境干预：pH、药物或毒素、渗透压与水分", expanded=True):
    env_cols_1 = st.columns(3)
    if env_cols_1[0].button("降低 pH", width="stretch", disabled=not cell.alive):
        cell.lower_ph(st.session_state.ph_step)
    if env_cols_1[1].button("升高 pH", width="stretch", disabled=not cell.alive):
        cell.raise_ph(st.session_state.ph_step)
    if env_cols_1[2].button("加入毒素", width="stretch", disabled=not cell.alive):
        cell.add_toxin(st.session_state.toxin_dose)

    env_cols_2 = st.columns(3)
    if env_cols_2[0].button("清除毒素", width="stretch", disabled=not cell.alive):
        cell.detoxify(st.session_state.toxin_dose)
    if env_cols_2[1].button("加水稀释", width="stretch", disabled=not cell.alive):
        cell.add_water(st.session_state.osmolarity_step)
    if env_cols_2[2].button("增加溶质", width="stretch", disabled=not cell.alive):
        cell.add_solute(st.session_state.osmolarity_step)

control_cols = st.columns(5)
if control_cols[0].button("运行一步", type="primary", width="stretch", disabled=not cell.alive):
    run_steps(cell, st.session_state.history, 1)
    st.session_state.run_mode = "单步完成"

batch_steps = control_cols[1].selectbox("连续步数", [5, 10, 20, 50, 100], index=1)
if control_cols[2].button("连续运行", type="primary", width="stretch", disabled=not cell.alive):
    completed = run_steps(cell, st.session_state.history, batch_steps)
    st.session_state.run_mode = f"连续运行完成（{completed} 步）"
if control_cols[3].button("暂停", width="stretch"):
    st.session_state.run_mode = "已暂停"

if control_cols[4].button("重置模拟", width="stretch"):
    st.session_state.cell, st.session_state.history = new_simulation(
        st.session_state.active_preset
    )
    for key in PARAMETER_WIDGET_KEYS:
        st.session_state.pop(key, None)
    st.session_state.run_mode = "已重置"
    st.rerun()

left, right = st.columns([1.05, 1.4])
with left:
    st.subheader("虚拟细胞")
    draw_cell(cell)
with right:
    st.subheader("实时数据")
    metric_cols = st.columns(3)
    with metric_cols[0]:
        show_metric("葡萄糖", cell.glucose)
        show_metric("健康度", cell.health)
    with metric_cols[1]:
        show_metric("氧气", cell.oxygen)
        show_metric("乳酸", cell.lactate)
    with metric_cols[2]:
        show_metric("ATP", cell.atp)
        st.metric("线粒体数量", f"{cell.mitochondria} / 12")
        st.progress(cell.mitochondria / 12)
        st.metric("模拟时间", cell.time)

    st.subheader("环境状态")
    environment_cols = st.columns(4)
    with environment_cols[0]:
        st.metric("pH", f"{cell.ph:.2f}")
    with environment_cols[1]:
        show_metric("毒素", cell.toxin)
    with environment_cols[2]:
        st.metric("渗透压", f"{cell.osmolarity:.0f}", help="教学相对单位，300 附近视为等渗")
        st.progress(max(0.0, min(1.0, (cell.osmolarity - 200.0) / 200.0)))
    with environment_cols[3]:
        show_metric("细胞水分", cell.water_balance)

st.subheader("历史曲线")
plot_history(st.session_state.history)
plot_environment_history(st.session_state.history)

st.subheader("实验数据")
history_data = pd.DataFrame(st.session_state.history)
download_col, info_col = st.columns([1, 2])
with download_col:
    st.download_button(
        "下载 CSV 数据",
        data=history_data.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"virtual_cell_history_t{cell.time}.csv",
        mime="text/csv",
        width="stretch",
    )
with info_col:
    st.caption(
        f"当前预设：{st.session_state.active_preset}｜共 {len(history_data)} 个数据点。"
        "CSV 可用 Excel、WPS 或其他表格软件打开。"
    )
with st.expander("查看原始数据表"):
    st.dataframe(history_data, width="stretch", hide_index=True)

with st.expander("这个模型如何工作？"):
    st.markdown(
        """
        - 氧气充足时，葡萄糖和氧气共同支持高效率 ATP 生成。
        - 氧气较低时，细胞切换到低效率无氧代谢，乳酸增加。
        - ATP 太低或乳酸太高会降低健康度；条件良好时健康度缓慢恢复。
        - 线粒体提高有氧代谢容量，但数量有上限，且会增加少量维护消耗。
        - 左侧实验设置可以改变未来步骤使用的参数；应用预设会重新开始实验。

        以上数值与反应速率均为**教学简化**，用于观察因果关系，不能用于科研或医疗判断。
        """
    )
