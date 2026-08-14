import unittest
from io import BytesIO

import pandas as pd

from data_quality import (
    DataQualityError,
    analyse_data_quality,
    load_tabular_data,
    validate_upload_metadata,
)


class UploadValidationTests(unittest.TestCase):
    def test_accepts_supported_extension_case_insensitively(self):
        self.assertEqual(validate_upload_metadata("sales.CSV", 100), ".csv")

    def test_rejects_unsupported_file_type(self):
        with self.assertRaisesRegex(DataQualityError, "仅支持 CSV"):
            validate_upload_metadata("sales.json", 100)

    def test_rejects_empty_and_oversized_files(self):
        with self.assertRaisesRegex(DataQualityError, "文件内容为空"):
            validate_upload_metadata("sales.csv", 0)
        with self.assertRaisesRegex(DataQualityError, "接入限制"):
            validate_upload_metadata("sales.csv", 101, max_bytes=100)

    def test_reads_utf8_and_common_chinese_csv_encodings(self):
        text = "商品,销售额\n智能手环,100\n"
        utf8_data = load_tabular_data(text.encode("utf-8"), ".csv")
        gb_data = load_tabular_data(text.encode("gb18030"), ".csv")

        self.assertEqual(utf8_data.iloc[0]["商品"], "智能手环")
        self.assertEqual(gb_data.iloc[0]["销售额"], 100)

    def test_reads_excel_workbook(self):
        buffer = BytesIO()
        pd.DataFrame({"商品": ["智能手环"], "销售额": [100]}).to_excel(
            buffer,
            index=False,
        )

        data = load_tabular_data(buffer.getvalue(), ".xlsx")

        self.assertEqual(data.iloc[0]["商品"], "智能手环")
        self.assertEqual(data.iloc[0]["销售额"], 100)

    def test_rejects_data_over_row_limit(self):
        csv_data = b"value\n1\n2\n3\n"
        with self.assertRaisesRegex(DataQualityError, "超过 2 行"):
            load_tabular_data(csv_data, ".csv", max_rows=2)


class DataQualityAnalysisTests(unittest.TestCase):
    def test_clean_data_passes_without_warnings(self):
        df = pd.DataFrame({"商品": ["A", "B"], "销售额": [100, 200]})

        report = analyse_data_quality(df)

        self.assertTrue(report["is_usable"])
        self.assertEqual(report["status"], "质量检查通过")
        self.assertEqual(report["warnings"], [])
        self.assertEqual(report["row_count"], 2)
        self.assertEqual(report["column_count"], 2)

    def test_reports_missing_values_duplicates_and_column_statistics(self):
        df = pd.DataFrame(
            {
                "商品": ["A", "A", None],
                "销售额": [100, 100, 300],
                "空字段": [None, None, None],
            }
        )

        report = analyse_data_quality(df)

        self.assertTrue(report["is_usable"])
        self.assertEqual(report["missing_cells"], 4)
        self.assertEqual(report["duplicate_rows"], 1)
        self.assertTrue(any("全空字段" in warning for warning in report["warnings"]))
        product_profile = report["column_profiles"][0]
        self.assertEqual(product_profile["缺失数"], 1)
        self.assertAlmostEqual(product_profile["缺失率"], 1 / 3)

    def test_counts_fully_duplicated_rows(self):
        df = pd.DataFrame({"商品": ["A", "A"], "销售额": [100, 100]})

        report = analyse_data_quality(df)

        self.assertEqual(report["duplicate_rows"], 1)
        self.assertTrue(any("完全重复" in warning for warning in report["warnings"]))

    def test_empty_data_is_blocked(self):
        report = analyse_data_quality(pd.DataFrame(columns=["商品", "销售额"]))

        self.assertFalse(report["is_usable"])
        self.assertEqual(report["status"], "不可分析")
        self.assertTrue(any("没有可分析的数据行" in item for item in report["blockers"]))

    def test_too_many_columns_are_blocked(self):
        df = pd.DataFrame([[1, 2, 3]], columns=["a", "b", "c"])

        report = analyse_data_quality(df, max_columns=2)

        self.assertFalse(report["is_usable"])
        self.assertTrue(any("字段数超过" in item for item in report["blockers"]))

    def test_duplicate_column_names_are_blocked(self):
        df = pd.DataFrame([[1, 2]], columns=["销售额", "销售额"])

        report = analyse_data_quality(df)

        self.assertFalse(report["is_usable"])
        self.assertTrue(any("重复字段名" in item for item in report["blockers"]))


if __name__ == "__main__":
    unittest.main()
