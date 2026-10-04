"""Locally validate a filled data-to-model hypothesis record.

This script reads one JSON file from the local filesystem, prints a short
sanitized validation summary, and never uploads, rewrites, or fits the data.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data_model_hypotheses import validate_local_hypothesis_mapping

MAX_MAPPING_BYTES = 1_048_576


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Reject duplicate JSON keys rather than silently taking the final value."""

    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"JSON 中发现重复字段：{key}。")
        result[key] = value
    return result


def validate_file(path: Path) -> dict[str, object]:
    """Read and structurally validate a local mapping JSON without exposing its path."""

    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_MAPPING_BYTES + 1)
        if len(raw) > MAX_MAPPING_BYTES:
            raise ValueError("映射文件超过 1 MiB；请勿把表达矩阵等原始数据放入此文件。")
        text = raw.decode("utf-8-sig")
    except OSError:
        raise ValueError("无法读取指定映射文件；请确认文件存在且当前用户有读取权限。") from None
    except UnicodeDecodeError:
        raise ValueError("映射文件必须使用 UTF-8 编码。") from None
    try:
        payload = json.loads(text, object_pairs_hook=_unique_object)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON 格式错误（第 {exc.lineno} 行，第 {exc.colno} 列）。") from None
    return validate_local_hypothesis_mapping(payload)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="在本机检查数据—模型假设映射结构，不上传数据、不校准模型。"
    )
    parser.add_argument("mapping_json", type=Path, help="由空白映射模板填写的 JSON 文件")
    args = parser.parse_args()
    try:
        report = validate_file(args.mapping_json)
    except ValueError as exc:
        print(f"校验未通过：{exc}", file=sys.stderr)
        return 2
    print(f"校验通过：{report['summary']}")
    print(
        f"观察记录数：{report['observation_count']}；映射等级：{report['mapping_evidence_grade']}；"
        "模型参数校准：未执行。"
    )
    print("注意：结构校验不验证数据来源、统计方法、生物学结论或实验设计。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
