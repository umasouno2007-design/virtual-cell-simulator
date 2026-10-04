"""Ensure UI upload limits match parser resource limits."""

from pathlib import Path
import tomllib
import unittest

from experiment_data import MAX_CSV_BYTES


ROOT = Path(__file__).resolve().parents[1]


class DeploymentConfigTests(unittest.TestCase):
    def test_streamlit_upload_limit_matches_csv_parser_limit(self) -> None:
        config = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))
        max_upload_size_mb = config["server"]["maxUploadSize"]
        self.assertEqual(max_upload_size_mb * 1024 * 1024, MAX_CSV_BYTES)


if __name__ == "__main__":
    unittest.main()
