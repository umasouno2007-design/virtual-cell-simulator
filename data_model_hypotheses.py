"""只读的公开数据—模型假设映射与教学场景导出。"""

from __future__ import annotations

import json
from math import isfinite
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from cell_scenario import export_single_cell_scenario, single_cell_history_row
from intracellular import IntracellularState
from microenvironment import MicroenvironmentState
from version import MODEL_VERSION

SCENARIO_PATH = Path(__file__).resolve().parent / "data" / "scenarios" / "oral_periodontitis_oxidative_stress_teaching.json"
REQUIRED_SCENARIO_FIELDS = {
    "schema", "id", "title", "model_version", "source_data", "observed_pattern",
    "teaching_hypothesis", "teaching_scenario", "evidence", "not_calibrated",
    "not_inferable", "limitations",
}
ENVIRONMENT_RANGES = {
    "time_h": (0.0, 100_000.0),
    "local_oxygen_availability": (0.0, 1.0),
    "glucose_mM": (0.0, 100.0),
    "glucose_reference_mM": (1e-6, 100.0),
    "lactate_mM": (0.0, 200.0),
    "pH": (5.5, 9.0),
    "temperature_C": (0.0, 50.0),
    "drug_uM": (0.0, 1e6),
    "local_confluence_percent": (0.0, 100.0),
    "doubling_time_h": (1.0, 500.0),
    "drug_ic50_uM": (1e-6, 1e6),
}
LOCAL_MAPPING_TOP_LEVEL_FIELDS = {
    "schema", "status", "notice", "source", "observations", "model_mapping",
}
LOCAL_MAPPING_SOURCE_FIELDS = {
    "dataset_accession", "study_citation", "sample_accessions", "tissue_and_condition",
    "analysis_repository_or_protocol", "analysis_version_or_commit",
    "cell_annotation_method_and_version", "pathway_gene_set_and_version",
    "statistical_unit", "source_checked_date",
}
LOCAL_MAPPING_OBSERVATION_FIELDS = {
    "cell_type", "comparison", "marker_genes", "pathway_score_name",
    "pathway_score_method", "reported_direction", "reported_value",
    "reported_unit", "uncertainty_or_adjusted_p_value", "data_location",
}
LOCAL_MAPPING_MODEL_FIELDS = {
    "question_only", "existing_ecell_scenario_id", "mapping_evidence_grade",
    "parameter_calibration_allowed", "unmeasured_model_quantities", "not_inferable",
}


