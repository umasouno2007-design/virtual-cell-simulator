"""Scope transient Streamlit checkpoints to one browser session.

Files are convenience caches, not durable records or a cross-device account store.
"""

from hashlib import sha256
from math import isclose, isfinite
from pathlib import Path

from cell import CellCulture
from scenario import import_scenario
from version import MODEL_VERSION, SCENARIO_SCHEMA_VERSION


def clear_failed_restore(session_state) -> None:
    """Discard a partially applied transient checkpoint, preserving only schema identity."""

    for key in list(session_state.keys()):
        if key != "app_state_version":
            del session_state[key]


def session_state_path(base_path: Path, session_id: str | None) -> Path | None:
    """Return a per-session checkpoint path; never expose the raw session ID in a path."""

    if not session_id or session_id == "test session id":
        return None
    suffix = sha256(session_id.encode("utf-8")).hexdigest()[:24]
    return base_path.with_name(f"{base_path.stem}.{suffix}{base_path.suffix}")


def restore_culture_checkpoint(payload: dict) -> tuple[CellCulture, list[dict]]:
    """Validate a transient checkpoint before exposing any part of it to the UI."""

    if not isinstance(payload, dict):
        raise ValueError("运行检查点必须是 JSON 对象。")
    raw_cell = payload.get("cell")
    if not isinstance(raw_cell, dict) or not isinstance(payload.get("parameters"), dict):
        raise ValueError("运行检查点缺少培养状态或模型参数。")
    environment_fields = {
        "glucose_mM": "glucose_mm", "glutamine_mM": "glutamine_mm",
        "lactate_mM": "lactate_mm", "oxygen_percent": "oxygen_percent",
        "oxygen_setpoint_percent": "oxygen_setpoint_percent", "pH": "ph",
        "temperature_C": "temperature_c", "CO2_percent": "co2_percent",
        "osmolality_mOsm_kg": "osmolality_mosm_kg", "drug_uM": "drug_um",
    }
    resume_fields = (
        "time_h", "dead_cells", "energy_index", "last_growth_rate_per_h",
        "last_death_rate_per_h",
    )
    if any(name not in raw_cell for name in (*environment_fields.values(), *resume_fields)):
        raise ValueError("运行检查点缺少续跑所需的培养字段。")
    scenario_payload = {
        "schema": SCENARIO_SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "created_at": "runtime-checkpoint",
        "cell": {
            "profile_key": payload.get("profile_key"),
            "initial_viable_cells": raw_cell.get("viable_cells"),
            "culture_volume_ml": raw_cell.get("culture_volume_ml"),
            "surface_area_cm2": raw_cell.get("surface_area_cm2"),
        },
        "resume_state": {name: raw_cell[name] for name in resume_fields},
        "environment": {name: raw_cell[source] for name, source in environment_fields.items()},
        "parameters": payload["parameters"],
        "run": {"duration_h": 72, "dt_h": 1},
        "events": payload.get("scheduled_actions", []),
        "evidence_level": "runtime-checkpoint",
    }
    cell, _ = import_scenario(scenario_payload)
    history = payload.get("history")
    if not isinstance(history, list) or not history:
        raise ValueError("运行检查点缺少有效培养时间线。")
    expected = cell.snapshot()
    history_bounds = {
        "time_h": (0.0, None), "viable_cells": (0.0, None),
        "dead_cells": (0.0, None), "viability_percent": (0.0, 100.0),
        "confluence_percent": (0.0, 100.0), "glucose_mM": (0.0, None),
        "glutamine_mM": (0.0, None), "lactate_mM": (0.0, None),
        "oxygen_percent": (0.0, 21.0), "pH": (6.2, 8.0),
        "oxygen_setpoint_percent": (0.0, 21.0),
        "temperature_C": (0.0, 50.0), "CO2_percent": (0.0, 100.0),
        "osmolality_mOsm_kg": (0.0, 1000.0), "drug_uM": (0.0, None),
        "energy_index": (0.0, 100.0), "growth_rate_per_h": (0.0, None),
        "death_rate_per_h": (0.0, None),
    }
    previous_time = -1.0
    for row in history:
        if not isinstance(row, dict) or not set(expected).issubset(row):
            raise ValueError("运行检查点的培养时间线字段不完整。")
        if row["cell_type"] != cell.profile_key or row["model_version"] != MODEL_VERSION:
            raise ValueError("运行检查点的培养时间线与细胞系或模型版本不一致。")
        for name in expected:
            if name in {"cell_type", "model_version"}:
                continue
            value = row[name]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
                raise ValueError(f"运行检查点的时间线字段 {name} 非有限数值。")
            if name == "time_h" and value < 0:
                raise ValueError("运行检查点的培养时间线不是非负单调时间序列。")
            low, high = history_bounds[name]
            if value < low or (high is not None and value > high):
                raise ValueError(f"运行检查点的时间线字段 {name} 超出当前模型范围。")
        if row["time_h"] < 0 or row["time_h"] < previous_time:
            raise ValueError("运行检查点的培养时间线不是非负单调时间序列。")
        previous_time = row["time_h"]
    if abs(previous_time - cell.time_h) > 1e-6:
        raise ValueError("运行检查点的当前时钟与时间线末点不一致。")
    last_row = history[-1]
    for name, current in expected.items():
        if name in {"cell_type", "model_version"}:
            continue
        if not isclose(float(last_row[name]), float(current), rel_tol=1e-9, abs_tol=1e-6):
            raise ValueError(f"运行检查点的当前培养状态与时间线末点不一致：{name}。")
    return cell, history


def restore_runtime_clock(payload: dict, allowed_multipliers: set[int]) -> tuple[float, int]:
    """Validate the wall-clock anchor and speed before a saved run can catch up."""

    try:
        wall_time = payload["last_wall_time"]
        raw_multiplier = payload["time_multiplier"]
        if isinstance(wall_time, bool) or isinstance(raw_multiplier, bool):
            raise ValueError
        wall_time = float(wall_time)
        multiplier = int(raw_multiplier)
        if float(raw_multiplier) != multiplier:
            raise ValueError
    except (KeyError, TypeError, ValueError, OverflowError):
        raise ValueError("运行检查点的时钟或时间倍率无效。") from None
    if not isfinite(wall_time) or wall_time <= 0 or multiplier not in allowed_multipliers:
        raise ValueError("运行检查点的时钟或时间倍率超出有效范围。")
    return wall_time, multiplier
