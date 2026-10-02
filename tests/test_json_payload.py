"""Malformed scene uploads should fail with readable, content-safe messages."""

import unittest

from cell_scenario import import_single_cell_scenario
from json_payload import decode_json_object
from scenario import import_scenario


class JsonPayloadTests(unittest.TestCase):
    def test_utf8_with_bom_is_accepted(self) -> None:
        self.assertEqual(decode_json_object(b"\xef\xbb\xbf{}"), {})

    def test_bad_encoding_is_a_readable_value_error_in_both_importers(self) -> None:
        for importer in (import_scenario, import_single_cell_scenario):
            with self.subTest(importer=importer.__name__):
                with self.assertRaisesRegex(ValueError, "UTF-8"):
                    importer(b"\xff\xfe")

    def test_malformed_json_reports_location_not_file_contents(self) -> None:
        with self.assertRaisesRegex(ValueError, "第 1 行、第 9 列"):
            decode_json_object('{"cell":}')

    def test_nonstandard_numeric_constant_is_rejected(self) -> None:
        for content in ('{"value": NaN}', '{"value": Infinity}'):
            with self.subTest(content=content):
                with self.assertRaisesRegex(ValueError, "不支持"):
                    decode_json_object(content)

    def test_duplicate_key_is_not_silently_overwritten(self) -> None:
        for content in ('{"schema": "old", "schema": "new"}', '{"cell": {"pH": 7.2, "pH": 6.8}}'):
            with self.subTest(content=content):
                with self.assertRaisesRegex(ValueError, "重复字段名"):
                    decode_json_object(content)


if __name__ == "__main__":
    unittest.main()
