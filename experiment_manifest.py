"""生成紧凑、可共享的实验配置快照。"""

from dataclasses import asdict
from datetime import datetime, timezone

from cell import CellCulture


def build_manifest(
    cell: CellCulture,
    *,
    app_version: str,
    preset_name: str,
    app_mode: str,
    time_multiplier: int,
    history: list[dict],
    events: list[dict],
    scheduled_actions: list[dict] | None = None,
    experiment_metadata: dict | None = None,
) -> dict:
    """返回 JSON 可序列化的配置，而非完整运行状态或上传原始数据。"""

    return {
        "schema": "e-cell-experiment-manifest/v1",
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "app_version": app_version,
        "experiment": {
            "profile_key": cell.profile_key,
            "preset_name": preset_name,
            "app_mode": app_mode,
            "time_multiplier": time_multiplier,
            "simulation_time_h": cell.time_h,
            "culture_volume_ml": cell.culture_volume_ml,
            "surface_area_cm2": cell.surface_area_cm2,
        },
        "environment": {
            "glucose_mM": cell.glucose_mm,
            "glutamine_mM": cell.glutamine_mm,
            "lactate_mM": cell.lactate_mm,
            "oxygen_percent": cell.oxygen_percent,
            "oxygen_setpoint_percent": cell.oxygen_setpoint_percent,
            "pH": cell.ph,
            "temperature_C": cell.temperature_c,
            "CO2_percent": cell.co2_percent,
            "osmolality_mOsm_kg": cell.osmolality_mosm_kg,
            "drug_uM": cell.drug_um,
        },
        "parameters": asdict(cell.parameters),
        "history_summary": {
            "point_count": len(history),
            "first_time_h": history[0].get("time_h") if history else None,
            "last_time_h": history[-1].get("time_h") if history else None,
        },
        "events": events,
        "scheduled_actions": scheduled_actions or [],
        "experiment_metadata": experiment_metadata or {},
        "limitations": "这是配置快照，不是经过实验验证的模型参数，也不包含原始实测文件。",
    }
