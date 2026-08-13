"""AI 生成的 pandas 代码：清洗、AST 校验和受限执行。

这是学习项目中的分层防护，不是操作系统级安全沙箱。
模块不依赖 Streamlit 或大模型 API，因此可以独立测试。
"""

import ast
import re

import pandas as pd


DEFAULT_MAX_CODE_LENGTH = 10_000
DEFAULT_MAX_AST_NODES = 300
DEFAULT_MAX_STRING_LENGTH = 2_000
DEFAULT_MAX_POWER = 10

ALLOWED_AGGREGATIONS = {
    "count",
    "first",
    "last",
    "max",
    "mean",
    "median",
    "min",
    "nunique",
    "size",
    "std",
    "sum",
    "var",
}

# 只开放数据分析常见操作。需要新能力时，应先补测试，再扩充允许清单。
ALLOWED_METHODS = {
    "abs",
    "agg",
    "aggregate",
    "all",
    "any",
    "astype",
    "between",
    "clip",
    "contains",
    "corr",
    "count",
    "cumprod",
    "cumsum",
    "describe",
    "diff",
    "drop",
    "drop_duplicates",
    "dropna",
    "duplicated",
    "endswith",
    "first",
    "fillna",
    "groupby",
    "head",
    "idxmax",
    "idxmin",
    "isin",
    "isna",
    "last",
    "lower",
    "max",
    "mean",
    "median",
    "melt",
    "min",
    "nlargest",
    "nsmallest",
    "notna",
    "nunique",
    "pct_change",
    "pivot",
    "pivot_table",
    "prod",
    "quantile",
    "rank",
    "rename",
    "replace",
    "reset_index",
    "round",
    "select_dtypes",
    "set_index",
    "size",
    "sort_index",
    "sort_values",
    "stack",
    "startswith",
    "std",
    "strip",
    "sum",
    "tail",
    "tolist",
    "unstack",
    "upper",
    "value_counts",
    "var",
    "where",
}

ALLOWED_ATTRIBUTES = {
    "columns",
    "day",
    "dt",
    "dtypes",
    "empty",
    "index",
    "iloc",
    "is_monotonic_decreasing",
    "is_monotonic_increasing",
    "loc",
    "month",
    "name",
    "ndim",
    "shape",
    "str",
    "T",
    "values",
    "year",
} | ALLOWED_METHODS

SAFE_FUNCTIONS = {
    "abs": abs,
    "len": len,
    "max": max,
    "min": min,
    "round": round,
    "sum": sum,
}

ALLOWED_NODE_TYPES = (
    ast.Module,
    ast.Assign,
    ast.Name,
    ast.Load,
    ast.Store,
    ast.Constant,
    ast.Attribute,
    ast.Subscript,
    ast.Slice,
    ast.Tuple,
    ast.List,
    ast.Dict,
    ast.Set,
    ast.Call,
    ast.keyword,
    ast.BinOp,
    ast.UnaryOp,
    ast.BoolOp,
    ast.Compare,
    ast.IfExp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.BitAnd,
    ast.BitOr,
    ast.BitXor,
    ast.And,
    ast.Or,
    ast.Not,
    ast.UAdd,
    ast.USub,
    ast.Invert,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.In,
    ast.NotIn,
    ast.Is,
    ast.IsNot,
)


class PythonValidationError(ValueError):
    """AI 生成的内容超出了允许的数据分析语法。"""


class PythonExecutionError(RuntimeError):
    """代码通过语法校验，但执行时失败。"""


