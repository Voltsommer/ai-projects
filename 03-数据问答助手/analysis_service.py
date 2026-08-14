"""组织 AI 生成、安全执行和回答生成的应用服务层。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from python_executor import execute_pandas_code
from sql_executor import clean_sql_output, execute_read_only_query

MAX_QUESTION_LENGTH = 500

@dataclass(frozen=True)
class AnalysisResult:
    answer: str
    result: Any
    generated_code: str
    language: str
    execution_type: str


def analyse_database_question(question, schema_text, table, connection, ai_service):
    _validate_question(question)
    raw_sql = ai_service.generate_sql(question, schema_text)
    sql = clean_sql_output(raw_sql)
    result = execute_read_only_query(sql, connection, allowed_tables={table})
    answer = ai_service.generate_answer(question, result)
    return AnalysisResult(
        answer=answer,
        result=result,
        generated_code=sql,
        language="sql",
        execution_type="数据库查询",
    )


def analyse_dataframe_question(question, dataframe, ai_service):
    _validate_question(question)
    if not isinstance(dataframe, pd.DataFrame):
        raise TypeError("dataframe 必须是 pandas DataFrame。")
    generated = ai_service.generate_pandas_code(question, dataframe)
    code, result = execute_pandas_code(generated, dataframe)
    answer = ai_service.generate_answer(question, result)
    return AnalysisResult(
        answer=answer,
        result=result,
        generated_code=code,
        language="python",
        execution_type="Pandas 分析",
    )


def _validate_question(question):
    if not isinstance(question, str) or not question.strip():
        raise ValueError("问题不能为空。")
    if len(question.strip()) > MAX_QUESTION_LENGTH:
        raise ValueError(f"问题不能超过 {MAX_QUESTION_LENGTH} 个字符。")