def validate_local_hypothesis_mapping(payload: Any) -> dict[str, Any]:
    """Validate a local observation-to-hypothesis record without model fitting.

    The mapping file may contain aggregate result summaries and provenance, but
    this validator never reads expression matrices or forwards observations to
    model parameters. It returns a sanitized summary, not the submitted text.
    """

    if not isinstance(payload, dict):
        raise ValueError("映射文件顶层必须是 JSON 对象。")
    if set(payload) != LOCAL_MAPPING_TOP_LEVEL_FIELDS:
        missing = LOCAL_MAPPING_TOP_LEVEL_FIELDS - payload.keys()
        extra = payload.keys() - LOCAL_MAPPING_TOP_LEVEL_FIELDS
        details = []
        if missing:
            details.append(f"缺少字段：{', '.join(sorted(missing))}")
        if extra:
            details.append(f"不支持的字段：{', '.join(sorted(extra))}；原始矩阵/额外数据不得放入映射文件")
        raise ValueError("映射文件字段不符合模板：" + "；".join(details) + "。")
    if payload.get("schema") != "e-cell-local-data-hypothesis/v1":
        raise ValueError("不支持的本地映射格式版本。")
    status = payload.get("status")
    if status not in {"template_only", "local_analysis_record"}:
        raise ValueError("status 只能是 template_only 或 local_analysis_record。")
    if not isinstance(payload.get("notice"), str) or not payload["notice"].strip():
        raise ValueError("notice 必须保留隐私与证据边界说明。")

    source = payload.get("source")
    model = payload.get("model_mapping")
    observations = payload.get("observations")
    if not isinstance(source, dict) or set(source) != LOCAL_MAPPING_SOURCE_FIELDS:
        raise ValueError("source 必须且只能包含模板定义的来源字段。")
    if not isinstance(model, dict) or set(model) != LOCAL_MAPPING_MODEL_FIELDS:
        raise ValueError("model_mapping 必须且只能包含模板定义的映射字段。")
    if not isinstance(observations, list) or not observations:
        raise ValueError("observations 必须是至少包含一个记录的列表。")
    if model.get("mapping_evidence_grade") != "C":
        raise ValueError("本地数据到模型的映射必须保持 C 级假设。")
    if model.get("parameter_calibration_allowed") is not False:
        raise ValueError("表达或通路结果不得用于 e-cell 参数校准。")
    for key in ("unmeasured_model_quantities", "not_inferable"):
        values = model.get(key)
        if not isinstance(values, list) or not all(isinstance(v, str) and v.strip() for v in values):
            raise ValueError(f"model_mapping.{key} 必须是文本说明列表。")
        if key == "not_inferable" and not values:
            raise ValueError("model_mapping.not_inferable 必须列出不可推断内容。")

    if status == "local_analysis_record":
        if not isinstance(model.get("question_only"), str) or not model["question_only"].strip():
            raise ValueError("model_mapping.question_only 必须写明待检验问题。")
        if not model["unmeasured_model_quantities"]:
            raise ValueError("完整记录必须写明未测量的模型量。")
        required_source = (
            "dataset_accession", "study_citation", "sample_accessions", "tissue_and_condition",
            "analysis_repository_or_protocol", "analysis_version_or_commit",
            "cell_annotation_method_and_version", "pathway_gene_set_and_version",
            "statistical_unit", "source_checked_date",
        )
        for key in required_source:
            value = source.get(key)
            if key == "sample_accessions":
                valid = isinstance(value, list) and bool(value) and all(isinstance(x, str) and x.strip() for x in value)
            else:
                valid = isinstance(value, str) and bool(value.strip())
            if not valid:
                raise ValueError(f"完整分析记录缺少来源字段：source.{key}。")
        try:
            from datetime import date
            from re import fullmatch
            if not fullmatch(r"\d{4}-\d{2}-\d{2}", source["source_checked_date"]):
                raise ValueError
            date.fromisoformat(source["source_checked_date"])
        except (TypeError, ValueError):
            raise ValueError("source.source_checked_date 必须使用 YYYY-MM-DD 日期格式。") from None
        scenario_id = model.get("existing_ecell_scenario_id")
        if scenario_id is not None and scenario_id != load_hypothesis_scenario()["id"]:
            raise ValueError("existing_ecell_scenario_id 必须引用仓库中已存在的教学情景，或设为 null。")

    for index, observation in enumerate(observations, start=1):
        if not isinstance(observation, dict) or set(observation) != LOCAL_MAPPING_OBSERVATION_FIELDS:
            raise ValueError(f"observations[{index}] 必须且只能包含模板定义的观察字段。")
        if status == "local_analysis_record":
            for key in ("cell_type", "comparison", "reported_direction", "data_location"):
                value = observation.get(key)
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"完整分析记录缺少观察字段：observations[{index}].{key}。")
            genes = observation.get("marker_genes")
            if not isinstance(genes, list) or not all(isinstance(gene, str) and gene.strip() for gene in genes):
                raise ValueError(f"observations[{index}].marker_genes 必须为文本列表。")
            if not genes and not observation.get("pathway_score_name"):
                raise ValueError(f"observations[{index}] 至少要记录标志基因或通路评分名称。")
            value = observation.get("reported_value")
            if isinstance(value, bool) or not isinstance(value, (int, float, str)) or not str(value).strip():
                raise ValueError(f"完整分析记录的 observations[{index}].reported_value 不能为空。")
            if isinstance(value, float) and not isfinite(value):
                raise ValueError(f"observations[{index}].reported_value 必须是有限数值。")

    if status == "template_only":
        source_has_values = any(value not in (None, "", []) for value in source.values())
        observations_have_values = any(
            value not in (None, "", [])
            for observation in observations
            for value in observation.values()
        )
        mapping_has_values = any(
            model.get(key) not in (None, "", [])
            for key in ("question_only", "existing_ecell_scenario_id", "unmeasured_model_quantities")
        )
        if source_has_values or observations_have_values or mapping_has_values:
            raise ValueError("模板中已填写观察或来源内容；请将 status 改为 local_analysis_record 并补全溯源字段。")

    return {
        "status": status,
        "observation_count": len(observations),
        "dataset_accession_present": bool(source.get("dataset_accession")),
        "parameter_calibration_allowed": False,
        "mapping_evidence_grade": "C",
        "summary": "空白模板结构有效，尚无本地观察记录。" if status == "template_only" else "本地分析记录结构有效；未校准模型参数。",
    }


