import sqlite3
import tempfile
import unittest
from pathlib import Path

from database import (
    DatabaseAccessError,
    connect_read_only,
    get_schema_text,
    list_user_tables,
    preview_table,
    require_known_table,
)


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.connections = []
        self.database_file = Path(self.temp_dir.name) / "sales.db"
        connection = sqlite3.connect(self.database_file)
        connection.execute("CREATE TABLE sales (商品 TEXT, 销售额 INTEGER)")
        connection.executemany(
            "INSERT INTO sales VALUES (?, ?)",
            [("智能手环", 100), ("蓝牙耳机", 80)],
        )
        connection.commit()
        connection.close()

    def tearDown(self):
        for connection in self.connections:
            connection.close()
        self.temp_dir.cleanup()

    def open_read_only(self):
        connection = connect_read_only(self.database_file)
        self.connections.append(connection)
        return connection

    def test_missing_database_is_rejected(self):
        with self.assertRaisesRegex(DatabaseAccessError, "找不到数据库"):
            connect_read_only(Path(self.temp_dir.name) / "missing.db")

    def test_lists_schema_and_preview(self):
        connection = self.open_read_only()

        self.assertEqual(list_user_tables(connection), ["sales"])
        self.assertIn("商品 TEXT", get_schema_text(connection, "sales"))
        preview = preview_table(connection, "sales", limit=1)
        self.assertEqual(len(preview), 1)
        self.assertEqual(preview.iloc[0]["商品"], "智能手环")

    def test_unknown_table_and_injection_are_rejected(self):
        connection = self.open_read_only()

        for table in ("missing", 'sales"; DROP TABLE sales; --'):
            with self.subTest(table=table):
                with self.assertRaisesRegex(DatabaseAccessError, "允许访问"):
                    require_known_table(connection, table)

    def test_connection_rejects_writes(self):
        connection = self.open_read_only()

        with self.assertRaises(sqlite3.OperationalError):
            connection.execute("DELETE FROM sales")

    def test_preview_limit_is_bounded(self):
        connection = self.open_read_only()

        with self.assertRaisesRegex(ValueError, "1 到 100"):
            preview_table(connection, "sales", limit=101)


if __name__ == "__main__":
    unittest.main()
