"""Scope transient Streamlit checkpoints to one browser session.

Files are convenience caches, not durable records or a cross-device account store.
"""

from hashlib import sha256
from math import isclose, isfinite
from pathlib import Path

from cell import CellCulture
from cell_communication import CellCommunicationState
from intracellular import IntracellularState
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


def restore_representative_checkpoint(
    payload: dict, *, culture_time_h: float | None = None,
) -> tuple[IntracellularState, list[dict], CellCommunicationState, list[dict]]:
    """Validate relative teaching states and their saved endpoints before UI restore."""

    def finite_number(value: object, name: str, low: float, high: float) -> float:
        if isinstance(value, bool):
            raise ValueError(f"运行检查点的 {name} 不是有效数值。")
        try:
            numeric = float(value)
        except (TypeError, ValueError, OverflowError):
            raise ValueError(f"运行检查点的 {name} 不是有效数值。") from None
        if not isfinite(numeric) or not low <= numeric <= high:
            raise ValueError(f"运行检查点的 {name} 超出允许范围。")
        return numeric

    raw_cell = payload.get("intracellular")
    raw_communication = payload.get("cell_communication")
    if not isinstance(raw_cell, dict) or not isinstance(raw_communication, dict):
        raise ValueError("运行检查点缺少细胞内或通信状态。")
    cell_fields = IntracellularState.__dataclass_fields__
    communication_fields = CellCommunicationState.__dataclass_fields__
    if not set(cell_fields).issubset(raw_cell) or not set(communication_fields).issubset(raw_communication):
        raise ValueError("运行检查点的代表性状态字段不完整。")
    clean_cell = {}
    for name in cell_fields:
        if name == "cycle_phase":
            phase = raw_cell[name]
            if phase not in {"G1", "S", "G2", "M"}:
                raise ValueError("运行检查点的细胞周期阶段无效。")
            clean_cell[name] = phase
        else:
            low, high = (50.0, 1200.0) if name == "cytosolic_calcium_nm" else (
                (0.0, 1e7) if name == "time_h" else (0.0, 100.0)
            )
            clean_cell[name] = finite_number(raw_cell[name], name, low, high)
    cell = IntracellularState(**clean_cell)
    if cell.cycle_phase != IntracellularState._phase_from_progress(cell.cycle_progress_percent):
        raise ValueError("运行检查点的细胞周期阶段与进度不一致。")
    clean_communication = {
        name: finite_number(raw_communication[name], name, 0.0, 1e7 if name == "time_h" else 100.0)
        for name in communication_fields
    }
    communication = CellCommunicationState(**clean_communication)
    if culture_time_h is not None and (
        not isclose(cell.time_h, culture_time_h, rel_tol=0.0, abs_tol=1e-6)
        or not isclose(communication.time_h, culture_time_h, rel_tol=0.0, abs_tol=1e-6)
    ):
        raise ValueError("运行检查点的代表性状态时钟与培养时钟不一致。")
    if not isclose(
        communication.resilient_fraction + communication.stressed_fraction + communication.injured_fraction,
        100.0, abs_tol=1e-6,
    ):
        raise ValueError("运行检查点的代表性子群比例不守恒。")

    def validate_history(rows: object, snapshot: dict, label: str) -> list[dict]:
        if not isinstance(rows, list) or not rows or any(not isinstance(row, dict) for row in rows):
            raise ValueError(f"运行检查点的{label}历史格式无效。")
        previous_time = -1.0
        for row in rows:
            if not set(snapshot).issubset(row):
                raise ValueError(f"运行检查点的{label}历史字段不完整。")
            time_h = finite_number(row["time_h"], f"{label}历史.time_h", 0.0, 1e7)
            if time_h < previous_time:
                raise ValueError(f"运行检查点的{label}历史时间不是单调序列。")
            previous_time = time_h
            for name in snapshot:
                if name == "time_h":
                    continue
                if name == "cycle_phase":
                    if row[name] not in {"G1", "S", "G2", "M"}:
                        raise ValueError(f"运行检查点的{label}历史周期阶段无效。")
                    if row[name] != IntracellularState._phase_from_progress(float(row["cycle_progress_percent"])):
                        raise ValueError(f"运行检查点的{label}历史周期阶段与进度不一致。")
                    continue
                low, high = (50.0, 1200.0) if name == "calcium_nM" else (0.0, 100.0)
                finite_number(row[name], f"{label}历史.{name}", low, high)
            if label == "通信" and not isclose(
                float(row["resilient_fraction"]) + float(row["stressed_fraction"])
                + float(row["injured_fraction"]), 100.0, abs_tol=1e-6,
            ):
                raise ValueError("运行检查点的历史子群比例不守恒。")
        last = rows[-1]
        for name, expected in snapshot.items():
            if name not in last:
                raise ValueError(f"运行检查点的{label}历史末点缺少 {name}。")
            if isinstance(expected, str):
                matches = last[name] == expected
            else:
                actual = finite_number(last[name], f"{label}历史末点.{name}", 0.0, 1e7)
                matches = isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-6)
            if not matches:
                raise ValueError(f"运行检查点的{label}历史末点与当前状态不一致：{name}。")
        return rows

    cell_history = validate_history(payload.get("intracellular_history"), cell.snapshot(), "细胞内")
    communication_history = validate_history(
        payload.get("cell_communication_history"), communication.snapshot(), "通信",
    )
    return cell, cell_history, communication, communication_history
