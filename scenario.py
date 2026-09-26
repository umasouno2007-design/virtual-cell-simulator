"""人类可读、可校验的培养情景配置；不保存原始 CSV。"""
import json
from math import isfinite
from dataclasses import asdict
from datetime import datetime, timezone
from cell import CellCulture, ModelParameters
from profiles import CELL_PROFILES
from version import MODEL_VERSION, SCENARIO_SCHEMA_VERSION

REQUIRED = {"schema", "model_version", "created_at", "cell", "environment", "parameters", "run", "events", "evidence_level"}

def export_scenario(cell: CellCulture, *, duration_h: float = 72, dt_h: float = 1, events: list | None = None, calibration_status: str = "未校准") -> dict:
    """导出可重跑假设，不含上传 CSV、历史数组或个人元数据。"""
    return {"schema": SCENARIO_SCHEMA_VERSION, "model_version": MODEL_VERSION, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "cell": {"profile_key": cell.profile_key, "initial_viable_cells": cell.viable_cells, "culture_volume_ml": cell.culture_volume_ml, "surface_area_cm2": cell.surface_area_cm2}, "environment": {"glucose_mM": cell.glucose_mm, "glutamine_mM": cell.glutamine_mm, "lactate_mM": cell.lactate_mm, "oxygen_percent": cell.oxygen_percent, "oxygen_setpoint_percent": cell.oxygen_setpoint_percent, "pH": cell.ph, "temperature_C": cell.temperature_c, "CO2_percent": cell.co2_percent, "osmolality_mOsm_kg": cell.osmolality_mosm_kg, "drug_uM": cell.drug_um}, "parameters": asdict(cell.parameters), "run": {"duration_h": duration_h, "dt_h": dt_h}, "events": events or [], "evidence_level": "A/B/C：参数关系证据等级见 MODEL_CARD.md；数值可能待校准。", "calibration_status": calibration_status, "data_file_fingerprint": None, "limitations": "场景文件记录模拟假设，不是 GLP/GMP 审计追踪、实验原始记录或临床文档。"}

def import_scenario(payload: bytes | str | dict) -> tuple[CellCulture, dict]:
    """校验并恢复场景，单位见 SCENARIO_FORMAT.md；非法输入抛出可读 ValueError。"""
    if isinstance(payload, bytes): payload = payload.decode("utf-8-sig")
    data = json.loads(payload) if isinstance(payload, str) else payload
    if not isinstance(data, dict): raise ValueError("场景根节点必须是 JSON 对象。")
    missing = REQUIRED.difference(data)
    if missing: raise ValueError("场景缺少字段：" + "、".join(sorted(missing)))
    if data["schema"] != SCENARIO_SCHEMA_VERSION: raise ValueError("不支持的场景格式版本。")
    cell_data, env, params, run = data["cell"], data["environment"], data["parameters"], data["run"]
    if cell_data.get("profile_key") not in CELL_PROFILES: raise ValueError("未知细胞系；请选择当前支持的细胞系。")
    try:
        volume, area = float(cell_data.get("culture_volume_ml", 0)), float(cell_data.get("surface_area_cm2", 0))
        duration, step = float(run.get("duration_h", 0)), float(run.get("dt_h", 0))
    except (TypeError, ValueError):
        raise ValueError("培养体积、面积、总时长和步长必须为数值。") from None
    if not 0 < volume <= 500 or not 0 < area <= 500: raise ValueError("培养体积或面积超出允许范围。")
    if not 0 < duration <= 168 or not 0 < step <= 6: raise ValueError("总时长或步长超出允许范围。")
    allowed = ModelParameters.__dataclass_fields__
    try:
        parameter_values = {k: float(v) for k, v in params.items() if k in allowed}
    except (TypeError, ValueError):
        raise ValueError("模型参数必须为数值。") from None
    if any(not isfinite(value) for value in parameter_values.values()):
        raise ValueError("模型参数不能为 NaN 或无穷大。")
    parameters = ModelParameters(**parameter_values)
    cell = CellCulture(cell_data["profile_key"], volume, area, cell_data.get("initial_viable_cells"), parameters)
    mapping = {"glucose_mM":"glucose_mm","glutamine_mM":"glutamine_mm","lactate_mM":"lactate_mm","oxygen_percent":"oxygen_percent","oxygen_setpoint_percent":"oxygen_setpoint_percent","pH":"ph","temperature_C":"temperature_c","CO2_percent":"co2_percent","osmolality_mOsm_kg":"osmolality_mosm_kg","drug_uM":"drug_um"}
    for key, attr in mapping.items():
        if key not in env: raise ValueError("场景环境缺少字段：" + key)
        try:
            value = float(env[key])
            if not isfinite(value):
                raise ValueError(f"环境字段 {key} 不能为 NaN 或无穷大。")
            setattr(cell, attr, value)
        except (TypeError, ValueError):
            raise ValueError(f"环境字段 {key} 必须为数值。") from None
    return cell, data
