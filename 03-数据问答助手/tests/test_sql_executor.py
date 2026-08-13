import sqlite3
import unittest

from sql_executor import (
    SqlExecutionError,
    SqlValidationError,
    clean_sql_output,
    execute_read_only_query,
    validate_read_only_query,
)


class SqlExecutorTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("CREATE TABLE sales (商品 TEXT, 销售额 INTEGER)")
        self.conn.executemany(
            "INSERT INTO sales VALUES (?, ?)",
            [("智能手环", 100), ("蓝牙耳机", 80), ("保温杯", 60)],
        )

    def tearDown(self):
        self.conn.close()

    def test_cleans_markdown_code_fence(self):
        raw_sql = "```sql\nSELECT * FROM sales;\n```"
        self.assertEqual(clean_sql_output(raw_sql), "SELECT * FROM sales;")

    def test_allows_select_and_with_queries(self):
        self.assertEqual(validate_read_only_query("SELECT * FROM sales"), "SELECT * FROM sales")
        result = execute_read_only_query(
            "WITH totals AS (SELECT SUM(销售额) AS 总额 FROM sales) SELECT * FROM totals",
            self.conn,
        )
        self.assertEqual(result.iloc[0]["总额"], 240)

    def test_rejects_write_statement(self):
        with self.assertRaisesRegex(SqlValidationError, "只允许执行"):
            execute_read_only_query("DELETE FROM sales", self.conn)

    def test_rejects_stacked_statements(self):
        with self.assertRaisesRegex(SqlValidationError, "一次只允许"):
            execute_read_only_query("SELECT * FROM sales; DROP TABLE sales", self.conn)

    def test_semicolon_inside_text_is_not_a_second_statement(self):
        result = execute_read_only_query("SELECT ';' AS 符号", self.conn)
        self.assertEqual(result.iloc[0]["符号"], ";")

    def test_limits_result_rows(self):
        result = execute_read_only_query("SELECT * FROM sales", self.conn, max_rows=2)
        self.assertEqual(len(result), 2)
        self.assertTrue(result.attrs["truncated"])

    def test_stops_query_after_timeout(self):
        slow_query = """
            WITH RECURSIVE counter(x) AS (
                VALUES(1)
                UNION ALL
                SELECT x + 1 FROM counter WHERE x < 100000000
            )
            SELECT SUM(x) FROM counter
        """
        with self.assertRaisesRegex(SqlExecutionError, "自动终止"):
            execute_read_only_query(slow_query, self.conn, timeout_seconds=0)


if __name__ == "__main__":
    unittest.main()
