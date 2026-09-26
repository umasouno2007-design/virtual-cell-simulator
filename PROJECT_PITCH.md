# 项目介绍与 GitHub 展示建议

## 30 秒（同学）

e-cell 是一个 Python + Streamlit 的虚拟细胞培养项目：我把贴壁细胞的生长、营养消耗、乳酸、pH 和氧环境做成可交互的经验动力学原型。它可以导入 CSV，把模拟和实测对齐并报告误差，但目前仍需真实实验数据校准。

## 2 分钟（潜在导师）

项目定位为“面向贴壁细胞培养条件探索的、文献驱动的经验动力学研究原型”。核心不是临床预测，而是把细胞库条件、环境操作、培养历史、实测 CSV、MAE/RMSE、两参数透明粗校准与配置快照放进同一个可审阅流程。细胞器页面是教学与机制探索模块，所有 ATP、ROS 等只作为相对指数呈现。仓库含教学合成 A549 留出验证案例、质量控制元数据和待校准范围说明；尚未完成独立湿实验验证。

## 5 分钟（跨学科合作者）

e-cell 采用单室、群体平均的经验动力学：由群体倍增时间构造最大比生长率，并以营养、氧、pH、温度、渗透压、乳酸、药物和汇合度作经验修正。上传数据后，系统按时间插值对齐模拟与观测，输出逐点残差、MAE、RMSE，并只在公开可审阅的 growth/uplake 两个缩放参数上进行网格粗校准。敏感性模块显示哪些趋势依赖未校准先验；没有可信范围的死亡、氧传递和缓冲参数会明确列为待测，而不输出伪精确置信区间。下一步应由可追溯、留出验证的真实培养批次检验模型。

## 仓库 About 建议

- 中文：文献驱动的贴壁细胞培养经验动力学研究原型，支持 CSV 对齐、误差评估与透明粗校准；不用于临床或替代湿实验。
- English: Literature-driven empirical kinetics prototype for adherent-cell culture exploration, with CSV alignment, error metrics and transparent calibration.

GitHub Topics：`python`、`streamlit`、`cell-culture`、`computational-biology`、`systems-biology`、`scientific-software`、`data-validation`、`reproducible-research`。

避免使用：`medical-ai`、`clinical-prediction`、`digital-twin`、`diagnosis`。

## 一句话描述

我开发了一个可导入实测数据、评估误差并透明校准的贴壁细胞培养经验动力学原型，用于实验条件探索而非临床预测。
