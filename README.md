# e-cell

e-cell V1.0-alpha.8 是一个**文献驱动、使用真实单位、可用实验数据校准**的虚拟细胞研究原型。界面包含“细胞培养”和“细胞生命活动”两个模式；它适合探索实验假设，但在完成参数拟合与独立验证前，不能替代湿实验或作为定量实验结论。

## 两种模拟模式

- **细胞培养**：观察群体生长、死亡、汇合度、营养消耗和培养环境。
- **细胞生命活动**：以代表性单细胞为视角，观察细胞核、线粒体、内质网、高尔基体、溶酶体和核糖体，以及 ATP、ROS、Ca²⁺、DNA 损伤、细胞周期、自噬与凋亡信号。

两个模式共享培养环境和连续时钟。氧、葡萄糖、pH、温度、药物和汇合度会影响细胞内部状态；后者再用于解释群体生长或死亡背后的机制。

### 3D 细胞生命活动视图

细胞生命活动模式使用可离线加载的 3D 生物医学真核细胞剖面图，展示半透明细胞膜与细胞质、细胞核和核仁、线粒体及其嵴、粗面/滑面内质网、高尔基体、溶酶体、运输囊泡与游离核糖体。图像作为内嵌资源提供给网页 iframe，不依赖 Pad 对静态文件路径的二次请求；若资源无法读取，会回退到离线 SVG 结构图。

网页浮层会随模拟状态更新：

- 线粒体标签显示膜电位，并用动态光晕表示功能水平；
- 细胞核显示细胞周期和 DNA 损伤；
- 内质网、溶酶体分别显示内质网应激、Ca²⁺ 与自噬水平；
- ATP、ROS、自噬和凋亡信号显示实时数值；
- ROS、DNA 损伤、内质网应激或凋亡升高时，状态色由青蓝切换为琥珀或珊瑚红。

所有标签均由网页实时叠加，3D 底图本身不包含文字或水印。

## 运行截图

### 细胞培养模式

![细胞培养模式主界面](assets/screenshots/culture-mode.png)

实时显示细胞数量、存活率、汇合度、培养环境和代谢指标。

### 细胞生命活动模式

![3D 细胞生命活动模型](assets/screenshots/cell-life-mode.png)

3D 细胞剖面、细胞器浮层标签与 ATP、ROS、DNA 损伤、自噬和凋亡状态联动。

## 当前支持的细胞系

- HeLa（宫颈癌细胞系）
- HEK-293（人胚肾来源转化细胞系）
- A549（肺腺癌细胞系）

每种细胞系分别保存推荐培养基、血清、温度、CO₂、接种密度、承载密度、群体倍增时间和代谢速率先验。界面会明确显示哪些数值来自细胞库，哪些只是等待校准的初始先验。

## 模型内容

## 像素实验室界面

新版首页直接进入原创 16-bit 像素实验室工作台。侧栏的“模拟模式”仍保留原有逻辑，但主界面以两个房间呈现：

- **细胞培养室**：像素培养皿、营养/氧气动画和培养状态 HUD；原有补料、环境、计划操作、曲线和 CSV 导出均保留。
- **细胞生命活动室**：细胞器地图、应激/能量 HUD、细胞内挑战、虚拟采样、虚拟检测、观察笔记与条件沙盒均保留。

所有专业图表继续使用 Matplotlib 正常绘制，避免复古风格降低数据可读性。侧栏提供“减少动态效果”开关，关闭纯视觉的气泡、脉冲和危险闪烁；它不会改变任何模拟结果。

### CellDex 细胞器交互

“细胞生命活动”模式提供四个可点击的原生交互热区：线粒体、细胞核、粗面内质网和溶酶体。点击后会高亮细胞图中对应标签、显示功能与状态解释、记录首次发现，并保存到 CellDex。线粒体直接显示 ATP、膜电位、ROS 与氧气；细胞核显示 DNA 损伤和周期；粗面内质网显示 ER 应激、Ca²⁺ 和蛋白合成；溶酶体显示自噬与凋亡信号。

这些读数均来自现有的细胞内模型。细胞器功能说明和风险提示属于教学解释；其中自噬、DNA 损伤和膜电位仍是相对功能指数，不能直接视为实验定量测量值。

