import unittest

from error_messages import user_error_message
from python_executor import PythonValidationError
from sql_executor import SqlExecutionError


class ErrorMessageTests(unittest.TestCase):
    def test_validation_error_does_not_expose_generated_code(self):
        error = PythonValidationError("不允许调用方法：to_pickle")

        message = user_error_message(error, "abc123")

        self.assertIn("未通过安全校验", message)
        self.assertIn("abc123", message)
        self.assertNotIn("to_pickle", message)

    def test_execution_error_does_not_expose_database_detail(self):
        error = SqlExecutionError("SQL 执行失败：no such column: secret")

        message = user_error_message(error)

        self.assertIn("执行失败", message)
        self.assertNotIn("secret", message)

    def test_unknown_error_uses_generic_service_message(self):
        message = user_error_message(RuntimeError("api response body"), "request-1")

        self.assertIn("分析服务暂时不可用", message)
        self.assertNotIn("response body", message)


if __name__ == "__main__":
    unittest.main()
