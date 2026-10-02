"""单细胞实验室与微型细胞群场景的可读、可校验 JSON 格式。"""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
from math import isfinite
from typing import Any

from intracellular import IntracellularState
from microcolony import MicrocolonyState, RepresentativeCell
from microenvironment import MicroenvironmentState
from version import MODEL_VERSION

SINGLE_SCHEMA = "e-cell-single-cell/v1"
COLONY_SCHEMA = "e-cell-microcolony/v1"
_LEGACY_ENVIRONMENT_EVENT_LIMITS = {
    "local_oxygen_availability": (0.0, 1.0),
    "glucose_mM": (0.0, 100.0), "glucose_reference_mM": (1e-6, 100.0),
    "lactate_mM": (0.0, 200.0), "pH": (5.5, 9.0),
    "temperature_C": (0.0, 50.0), "drug_uM": (0.0, 1e6),
    "local_confluence_percent": (0.0, 100.0),
}
_ENVIRONMENT_EVENT_LIMITS = {
    **_LEGACY_ENVIRONMENT_EVENT_LIMITS,
    "doubling_time_h": (1.0, 500.0),
    "drug_ic50_uM": (1e-6, 1e6),
}
_ENVIRONMENT_SNAPSHOT_KEYS = {"time_h", *_ENVIRONMENT_EVENT_LIMITS}
_LEGACY_ENVIRONMENT_SNAPSHOT_KEYS = {"time_h", *_LEGACY_ENVIRONMENT_EVENT_LIMITS}
LIMITATION = (
    "场景记录经验模型假设和代表性相对指数；不是实验原始记录、空间成像、"
    "真实细胞通信测量、GLP/GMP 审计追踪或临床文档。"
)


def add_traceability_fields(
    rows: list[dict], *, evidence_level: str, limitation: str = LIMITATION,
) -> list[dict[str, Any]]:
    """为导出轨迹附加版本、证据等级、环境记录状态和解释边界。"""

    environment_fields = set(_LEGACY_ENVIRONMENT_EVENT_LIMITS)
    full_environment_fields = set(_ENVIRONMENT_EVENT_LIMITS)
    history_starts_at_zero = bool(rows) and abs(float(rows[0].get("time_h", -1.0))) <= 1e-9
    history_start = rows[0].get("time_h") if rows else None
    result = []
    for row in rows:
        item = {
            **row,
            "model_version": MODEL_VERSION,
            "evidence_level": evidence_level,
            "limitations": limitation,
            "history_starts_at_zero": history_starts_at_zero,
            "history_window_truncated": bool(rows) and not history_starts_at_zero,
            "history_start_time_h": history_start,
        }
        item["environment_recorded"] = environment_fields.issubset(row)
        item["environment_inputs_complete"] = full_environment_fields.issubset(row)
        result.append(item)
    return result


def single_cell_history_row(
    state: IntracellularState, environment: MicroenvironmentState,
) -> dict[str, Any]:
    """合并单细胞状态与该时点环境快照；所有环境值保留原单位/代理含义。"""

    row = {**state.snapshot(), **environment.snapshot()}
    row["environment_time_h"] = environment.time_h
    row["time_h"] = state.time_h
    row["environment_recorded"] = True
    row["environment_inputs_complete"] = True
    return row


def environment_change_event(
    previous: dict[str, float], current: MicroenvironmentState, time_h: float,
) -> dict[str, Any] | None:
    """把用户环境改动记录成事件；只记录发生变化的字段及前后值。"""

    latest = current.snapshot()
    changes = {
        key: {"from": float(value), "to": float(latest[key])}
        for key, value in previous.items()
        if key in latest and key != "time_h" and float(value) != float(latest[key])
    }
    if not changes:
        return None
    return {
        "time_h": float(time_h),
        "event": "微环境输入变更",
        "event_type": "environment_update",
        "changes": changes,
    }


