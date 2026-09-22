"""证据目录完整性与可追溯性测试。"""

import unittest
from urllib.parse import urlparse

from evidence import EVIDENCE_ENTRIES, REFERENCES, evidence_rows
from profiles import CELL_PROFILES


class EvidenceCatalogTestCase(unittest.TestCase):
    def test_every_source_key_resolves_to_https(self) -> None:
        for entry in EVIDENCE_ENTRIES:
            for source_key in entry.sources:
                self.assertIn(source_key, REFERENCES)
        for reference in REFERENCES.values():
            parsed = urlparse(reference.url)
            self.assertEqual(parsed.scheme, "https")
            self.assertTrue(parsed.netloc)

    def test_all_evidence_levels_are_explicit(self) -> None:
        allowed = {"A 直接支持", "B 文献推断·待校准", "C 演示规则"}
        self.assertTrue(EVIDENCE_ENTRIES)
        self.assertTrue(all(entry.level in allowed for entry in EVIDENCE_ENTRIES))
        self.assertTrue(all(entry.limitation for entry in EVIDENCE_ENTRIES))

    def test_table_contains_required_columns(self) -> None:
        required = {"模拟机制", "数学/逻辑关系", "适用范围", "证据等级", "来源", "当前限制"}
        self.assertTrue(required.issubset(evidence_rows()[0]))

    def test_profiles_include_atcc_and_cellosaurus_traceability(self) -> None:
        for profile in CELL_PROFILES.values():
            urls = " ".join(reference.url for reference in profile.references)
            self.assertIn("atcc.org", urls)
            self.assertIn("cellosaurus.org", urls)

    def test_audited_reference_count_and_hela_doubling_time(self) -> None:
        self.assertEqual(len(REFERENCES), 19)
        self.assertAlmostEqual(CELL_PROFILES["hela"].doubling_time_h, 31.2)


if __name__ == "__main__":
    unittest.main()
