# 实验场景格式（JSON）

场景文件用于复现 e-cell 的**模拟假设**，格式版本为 `e-cell-scenario/v1`。它保存细胞系、初始状态、环境、模型参数、运行设置和操作事件；不保存原始 CSV、个人信息或实验室原始记录。

最小示例见 [`data/example_a549_scenario.json`](data/example_a549_scenario.json)。

## 字段与单位

| 区域 | 字段 | 单位/要求 |
|---|---|---|
| `cell` | `profile_key` | 当前支持的细胞系键，例如 `a549` |
| `cell` | `initial_viable_cells` | cells |
| `cell` | `culture_volume_ml`、`surface_area_cm2` | mL、cm²；均须大于 0 |
| `environment` | `glucose_mM`、`glutamine_mM`、`lactate_mM` | mM |
| `environment` | `oxygen_percent`、`CO2_percent` | % |
| `environment` | `pH`、`temperature_C`、`osmolality_mOsm_kg`、`drug_uM` | 无量纲、°C、mOsm/kg、µM |
| `parameters` | 模型参数 | 与 `ModelParameters` 同名；证据与限制见 `MODEL_CARD.md` |
| `run` | `duration_h`、`dt_h` | h；当前界面限定总时长 0–168、步长 0–6 |
| `events` | 操作事件列表 | 仅记录配置；不嵌入上传 CSV |

导入前会检查格式版本、必填字段、支持的细胞系、数值及基础范围。未来格式迁移必须保留旧格式读取器或在发行说明中标记为破坏性变更。

## 边界

场景记录的是可重复运行的模型设置，不构成 GLP/GMP 审计追踪、实验原始记录、临床文档或生物学验证。相同场景仅保证在相同模型版本及浮点误差范围内可复跑；它不能证明参数已经由湿实验校准。