def _created_at() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def export_single_cell_scenario(
    environment: MicroenvironmentState,
    state: IntracellularState,
    history: list[dict],
    events: list[dict],
) -> dict[str, Any]:
    """导出单细胞当前状态、保留历史与事件，不包含用户上传原始 CSV。"""

    environment_data = asdict(environment)
    environment_data["time_h"] = state.time_h
    history_data = deepcopy(history)
    history_starts_at_zero = bool(history) and abs(float(history[0].get("time_h", -1.0))) <= 1e-9
    return {
        "schema": SINGLE_SCHEMA,
        "model_version": MODEL_VERSION,
        "created_at": _created_at(),
        "evidence_level": {"environment_state": "B", "weights_thresholds": "C"},
        "environment": environment_data,
        # 不把因会话长度限制而保留的首条历史误称为初始状态。
        "initial_state": history_data[0] if history_starts_at_zero else None,
        "first_recorded_state": history_data[0] if history_data else None,
        "history_starts_at_zero": history_starts_at_zero,
        "history_window_truncated": bool(history) and not history_starts_at_zero,
        "history_start_time_h": history[0].get("time_h") if history else None,
        "current_state": asdict(state),
        "history": history_data,
        "events": deepcopy(events),
        "limitations": LIMITATION,
    }


def import_single_cell_scenario(payload: bytes | str | dict) -> tuple[MicroenvironmentState, IntracellularState, list[dict], list[dict]]:
    """校验并恢复单细胞场景；非法格式抛出可读 ``ValueError``。"""

    data = _decode(payload)
    _check_common(data, SINGLE_SCHEMA)
    try:
        env = _environment_from_mapping(data["environment"])
        state = _state_from_mapping(data["current_state"])
        if abs(env.time_h - state.time_h) > 1e-6:
            raise ValueError("当前微环境时间与单细胞状态时间不一致。")
        history = _validate_rows(data.get("history", []), maximum=25_000)
        if history:
            _validate_single_history(history, state)
        starts_at_zero = bool(history) and abs(float(history[0]["time_h"])) <= 1e-9
        _validate_history_window_metadata(
            data, history, starts_at_zero,
            float(history[0]["time_h"]) if history else None,
        )
        events = _validate_events(data.get("events", []), final_time=state.time_h)
    except (TypeError, KeyError, ValueError) as exc:
        raise ValueError(f"单细胞场景字段无效：{exc}") from None
    if not history:
        history = [state.snapshot()]
    return env, state, history, events


def export_microcolony_scenario(colony: MicrocolonyState, environment: MicroenvironmentState) -> dict[str, Any]:
    """导出微群体初始差异、当前状态和所选细胞时间线。"""

    environment_data = asdict(environment)
    environment_data["time_h"] = colony.time_h
    initial_cell_ids = {
        int(row["cell_id"]) for row in colony.history
        if abs(float(row.get("time_h", -1.0))) <= 1e-9
    }
    history_starts_at_zero = initial_cell_ids == {cell.cell_id for cell in colony.cells}
    return {
        "schema": COLONY_SCHEMA,
        "model_version": MODEL_VERSION,
        "created_at": _created_at(),
        "evidence_level": {"shared_environment": "B", "heterogeneity_and_communication": "C"},
        "environment": environment_data,
        "cell_count": len(colony.cells),
        "communication_enabled": bool(colony.communication_enabled),
        "time_h": colony.time_h,
        "cells": [
            {
                "cell_id": cell.cell_id, "x": cell.x, "y": cell.y,
                "baseline_offset": cell.baseline_offset,
                "local_signal_index": cell.local_signal_index,
                "state": asdict(cell.state),
            }
            for cell in colony.cells
        ],
        "history": deepcopy(colony.history),
        "history_starts_at_zero": history_starts_at_zero,
        "history_window_truncated": bool(colony.history) and not history_starts_at_zero,
        "history_start_time_h": min(
            (float(row["time_h"]) for row in colony.history), default=None,
        ),
        "limitations": LIMITATION,
    }


