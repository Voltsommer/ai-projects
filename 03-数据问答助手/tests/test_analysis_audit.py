import json
import unittest

import pandas as pd

from analysis_audit import (
    build_analysis_record,
    build_result_preview,
    result_preview_to_dataframe,
    serialise_messages,
)


class AnalysisAuditTests(unittest.TestCase):
    def test_dataframe_preview_is_limited_and_json_serialisable(self):
        result = pd.DataFrame({"商品": [f"商品{i}" for i in range(25)], "销售额": range(25)})

        preview = build_result_preview(result)

        self.assertEqual(preview["kind"], "table")
        self.assertEqual(preview["total_rows"], 25)
        self.assertEqual(preview["shown_rows"], 20)
        self.assertTrue(preview["truncated"])
        json.dumps(preview, ensure_ascii=False)

    def test_series_index_is_kept_as_a_visible_column(self):
        result = pd.Series(
            [36500, 35640],
            index=pd.Index(["运动鞋", "智能手环"], name="商品"),
            name="销售额",
        )

        table = result_preview_to_dataframe(build_result_preview(result))

        self.assertEqual(list(table.columns), ["商品", "销售额"])
        self.assertEqual(table.iloc[0].to_dict(), {"商品": "运动鞋", "销售额": 36500})

    def test_scalar_result_is_stored_as_text(self):
        preview = build_result_preview(103640)

        self.assertEqual(preview, {"kind": "text", "value": "103640", "truncated": False})

    def test_analysis_record_contains_execution_metadata(self):
        analysis = build_analysis_record(
            "数据库查询",
            "SELECT SUM(销售额) FROM sales",
            "sql",
            103640,
        )

        self.assertEqual(analysis["execution_type"], "数据库查询")
        self.assertEqual(analysis["language"], "sql")
        self.assertIn("SELECT", analysis["code"])

    def test_message_serialisation_keeps_audit_but_drops_runtime_chart(self):
        messages = [
            {
                "role": "assistant",
                "content": "分析完成",
                "analysis": {"execution_type": "数据库查询"},
                "chart_data": pd.DataFrame({"销售额": [1, 2]}),
            }
        ]

        clean = serialise_messages(messages)

        self.assertIn("analysis", clean[0])
        self.assertNotIn("chart_data", clean[0])
        json.dumps(clean, ensure_ascii=False)


if __name__ == "__main__":
    unittest.main()
