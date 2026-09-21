# 虚拟细胞培养与代谢模拟器

V1.0-alpha 将原来的教学型相对数值模型升级为一个**文献驱动、使用真实单位、可用实验数据校准**的细胞培养研究原型。它适合探索实验假设、比较培养条件和设计采样时间点，但在完成参数拟合与独立验证前，不能替代湿实验或作为定量实验结论。

## 当前支持的细胞系

- HeLa（宫颈癌细胞系）
- HEK-293（人胚肾来源转化细胞系）
- A549（肺腺癌细胞系）

每种细胞系分别保存推荐培养基、血清、温度、CO₂、接种密度、承载密度、群体倍增时间和代谢速率先验。界面会明确显示哪些数值来自细胞库，哪些只是等待校准的初始先验。

## 模型内容

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

## 数学结构

最大比生长率由群体倍增时间换算：

```text
μmax = ln(2) / doubling_time
```

实际生长率由葡萄糖、氧、pH、温度、渗透压、乳酸、药物与汇合度修正。葡萄糖和氧采用 Monod 型饱和项，药物采用 Hill/IC50 抑制项，贴壁细胞使用承载密度描述接触抑制。代谢物按细胞数、培养液体积和时间积分。

## 安装和运行

需要 Python 3.10 或更高版本：

```bash
pip install -r requirements.txt
streamlit run app.py
```

在 Pad 上使用时，建议把 GitHub 仓库部署到 Streamlit Community Cloud，再用浏览器访问网页。

## 文件结构

```text
virtual_cell/
├── app.py                 # Streamlit 界面、图表和数据导出
├── cell.py                # 生长、死亡、代谢和药物动力学
├── profiles.py            # 细胞系参数、来源和置信状态
├── simulation.py          # 场景、运行控制和状态判定
├── requirements.txt       # 依赖
├── README.md              # 本说明
├── DEPLOYMENT.md          # 部署说明
└── tests/
    └── test_cell.py       # 核心模型测试
```

## 参数来源

- [ATCC HeLa CCL-2](https://www.atcc.org/products/ccl-2)：EMEM + 10% FBS、37°C、5% CO₂、贴壁培养和传代建议。
- [ATCC HEK-293 CRL-1573](https://www.atcc.org/products/crl-1573)：EMEM + 10% FBS、37°C、5% CO₂、接种密度和培养建议。
- [ATCC A549 CCL-185](https://www.atcc.org/products/ccl-185)：F-12K + 10% FBS、37°C、5% CO₂、培养密度及约 22 h 群体倍增时间。
- [Warburg-associated acidification represses lactic fermentation](https://pmc.ncbi.nlm.nih.gov/articles/PMC10584866/)：支持低 pH 对 HEK/HeLa 糖酵解和乳酸生成的抑制关系。
- [Preliminary studies of cell culture strategies for HEK293 cells](https://pmc.ncbi.nlm.nih.gov/articles/PMC3980760/)：提供 HEK293 培养、生长、葡萄糖、乳酸和溶氧控制资料。

## 实验使用前必须完成

1. 明确细胞株来源、传代数、培养基品牌/批次、血清批次和培养器皿。
2. 采集多个时间点的活细胞数、存活率、葡萄糖、乳酸、pH 和溶氧数据。
3. 至少使用 3 个生物学重复估计误差。
4. 拟合 `growth_scale`、`uptake_scale`、死亡率、氧传递和缓冲参数。
5. 若模拟药物，必须使用该药物在同一细胞系和相近实验条件下的 IC50/Hill 数据。
6. 使用没有参与拟合的独立实验批次验证，并报告 RMSE、偏差和置信区间。
7. 进行细胞身份认证（如 STR）和支原体检测。

## 当前限制

- 当前是经验动力学模型，不是全基因组代谢模型，也不是 PBPK/QSP 模型。
- 代谢摄取率与部分倍增时间是等待校准的先验，不是通用常数。
- 暂未表示细胞周期各阶段、转录组、信号网络、三维扩散、基质或克隆异质性。
- 不能用于临床判断、人体给药、诊断或替代真实实验。

## 下一阶段

- 导入用户实验 CSV 并自动拟合参数、计算置信区间
- 添加更多细胞系和 Cellosaurus/ATCC 标识符
- 增加传代、接种、部分换液和采样事件时间表
- 为具体药物建立细胞系特异性的剂量—反应模型
- 加入谷氨酰胺、氨、ROS、细胞周期与凋亡状态
- 在有足够数据后增加 3D 球体扩散或代谢网络模型
