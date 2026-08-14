"""把内部异常翻译为不泄露实现细节的用户提示。"""

from __future__ import annotations

from database import DatabaseAccessError
from data_quality import DataQualityError
from persistence import PersistenceError
from init_db import SampleDatabaseError
from python_executor import PythonExecutionError, PythonValidationError
from sql_executor import SqlExecutionError, SqlValidationError


def user_error_message(error: Exception, request_id: str | None = None) -> str:
    if isinstance(error, (SqlValidationError, PythonValidationError)):
        message = "生成的分析逻辑未通过安全校验，请换一种问法后重试。"
    elif isinstance(error, (SqlExecutionError, PythonExecutionError)):
        message = "分析逻辑执行失败，请检查字段名称或缩小问题范围后重试。"
    elif isinstance(error, DataQualityError):
        message = str(error)
    elif isinstance(error, (DatabaseAccessError, SampleDatabaseError)):
        message = "数据库暂时不可用，请检查示例数据库是否已正确初始化。"
    elif isinstance(error, PersistenceError):
        message = "结果已生成，但本地记录保存失败。"
    else:
        message = "分析服务暂时不可用，请稍后重试。"

    if request_id:
        message += f" 请求编号：{request_id}"
    return message
