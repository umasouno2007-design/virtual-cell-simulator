"""Safely decode user-supplied JSON objects without exposing raw file contents."""

import json


def decode_json_object(payload: bytes | str | dict) -> dict:
    """Return a JSON object or raise a concise ValueError for malformed input."""

    if isinstance(payload, bytes):
        try:
            payload = payload.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise ValueError("场景文件不是 UTF-8 编码的 JSON；请重新保存后导入。") from None
    if isinstance(payload, str):
        try:
            payload = json.loads(
                payload,
                parse_constant=lambda value: _reject_nonstandard_constant(value),
                object_pairs_hook=_unique_keys,
            )
        except json.JSONDecodeError as error:
            raise ValueError(f"场景 JSON 格式错误：第 {error.lineno} 行、第 {error.colno} 列。") from None
        except ValueError as error:
            # Preserve our explicit duplicate-key/non-standard-number diagnostics;
            # normalize parser errors such as an integer exceeding Python's limit.
            if str(error).startswith("场景 JSON "):
                raise
            raise ValueError("场景 JSON 含有无法解析的数值或结构。") from None
    if not isinstance(payload, dict):
        raise ValueError("场景根节点必须是 JSON 对象。")
    pending: list[object] = [payload]
    visited_containers: set[int] = set()
    while pending:
        value = pending.pop()
        if isinstance(value, str):
            if any("\ud800" <= character <= "\udfff" for character in value):
                raise ValueError("场景 JSON 含有无效 Unicode 字符；请以 UTF-8 重新导出文件。")
        elif isinstance(value, dict):
            identity = id(value)
            if identity not in visited_containers:
                visited_containers.add(identity)
                pending.extend(value.keys())
                pending.extend(value.values())
        elif isinstance(value, list):
            identity = id(value)
            if identity not in visited_containers:
                visited_containers.add(identity)
                pending.extend(value)
    return payload


def _reject_nonstandard_constant(value: str) -> None:
    raise ValueError(f"场景 JSON 不支持 {value}；请使用有限数值或 null。")


def _unique_keys(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("场景 JSON 包含重复字段名；请删除重复项后重新导入。")
        result[key] = value
    return result
