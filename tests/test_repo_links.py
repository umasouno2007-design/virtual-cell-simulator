"""仓库文档本地链接检查器测试。"""

import tempfile
import unittest
from pathlib import Path

from scripts.check_repo_links import (
    check_markdown_links,
    local_markdown_targets,
    markdown_files,
)


class RepositoryLinkCheckTests(unittest.TestCase):
    def test_local_targets_skip_code_fences_and_external_links(self) -> None:
        markdown = """[本地](docs/模型说明.md) ![截图](<assets/a%20b.png>)
https://example.test [外部](https://example.test/docs)
```md
[示例](missing.md)
```
"""
        self.assertEqual(
            list(local_markdown_targets(markdown)),
            [(1, "docs/模型说明.md"), (1, "assets/a b.png")],
        )

    def test_missing_and_out_of_repository_targets_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            docs = root / "docs"
            docs.mkdir()
            source = docs / "README.md"
            source.write_text("[missing](missing.md) [outside](../../outside.md)\n", encoding="utf-8")
            errors = check_markdown_links([source], root)
        self.assertEqual(len(errors), 2)
        self.assertIn("本地链接不存在", errors[0])
        self.assertIn("越出仓库范围", errors[1])

    def test_all_project_docs_have_valid_local_links(self) -> None:
        root = Path(__file__).resolve().parents[1]
        errors = check_markdown_links(markdown_files(root), root)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