def truncate_microcolony_scenario_history(
    payload: dict[str, Any], maximum_rows: int,
) -> dict[str, Any]:
    """为短期运行状态保存裁剪微群体轨迹，并同步重算窗口元数据。"""

    if type(maximum_rows) is not int or maximum_rows < 1:
        raise ValueError("maximum_rows 必须是正整数。")
    result = deepcopy(payload)
    rows = result.get("history", [])
    if not isinstance(rows, list):
        raise ValueError("微群体 history 必须是列表。")
    cell_count = len(result.get("cells", []))
    if cell_count == 0 or maximum_rows < cell_count:
        raise ValueError("maximum_rows 至少要容纳一个完整微群体时点。")
    complete_rows = (maximum_rows // cell_count) * cell_count
    if len(rows) > complete_rows:
        rows = rows[-complete_rows:]
        result["history_truncated_for_runtime"] = True
    all_cell_ids = {int(item["cell_id"]) for item in result.get("cells", [])}
    if rows:
        first_time = float(rows[0]["time_h"])
        first_ids = {
            int(row["cell_id"]) for row in rows
            if abs(float(row["time_h"]) - first_time) <= 1e-9
        }
        if first_ids != all_cell_ids:
            rows = [row for row in rows if float(row["time_h"]) > first_time + 1e-9]
            result["history_truncated_for_runtime"] = True
    result["history"] = rows
    initial_cell_ids = {
        int(row["cell_id"])
        for row in rows
        if abs(float(row.get("time_h", -1.0))) <= 1e-9
    }
    starts_at_zero = bool(rows) and initial_cell_ids == all_cell_ids
    result["history_starts_at_zero"] = starts_at_zero
    result["history_window_truncated"] = bool(rows) and not starts_at_zero
    result["history_start_time_h"] = min(
        (float(row["time_h"]) for row in rows), default=None,
    )
    return result


def import_microcolony_scenario(payload: bytes | str | dict) -> tuple[MicrocolonyState, MicroenvironmentState]:
    """校验并恢复 3–50 个细胞的教学性微群体场景。"""

    data = _decode(payload)
    _check_common(data, COLONY_SCHEMA)
    try:
        raw_count = data["cell_count"]
        if type(raw_count) is not int:
            raise ValueError("cell_count 必须是整数。")
        count = raw_count
        if not 3 <= count <= 50:
            raise ValueError("代表性细胞数量必须为 3–50。")
        raw_cells = data["cells"]
        if not isinstance(raw_cells, list) or len(raw_cells) != count:
            raise ValueError("细胞列表数量与 cell_count 不一致。")
        env = _environment_from_mapping(data["environment"])
        time_h = _finite(data["time_h"], "time_h")
        if time_h < 0:
            raise ValueError("模拟时间不能为负数。")
        if abs(env.time_h - time_h) > 1e-6:
            raise ValueError("当前微环境时间与微群体模拟时间不一致。")
        cells = []
        seen_ids: set[int] = set()
        for item in raw_cells:
            raw_cell_id = item["cell_id"]
            if type(raw_cell_id) is not int or not 1 <= raw_cell_id <= 50:
                raise ValueError("cell_id 必须是 1–50 范围内的整数。")
            cell_id = raw_cell_id
            if cell_id in seen_ids:
                raise ValueError("代表性细胞编号不得重复。")
            seen_ids.add(cell_id)
            x, y = _finite(item["x"], "x"), _finite(item["y"], "y")
            if not 0 <= x <= 7 or not 0 <= y <= 6:
                raise ValueError("二维排版坐标超出允许范围。")
            offset = _finite(item["baseline_offset"], "baseline_offset")
            signal = _finite(item["local_signal_index"], "local_signal_index")
            if not 0 <= signal <= 100 or abs(offset) > 10:
                raise ValueError("初始差异或局部信号超出允许范围。")
            cells.append(RepresentativeCell(
                cell_id, x, y,
                _state_from_mapping(item["state"]), offset, signal,
            ))
            if abs(cells[-1].state.time_h - time_h) > 1e-6:
                raise ValueError("细胞状态时间与微群体模拟时间不一致。")
        history = _validate_rows(data.get("history", []), maximum=25_000)
        if history:
            _validate_colony_history(history, seen_ids, time_h)
        initial_cell_ids = {
            int(row["cell_id"]) for row in history
            if abs(float(row["time_h"])) <= 1e-9
        }
        starts_at_zero = initial_cell_ids == seen_ids
        _validate_history_window_metadata(
            data, history, starts_at_zero,
            min((float(row["time_h"]) for row in history), default=None),
        )
        enabled = data["communication_enabled"]
        if not isinstance(enabled, bool):
            raise ValueError("communication_enabled 必须是布尔值。")
        colony = MicrocolonyState(
            cell_count=count,
            communication_enabled=enabled,
            time_h=time_h,
            cells=cells,
            history=history,
        )
    except (TypeError, KeyError, ValueError) as exc:
        raise ValueError(f"微型细胞群场景字段无效：{exc}") from None
    return colony, env


def _decode(payload: bytes | str | dict) -> dict:
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8-sig")
    data = json.loads(payload) if isinstance(payload, str) else payload
    if not isinstance(data, dict):
        raise ValueError("场景根节点必须是 JSON 对象。")
    return data


def _check_common(data: dict, schema: str) -> None:
    if data.get("schema") != schema:
        raise ValueError("不支持的场景格式版本。")
    model_version = data.get("model_version")
    if not model_version:
        raise ValueError("场景缺少 model_version。")
    if model_version != MODEL_VERSION:
        raise ValueError(
            f"场景模型版本为 v{model_version}，当前为 v{MODEL_VERSION}；"
            "为避免将旧状态按新规则继续推进，请使用相同模型版本导入。"
        )
    if not data.get("created_at"):
        raise ValueError("场景缺少 created_at。")


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} 必须是数值，不能是布尔值。")
    value = float(value)
    if not isfinite(value):
        raise ValueError(f"{name} 必须是有限数值。")
    return value