## 素材与许可证

| 素材 | 来源 | 许可证 / 权利 | 用途 |
| --- | --- | --- | --- |
| `assets/pixel-lab-original-v1.png` | 本项目中由 OpenAI Image Generation 依据原创提示生成 | 本项目原创生成资产；不含第三方游戏角色、Logo、字体、地图或素材 | 像素实验室工作台背景 |

项目不热链接外部图片；该素材随仓库分发并可离线使用。页面中的培养皿、HUD、像素边框、状态动画和细胞器标记由本地 HTML/CSS/SVG 代码绘制，不使用外部素材包。

- 时间：小时（h）
- 活细胞数、死细胞数、存活率与汇合度
- 葡萄糖和乳酸：mM
- 氧：培养环境/溶氧代理百分比
- 温度：°C
- CO₂：%
- pH
- 渗透压：mOsm/kg
- 药物浓度：µM
- 药物 IC50 与 Hill 系数
- 生长、死亡、营养消耗、乳酸生成、氧传递、接触抑制和换液
- 带单位的 CSV 数据导出
- 实测 CSV 导入、列名自动识别、模拟—实测曲线叠加、逐指标 MAE/RMSE 和对齐结果导出
- 可导出的实验事件时间线：创建/重置、开始/暂停、单步推进、换液、补糖、补氧、加药、环境调整与应用粗校准

### 实测数据对比

在“细胞培养”模式的“导入实测数据并与模拟对比”中上传 CSV。时间列支持 `time_h`、`time`、`hour` 或 `时间`；可选指标支持活细胞数、存活率、葡萄糖、乳酸、pH 与氧。系统只会在当前浏览器会话中读取文件，不会将实测 CSV 写入项目目录或运行时状态。

图中圆点为模拟历史，叉号为实测数据；系统将模拟历史线性插值到实测时间点，输出“模拟值 − 实测值”的逐点残差、MAE、RMSE 和可下载的对齐 CSV。该功能用于检查模型偏差，**不会自动修改任何参数**。

当至少有两个时间点，且包含活细胞数、葡萄糖或乳酸中的任一指标时，可执行“两参数粗校准”。它只在 `growth_scale`（0.1–2.0）与 `uptake_scale`（0.1–3.0）的透明网格中搜索，以这些指标的归一化残差最小为目标；死亡率、氧传递、pH、药物和细胞内指标均不会被拟合。应用建议只影响后续模拟，已有历史保持不变。只有当上传实验与当前模拟首点的细胞系、接种量、体积、环境和操作流程一致时，结果才可作为下一轮实验的参数初值。

### 实验事件时间线

“实验事件时间线”会记录每项操作的模拟时间、记录时间、事件名称和参数摘要，并可导出 CSV。它用于和纸质/电子实验记录、培养箱日志及实测数据相互核对；这不是符合 GLP/GMP 的审计追踪系统，记录时间来自运行页面的本机时钟。

### 实验配置快照

“实验事件时间线”还可下载实验配置快照 JSON。它包含当前细胞系、模式、培养器皿、环境、可校准参数、模拟时间倍率、历史时间范围和事件记录，适合和导出的 CSV 一起保存或分享。快照不包含上传的实测文件或完整历史数组；它只是复现设置的辅助记录，不是经过验证的审计记录或实验数据替代品。

### 计划操作（实验方案）

可为指定模拟时间预先安排补充葡萄糖、补充溶氧、部分换液、设置药物浓度，以及演示性的氧化刺激/抗氧化响应。连续培养恢复补算和单步推进都会在越过计划时间时精确停在该时间点执行，随后在事件时间线记录“计划执行”。这是实验流程编排工具，不代表任何细胞系的标准操作规程；剂量、换液比例、刺激强度和时点仍须由实验方案与实测数据确定。

### 细胞内部指标的实验验证建议

“细胞生命活动”模式新增“模型指标的实验验证建议”。它为 ATP、线粒体膜电位、ROS、DNA 损伤、内质网应激、自噬、凋亡和细胞周期列出建议的组合读出与解释边界，例如自噬应以 LC3/p62 加溶酶体抑制条件评估通量，不能把单一 LC3 点直接当作自噬活性。所有页面百分比仍然是模型相对指数，不是 ATP 浓度、膜电位 mV、凋亡率或细胞周期实测比例。

