"""可观测性映射完整性测试。"""

import unittest

from evidence import REFERENCES
from observability import OBSERVABLES, observability_rows


class ObservabilityTestCase(unittest.TestCase):
    def test_every_observable_has_boundary_and_known_evidence(self) -> None:
        self.assertGreaterEqual(len(OBSERVABLES), 8)
        for item in OBSERVABLES:
            self.assertTrue(item.suggested_readout)
            self.assertTrue(item.interpretation_boundary)
            self.assertTrue(all(key in REFERENCES for key in item.evidence_keys))

    def test_table_rows_have_required_columns(self) -> None:
        self.assertEqual(
            set(observability_rows()[0]),
            {"模型指标", "建议实验读出", "解释边界", "依据"},
        )


if __name__ == "__main__":
    unittest.main()