def _validate_history_environment(row: dict, label: str) -> None:
    """验证历史行中的可选环境快照；状态-only旧记录仍可读取。"""

    expected_fields = set(_LEGACY_ENVIRONMENT_EVENT_LIMITS)
    present = expected_fields.intersection(row)
    if present and present != expected_fields:
        raise ValueError(f"{label}环境快照字段不完整。")
    recorded = present == expected_fields
    optional_fields = set(_ENVIRONMENT_EVENT_LIMITS) - expected_fields
    optional_present = optional_fields.intersection(row)
    if optional_present and (not recorded or optional_present != optional_fields):
        raise ValueError(f"{label}环境模型输入字段不完整。")
    inputs_complete = recorded and optional_present == optional_fields
    if "environment_time_h" in row:
        if not recorded:
            raise ValueError(f"{label}含环境时间但缺少完整环境快照。")
        environment_time = _finite(row["environment_time_h"], f"{label}.environment_time_h")
        state_time = _finite(row.get("time_h"), f"{label}.time_h")
        if abs(environment_time - state_time) > 1e-6:
            raise ValueError(f"{label}环境快照时间与状态时间不一致。")
    if "environment_recorded" in row:
        if type(row["environment_recorded"]) is not bool or row["environment_recorded"] is not recorded:
            raise ValueError(f"{label} environment_recorded 标记与实际字段不一致。")
    if "environment_inputs_complete" in row:
        if type(row["environment_inputs_complete"]) is not bool or row["environment_inputs_complete"] is not inputs_complete:
            raise ValueError(f"{label} environment_inputs_complete 标记与实际字段不一致。")
    if not recorded:
        return
    for field, (low, high) in _ENVIRONMENT_EVENT_LIMITS.items():
        if field not in row:
            continue
        value = _finite(row[field], f"{label}.{field}")
        if not low <= value <= high:
            raise ValueError(f"{label}环境字段 {field} 超出允许范围 {low}–{high}。")


def _validate_history_window_metadata(
    payload: dict, history: list[dict], starts_at_zero: bool,
    start_time_h: float | None,
) -> None:
    """若场景包含历史窗口声明，检查它是否与实际轨迹一致。"""

    expected_truncated = bool(history) and not starts_at_zero
    for key, expected in (
        ("history_starts_at_zero", starts_at_zero),
        ("history_window_truncated", expected_truncated),
    ):
        if key in payload and (type(payload[key]) is not bool or payload[key] is not expected):
            raise ValueError(f"{key} 与历史记录不一致。")
    if "history_start_time_h" in payload:
        actual = payload["history_start_time_h"]
        if start_time_h is None:
            if actual is not None:
                raise ValueError("history_start_time_h 与空历史不一致。")
        elif abs(_finite(actual, "history_start_time_h") - start_time_h) > 1e-6:
            raise ValueError("history_start_time_h 与历史记录不一致。")
    if "initial_state" in payload:
        expected_initial = history[0] if starts_at_zero and history else None
        if payload["initial_state"] != expected_initial:
            raise ValueError("initial_state 与历史起点不一致。")
    if "first_recorded_state" in payload:
        expected_first = history[0] if history else None
        if payload["first_recorded_state"] != expected_first:
            raise ValueError("first_recorded_state 与历史记录不一致。")


