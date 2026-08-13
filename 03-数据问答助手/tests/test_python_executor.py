import unittest

import pandas as pd

from python_executor import (
    PythonExecutionError,
    PythonValidationError,
    clean_python_output,
    execute_pandas_code,
    validate_pandas_code,
)


class PythonExecutorTests(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame(
            {
                "商品": ["智能手环", "蓝牙耳机", "智能手环"],
                "品类": ["数码", "数码", "数码"],
                "销售额": [100, 80, 120],
            }
        )

    def test_cleans_markdown_code_fence(self):
        raw_code = "```python\nanswer = df['销售额'].sum()\n```"
        self.assertEqual(clean_python_output(raw_code), "answer = df['销售额'].sum()")

    def test_executes_grouped_analysis(self):
        code = "answer = df.groupby('商品')['销售额'].sum().sort_values(ascending=False)"
        cleaned_code, result = execute_pandas_code(code, self.df)

        self.assertEqual(cleaned_code, code)
        self.assertEqual(result.index[0], "智能手环")
        self.assertEqual(result.iloc[0], 220)

    def test_allows_temporary_variables_and_filtering(self):
        code = "filtered = df[df['销售额'] >= 100]\nanswer = filtered['销售额'].mean()"
        _, result = execute_pandas_code(code, self.df)
        self.assertEqual(result, 110)

    def test_allows_common_statistical_methods(self):
        code = "answer = df['销售额'].std()"
        _, result = execute_pandas_code(code, self.df)
        self.assertAlmostEqual(result, self.df["销售额"].std())

    def test_rejects_import(self):
        with self.assertRaisesRegex(PythonValidationError, "只允许赋值语句"):
            execute_pandas_code("import os\nanswer = 1", self.df)

    def test_rejects_file_access(self):
        with self.assertRaisesRegex(PythonValidationError, "不允许调用函数"):
            execute_pandas_code("answer = open('secret.txt')", self.df)

    def test_rejects_dunder_attribute_access(self):
        with self.assertRaisesRegex(PythonValidationError, "不允许访问属性"):
            execute_pandas_code("answer = df.__class__", self.df)

    def test_rejects_dataframe_export_method(self):
        with self.assertRaisesRegex(PythonValidationError, "不允许调用方法"):
            execute_pandas_code("answer = df.to_csv('stolen.csv')", self.df)

    def test_allows_whitelisted_aggregation(self):
        code = "answer = df.groupby('商品').agg({'销售额': ['sum', 'mean']})"
        _, result = execute_pandas_code(code, self.df)
        self.assertEqual(result.loc["智能手环", ("销售额", "sum")], 220)

    def test_rejects_method_selected_through_aggregation_string(self):
        with self.assertRaisesRegex(PythonValidationError, "不允许使用聚合函数"):
            execute_pandas_code("answer = df['销售额'].agg('to_pickle')", self.df)

        with self.assertRaisesRegex(PythonValidationError, "不允许使用聚合函数"):
            execute_pandas_code("answer = df['销售额'].agg(['to_pickle', 'sum'])", self.df)

    def test_rejects_inplace_changes(self):
        code = "changed = df.drop(columns=['销售额'], inplace=True)\nanswer = df"
        with self.assertRaisesRegex(PythonValidationError, "inplace=True"):
            execute_pandas_code(code, self.df)

    def test_rejects_large_sequence_allocation(self):
        with self.assertRaisesRegex(PythonValidationError, "批量复制"):
            execute_pandas_code("answer = [0] * 1000000000", self.df)

    def test_rejects_large_power_operation(self):
        with self.assertRaisesRegex(PythonValidationError, "指数过大"):
            execute_pandas_code("answer = 10 ** 1000000000", self.df)

    def test_rejects_loop(self):
        code = "total = 0\nfor value in df['销售额']:\n    total = total + value\nanswer = total"
        with self.assertRaisesRegex(PythonValidationError, "只允许赋值语句"):
            execute_pandas_code(code, self.df)

    def test_requires_answer_assignment(self):
        with self.assertRaisesRegex(PythonValidationError, "answer"):
            validate_pandas_code("total = df['销售额'].sum()")

    def test_rejects_assignment_into_dataframe(self):
        with self.assertRaisesRegex(PythonValidationError, "只允许给"):
            execute_pandas_code("df['销售额'] = 0\nanswer = df", self.df)

    def test_original_dataframe_is_not_changed(self):
        original = self.df.copy(deep=True)
        _, result = execute_pandas_code("answer = df.drop(columns=['销售额'])", self.df)

        pd.testing.assert_frame_equal(self.df, original)
        self.assertNotIn("销售额", result.columns)

    def test_wraps_runtime_error(self):
        with self.assertRaisesRegex(PythonExecutionError, "执行失败"):
            execute_pandas_code("answer = df['不存在的列'].sum()", self.df)


if __name__ == "__main__":
    unittest.main()
