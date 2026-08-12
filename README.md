# AI 应用作品集

用 Python + 大模型 API 从零搭建的 AI 应用系列，方向：**AI 应用开发 / 企业数据智能**。

全部项目共用一套技术栈：DeepSeek API + OpenAI SDK，逐步从命令行 → 网页界面 → 数据智能应用。

## 项目列表

| 目录 | 项目 | 亮点 |
|------|------|------|
| [01-学习助手](01-学习助手/) | 命令行 AI 学习助手 | 多轮对话 + 错误处理 |
| [02-网页学习助手](02-网页学习助手/) | 网页版 AI 学习助手 | Streamlit 聊天界面 |
| [03-数据问答助手](03-数据问答助手/) | 企业数据问答助手 | 自然语言问数据 → AI 写代码 → 图表 |

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

**核心作品**：上传数据后，用自然语言问数据，AI 写 pandas 代码、Python 精确计算、图表展示。

- **上传 CSV / Excel** → 表格预览
- **自然语言提问** → AI 生成 pandas 代码 → Python 执行（100% 精确）
- **自动出图表**：结果为结构化数据时自动画柱状图
- **调试面板**：可展开查看 AI 生成的代码和实际执行结果
- **代码沙箱**：`exec` 执行时屏蔽内置函数，防止不可信代码访问系统
- 技术要点：NL2SQL / Text-to-Code 架构、提示词工程质量、Streamlit 聊天状态管理

```bash
pip install -r 03-数据问答助手/requirements.txt
export DEEPSEEK_API_KEY="你的key"
streamlit run 03-数据问答助手/app.py
```

---

## 通用说明

- 所有项目需要 **DeepSeek API Key**，通过环境变量 `DEEPSEEK_API_KEY` 提供（不写死在代码里）
- 环境变量设置：Windows PowerShell 用 `$env:DEEPSEEK_API_KEY="你的key"`，macOS/Linux 用 `export DEEPSEEK_API_KEY="你的key"`
- 示例数据：`03-数据问答助手/sample_data.csv`