def _state_from_mapping(values: dict) -> IntracellularState:
    allowed = IntracellularState.__dataclass_fields__
    missing = set(allowed).difference(values)
    if missing:
        raise ValueError("细胞状态缺少字段：" + "、".join(sorted(missing)))
    cleaned = dict(values)
    for key in allowed:
        if key == "cycle_phase":
            continue
        cleaned[key] = _finite(cleaned[key], key)
    state = IntracellularState(**{key: cleaned[key] for key in allowed})
    if any(not 0 <= float(getattr(state, key)) <= 100 for key in (
        "atp_percent", "mitochondrial_potential_percent", "glycolysis_percent",
        "ros_percent", "dna_damage_percent", "er_stress_percent", "autophagy_percent",
        "protein_synthesis_percent", "growth_signal_percent", "apoptosis_signal_percent",
        "cycle_progress_percent",
    )):
        raise ValueError("细胞相对指数必须位于 0–100。")
    if not 50 <= state.cytosolic_calcium_nm <= 1200 or state.time_h < 0:
        raise ValueError("钙代理或时间超出允许范围。")
    if state.cycle_phase not in {"G1", "S", "G2", "M"}:
        raise ValueError("未知细胞周期阶段。")
    return state


def _environment_from_mapping(values: dict) -> MicroenvironmentState:
    """拒绝越界环境，避免导入时静默裁剪成另一组实验条件。"""

    if not isinstance(values, dict):
        raise ValueError("environment 必须是对象。")
    allowed = MicroenvironmentState.__dataclass_fields__
    missing = set(allowed).difference(values)
    if missing:
        raise ValueError("微环境缺少字段：" + "、".join(sorted(missing)))
    limits = {
        "time_h": (0, 1e7), "local_oxygen_availability": (0, 1),
        "glucose_mm": (0, 100), "glucose_reference_mm": (1e-6, 100),
        "lactate_mm": (0, 200), "ph": (5.5, 9), "temperature_c": (0, 50),
        "drug_um": (0, 1e6), "local_confluence_percent": (0, 100),
        "doubling_time_h": (1, 500), "drug_ic50_um": (1e-6, 1e6),
    }
    clean: dict[str, float] = {}
    for key, (low, high) in limits.items():
        value = _finite(values[key], key)
        if not low <= value <= high:
            raise ValueError(f"微环境字段 {key} 超出允许范围 {low}–{high}。")
        clean[key] = value
    return MicroenvironmentState(**clean)


def _validate_rows(rows: Any, maximum: int) -> list[dict]:
    if not isinstance(rows, list) or len(rows) > maximum:
        raise ValueError("历史/事件列表格式错误或条目过多。")
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError("历史/事件列表必须由对象组成。")
    return rows


_HISTORY_INDEX_FIELDS = (
    "ATP_percent", "mitochondrial_potential_percent", "glycolysis_percent",
    "ROS_percent", "DNA_damage_percent", "ER_stress_percent", "autophagy_percent",
    "protein_synthesis_percent", "growth_signal_percent", "apoptosis_signal_percent",
    "cycle_progress_percent",
)


def _validate_single_history(rows: list[dict], state: IntracellularState) -> None:
    previous_time = -1.0
    for row in rows:
        _validate_history_environment(row, "单细胞历史")
        time_h = _finite(row.get("time_h"), "history.time_h")
        if time_h < previous_time or time_h < 0:
            raise ValueError("单细胞历史时间必须非负且单调不减。")
        previous_time = time_h
        for key in _HISTORY_INDEX_FIELDS:
            value = _finite(row.get(key), f"history.{key}")
            if not 0 <= value <= 100:
                raise ValueError(f"历史指标 {key} 超出 0–100。")
        calcium = _finite(row.get("calcium_nM"), "history.calcium_nM")
        if not 50 <= calcium <= 1200:
            raise ValueError("历史钙代理超出 50–1200 nM。")
        cycle = row.get("cycle_phase")
        if cycle not in {"G1", "S", "G2", "M"}:
            raise ValueError("历史记录中的细胞周期阶段无效。")
    if abs(previous_time - state.time_h) > 1e-6:
        raise ValueError("单细胞当前状态时间与历史末时点不一致。")


