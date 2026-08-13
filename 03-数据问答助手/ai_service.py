"""DeepSeek 请求与提示词：独立于 Streamlit 界面，便于离线测试。"""

from openai import OpenAI


DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"


class DeepSeekService:
    """负责生成 pandas 代码、SQL 和最终自然语言回答。"""

    def __init__(self, api_key=None, client=None, model=DEFAULT_MODEL):
        if client is None:
            if not api_key:
                raise ValueError("缺少 DeepSeek API Key。")
            client = OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)
        self._client = client
        self._model = model

    def _complete(self, messages) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            stream=False,
        )
        content = response.choices[0].message.content
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("DeepSeek 返回了空内容。")
        return content.strip()

    def generate_pandas_code(self, question, df) -> str:
        schema = df.dtypes.to_string()
        system_prompt = (
            f"你是数据分析专家。数据是 pandas DataFrame（变量名 df），每一行是一条销售记录，列名和类型：\n{schema}\n"
            "请编写 pandas 代码回答用户问题。要求：\n"
            "1. 只输出赋值语句，不解释；结果存进 answer 变量；不要 import、循环、函数或类定义；df 已加载。\n"
            "2. 问题里问'哪个商品/品类/地区…最高/最多/合计'这类，必须先按对应维度分组汇总再比较，不能直接对单行取最大。\n"
            "3. 示例：'哪个商品销售额最高' → answer = df.groupby('商品')['销售额'].sum().idxmax()\n"
            "4. 如果问题适合用图表展示（对比、分布、趋势），让 answer 是 pandas Series 或 DataFrame：索引是类别/时间，值是数值。\n"
            "5. 不要修改 df，不要读写文件，不要使用 inplace=True；需要中间结果时，只使用普通临时变量赋值。"
        )
        return self._complete(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ]
        )

    def generate_sql(self, question, schema_text) -> str:
        system_prompt = (
            f"你是 SQL 专家。数据库模式如下：\n{schema_text}\n"
            "请根据用户问题生成 SQL 查询语句。要求：\n"
            "1. 只输出 SQL 语句本身（可直接执行的查询），不要解释，不要加任何 Python 前缀（如 answer = ）、引号或 markdown 代码块。\n"
            "2. 问题里问'哪个商品/品类/地区…最高/最多/合计'这类，必须先按对应维度分组汇总再比较，不能直接对单行取最大。\n"
            "3. 示例：'哪个商品销售额最高' → SELECT 商品, SUM(销售额) AS 总销售额 FROM sales GROUP BY 商品 ORDER BY 总销售额 DESC LIMIT 1\n"
            "4. 如果问题适合用图表展示（对比、分布、趋势），让查询结果包含类别/时间列和数值列。"
        )
        return self._complete(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ]
        )

    def generate_answer(self, question, result) -> str:
        return self._complete(
            [
                {
                    "role": "system",
                    "content": "你是数据分析专家。根据用户的问题和执行结果生成自然语言回答，简洁、给出具体数字。",
                },
                {
                    "role": "user",
                    "content": f"用户问题: {question}\n\n执行结果:\n{result}",
                },
            ]
        )