在“细胞刺激与虚拟采样”中可选择氧化刺激或抗氧化响应的演示强度，并在任意模拟时点记录 ATP、ROS、膜电位、DNA 损伤、内质网应激或凋亡信号的虚拟样本，导出为 CSV。该交互用于理解模型中的因果方向与时间序列；它不模拟具体试剂、探针、剂量、细胞内浓度或检测误差，也不能替代真实检测。

“虚拟多重检测台”可从当前模型状态生成 ATP 发光、线粒体膜电位、ROS、ER 应激、自噬和凋亡的合成重复孔，并导出 CSV。每行都会标记源模型指标和 `is_synthetic_demo=true`。线性映射、相对单位与孔间变异都是 C 级演示规则；它们只能帮助比较同一模拟内的干预前后趋势，绝不可与真实读板数据混用或用于结论。

可在“干预前后状态对比”中将当前细胞内状态设为基线，随后以表格和 CSV 对比 ATP、膜电位、ROS、DNA 损伤、ER 应激、自噬、凋亡和周期进度的变化。此处“变化”只表示模型相对指数的差值，不提供生物学显著性、因果判断、组间统计或实验重复验证。

“细胞内条件沙盒”会深拷贝当前培养物与细胞内状态，预览候选氧气、葡萄糖或药物条件下未来 1–24 小时的相对趋势；原实验状态不会被改写。用户应在审查预测后，使用正常培养操作手动应用条件。细胞周期导航则用同一模拟时钟推进到下一阶段检查点附近，以便观察周期与细胞器状态的同步变化；其阶段边界和时间估算均为演示规则。

“细胞内观察笔记”允许用户把假设、观察焦点和当时的内部状态快照一起保存并导出。笔记属于实验设计/学习记录，不会自动验证机制，也不应替代实验记录系统、统计分析或真实重复实验。

“细胞内因果链追踪”把当前模型状态组织成氧化应激、能量稳态或蛋白稳态三条可高亮的观察链。它帮助用户从上游环境/刺激一路观察细胞器代理指标和细胞命运信号，但连线表示模型的教学性因果假设，不能视为已验证的特异性分子通路。

## 数学结构

最大比生长率由群体倍增时间换算：

```text
μmax = ln(2) / doubling_time
```

实际生长率由葡萄糖、氧、pH、温度、渗透压、乳酸、药物与汇合度修正。葡萄糖和氧采用 Monod 型饱和项，药物采用 Hill/IC50 抑制项，贴壁细胞使用承载密度描述接触抑制。代谢物按细胞数、培养液体积和时间积分。

## 安装和运行

需要 Python 3.10 或更高版本：

```powershell
cd "C:\Users\umaso\Documents\Codex\e-cell"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\streamlit.exe run app.py
```

启动后在浏览器访问：

```text
http://localhost:8501/
```

如果已经安装依赖，也可以直接运行：

```powershell
pip install -r requirements.txt
streamlit run app.py
```

在 Pad 上使用时，建议把 GitHub 仓库部署到 Streamlit Community Cloud，再用浏览器访问网页。

## 文件结构

```text
e-cell/
├── app.py                 # Streamlit 界面、图表和数据导出
├── cell.py                # 生长、死亡、代谢和药物动力学
├── intracellular.py       # 细胞器功能、应激、周期和命运状态
├── evidence.py            # 机制证据等级、来源与适用边界
├── experiment_data.py     # 实测 CSV 标准化、对齐与残差计算
├── experiment_manifest.py # 可共享的实验配置快照（JSON）
├── calibration.py          # 生长/摄取缩放的可审阅网格搜索
├── observability.py        # 模型内部指标与实验读出的边界映射
├── profiles.py            # 细胞系参数、来源和置信状态
├── simulation.py          # 场景、运行控制和状态判定
├── requirements.txt       # 依赖
├── README.md              # 本说明
├── DEPLOYMENT.md          # 部署说明
└── tests/
    ├── test_cell.py       # 培养模型测试
    ├── test_intracellular.py # 细胞内部模型测试
    ├── test_app.py        # 界面状态测试
    ├── test_calibration.py # 两参数粗校准测试
    ├── test_experiment_data.py # 实测数据导入与对比测试
    ├── test_experiment_manifest.py # 实验配置快照测试
    └── test_observability.py # 细胞内部指标验证映射测试
```

