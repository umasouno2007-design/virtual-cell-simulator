# e-cell · Virtual Cell Simulator

**面向贴壁细胞培养条件探索的、文献驱动的经验动力学研究原型。**

当前阶段：用于教学、实验设计讨论和模型假设检查；尚未完成独立实验验证。它不是数字孪生、临床工具、湿实验替代品或细胞器定量测量系统。

| 细胞培养工作流 | 细胞生命活动模块 |
| --- | --- |
| ![细胞培养模式](assets/screenshots/culture-mode.png) | ![细胞生命活动模式](assets/screenshots/cell-life-mode.png) |
| 配置培养条件、推进模拟、对齐实测 CSV 与导出。 | 代表性细胞的相对状态与机制探索视图。 |

**Online demo：** 待部署。仓库当前没有可核验的公开 Demo 地址。

## 30 秒启动 / Quick start

```bash
git clone https://github.com/umasouno2007-design/virtual-cell-simulator.git
cd virtual-cell-simulator
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# macOS / Linux：source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

浏览器通常访问 <http://localhost:8501>；如端口被占用，请使用终端显示的地址。

## 研究问题与适用范围

e-cell 用统一界面组织贴壁细胞培养的初始条件、环境压力、群体生长/死亡、葡萄糖/谷氨酰胺/乳酸/氧/pH 趋势，以及与带来源时间序列的透明对齐。当前预设为 A549、HeLa、HEK-293；预设不等于任何批次、传代数或实验室条件的验证。

## 核心工作流

1. 配置细胞系、接种量、体积、面积和培养环境。
2. 推进经验动力学模拟，记录补料、换液、氧和药物等事件。
3. 导入实测 CSV，查看数据质量、模拟—观测对齐、残差、MAE 与 RMSE。
4. 使用 `growth_scale` 与 `uptake_scale` 的透明网格搜索作参数初值探索；结果不构成统计推断。
5. 导出结果、事件、质量报告与场景 JSON；场景文件仅记录模拟假设。

## 模型结构

- `cell.py`：群体平均增殖/死亡、简化物料衡算、氧传递与 pH 缓冲近似。
- `simulation.py`：可复现的培养场景和推进控制。
- `experiment_data.py`、`calibration.py`：CSV 标准化、时间对齐、残差与两参数透明粗校准。
- `intracellular.py`：单个代表性细胞的相对状态模型；权重、阈值与时间常数待校准。
- `cell_communication.py`：可选的代表性子群机制探索层，默认不改变主培养动力学。

证据等级：A 为直接来源支持；B 为方向有依据、数值待校准；C 为教学/交互规则。完整条目见 [evidence.py](evidence.py)、[MECHANISTIC_EVIDENCE_AUDIT.md](MECHANISTIC_EVIDENCE_AUDIT.md) 与 [MODEL_CARD.md](MODEL_CARD.md)。

## 输入、输出与单位

输入包括初始活细胞数（cells）、体积（mL）、面积（cm²）、葡萄糖/谷氨酰胺/乳酸（mM）、培养环境氧设定值（%）、CO₂（%）、pH、温度（°C）、渗透压（mOsm/kg）、药物（µM）和模拟时长（h）。

输出包括活/死细胞数、存活率、汇合度、环境趋势、事件与模型状态。培养环境氧设定值经单室模型形成“局部氧可用性代理”，不等同于培养箱头空间氧、实测溶氧或组织生理氧。

## 数据导入、质量检查与透明校准

导入后，系统检查时间顺序、重复点、缺失/负值、关键列、单位和留出点可行性。通过只表示格式与最低建模条件可用，不是实验质量认证。详细列格式、单位与隐私边界见 [data/README.md](data/README.md)。

粗校准仅运行 `growth_scale × uptake_scale` 的透明网格搜索，并报告训练/留出误差、搜索边界与警告。搜索边界最优、起点不一致、时间点不足或系统残差时，不能把结果解释为可靠校准。场景格式见 [SCENARIO_FORMAT.md](SCENARIO_FORMAT.md)。

## 细胞生命活动模块的解释边界

该模块是**单个代表性细胞的相对状态模型**。ATP、线粒体膜电位、ROS、DNA 损伤、ER 应激、自噬、促凋亡压力和周期均为无量纲相对指数，不是 ATP 浓度、膜电位 mV、ROS 物种、DNA 损伤灶、自噬通量、凋亡细胞比例或真实周期分布。

ROS 不能被一概视为损伤，ER 应激/UPR 与自噬可具有适应性或损伤性结果；模型不把低氧直接编码为 ROS 必然单调上升。细胞通信视图是教学性代表性子群近似，不是细胞因子浓度、受体占有率、空间组学或通信预测。详细边界见 [CELL_COMMUNICATION_MODEL.md](CELL_COMMUNICATION_MODEL.md)。

## 可复现验证案例

`data/a549_teaching_synthetic.csv` 是**教学合成数据**，并非真实实验数据或独立验证数据。它用于复跑“训练点粗校准—留出点评估—图形与指标导出”的软件流程，不能证明 A549 模型的生物学有效性。

```bash
python scripts/validate_a549_teaching_case.py
```

输出位于 `assets/validation/a549_teaching_case/`。案例的搜索边界结果应被视为需要更多参数化或真实数据的提示，而不是准确性证明。

## 模型局限与禁止用途

模型不是全基因组代谢网络，也未显式表示批次、传代、污染、实际氧传递、细胞异质性、完整 UPR 分支、药物特异性机制或空间微环境。禁止用于临床决策、患者风险、治疗预测、GxP/GLP 审计、监管结论或替代实验测量。

## 开发、测试、引用与许可证

```bash
python -m unittest discover -s tests -p "test_*.py"
python scripts/smoke_check.py
```

- 部署前检查：[DEPLOYMENT.md](DEPLOYMENT.md)
- 模型版本、适用范围和失败模式：[MODEL_CARD.md](MODEL_CARD.md)
- 机制证据审计：[MECHANISTIC_EVIDENCE_AUDIT.md](MECHANISTIC_EVIDENCE_AUDIT.md)
- 数据协作记录模板：[EXPERIMENT_PROTOCOL_TEMPLATE.md](EXPERIMENT_PROTOCOL_TEMPLATE.md)
- 引用信息：[CITATION.cff](CITATION.cff)
- 许可证：[MIT License](LICENSE)
