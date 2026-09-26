"""部署前无网页 smoke check。"""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from cell import CellCulture
from experiment_manifest import build_manifest
from scripts.validate_a549_teaching_case import run_case

def main():
    assert (ROOT / "data" / "a549_teaching_synthetic.csv").is_file()
    cell = CellCulture("a549"); cell.step(1)
    assert cell.snapshot()["time_h"] == 1
    assert build_manifest(cell, app_version="smoke", preset_name="标准培养", app_mode="细胞培养", time_multiplier=60, history=[cell.snapshot()], events=[])["experiment"]["profile_key"] == "a549"
    assert run_case(output_dir=None)["validation_metrics"]
    print("smoke check passed")
if __name__ == "__main__": main()
