# 公开数据—模型假设映射

本页把公开转录组论文中的**来源报告观察**与 e-cell 中可做的**教学性机制探索问题**分开记录。转录组没有用于拟合或校准 e-cell；没有改动 ROS、ATP、凋亡、通信参数或默认值。

## 数据来源与观察

当前工作区没有包含此前口腔组织单细胞项目的分析结果表、对象文件、脚本输出或数据来源清单。因此，下面不是对该本地项目结果的复述，而是一个有明确出处的公开文献参考映射；获得本地结果后应另行增加样本、分析版本、细胞注释、标志基因和通路评分记录，不应覆盖本段来源说明。

Song 等人论文 Figure 9H 报告：牙周炎受累位点单核细胞氧化应激基因集评分较对照位点高，T 细胞方向相反。**但来源引用无法由所列单一样本 accession 支持**：论文方法将单细胞分析关联到 GSM5005043，并称其数据包含受累样本及一个正常样本；GEO 对 GSM5005043 的元数据显示它是单个 BM150、Healthy、Buccal 样本，而同一 GSE164241 系列中的牙周炎样本另有 accession（例如 GSM5005058，PD134，Periodontitis，Gingiva）。仅凭 GSM5005043 无法复核文中组间比较的完整输入及统计单位。因此本项目仅称这是“论文报告、分析输入待核”，不称为已核实的数据模式或本地分析结果。应先核对论文分析代码和实际样本清单，再决定是否复算。论文报告 CASP3、TXN、IL1B 等基因并对细胞亚群计算氧化应激 OSscore；本映射没有可追溯的原始表达矩阵或 OSscore 数值，因此不复刻具体评分。基因/通路分数也不等价于相应蛋白、酶活或细胞内 ROS 的测量。

来源：Song G, et al. *Uncovering the potential role of oxidative stress in the development of periodontitis and establishing a stable diagnostic model via combining single-cell and machine learning analysis*. Front Immunol. 2023;14:1181467. [论文全文与方法/结果](https://pmc.ncbi.nlm.nih.gov/articles/PMC10355807/) · [DOI](https://doi.org/10.3389/fimmu.2023.1181467) · [GEO GSE164241](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE164241) · GEO 样本：[健康 BM150/GSM5005043](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSM5005043) 与 [牙周炎 PD134/GSM5005058](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSM5005058)。论文图示比较的输入与统计单位仍需作者分析代码/完整样本清单进一步核对。

作为组织图谱背景，Williams 等人的原始口腔黏膜图谱报告健康及牙周炎组织中存在上皮、内皮、成纤维和免疫细胞等群体，并提供了细胞类型标志基因与数据集；见 [原始研究](https://pmc.ncbi.nlm.nih.gov/articles/PMC8359928/) 与 [GEO GSE164241](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE164241)。不同研究的样本纳入和再分析方法可能不同，不应混成一个未经核对的“本地分析结果”。

| 类别 | 当前记录 | 可以支持什么 | 不能支持什么 |
| --- | --- | --- | --- |
| 公开论文报告（分析输入待核） | Figure 9H 报告单核细胞评分在受累位点较高、T 细胞方向相反；论文把分析关联到 GSM5005043，但该 GEO accession 是健康 BM150 buccal 单样本，系列中的牙周炎样本另有 accession。 | 仅作为需核对完整样本清单和统计单位后才能复算的研究线索。 | 暂不能视为由所列单一 accession 独立复核的公开数据观察；不证明 ROS 浓度升高、细胞器功能改变、凋亡增加或因果方向。 |
| e-cell 教学假设 | 可用现有教学性氧化压力脉冲，观察代表性细胞 ROS、DNA 损伤、促凋亡压力相对指数在现有规则下的变化。 | 展示 e-cell 现有代理指标之间的规则性响应，并讨论下一步需要什么实验读出。 | 不模拟单核细胞、T 细胞、口腔组织、牙周炎免疫微环境或基因集评分。 |
| 未推断内容 | 公开表达与 e-cell 状态指标之间没有经验证的数值映射。 | 保留为待验证问题。 | 不可由表达直接推出蛋白量/活性、ATP、线粒体膜电位、ROS、真实细胞命运、细胞通信强度或治疗效果。 |

## 可重复的教学情景

界面“数据启发假设”页可只读查看并下载 [教学情景 JSON 定义](data/scenarios/oral_periodontitis_oxidative_stress_teaching.json)。下载生成的是可由单细胞实验室导入的 `e-cell-single-cell/v1` 场景，并在不参与模型计算的扩展字段中保留论文观察、来源警告、未校准项目和复现步长/时长。场景记录 e-cell 已有的氧化压力脉冲，相对教学输入指数为 20；该数字来自软件现有演示交互，不来自公开数据、实验剂量或校准。导入后以 1 h 步长推进 24 h，可复跑同一演示情景。它不自动载入、不改变默认设置，也不写回任何动力学参数；结果不是对 GSE164241 的复现。

从项目根目录可将这一教学情景完整推进 24 h，并在指定目录导出 JSON 与状态时间线 CSV：

```bash
python scripts/run_data_inspired_hypothesis.py --output-dir outputs/data_inspired_hypothesis
```

脚本按场景元数据中的 1 h 步长重复推进，CSV 每行标注模型版本、C 级映射、来源链接和“无参数校准”。模型内部沿用的旧字段在该导出中改用 `_relative_index` 名称（如钙相关状态不再导出为 `calcium_nM`），避免被误读为百分比或实测浓度。重复运行会产生相同的轨迹；这是软件行为的可重复性检查，不代表复现了公开数据结果。

结构与确定性测试：

```bash
python -m unittest tests.test_data_model_hypotheses
```

## 后续接入本地口腔单细胞结果的最低记录项

空白 [本地数据—假设映射 JSON 模板](data/hypothesis_mapping_template.json)预留了数据集 accession、样本、组织/条件、分析版本、细胞注释、标志基因、通路评分及统计单位；其状态为 `template_only`，不包含示例观察，也禁止参数校准。取得用户授权的本地结果后，需保留数据集 accession、样本/供体与组织部位、病例定义、分析脚本版本、细胞注释来源、标志基因/通路基因集定义、评分方法、统计比较单位和不确定性。只有核实原始输出后，才能把它标记为“本地项目观察”；不得把单细胞作为细胞独立重复来替代供体重复。表达模式只生成待检验假设，不得直接更改 e-cell 参数。

填写副本后，可在本机运行结构校验；该工具只读取不超过 1 MiB 的摘要 JSON，输出不含用户文件路径，不联网、不上传原始/矩阵数据、不更改文件，也不进入模型参数：

```bash
python scripts/validate_local_hypothesis_mapping.py path/to/your_mapping.json
```

若记录尚未填充，校验器会把它标记为模板而非观察结果。完整记录必须明确数据集与样本 accession、分析版本、细胞注释/基因集方法、统计单位和检查日期。额外字段（包括原始表达矩阵）会被拒绝；通过仅代表结构完整，不能证明来源、统计方法、结论或假设正确。

## 明确边界

- 公开表达数据只作假设生成和方法学习，不进入 `intracellular.py`、`cell.py` 或 `cell_communication.py` 参数估计。
- 基因表达/富集分数不是蛋白丰度、蛋白活性、代谢通量或细胞器的直接测量；不同细胞类型也不能互换成 A549、HeLa、HEK-293。
- e-cell 细胞内输出是未按细胞系校准的相对状态指数；教学通信输出不是细胞因子浓度或真实邻近通信。
- 该映射不构成独立模型验证、诊断标志物验证、临床推断或实验结论。