def clean_python_output(raw_code: str) -> str:
    """去掉模型偶尔返回的 Markdown 代码块。"""
    if not isinstance(raw_code, str) or not raw_code.strip():
        raise PythonValidationError("AI 没有返回可执行的 pandas 代码。")

    code = raw_code.strip()
    fenced = re.fullmatch(
        r"```(?:python|py)?\s*(.*?)\s*```",
        code,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if fenced:
        code = fenced.group(1).strip()

    if not code:
        raise PythonValidationError("清洗后没有可执行的 pandas 代码。")
    if len(code) > DEFAULT_MAX_CODE_LENGTH:
        raise PythonValidationError("AI 生成的代码过长，已拒绝执行。")
    return code


class _PandasCodeValidator(ast.NodeVisitor):
    """用允许清单检查 AST 中的语句、名称、属性和函数调用。"""

    def __init__(self, tree: ast.Module):
        self.node_count = 0
        self.assigned_names = {
            target.id
            for node in tree.body
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name)
        }

    def generic_visit(self, node):
        self.node_count += 1
        if self.node_count > DEFAULT_MAX_AST_NODES:
            raise PythonValidationError("AI 生成的代码结构过于复杂，已拒绝执行。")
        if not isinstance(node, ALLOWED_NODE_TYPES):
            raise PythonValidationError(
                f"不允许使用语法：{type(node).__name__}。请只生成 pandas 分析表达式。"
            )
        super().generic_visit(node)

    def visit_Assign(self, node):
        for target in node.targets:
            if not isinstance(target, ast.Name):
                raise PythonValidationError("只允许给 answer 或临时变量赋值。")
            if target.id == "df":
                raise PythonValidationError("不允许覆盖原始数据变量 df。")
            if target.id.startswith("_"):
                raise PythonValidationError("临时变量名不能以下划线开头。")
        self.generic_visit(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            allowed_names = {"df", *self.assigned_names, *SAFE_FUNCTIONS}
            if node.id not in allowed_names:
                raise PythonValidationError(f"不允许访问名称：{node.id}。")
        self.generic_visit(node)

    def visit_Attribute(self, node):
        if node.attr.startswith("_") or node.attr not in ALLOWED_ATTRIBUTES:
            raise PythonValidationError(f"不允许访问属性或方法：{node.attr}。")
        self.generic_visit(node)

    def visit_Constant(self, node):
        if isinstance(node.value, (str, bytes)) and len(node.value) > DEFAULT_MAX_STRING_LENGTH:
            raise PythonValidationError("代码中的字符串常量过长，已拒绝执行。")
        self.generic_visit(node)

    def visit_BinOp(self, node):
        if isinstance(node.op, ast.Mult) and (
            self._is_literal_sequence(node.left) or self._is_literal_sequence(node.right)
        ):
            raise PythonValidationError("不允许通过乘法批量复制字符串或容器。")
        if isinstance(node.op, ast.Pow):
            if not isinstance(node.right, ast.Constant) or not isinstance(node.right.value, (int, float)):
                raise PythonValidationError("幂运算的指数必须是较小的数字常量。")
            if abs(node.right.value) > DEFAULT_MAX_POWER:
                raise PythonValidationError("幂运算的指数过大，已拒绝执行。")
        self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Attribute):
            if node.func.attr not in ALLOWED_METHODS:
                raise PythonValidationError(f"不允许调用方法：{node.func.attr}。")
            if node.func.attr in {"agg", "aggregate"}:
                self._validate_aggregation_call(node)
            elif node.func.attr == "pivot_table":
                self._validate_pivot_table_call(node)
        elif isinstance(node.func, ast.Name):
            if node.func.id not in SAFE_FUNCTIONS:
                raise PythonValidationError(f"不允许调用函数：{node.func.id}。")
        else:
            raise PythonValidationError("只允许调用白名单中的 pandas 方法和基础函数。")

        for keyword in node.keywords:
            if keyword.arg is None:
                raise PythonValidationError("不允许使用 **kwargs 展开参数。")
            if keyword.arg == "inplace":
                if not isinstance(keyword.value, ast.Constant) or keyword.value.value is not False:
                    raise PythonValidationError("不允许使用 inplace=True 修改数据。")
        self.generic_visit(node)

    @staticmethod
    def _is_literal_sequence(node: ast.AST) -> bool:
        return isinstance(node, (ast.List, ast.Tuple, ast.Set, ast.Dict)) or (
            isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes))
        )

    def _validate_aggregation_call(self, node: ast.Call):
        if not node.args and not node.keywords:
            raise PythonValidationError("agg 必须明确指定允许的聚合函数。")

        for argument in node.args:
            self._validate_aggregation_spec(argument)
        for keyword in node.keywords:
            if keyword.arg == "axis":
                if not isinstance(keyword.value, ast.Constant) or keyword.value.value not in {0, 1}:
                    raise PythonValidationError("agg 的 axis 只允许使用 0 或 1。")
            elif keyword.arg in {"engine", "engine_kwargs"}:
                raise PythonValidationError("不允许为 agg 指定执行引擎。")
            else:
                self._validate_aggregation_spec(keyword.value, allow_named_tuple=True)

    def _validate_pivot_table_call(self, node: ast.Call):
        if len(node.args) >= 4:
            self._validate_aggregation_spec(node.args[3])
        for keyword in node.keywords:
            if keyword.arg == "aggfunc":
                self._validate_aggregation_spec(keyword.value)

    def _validate_aggregation_spec(self, node: ast.AST, *, allow_named_tuple: bool = False):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value not in ALLOWED_AGGREGATIONS:
                raise PythonValidationError(f"不允许使用聚合函数：{node.value}。")
            return
        if isinstance(node, (ast.List, ast.Tuple)):
            # 命名聚合格式：新列名=(原列名, "sum")
            if (
                allow_named_tuple
                and isinstance(node, ast.Tuple)
                and len(node.elts) == 2
                and isinstance(node.elts[0], ast.Constant)
                and isinstance(node.elts[0].value, str)
            ):
                self._validate_aggregation_spec(node.elts[1])
                return
            for element in node.elts:
                self._validate_aggregation_spec(element)
            return
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
                    raise PythonValidationError("agg 字典的列名必须是普通字符串。")
                self._validate_aggregation_spec(value)
            return
        raise PythonValidationError("聚合函数必须使用允许清单中的字符串常量。")


def validate_pandas_code(raw_code: str) -> tuple[str, ast.Module]:
    """返回清洗后的代码和校验通过的语法树。"""
    code = clean_python_output(raw_code)
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as error:
        raise PythonValidationError(f"Python 语法错误：{error.msg}。") from error

    if not tree.body:
        raise PythonValidationError("代码中没有可执行语句。")
    if not all(isinstance(statement, ast.Assign) for statement in tree.body):
        raise PythonValidationError("只允许赋值语句，最终结果必须保存到 answer。")

    answer_assignments = [
        statement
        for statement in tree.body
        if any(isinstance(target, ast.Name) and target.id == "answer" for target in statement.targets)
    ]
    if not answer_assignments:
        raise PythonValidationError("代码必须把最终结果保存到 answer 变量。")

    _PandasCodeValidator(tree).visit(tree)
    return code, tree


def execute_pandas_code(raw_code: str, df: pd.DataFrame):
    """校验后在 DataFrame 深拷贝上执行，并返回 answer。"""
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df 必须是 pandas DataFrame。")

    code, tree = validate_pandas_code(raw_code)
    safe_df = df.copy(deep=True)
    local_vars = {"df": safe_df}
    safe_globals = {"__builtins__": SAFE_FUNCTIONS}

    try:
        exec(compile(tree, "<ai-pandas-code>", "exec"), safe_globals, local_vars)
    except Exception as error:
        raise PythonExecutionError(f"pandas 代码执行失败：{error}") from error

    if "answer" not in local_vars or local_vars["answer"] is None:
        raise PythonExecutionError("代码没有生成有效的 answer 结果。")
    return code, local_vars["answer"]
