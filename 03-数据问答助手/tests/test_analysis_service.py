import sqlite3
import unittest

import pandas as pd

from analysis_service import analyse_database_question, analyse_dataframe_question


class FakeAiService:
    def __init__(self):
        self.answer_result = None

    def generate_sql(self, question, schema_text):
        self.sql_request = (question, schema_text)
        return "```sql\nSELECT 商品, SUM(销售额) AS 总销售额 FROM sales GROUP BY 商品\n```"

    def generate_pandas_code(self, question, dataframe):
        self.pandas_request = (question, list(dataframe.columns))
        return "answer = df.groupby('商品')['销售额'].sum()"

    def generate_answer(self, question, result):
        self.answer_result = result
        return f"已完成：{question}"


class AnalysisServiceTests(unittest.TestCase):
    def setUp(self):
        self.ai_service = FakeAiService()
        self.dataframe = pd.DataFrame(
            {"商品": ["智能手环", "蓝牙耳机", "智能手环"], "销售额": [100, 80, 120]}
        )

    def test_dataframe_pipeline_runs_generation_execution_and_answer(self):
        outcome = analyse_dataframe_question(
            "各商品销售额是多少？",
            self.dataframe,
            self.ai_service,
        )

        self.assertEqual(outcome.execution_type, "Pandas 分析")
        self.assertEqual(outcome.language, "python")
        self.assertEqual(outcome.result.loc["智能手环"], 220)
        self.assertEqual(outcome.answer, "已完成：各商品销售额是多少？")
        self.assertIs(self.ai_service.answer_result, outcome.result)

    def test_database_pipeline_cleans_and_executes_generated_sql(self):
        connection = sqlite3.connect(":memory:")
        self.addCleanup(connection.close)
        self.dataframe.to_sql("sales", connection, index=False)

        outcome = analyse_database_question(
            "各商品销售额是多少？",
            "表 sales 的列：商品 TEXT, 销售额 INTEGER",
            "sales",
            connection,
            self.ai_service,
        )

        self.assertEqual(outcome.language, "sql")
        self.assertFalse(outcome.generated_code.startswith("```"))
        self.assertEqual(outcome.result.set_index("商品").loc["智能手环", "总销售额"], 220)

    def test_empty_question_is_rejected_before_ai_call(self):
        with self.assertRaisesRegex(ValueError, "问题不能为空"):
            analyse_dataframe_question("  ", self.dataframe, self.ai_service)
        self.assertFalse(hasattr(self.ai_service, "pandas_request"))

    def test_oversized_question_is_rejected_before_ai_call(self):
        with self.assertRaisesRegex(ValueError, "不能超过 500"):
            analyse_dataframe_question("问" * 501, self.dataframe, self.ai_service)


if __name__ == "__main__":
    unittest.main()
