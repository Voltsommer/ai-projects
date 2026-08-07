# AI 学习助手（命令行版）

基于 DeepSeek API 的多轮对话 AI 学习助手。这是我 AI 应用开发方向的第一个作品。

## 功能

- **连续对话**：自动维护对话历史，让模型记住上下文
- **角色设定**：通过 system 提示词定制 AI 人设
- **`/exit` 退出**：命令行交互支持退出命令
- **错误处理**：网络 / API 出错不崩溃，并自动清理对话历史中的残留消息

## 技术要点

- Python + OpenAI SDK 调用 DeepSeek API
- 多轮对话的消息历史管理（`messages` 列表 + 全量回传）
- `try / except / else` 区分成功路径与错误路径
- API Key 通过环境变量管理，不写死在代码里

## 运行

```bash
# 1. 安装依赖
pip install openai

# 2. 设置环境变量
#   Windows PowerShell:
#     $env:DEEPSEEK_API_KEY = "你的key"
#   macOS / Linux:
#     export DEEPSEEK_API_KEY="你的key"

# 3. 运行
python main.py
```

## 演示

```
你 > 给我讲讲 Python 里列表和字典的区别
AI > （给出讲解……）

你 > 那元组呢？
AI > （能记住上一轮上下文，结合列表、字典一起对比讲解）
```
