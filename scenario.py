"""人类可读、可校验的培养情景配置；不保存原始 CSV。"""
import re
from copy import deepcopy
from math import isfinite
from dataclasses import asdict
from datetime import datetime, timezone
from cell import CellCulture, ModelParameters
from json_payload import decode_json_object
from profiles import CELL_PROFILES
from version import MODEL_VERSION, SCENARIO_SCHEMA_VERSION

REQUIRED = {"schema", "model_version", "created_at", "cell", "environment", "parameters", "run", "events", "evidence_level"}
ENVIRONMENT_BOUNDS = {
    # 这些边界与培养界面/模型现有状态边界一致，不表示推荐实验范围。
    "oxygen_percent": (0.0, 21.0), "oxygen_setpoint_percent": (0.1, 21.0),
    "pH": (6.2, 8.0), "temperature_C": (30.0, 42.0),
    "CO2_percent": (0.0, 20.0), "osmolality_mOsm_kg": (200.0, 450.0),
    "drug_uM": (0.0, 10000.0),
}
UI_PARAMETER_BOUNDS = {
    "growth_scale": (0.1, 2.0), "uptake_scale": (0.1, 3.0),
    "death_rate_per_h": (0.0, 0.1), "drug_ic50_um": (0.001, 10000.0),
    "drug_hill": (0.2, 4.0), "oxygen_transfer_per_h": (0.01, 2.0),
}
POSITIVE_PARAMETER_FIELDS = {
    "glucose_half_saturation_mm", "glutamine_half_saturation_mm",
    "oxygen_half_saturation_percent", "lactate_inhibition_mm", "buffer_capacity_mm_per_ph",
}
SCHEDULED_EVENT_BOUNDS = {
    # 与 app.py 中的计划操作菜单一致；教学刺激仍为相对强度而非实验剂量。
    "补充葡萄糖": (0.1, 20.0), "补充溶氧": (0.5, 10.0),
    "部分换液": (10.0, 100.0), "设置药物": (0.0, 10000.0),
    "施加氧化刺激": (5.0, 80.0), "增强抗氧化响应": (5.0, 60.0),
}


def _scenario_float(value):
    """Parse a JSON numeric field without treating booleans as 0/1."""

    if isinstance(value, bool):
        raise TypeError("布尔值不是数值输入。")
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("数值无法转换为有限浮点数。") from None

def export_scenario(
    cell: CellCulture, *, duration_h: float = 72, dt_h: float = 1,
    events: list | None = None, calibration_status: str = "未校准",
    data_file_fingerprint: str | None = None,
) -> dict:
    """导出可续跑的培养状态与假设，不含上传 CSV 或历史数组。"""
    try:
        duration = _scenario_float(duration_h)
        step = _scenario_float(dt_h)
    except (TypeError, ValueError):
        raise ValueError("场景总时长和步长必须是数值。") from None
    if not isfinite(duration) or not 0.0 < duration <= 168.0:
        raise ValueError("场景总时长必须在 0–168 h 范围内。")
    if not isfinite(step) or not 0.0 < step <= 6.0:
        raise ValueError("场景步长必须在 0–6 h 范围内。")
    if data_file_fingerprint is not None and (
        not isinstance(data_file_fingerprint, str)
        or not re.fullmatch(r"[0-9a-f]{64}", data_file_fingerprint)
    ):
        raise ValueError("数据文件指纹必须是 64 位小写 SHA-256 十六进制字符串。")
    return {"schema": SCENARIO_SCHEMA_VERSION, "model_version": MODEL_VERSION, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "cell": {"profile_key": cell.profile_key, "initial_viable_cells": cell.viable_cells, "culture_volume_ml": cell.culture_volume_ml, "surface_area_cm2": cell.surface_area_cm2}, "resume_state": {"time_h": cell.time_h, "dead_cells": cell.dead_cells, "energy_index": cell.energy_index, "last_growth_rate_per_h": cell.last_growth_rate_per_h, "last_death_rate_per_h": cell.last_death_rate_per_h}, "environment": {"glucose_mM": cell.glucose_mm, "glutamine_mM": cell.glutamine_mm, "lactate_mM": cell.lactate_mm, "oxygen_percent": cell.oxygen_percent, "oxygen_setpoint_percent": cell.oxygen_setpoint_percent, "pH": cell.ph, "temperature_C": cell.temperature_c, "CO2_percent": cell.co2_percent, "osmolality_mOsm_kg": cell.osmolality_mosm_kg, "drug_uM": cell.drug_um}, "parameters": asdict(cell.parameters), "run": {"duration_h": duration, "dt_h": step}, "events": deepcopy(events or []), "evidence_level": "A/B/C：参数关系证据等级见 MODEL_CARD.md；数值可能待校准。", "calibration_status": calibration_status, "data_file_fingerprint": data_file_fingerprint, "limitations": "场景只保存续跑起点与配置，不含此前完整历史；不是 GLP/GMP 审计追踪、实验原始记录或临床文档。"}

