"""部署前无网页 smoke check：培养、单细胞、微群体与数据启发场景往返。"""

from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cell import CellCulture
from cell_scenario import (
    environment_change_event,
    export_microcolony_scenario,
    export_single_cell_scenario,
    import_microcolony_scenario,
    import_single_cell_scenario,
    single_cell_history_row,
)
from data_model_hypotheses import export_hypothesis_scenario_json, load_hypothesis_scenario
from experiment_manifest import build_manifest
from intracellular import IntracellularState
from intracellular_forecast import forecast_intracellular_state
from microcolony import MicrocolonyState
from microenvironment import MicroenvironmentState
from scenario import import_scenario
from scripts.validate_a549_teaching_case import run_case
from scripts.run_data_inspired_hypothesis import run_scenario as run_hypothesis_scenario
from virtual_assays import simulate_virtual_assay


def _single_cell_run() -> tuple[IntracellularState, MicroenvironmentState, list[dict], list[dict]]:
    environment = MicroenvironmentState(local_oxygen_availability=0.65, glucose_mm=4.0)
    state = IntracellularState()
    history = [single_cell_history_row(state, environment)]
    events = []
    for hours in (1.0, 2.0, 1.0):
        state.step(environment, hours)
        environment.time_h = state.time_h
        history.append(single_cell_history_row(state, environment))
        if state.time_h == 1.0:
            previous = environment.snapshot()
            environment.local_oxygen_availability = 0.55
            events.append(environment_change_event(previous, environment, state.time_h))
    state.apply_oxidative_stress(20.0)
    history.append(single_cell_history_row(state, environment))
    events.append({
        "time_h": state.time_h,
        "event": "教学性氧化压力脉冲",
        "event_type": "oxidative_stress",
        "input_index": 20.0,
        "environment": environment.snapshot(),
    })
    return state, environment, history, events


def main() -> None:
    assert (ROOT / "data" / "a549_teaching_synthetic.csv").is_file()
    example_scene = ROOT / "data" / "example_a549_scenario.json"
    assert example_scene.is_file()
    restored_example, _ = import_scenario(example_scene.read_text(encoding="utf-8"))
    assert restored_example.profile_key == "a549"

    # 假设映射只读，不作参数拟合；下载场景须兼容既有单细胞导入器。
    hypothesis = load_hypothesis_scenario()
    assert hypothesis["evidence"]["model_mapping_grade"] == "C"
    assert hypothesis["evidence"]["parameter_calibration"] == "none"
    inspired_payload = export_hypothesis_scenario_json()
    _, inspired_state, inspired_history, inspired_events = import_single_cell_scenario(inspired_payload)
    assert inspired_history and inspired_events[0]["event_type"] == "oxidative_stress"
    assert inspired_state.ros_percent > IntracellularState().ros_percent
    with TemporaryDirectory() as output_dir:
        hypothesis_json, hypothesis_csv = run_hypothesis_scenario(Path(output_dir))
        assert hypothesis_json.is_file() and hypothesis_json.stat().st_size > 0
        assert hypothesis_csv.is_file() and hypothesis_csv.stat().st_size > 0

    # 原培养动力学和实验清单仍可运行。
    culture = CellCulture("a549")
    culture.step(1)
    assert culture.snapshot()["time_h"] == 1
    manifest = build_manifest(
        culture,
        app_version="smoke",
        preset_name="标准培养",
        app_mode="培养环境与数据工作流",
        time_multiplier=60,
        history=[culture.snapshot()],
        events=[],
    )
    assert manifest["experiment"]["profile_key"] == "a549"
    assert run_case(output_dir=None)["validation_metrics"]

    # 相同环境与步长必须产生确定性相同结果，且场景状态可往返恢复。
    first_state, first_env, first_history, first_events = _single_cell_run()
    second_state, _, _, _ = _single_cell_run()
    assert first_state.snapshot() == second_state.snapshot()
    single_payload = export_single_cell_scenario(first_env, first_state, first_history, first_events)
    restored_env, restored_state, restored_history, restored_events = import_single_cell_scenario(single_payload)
    assert restored_state.snapshot() == first_state.snapshot()
    assert restored_env.time_h == first_env.time_h
    assert restored_history == first_history
    assert restored_events == first_events
    assert single_payload["history_starts_at_zero"]
    assert all(row["environment_recorded"] for row in restored_history)
    first_state.step(first_env, 0.5)
    restored_state.step(restored_env, 0.5)
    assert first_state.snapshot() == restored_state.snapshot()

    # 微型群体与其场景 schema 在无 Streamlit 界面时也能工作。
    colony = MicrocolonyState(cell_count=8, communication_enabled=True)
    colony_env = MicroenvironmentState(local_oxygen_availability=0.5, glucose_mm=3.0)
    for _ in range(3):
        colony.step(colony_env, 1.0)
    assert colony.finite()
    subgroup_trajectory = colony.subgroup_trajectory()
    for time_h in {row["time_h"] for row in subgroup_trajectory}:
        rows = [row for row in subgroup_trajectory if row["time_h"] == time_h]
        assert len(rows) == 4
        assert abs(sum(row["占该时点记录比例（%）"] for row in rows) - 100.0) < 1e-9
    colony_payload = export_microcolony_scenario(colony, colony_env)
    restored_colony, _ = import_microcolony_scenario(colony_payload)
    assert restored_colony.summary() == colony.summary()
    assert restored_colony.history == colony.history

    # 次级教学工具只消费复制的相对状态；其输出须可在无网页环境中生成。
    forecast = forecast_intracellular_state(
        CellCulture("a549"), IntracellularState(),
        attribute="oxygen_percent", value=5.0, horizon_h=1.0,
    )
    assert forecast["completed_h"] == 1.0
    assert forecast["candidate_state"]["ATP_percent"] >= 0.0
    assay = simulate_virtual_assay(
        "atp_luminescence", IntracellularState().snapshot(), replicates=2, seed=1,
    )
    assert len(assay) == 2 and all(row["is_synthetic_demo"] for row in assay)

    print("smoke check passed")


if __name__ == "__main__":
    main()
