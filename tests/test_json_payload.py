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

    def test_extreme_json_integer_returns_readable_validation_error(self) -> None:
        content = '{"value": ' + ("9" * 5000) + "}"
        with self.assertRaisesRegex(ValueError, "无法解析的数值或结构"):
            decode_json_object(content)

    def test_unpaired_surrogate_is_rejected_but_valid_unicode_is_preserved(self) -> None:
        with self.assertRaisesRegex(ValueError, "无效 Unicode 字符"):
            decode_json_object(r'{"label":"\ud800"}')
        self.assertEqual(decode_json_object(r'{"label":"\ud83d\ude00"}'), {"label": "😀"})
        with self.assertRaisesRegex(ValueError, "无效 Unicode 字符"):
            decode_json_object({"nested": ["\udfff"]})


if __name__ == "__main__":
    unittest.main()
