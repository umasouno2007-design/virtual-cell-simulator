"""Transient checkpoints must never cross browser sessions."""

import unittest
from dataclasses import asdict
from pathlib import Path

from cell import CellCulture
from runtime_storage import restore_culture_checkpoint, session_state_path


class RuntimeStorageTests(unittest.TestCase):
    @staticmethod
    def _checkpoint() -> dict:
        cell = CellCulture("a549")
        fields = (
            "culture_volume_ml", "surface_area_cm2", "viable_cells", "dead_cells",
            "time_h", "glucose_mm", "glutamine_mm", "lactate_mm", "oxygen_percent",
            "oxygen_setpoint_percent", "ph", "temperature_c", "co2_percent",
            "osmolality_mosm_kg", "drug_um", "energy_index",
            "last_growth_rate_per_h", "last_death_rate_per_h",
        )
        return {
            "profile_key": cell.profile_key,
            "cell": {name: getattr(cell, name) for name in fields},
            "parameters": asdict(cell.parameters),
            "history": [cell.snapshot()],
            "scheduled_actions": [],
        }

    def test_each_session_has_a_distinct_non_global_state_path(self):
        base = Path("/tmp/e-cell/.runtime_state.json")
        first = session_state_path(base, "browser-A")
        second = session_state_path(base, "browser-B")
        self.assertNotEqual(first, second)
        self.assertNotEqual(first, base)
        self.assertEqual(first.parent, base.parent)
        self.assertEqual(first, session_state_path(base, "browser-A"))
        self.assertNotIn("browser-A", first.name)

    def test_no_live_session_does_not_read_shared_checkpoint(self):
        base = Path("/tmp/e-cell/.runtime_state.json")
        self.assertIsNone(session_state_path(base, None))
        self.assertIsNone(session_state_path(base, "test session id"))
        escaped = session_state_path(base, "../../other-user")
        self.assertEqual(escaped.parent, base.parent)

    def test_valid_culture_checkpoint_restores_without_changing_outputs(self):
        payload = self._checkpoint()
        cell, history = restore_culture_checkpoint(payload)
        self.assertEqual(cell.snapshot(), history[-1])

    def test_corrupt_numeric_or_history_is_rejected_before_ui_restore(self):
        payload = self._checkpoint()
        payload["cell"]["glucose_mm"] = float("nan")
        with self.assertRaisesRegex(ValueError, "NaN"):
            restore_culture_checkpoint(payload)
        payload = self._checkpoint()
        payload["history"][0]["time_h"] = -1.0
        with self.assertRaisesRegex(ValueError, "单调"):
            restore_culture_checkpoint(payload)