## 理论基础与证据等级

项目将“关系有文献依据”和“数值已经在本体系验证”严格区分。代码中的证据目录位于 `evidence.py`，网页的“参数来源与可追溯性”会展示同一套内容。

- **A 直接支持**：权威细胞库或论文直接给出培养条件、细胞系属性或所采用的关系/数学形式。
- **B 文献推断·待校准**：机制方向有文献依据，但当前系数、阈值、曲线宽度或适用范围没有在本项目培养体系中拟合。
- **C 演示规则**：为了教学、交互或产生连续趋势设置，不具有定量预测含义。

> 等级针对表中“关系”而不是整行所有数值。即使关系为 A，默认 IC50、速率或初始浓度仍可能需要实验校准。

| 模拟机制 | 数学/逻辑关系 | 适用范围 | 证据等级 | 来源 | 当前限制 |
|---|---|---|---|---|---|
| 细胞系身份与培养条件 | 按细胞库配置培养基、血清、37°C、5% CO₂和贴壁属性 | 指定 HeLa、HEK-293、A549 | A | [ATCC HeLa](https://www.atcc.org/products/ccl-2)、[ATCC HEK-293](https://www.atcc.org/products/crl-1573)、[ATCC A549](https://www.atcc.org/products/ccl-185)、Cellosaurus | 批次、传代数、品牌和血清会改变表型 |
| 增殖动力学 | `μmax = ln(2)/倍增时间`，再以环境项修正 | 对数生长期群体平均 | B | [A549 产品页](https://www.atcc.org/products/ccl-185)、[HeLa Cellosaurus](https://www.cellosaurus.org/CVCL_0030)、[HEK293 培养研究](https://pmc.ncbi.nlm.nih.gov/articles/PMC3980760/) | 环境修正系数和 HEK-293 倍增时间待拟合 |
| 死亡动力学 | 基础死亡率叠加营养、环境和药物应激 | 定性比较 | C | 无直接定量来源 | 加和形式、阈值和系数均待验证 |
| 葡萄糖/谷氨酰胺消耗 | 平均活细胞数×比摄取率×时间的物料衡算；饱和限制 | 二维哺乳动物细胞培养 | B | [Mulukutla 等](https://pubmed.ncbi.nlm.nih.gov/20691487/)、[Locasale 与 Cantley](https://pubmed.ncbi.nlm.nih.gov/21982705/) | 摄取率和半饱和常数均为先验 |
| 乳酸生成 | 葡萄糖消耗乘表观乳酸产率 | 有氧糖酵解占主导的情景 | B | [葡萄糖代谢综述](https://pubmed.ncbi.nlm.nih.gov/20691487/)、[pH 控制研究](https://pubmed.ncbi.nlm.nih.gov/31044169/) | 固定产率忽略细胞系差异与代谢重编程 |
| 氧消耗/传递 | 细胞消耗氧，一阶传质项向设定值恢复 | 充分混合单室近似 | B | [培养氧水平综述](https://pubmed.ncbi.nlm.nih.gov/36231085/)、[HEK293 培养研究](https://pmc.ncbi.nlm.nih.gov/articles/PMC3980760/) | 氧百分比是代理量；OUR 与 kLa 需实测 |
| pH 与 CO₂ | 乳酸酸负荷和 CO₂ 偏移改变 pH；近生理 pH 有利生长 | 碳酸氢盐缓冲培养基的定性趋势 | B | [Michl 等](https://pubmed.ncbi.nlm.nih.gov/31044169/) | 未显式求解碳酸盐平衡；CO₂ 系数为演示参数 |
| 温度 | 偏离 37°C 时降低生长修正 | 当前三种人源贴壁细胞 | B | 三个 ATCC 产品页 | 37°C 推荐条件为 A；高斯曲线宽度为 B |
| 渗透压 | 偏离 300 mOsm/kg 时降低生长修正 | 从 CHO 外推至人源贴壁细胞 | B | [Takagi 等](https://pubmed.ncbi.nlm.nih.gov/19002978/) | 跨细胞系外推，最适值和曲线宽度待测 |
| 药物浓度 | Hill/IC50 浓度—效应抑制项 | 同细胞系、终点和暴露时间的数据 | A | [Sebaugh](https://pubmed.ncbi.nlm.nih.gov/22328315/) | 默认 IC50、Hill 系数和衰减速率不是药物实测值 |
| 汇合度 | `1-N/K` 线性降低增殖能力 | 贴壁单层培养 | B | [Pavel 等](https://pubmed.ncbi.nlm.nih.gov/30054475/) | YAP/TAZ 方向有支持；线性形式与 K 未验证，癌细胞可失去接触抑制 |
| ATP/线粒体膜电位 | 氧、温度、药物影响膜电位；膜电位与糖酵解共同影响 ATP 指数 | 代表性单细胞趋势 | B | [Handy 与 Loscalzo](https://pubmed.ncbi.nlm.nih.gov/22146081/) | 百分比不是 ATP 浓度或膜电位 mV，权重待校准 |
| ROS/DNA 损伤/凋亡 | 应激提高 ROS，ROS 与损伤、线粒体失稳及死亡信号关联 | 趋势探索 | B | [线粒体氧化还原综述](https://pubmed.ncbi.nlm.nih.gov/22146081/)、[Jackson 与 Bartek](https://pubmed.ncbi.nlm.nih.gov/19847258/) | 不区分 ROS 物种或损伤类型；阈值与修复速率为演示参数 |
| 内质网应激 | 营养/药物/氧化应激提高 UPR；持续未缓解可转向凋亡 | UPR 功能指数 | B | [Walter 与 Ron](https://pubmed.ncbi.nlm.nih.gov/22116877/) | 未分别建模 IRE1、PERK、ATF6 |
| 自噬 | 能量不足和 ER 应激提高自噬指数 | 仅表示调节方向 | B | [Klionsky 等](https://pubmed.ncbi.nlm.nih.gov/33634751/) | 单一指数不等于自噬通量，需多指标/通量实验验证 |
| 细胞周期 | G1→S→G2→M；严重应激时暂停推进 | 交互展示 | C | 无针对当前分段的直接来源 | 阶段比例与推进速度未按细胞系校准 |
| 状态徽标与干预按钮 | 阈值颜色、氧化刺激、抗氧化响应和动画 | 教学与交互 | C | 无 | 不代表药剂剂量、反应时间或实验分级 |

### 细胞系参数来源

| 细胞系 | 身份标识 | 推荐培养条件 | 当前倍增时间 | 证据状态 |
|---|---|---|---:|---|
| HeLa | [ATCC CCL-2](https://www.atcc.org/products/ccl-2)；[RRID:CVCL_0030](https://www.cellosaurus.org/CVCL_0030) | EMEM + 10% FBS；37°C；5% CO₂ | 31.2 h（Cellosaurus 记录 1.3 天） | 培养条件/倍增时间有来源；接种上限和代谢速率待校准 |
| HEK-293 | [ATCC CRL-1573](https://www.atcc.org/products/crl-1573)；[RRID:CVCL_0045](https://www.cellosaurus.org/CVCL_0045) | EMEM + 10% FBS；37°C；5% CO₂；ATCC 建议接种 1–4×10⁴ cells/cm² | 30 h | 培养条件/接种密度有来源；30 h 与代谢速率是待校准先验 |
| A549 | [ATCC CCL-185](https://www.atcc.org/products/ccl-185)；[RRID:CVCL_0023](https://www.cellosaurus.org/CVCL_0023) | F-12K + 10% FBS；37°C；5% CO₂ | 约 22 h（ATCC） | 培养条件、密度、倍增时间有来源；代谢速率待校准 |

### 已核对参考资料（19 项）

1. [ATCC HeLa CCL-2](https://www.atcc.org/products/ccl-2)
2. [ATCC 293 [HEK-293] CRL-1573](https://www.atcc.org/products/crl-1573)
3. [ATCC A549 CCL-185](https://www.atcc.org/products/ccl-185)
4. [Cellosaurus HeLa CVCL_0030](https://www.cellosaurus.org/CVCL_0030)
5. [Cellosaurus HEK293 CVCL_0045](https://www.cellosaurus.org/CVCL_0045)
6. [Cellosaurus A-549 CVCL_0023](https://www.cellosaurus.org/CVCL_0023)
7. [Preliminary studies of cell culture strategies for HEK293 cells](https://pmc.ncbi.nlm.nih.gov/articles/PMC3980760/)
8. [Glucose metabolism in mammalian cell culture](https://pubmed.ncbi.nlm.nih.gov/20691487/)
9. [Metabolic flux and the regulation of mammalian cell growth](https://pubmed.ncbi.nlm.nih.gov/21982705/)
10. [Evidence-based guidelines for controlling pH in mammalian live-cell culture systems](https://pubmed.ncbi.nlm.nih.gov/31044169/)
11. [Supraphysiological Oxygen Levels in Mammalian Cell Culture](https://pubmed.ncbi.nlm.nih.gov/36231085/)
12. [Effect of osmolarity on CHO-cell metabolism and morphology](https://pubmed.ncbi.nlm.nih.gov/19002978/)
13. [Contact inhibition controls survival and proliferation via YAP/TAZ-autophagy](https://pubmed.ncbi.nlm.nih.gov/30054475/)
14. [Guidelines for accurate EC50/IC50 estimation](https://pubmed.ncbi.nlm.nih.gov/22328315/)
15. [Redox regulation of mitochondrial function](https://pubmed.ncbi.nlm.nih.gov/22146081/)
16. [The unfolded protein response](https://pubmed.ncbi.nlm.nih.gov/22116877/)
17. [The DNA-damage response in human biology and disease](https://pubmed.ncbi.nlm.nih.gov/19847258/)
18. [Guidelines for monitoring autophagy (4th edition)](https://pubmed.ncbi.nlm.nih.gov/33634751/)
19. [Warburg-associated acidification represses lactic fermentation](https://pmc.ncbi.nlm.nih.gov/articles/PMC10584866/)

## 实验使用前必须完成

1. 明确细胞株来源、传代数、培养基品牌/批次、血清批次和培养器皿。
2. 采集多个时间点的活细胞数、存活率、葡萄糖、乳酸、pH 和溶氧数据。
3. 至少使用 3 个生物学重复估计误差。
4. 拟合 `growth_scale`、`uptake_scale`、死亡率、氧传递和缓冲参数。
5. 若模拟药物，必须使用该药物在同一细胞系和相近实验条件下的 IC50/Hill 数据。
6. 使用没有参与拟合的独立实验批次验证，并报告 RMSE、偏差和置信区间。
7. 进行细胞身份认证（如 STR）和支原体检测。

## 模型局限与不确定性

- 当前是低维经验动力学模型，**不是全基因组代谢模型（GEM）**，也不是 PBPK、QSP 或数字孪生。
- 代谢摄取率、半饱和常数、死亡率、氧传递、缓冲能力和部分倍增时间是等待校准的先验，不是通用生物常数。
- 营养、pH、温度、渗透压、乳酸、药物和汇合度的影响被相乘组合；真实系统存在耦合、适应、滞后与非单调响应。
- “氧百分比”是单室代理量，不等价于培养液中经校准的溶解氧张力；模型未解三维扩散和边界层。
- 细胞内部的 ATP、膜电位、ROS、DNA 损伤、ER 应激、自噬和凋亡均为相对功能指数，不是实验仪器输出；它们的权重、阈值和时间常数属于演示规则。
- 未表示具体基因调控网络、化学计量代谢网络、细胞间异质性、克隆选择、细胞外基质、免疫微环境或传代漂移。
- 文献中的细胞系结论不能自动外推到其他亚株、培养基、血清、氧环境或药物暴露条件。
- 项目不能替代湿实验、细胞身份认证、污染检测或独立验证；**不能用于临床判断、诊断、人体给药或安全决策**。

## 下一阶段

- 导入用户实验 CSV 并自动拟合参数、计算置信区间
- 添加更多细胞系和 Cellosaurus/ATCC 标识符
- 增加传代、接种、部分换液和采样事件时间表
- 为具体药物建立细胞系特异性的剂量—反应模型
- 在获得可追溯实验数据后校准氨、ROS、细胞周期与凋亡子模型
- 在有足够数据后增加 3D 球体扩散或代谢网络模型
