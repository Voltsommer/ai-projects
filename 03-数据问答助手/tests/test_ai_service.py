import unittest
from types import SimpleNamespace

import pandas as pd

from ai_service import DeepSeekService


class FakeCompletions:
    def __init__(self, content="测试返回值"):
        self.content = content
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        message = SimpleNamespace(content=self.content)
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])


class FakeClient:
    def __init__(self, content="测试返回值"):
        self.completions = FakeCompletions(content)
        self.chat = SimpleNamespace(completions=self.completions)


class DeepSeekServiceTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient()
        self.service = DeepSeekService(client=self.client)

    def test_generate_pandas_code_includes_schema_and_safety_rules(self):
        df = pd.DataFrame({"商品": ["运动鞋"], "销售额": [9500]})

        result = self.service.generate_pandas_code("哪个商品销售额最高？", df)

        call = self.client.completions.calls[0]
        self.assertEqual(result, "测试返回值")
        self.assertEqual(call["model"], "deepseek-chat")
        self.assertFalse(call["stream"])
        self.assertIn("商品", call["messages"][0]["content"])
        self.assertIn("不要修改 df", call["messages"][0]["content"])
        self.assertEqual(call["messages"][1]["content"], "哪个商品销售额最高？")

    def test_generate_sql_includes_schema_and_select_only_instruction(self):
        self.service.generate_sql("各商品销售额？", "表 sales 的列：商品 TEXT, 销售额 INTEGER")

        call = self.client.completions.calls[0]
        system_prompt = call["messages"][0]["content"]
        self.assertIn("表 sales 的列", system_prompt)
        self.assertIn("只输出 SQL 语句本身", system_prompt)

    def test_generate_answer_includes_question_and_execution_result(self):
        self.service.generate_answer("总销售额？", 103640)

        user_message = self.client.completions.calls[0]["messages"][1]["content"]
        self.assertIn("总销售额？", user_message)
        self.assertIn("103640", user_message)

    def test_rejects_empty_model_response(self):
        service = DeepSeekService(client=FakeClient("   "))

        with self.assertRaisesRegex(RuntimeError, "空内容"):
            service.generate_answer("问题", "结果")

    def test_requires_api_key_when_no_client_is_injected(self):
        with self.assertRaisesRegex(ValueError, "API Key"):
            DeepSeekService()


if __name__ == "__main__":
    unittest.main()