def load_hypothesis_scenario() -> dict[str, Any]:
    """加载仓库内静态假设场景，并校验最小结构；不访问网络或运行模型。"""

    try:
        payload = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取数据启发假设场景：{exc}") from None
    validate_hypothesis_scenario(payload)
    return payload


def validate_hypothesis_scenario(payload: Any) -> None:
    """校验假设场景必需字段、边界声明及教学输入，不代表生物学有效性。"""

    if not isinstance(payload, dict):
        raise ValueError("假设场景必须是 JSON 对象。")
    missing = REQUIRED_SCENARIO_FIELDS - payload.keys()
    if missing:
        raise ValueError(f"假设场景缺少必需字段：{', '.join(sorted(missing))}。")
    if payload["schema"] != "e-cell-data-inspired-hypothesis/v1":
        raise ValueError("不支持的假设场景格式版本。")
    for key in ("source_data", "observed_pattern", "teaching_hypothesis", "teaching_scenario", "evidence"):
        if not isinstance(payload[key], dict):
            raise ValueError(f"假设场景字段 {key} 必须为对象。")
    if not isinstance(payload["id"], str) or not payload["id"].strip():
        raise ValueError("假设场景 id 必须是非空文本。")
    if not isinstance(payload["title"], str) or not payload["title"].strip():
        raise ValueError("假设场景 title 必须是非空文本。")
    if not isinstance(payload["model_version"], str) or not payload["model_version"].strip():
        raise ValueError("假设场景 model_version 必须是非空文本。")
    if payload["model_version"] != MODEL_VERSION:
        raise ValueError(
            f"假设场景基于模型 v{payload['model_version']}，当前为 v{MODEL_VERSION}；"
            "请复核环境与教学规则后更新场景版本。"
        )
    source = payload["source_data"]
    source_fields = (
        "analysis_status", "dataset", "series_scope", "single_cell_sample_reference",
        "disease_sample_reference", "provenance_status", "paper",
        "paper_url", "dataset_url", "sample_url", "disease_sample_url",
        "reported_method", "provenance_conflict",
    )
    if any(not isinstance(source.get(key), str) or not source[key].strip() for key in source_fields):
        raise ValueError("来源信息必须包含数据状态、accession、文献和可追溯链接。")
    for key in ("paper_url", "dataset_url", "sample_url", "disease_sample_url"):
        parsed_url = urlparse(source[key])
        if parsed_url.scheme != "https" or not parsed_url.hostname:
            raise ValueError("来源链接必须是包含有效主机名的 HTTPS URL。")
    if source["provenance_status"] != "unresolved_accession_scope":
        raise ValueError("当前论文—样本 accession 对应关系尚未解决，不能标为已核实。")
    observed = payload["observed_pattern"]
    if (
        not isinstance(observed.get("cell_types"), list)
        or not observed["cell_types"]
        or not all(isinstance(item, str) and item.strip() for item in observed["cell_types"])
        or not isinstance(observed.get("reported_genes"), list)
        or not observed["reported_genes"]
        or not all(isinstance(item, str) and item.strip() for item in observed["reported_genes"])
        or any(not isinstance(observed.get(key), str) or not observed[key].strip()
               for key in ("reported_result", "reported_score", "source_location", "evidence_type", "caveat"))
    ):
        raise ValueError("数据观察必须包含细胞类型、报告结果、来源位置、证据类型和限制。")
    hypothesis = payload["teaching_hypothesis"]
    if any(not isinstance(hypothesis.get(key), str) or not hypothesis[key].strip()
           for key in ("question", "mapping_boundary", "evidence_grade")):
        raise ValueError("教学假设必须包含问题、映射边界和证据等级。")
    for key in ("not_calibrated", "not_inferable", "limitations"):
        if not isinstance(payload[key], list) or not payload[key] or not all(isinstance(item, str) and item.strip() for item in payload[key]):
            raise ValueError(f"假设场景字段 {key} 必须是非空文字列表。")
    teaching = payload["teaching_scenario"]
    if teaching.get("default_enabled") is not False:
        raise ValueError("数据启发场景不得成为模型默认设置。")
    if teaching.get("mode") != "单细胞实验室":
        raise ValueError("当前教学案例必须明确绑定到单细胞实验室，不支持隐式切换模式。")
    if teaching.get("intervention_type") != "existing_oxidative_stress_pulse":
        raise ValueError("假设场景只能引用现有教学性干预，不得定义新机制。")
    intensity = teaching.get("relative_input_index")
    if isinstance(intensity, bool) or not isinstance(intensity, (int, float)) or not 0 <= intensity <= 100:
        raise ValueError("相对教学输入指数必须在 0–100 范围内。")
    duration = teaching.get("suggested_duration_h")
    step = teaching.get("time_step_h")
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in (duration, step)):
        raise ValueError("假设场景的时长和时间步长必须为数值。")
    if not 0 < step <= 6 or not 0 < duration <= 168:
        raise ValueError("假设场景时长须大于 0 且不超过 168 h，时间步须在 0–6 h。")
    if not isfinite(float(duration / step)) or abs(duration / step - round(duration / step)) > 1e-9:
        raise ValueError("假设场景总时长必须是时间步长的整数倍，便于按相同步数复跑。")
    environment = teaching.get("initial_environment")
    if not isinstance(environment, dict) or set(environment) != set(ENVIRONMENT_RANGES):
        raise ValueError("初始微环境必须完整包含已定义字段，不能省略或附加未知字段。")
    for key, (low, high) in ENVIRONMENT_RANGES.items():
        value = environment[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(float(value)):
            raise ValueError(f"初始微环境 {key} 必须为有限数值。")
        if not low <= value <= high:
            raise ValueError(f"初始微环境 {key} 超出允许范围 {low}–{high}。")
    if payload["evidence"].get("parameter_calibration") != "none":
        raise ValueError("公开表达数据不得写为 e-cell 参数校准来源。")
    if payload["evidence"].get("model_mapping_grade") != "C":
        raise ValueError("数据到 e-cell 的映射必须标为 C 级教学假设。")


def export_hypothesis_scenario_json() -> str:
    """导出可由单细胞实验室导入的确定性教学场景，不含表达矩阵或拟合参数。"""

    hypothesis = load_hypothesis_scenario()
    teaching = hypothesis["teaching_scenario"]
    source_environment = teaching["initial_environment"]
    environment = MicroenvironmentState(
        time_h=source_environment["time_h"],
        local_oxygen_availability=source_environment["local_oxygen_availability"],
        glucose_mm=source_environment["glucose_mM"],
        glucose_reference_mm=source_environment["glucose_reference_mM"],
        lactate_mm=source_environment["lactate_mM"],
        ph=source_environment["pH"],
        temperature_c=source_environment["temperature_C"],
        drug_um=source_environment["drug_uM"],
        local_confluence_percent=source_environment["local_confluence_percent"],
        doubling_time_h=source_environment["doubling_time_h"],
        drug_ic50_um=source_environment["drug_ic50_uM"],
    )
    state = IntracellularState()
    state.apply_oxidative_stress(float(teaching["relative_input_index"]))
    history = [single_cell_history_row(state, environment)]
    events = [{
        "time_h": state.time_h,
        "event": "教学性氧化压力脉冲（公开数据启发假设场景）",
        "event_type": "oxidative_stress",
        "input_index": float(teaching["relative_input_index"]),
        "environment": environment.snapshot(),
    }]
    payload = export_single_cell_scenario(environment, state, history, events)
    # 附加可忽略扩展元数据：现有导入器按单细胞场景字段恢复，且不会将其用于参数拟合。
    payload["data_inspired_hypothesis"] = {
        "schema": hypothesis["schema"],
        "id": hypothesis["id"],
        "title": hypothesis["title"],
        "source_dataset": hypothesis["source_data"]["dataset"],
        "source_provenance_status": hypothesis["source_data"]["provenance_status"],
        "source_paper_url": hypothesis["source_data"]["paper_url"],
        "source_dataset_url": hypothesis["source_data"]["dataset_url"],
        "source_sample_url": hypothesis["source_data"]["sample_url"],
        "source_disease_sample_url": hypothesis["source_data"]["disease_sample_url"],
        "disease_sample_reference": hypothesis["source_data"]["disease_sample_reference"],
        "reported_observation": hypothesis["observed_pattern"]["reported_result"],
        "reported_genes": hypothesis["observed_pattern"]["reported_genes"],
        "reported_score": hypothesis["observed_pattern"]["reported_score"],
        "provenance_warning": hypothesis["source_data"]["provenance_conflict"],
        "model_mapping_grade": hypothesis["evidence"]["model_mapping_grade"],
        "public_observation_grade": hypothesis["evidence"]["public_observation_grade"],
        "parameter_calibration": "none",
        "reproduction_protocol": {
            "intervention_relative_input_index": float(teaching["relative_input_index"]),
            "time_step_h": float(teaching["time_step_h"]),
            "duration_h": float(teaching["suggested_duration_h"]),
        },
        "not_calibrated": list(hypothesis["not_calibrated"]),
        "limitations": hypothesis["limitations"],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