def _validate_events(rows: Any, final_time: float) -> list[dict]:
    events = _validate_rows(rows, maximum=10_000)
    previous_time = -1.0
    for row in events:
        if "time_h" not in row or not isinstance(row.get("event"), str):
            raise ValueError("事件记录必须包含 time_h 与文字 event。")
        time_h = _finite(row["time_h"], "event.time_h")
        if not 0 <= time_h <= final_time:
            raise ValueError("事件时间必须位于当前单细胞模拟时段内。")
        if time_h < previous_time:
            raise ValueError("单细胞事件必须按记录顺序保持时间单调不减。")
        previous_time = time_h
        if row.get("event_type") == "environment_update":
            changes = row.get("changes")
            if not isinstance(changes, dict) or not changes:
                raise ValueError("微环境变更事件必须包含 changes 对象。")
            for field, values in changes.items():
                if field not in _ENVIRONMENT_EVENT_LIMITS:
                    raise ValueError(f"未知的微环境变更字段：{field}。")
                if not isinstance(values, dict) or not {"from", "to"}.issubset(values):
                    raise ValueError(f"微环境变更字段 {field} 必须包含 from 与 to。")
                low, high = _ENVIRONMENT_EVENT_LIMITS[field]
                before = _finite(values["from"], f"{field}.from")
                after = _finite(values["to"], f"{field}.to")
                if not low <= before <= high or not low <= after <= high:
                    raise ValueError(f"微环境变更字段 {field} 超出允许范围 {low}–{high}。")
                if before == after:
                    raise ValueError(f"微环境变更字段 {field} 的前后值不能相同。")
        if row.get("event_type") == "environment_load" and row.get("source") != "culture_workflow":
            raise ValueError("环境载入事件的 source 无效。")
        if row.get("event_type") == "oxidative_stress":
            intensity = _finite(row.get("input_index"), "event.input_index")
            if not 0 <= intensity <= 100:
                raise ValueError("教学压力输入指数必须位于 0–100。")
            snapshot = row.get("environment")
            if snapshot is not None:
                if not isinstance(snapshot, dict) or set(snapshot) not in (
                    _ENVIRONMENT_SNAPSHOT_KEYS, _LEGACY_ENVIRONMENT_SNAPSHOT_KEYS,
                ):
                    raise ValueError("干预事件中的微环境快照字段不完整或包含未知字段。")
                if abs(_finite(snapshot["time_h"], "event.environment.time_h") - time_h) > 1e-6:
                    raise ValueError("干预事件时间与环境快照时间不一致。")
                for field, (low, high) in _ENVIRONMENT_EVENT_LIMITS.items():
                    if field not in snapshot:
                        continue
                    value = _finite(snapshot[field], f"event.environment.{field}")
                    if not low <= value <= high:
                        raise ValueError(f"干预事件环境字段 {field} 超出允许范围 {low}–{high}。")
    return events


def _validate_colony_history(rows: list[dict], cell_ids: set[int], final_time: float) -> None:
    previous_time = -1.0
    latest_by_cell: dict[int, dict] = {}
    seen_pairs: set[tuple[float, int]] = set()
    for row in rows:
        _validate_history_environment(row, "微群体历史")
        time_h = _finite(row.get("time_h"), "history.time_h")
        try:
            cell_id = int(row.get("cell_id"))
        except (TypeError, ValueError):
            raise ValueError("微群体历史缺少有效 cell_id。") from None
        if time_h < previous_time or not 0 <= time_h <= final_time or cell_id not in cell_ids:
            raise ValueError("微群体历史时间顺序、范围或 cell_id 无效。")
        pair = (time_h, cell_id)
        if pair in seen_pairs:
            raise ValueError("同一时间点的代表性细胞历史不得重复。")
        seen_pairs.add(pair)
        previous_time = time_h
        subgroup = row.get("subgroup")
        if subgroup not in {"稳态", "代谢压力", "氧化应激", "促凋亡压力"}:
            raise ValueError("微群体历史子群标签无效。")
        if "communication_enabled" in row and not isinstance(row["communication_enabled"], bool):
            raise ValueError("微群体历史通信开关必须是布尔值。")
        layout_x = _finite(row.get("layout_x"), "history.layout_x")
        layout_y = _finite(row.get("layout_y"), "history.layout_y")
        if not 0 <= layout_x <= 7 or not 0 <= layout_y <= 6:
            raise ValueError("微群体历史排版坐标超出范围。")
        for key in _HISTORY_INDEX_FIELDS:
            value = _finite(row.get(key), f"history.{key}")
            if not 0 <= value <= 100:
                raise ValueError(f"历史指标 {key} 超出 0–100。")
        calcium = _finite(row.get("calcium_nM"), "history.calcium_nM")
        if not 50 <= calcium <= 1200:
            raise ValueError("微群体历史钙代理超出 50–1200 nM。")
        latest_by_cell[cell_id] = row
    for cell_id, row in latest_by_cell.items():
        if abs(float(row["time_h"]) - final_time) > 1e-6:
            raise ValueError(f"代表性细胞 {cell_id} 的历史未到达当前微群体时间。")
    if latest_by_cell and set(latest_by_cell) != cell_ids:
        raise ValueError("微群体历史末时点必须包含全部代表性细胞。")
