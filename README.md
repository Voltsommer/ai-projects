# AI 应用作品集

用 Python + 大模型 API 从零搭建的 AI 应用系列，方向：**AI 应用开发 / 企业数据智能**。

全部项目共用一套技术栈：DeepSeek API + OpenAI SDK，逐步从命令行 → 网页界面 → 数据智能应用。

## 项目列表

| 目录 | 项目 | 亮点 |
|------|------|------|
| [01-学习助手](01-学习助手/) | 命令行 AI 学习助手 | 多轮对话 + 错误处理 |
| [02-网页学习助手](02-网页学习助手/) | 网页版 AI 学习助手 | Streamlit 聊天界面 |
| [03-数据问答助手](03-数据问答助手/) | 企业数据问答助手 | 自然语言问数据 → AI 写代码（pandas / SQL）→ 图表 |

---

## 01 · 命令行 AI 学习助手

基于 DeepSeek API 的多轮对话助手。我的第一个 AI 应用。

- **连续对话**：自动维护对话历史，让模型记住上下文
- **角色设定**：通过 system 提示词定制 AI 人设
- **`/exit` 退出**：命令行交互支持退出命令
- **错误处理**：网络 / API 出错不崩溃，并自动清理对话历史中的残留消息
- 技术要点：`messages` 消息历史管理、`try / except / else` 区分成功与错误路径

```bash
pip install openai
export DEEPSEEK_API_KEY="你的key"
python 01-学习助手/main.py
```

---

## 02 · 网页版 AI 学习助手（Streamlit）

把命令行助手搬进浏览器，学会用 Streamlit 做聊天界面。

- `st.session_state` 保存对话历史（跨重跑保留）
- `st.chat_message` / `st.chat_input` 聊天组件
- `st.error` 界面内错误提示

```bash
pip install -r 02-网页学习助手/requirements.txt
export DEEPSEEK_API_KEY="你的key"
streamlit run 02-网页学习助手/app.py
```

---

## 03 · 企业数据问答助手（Streamlit）

**核心作品**：用自然语言问数据，AI 写代码（pandas / SQL）、Python 精确计算、自动出图表。支持**上传文件**和**连接数据库**两种数据来源。

- **两种数据来源**：上传 CSV / Excel，或直接连接 SQLite 数据库查询
- **自然语言提问** → AI 生成 pandas 代码（文件模式）或 SQL（数据库模式）→ 由程序执行计算，减少模型直接心算造成的数值幻觉
- **自动出图表**：类别 → 柱状图，月份 / 数字 → 折线图，按数据可视化规范定制配色与布局
- **调试面板**：可展开查看 AI 生成的代码（SQL）和实际执行结果
- **分层执行防护**：SQL 经过输出清洗、只读查询白名单、SQLite 只读授权、超时和行数限制；pandas 代码使用屏蔽内置函数的受限执行环境
- **数据持久化**：对话文字与上次上传的数据存本地，刷新页面后可恢复；侧边栏一键清除对话
- 技术要点：NL2SQL / Text-to-Code 架构、提示词工程、SQL 分层执行防护、Streamlit 状态管理

```bash
pip install -r 03-数据问答助手/requirements.txt
export DEEPSEEK_API_KEY="你的key"

# 首次使用：生成示例数据库（可选，仅数据库模式需要）
cd 03-数据问答助手 && python init_db.py

streamlit run 03-数据问答助手/app.py

# 离线运行 SQL 安全测试（不会调用 DeepSeek）
cd 03-数据问答助手
python -m unittest discover -s tests -v
```

---

## 通用说明

- 所有项目需要 **DeepSeek API Key**，通过环境变量 `DEEPSEEK_API_KEY` 提供（不写死在代码里）
- 环境变量设置：Windows PowerShell 用 `$env:DEEPSEEK_API_KEY="你的key"`，macOS/Linux 用 `export DEEPSEEK_API_KEY="你的key"`
- 示例数据：`03-数据问答助手/sample_data.csv`

> 安全说明：程序执行能提高数值计算的可靠性，但 AI 仍可能选错字段或聚合方式，因此调试面板会保留生成逻辑和实际结果供核对。当前 pandas `exec` 是学习项目中的基础限制，不等同于操作系统级安全沙箱，不应直接用于执行不受信任用户提交的代码。
