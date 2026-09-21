"""文献驱动的虚拟细胞培养模拟器 Streamlit 界面。"""

import html

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from profiles import CELL_PROFILES
from simulation import PRESETS, cell_status, new_simulation, run_steps


st.set_page_config(page_title="虚拟细胞培养与代谢模拟器", page_icon="🧫", layout="wide")


def initialize_state() -> None:
    """初始化 Streamlit 会话。"""

    if "profile_key" not in st.session_state:
        st.session_state.profile_key = "hela"
    if "preset_name" not in st.session_state:
        st.session_state.preset_name = "标准培养"
    if "cell" not in st.session_state or "history" not in st.session_state:
        st.session_state.cell, st.session_state.history = new_simulation()
    if "run_message" not in st.session_state:
        st.session_state.run_message = "尚未运行"


def reset_simulation(profile_key: str, preset_name: str, volume: float, area: float) -> None:
    """按当前设置创建新的培养模拟。"""

    st.session_state.cell, st.session_state.history = new_simulation(
        profile_key, preset_name, volume, area
    )
    st.session_state.profile_key = profile_key
    st.session_state.preset_name = preset_name
    st.session_state.run_message = "已创建新实验"


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
    col1, col2, col3, col4 = st.columns(4)
    dt_h = col1.selectbox("每步时长（h）", [0.25, 0.5, 1.0, 2.0, 4.0], index=2)
    steps = col2.selectbox("运行步数", [1, 6, 12, 24, 48, 72], index=0)
    if col3.button("运行", type="primary", width="stretch", disabled=not cell.alive):
        completed = run_steps(cell, st.session_state.history, steps, dt_h)
        st.session_state.run_message = f"已运行 {completed} 步，共 {completed * dt_h:g} h"
        st.rerun()
    if col4.button("全量换液", width="stretch", disabled=not cell.alive):
        cell.exchange_medium(1.0)
        st.session_state.history.append(cell.snapshot())
        st.session_state.run_message = "已全量换液"
        st.rerun()

    with st.expander("环境与药物设置", expanded=True):
        a, b, c, d = st.columns(4)
        cell.temperature_c = a.number_input("温度（°C）", 30.0, 42.0, cell.temperature_c, 0.1)
        cell.co2_percent = b.number_input("CO₂（%）", 0.0, 20.0, cell.co2_percent, 0.5)
        cell.oxygen_setpoint_percent = c.number_input(
            "氧设定值（%）", 0.1, 21.0, cell.oxygen_setpoint_percent, 0.5
        )
        cell.osmolality_mosm_kg = d.number_input(
            "渗透压（mOsm/kg）", 200.0, 450.0, cell.osmolality_mosm_kg, 5.0
        )
        e, f, g = st.columns(3)
        cell.ph = e.number_input("当前 pH", 6.2, 8.0, cell.ph, 0.05)
        dose = f.number_input("设置药物浓度（µM）", 0.0, 10000.0, cell.drug_um, 0.5)
        if g.button("应用药物浓度", width="stretch"):
            cell.add_drug(dose)
            st.session_state.history.append(cell.snapshot())
            st.session_state.run_message = f"药物浓度设为 {dose:g} µM"
            st.rerun()


def metrics(cell) -> None:
    """显示实验常用的状态指标。"""

    st.subheader("实时培养状态")
    rows = [st.columns(6), st.columns(6)]
    values = [
        ("时间", f"{cell.time_h:.1f} h"),
        ("活细胞数", f"{cell.viable_cells:,.0f}"),
        ("存活率", f"{cell.viability_percent:.1f}%"),
        ("汇合度", f"{cell.confluence_percent:.1f}%"),
        ("能量指数", f"{cell.energy_index:.1f}"),
        ("葡萄糖", f"{cell.glucose_mm:.3f} mM"),
        ("谷氨酰胺", f"{cell.glutamine_mm:.3f} mM"),
        ("乳酸", f"{cell.lactate_mm:.3f} mM"),
        ("溶氧", f"{cell.oxygen_percent:.2f}%"),
        ("pH", f"{cell.ph:.2f}"),
        ("药物", f"{cell.drug_um:.3f} µM"),
        ("渗透压", f"{cell.osmolality_mosm_kg:.0f} mOsm/kg"),
    ]
    for column, (label, value) in zip(rows[0] + rows[1], values):
        column.metric(label, value)


def plot_history(history) -> None:
    """绘制细胞数量、代谢物和环境条件曲线。"""

    data = pd.DataFrame(history)
    fig, axes = plt.subplots(2, 2, figsize=(11, 7))
    axes[0, 0].plot(data["time_h"], data["viable_cells"], label="Viable cells")
    axes[0, 0].plot(data["time_h"], data["dead_cells"], label="Dead cells")
    axes[0, 0].set_ylabel("Cell count")
    axes[0, 0].legend()
    axes[0, 1].plot(data["time_h"], data["glucose_mM"], label="Glucose")
    axes[0, 1].plot(data["time_h"], data["lactate_mM"], label="Lactate")
    axes[0, 1].set_ylabel("mM")
    axes[0, 1].legend()
    axes[1, 0].plot(data["time_h"], data["viability_percent"], label="Viability")
    axes[1, 0].plot(data["time_h"], data["confluence_percent"], label="Confluence")
    axes[1, 0].set_ylabel("Percent")
    axes[1, 0].legend()
    axes[1, 1].plot(data["time_h"], data["pH"], label="pH")
    axes[1, 1].plot(data["time_h"], data["oxygen_percent"], label="Oxygen %")
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


initialize_state()
sidebar()
cell = st.session_state.cell

st.title("虚拟细胞培养与代谢模拟器")
st.caption("V1.0-alpha · 文献驱动、真实单位、可校准参数与多细胞系")
st.error("研究原型：可用于假设探索和实验设计辅助；尚未经过实验验证，不能替代湿实验。")

status_text, status_level = cell_status(cell)
getattr(st, status_level)(
    f"当前状态：{html.escape(status_text)}｜{st.session_state.run_message}"
)

left, right = st.columns([1, 1.25])
with left:
    show_profile(cell)
with right:
    metrics(cell)

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
