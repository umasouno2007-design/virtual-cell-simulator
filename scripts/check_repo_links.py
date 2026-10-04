"""检查仓库 Markdown 中可验证的本地文件链接。"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
LINK_PATTERN = re.compile(r"!?\[[^\]]*\]\(\s*(?:<([^>]+)>|([^\s)]+))[^)]*\)")
FENCE_PATTERN = re.compile(r"^\s*(`{3,}|~{3,})")
IGNORED_DIRS = {".git", ".venv", "__pycache__", ".mplcache", "outputs", "work"}


def local_markdown_targets(markdown: str):
    """Yield (line number, destination) for inline local Markdown links/images."""

    fence_marker: str | None = None
    for line_number, line in enumerate(markdown.splitlines(), start=1):
        fence = FENCE_PATTERN.match(line)
        if fence:
            marker = fence.group(1)
            if fence_marker is None:
                fence_marker = marker[0] * len(marker)
            elif marker[0] == fence_marker[0] and len(marker) >= len(fence_marker):
                fence_marker = None
            continue
        if fence_marker is not None:
            continue
        for match in LINK_PATTERN.finditer(line):
            destination = match.group(1) or match.group(2) or ""
            parsed = urlsplit(destination)
            if parsed.scheme or destination.startswith("//") or not parsed.path:
                continue
            yield line_number, unquote(parsed.path)


def markdown_files(root: Path) -> list[Path]:
    """Return project Markdown files, excluding generated and environment trees."""

    return sorted(
        path for path in root.rglob("*.md")
        if not any(part in IGNORED_DIRS or part.startswith(".") for part in path.relative_to(root).parts[:-1])
    )


def check_markdown_links(paths: list[Path], root: Path) -> list[str]:
    """Return readable errors for links that escape or do not exist in the repository."""

    errors: list[str] = []
    resolved_root = root.resolve()
    for markdown_path in paths:
        text = markdown_path.read_text(encoding="utf-8")
        for line_number, target in local_markdown_targets(text):
            resolved_target = (markdown_path.parent / target).resolve()
            try:
                resolved_target.relative_to(resolved_root)
            except ValueError:
                errors.append(f"{markdown_path.relative_to(root)}:{line_number}: 链接越出仓库范围：{target}")
                continue
            if not resolved_target.exists():
                errors.append(f"{markdown_path.relative_to(root)}:{line_number}: 本地链接不存在：{target}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="验证仓库 Markdown 中的本地链接与图片路径")
    parser.add_argument("paths", nargs="*", type=Path, help="要检查的 Markdown 文件；省略时检查仓库文档")
    args = parser.parse_args()
    paths = [(ROOT / path).resolve() for path in args.paths] if args.paths else markdown_files(ROOT)
    errors = check_markdown_links(paths, ROOT)
    if errors:
        print("仓库 Markdown 链接检查失败：")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Markdown 本地链接检查通过：{len(paths)} 个文件。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