def import_scenario(payload: bytes | str | dict) -> tuple[CellCulture, dict]:
    """校验并恢复场景，单位见 SCENARIO_FORMAT.md；非法输入抛出可读 ValueError。"""
    data = decode_json_object(payload)
    missing = REQUIRED.difference(data)
    if missing: raise ValueError("场景缺少字段：" + "、".join(sorted(missing)))
    if data["schema"] != SCENARIO_SCHEMA_VERSION: raise ValueError("不支持的场景格式版本。")
    if data["model_version"] != MODEL_VERSION:
        raise ValueError(
            f"场景模型版本为 {data['model_version']}，当前版本为 {MODEL_VERSION}；"
            "请使用匹配版本载入，或在当前版本重新配置输入。"
        )
    for name in ("created_at", "evidence_level"):
        if not isinstance(data[name], str) or not data[name].strip():
            raise ValueError(f"场景元数据 {name} 必须是非空文本。")
    for name in ("calibration_status", "limitations"):
        if name in data and (not isinstance(data[name], str) or not data[name].strip()):
            raise ValueError(f"场景元数据 {name} 必须是非空文本。")
    fingerprint = data.get("data_file_fingerprint")
    if fingerprint is not None and (
        not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint)
    ):
        raise ValueError("数据文件指纹必须是 64 位小写 SHA-256 十六进制字符串或 null。")
    cell_data, env, params, run = data["cell"], data["environment"], data["parameters"], data["run"]
    if not all(isinstance(item, dict) for item in (cell_data, env, params, run)):
        raise ValueError("场景的 cell、environment、parameters 和 run 必须是 JSON 对象。")
    events = data["events"]
    if not isinstance(events, list):
        raise ValueError("场景 events 必须是计划操作列表。")
    for index, event in enumerate(events, start=1):
        if not isinstance(event, dict):
            raise ValueError(f"第 {index} 个计划操作必须是 JSON 对象。")
        action = event.get("action")
        if not isinstance(action, str) or action not in SCHEDULED_EVENT_BOUNDS:
            raise ValueError(f"第 {index} 个计划操作类型不受支持。")
        try:
            at_time = _scenario_float(event["at_time_h"])
            value = _scenario_float(event["value"])
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"第 {index} 个计划操作缺少有效的执行时间或操作量。") from None
        if not isfinite(at_time) or at_time < 0:
            raise ValueError(f"第 {index} 个计划操作时间必须为有限非负小时数。")
        minimum, maximum = SCHEDULED_EVENT_BOUNDS[action]
        if not isfinite(value) or not minimum <= value <= maximum:
            raise ValueError(f"第 {index} 个计划操作量超出当前界面范围 [{minimum}, {maximum}]。")
        status = event.get("status", "pending")
        if not isinstance(status, str) or status not in {"pending", "executed", "skipped"}:
            raise ValueError(f"第 {index} 个计划操作状态不受支持。")
        if "executed_at_h" in event:
            if status == "pending":
                raise ValueError(f"第 {index} 个待执行操作却含实际处理时间。")
            try:
                executed_at = _scenario_float(event["executed_at_h"])
            except (TypeError, ValueError):
                raise ValueError(f"第 {index} 个计划操作的实际执行时间必须为数值。") from None
            if not isfinite(executed_at) or executed_at < at_time:
                raise ValueError(f"第 {index} 个计划操作的实际执行时间不能早于计划时间。")
    profile_key = cell_data.get("profile_key")
    if not isinstance(profile_key, str) or profile_key not in CELL_PROFILES:
        raise ValueError("未知细胞系；请选择当前支持的细胞系。")
    try:
        volume, area = _scenario_float(cell_data.get("culture_volume_ml", 0)), _scenario_float(cell_data.get("surface_area_cm2", 0))
        duration, step = _scenario_float(run.get("duration_h", 0)), _scenario_float(run.get("dt_h", 0))
    except (TypeError, ValueError):
        raise ValueError("培养体积、面积、总时长和步长必须为数值。") from None
    if not 0 < volume <= 500 or not 0 < area <= 500: raise ValueError("培养体积或面积超出允许范围。")
    if not 0 < duration <= 168 or not 0 < step <= 6: raise ValueError("总时长或步长超出允许范围。")
    allowed = ModelParameters.__dataclass_fields__
    missing_parameters = set(allowed).difference(params)
    if missing_parameters:
        raise ValueError("场景模型参数不完整：" + "、".join(sorted(missing_parameters)))
    unknown_parameters = set(params).difference(allowed)
    if unknown_parameters:
        raise ValueError("场景包含当前模型版本未知参数：" + "、".join(sorted(unknown_parameters)))
    try:
        parameter_values = {k: _scenario_float(v) for k, v in params.items()}
    except (TypeError, ValueError):
        raise ValueError("模型参数必须为数值。") from None
    if any(not isfinite(value) for value in parameter_values.values()):
        raise ValueError("模型参数不能为 NaN 或无穷大。")
    for name, (minimum, maximum) in UI_PARAMETER_BOUNDS.items():
        if not minimum <= parameter_values[name] <= maximum:
            raise ValueError(f"模型参数 {name} 超出当前界面允许范围 [{minimum}, {maximum}]。")
    if any(parameter_values[name] <= 0 for name in POSITIVE_PARAMETER_FIELDS):
        raise ValueError("半饱和常数、抑制尺度和缓冲能力必须为有限正数。")
    parameters = ModelParameters(**parameter_values)
    try:
        initial_cells = _scenario_float(cell_data["initial_viable_cells"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("场景缺少有效的 initial_viable_cells。") from None
    if not isfinite(initial_cells) or initial_cells < 0:
        raise ValueError("初始活细胞数必须为有限非负数。")
    cell = CellCulture(cell_data["profile_key"], volume, area, initial_cells, parameters)
    # 旧 v1 文件没有 resume_state，按原格式从 t=0 / dead=0 载入。
    # 一旦声明续跑状态，则所有动力学起点字段必须齐全，不能部分回退默认值。
    resume = data.get("resume_state", {})
    if not isinstance(resume, dict):
        raise ValueError("resume_state 必须是 JSON 对象。")
    resume_fields = {
        "time_h": (0.0, None), "dead_cells": (0.0, None),
        "energy_index": (0.0, 100.0),
        "last_growth_rate_per_h": (0.0, None),
        "last_death_rate_per_h": (0.0, None),
    }
    if "resume_state" in data:
        missing_resume = set(resume_fields).difference(resume)
        unknown_resume = set(resume).difference(resume_fields)
        if missing_resume or unknown_resume:
            raise ValueError("续跑状态字段不完整或未知：" + "、".join(sorted(missing_resume | unknown_resume)))
    for name, (minimum, maximum) in resume_fields.items():
        if name not in resume:
            continue
        try:
            value = _scenario_float(resume[name])
        except (TypeError, ValueError):
            raise ValueError(f"续跑状态 {name} 必须为数值。") from None
        if not isfinite(value) or value < minimum or (maximum is not None and value > maximum):
            raise ValueError(f"续跑状态 {name} 超出有限有效范围。")
        setattr(cell, name, value)
    for index, event in enumerate(events, start=1):
        at_time = float(event["at_time_h"])
        status = event.get("status", "pending")
        if status == "pending" and at_time < cell.time_h - 1e-9:
            raise ValueError(f"第 {index} 个待执行操作早于续跑起点；请重新安排时间。")
        if status == "executed" and at_time > cell.time_h + 1e-9:
            raise ValueError(f"第 {index} 个已执行操作晚于续跑起点。")
        if "executed_at_h" in event and float(event["executed_at_h"]) > cell.time_h + 1e-9:
            raise ValueError(f"第 {index} 个操作的实际执行时间晚于续跑起点。")
    mapping = {"glucose_mM":"glucose_mm","glutamine_mM":"glutamine_mm","lactate_mM":"lactate_mm","oxygen_percent":"oxygen_percent","oxygen_setpoint_percent":"oxygen_setpoint_percent","pH":"ph","temperature_C":"temperature_c","CO2_percent":"co2_percent","osmolality_mOsm_kg":"osmolality_mosm_kg","drug_uM":"drug_um"}
    for key, attr in mapping.items():
        if key not in env: raise ValueError("场景环境缺少字段：" + key)
        try:
            value = _scenario_float(env[key])
        except (TypeError, ValueError):
            raise ValueError(f"环境字段 {key} 必须为数值。") from None
        if not isfinite(value):
            raise ValueError(f"环境字段 {key} 不能为 NaN 或无穷大。")
        if key in ENVIRONMENT_BOUNDS:
            minimum, maximum = ENVIRONMENT_BOUNDS[key]
            if not minimum <= value <= maximum:
                raise ValueError(f"环境字段 {key} 超出当前模型界面范围 [{minimum}, {maximum}]。")
        elif value < 0:
            raise ValueError(f"环境字段 {key} 不能为负数。")
        setattr(cell, attr, value)
    return cell, data
