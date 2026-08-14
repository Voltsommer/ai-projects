# 企业数据问答助手

一个面向企业数据分析场景的 Streamlit 作品集项目：用户用自然语言提问，模型生成受限的 pandas 代码或只读 SQL，程序执行得到结果，再生成可审计的文字回答和图表。

## 项目价值

这个项目重点展示的不是“让模型直接心算”，而是把大模型放在可控制的分析链路中：

1. 数据接入前进行格式、规模和质量检查。
2. 模型只负责生成分析逻辑。
3. SQL / pandas 执行器分别进行清洗、白名单校验和资源限制。
4. 程序执行并返回确定的计算结果。
5. 模型把结果翻译为业务语言。
6. 页面保留生成逻辑和结果预览，支持人工核对。

## 核心能力

- CSV / Excel 文件与 SQLite 数据库双数据源
- 上传文件最大 10 MB、10 万行、100 个字段
- 缺失值、重复行、空字段、字段类型等质量报告
- SQL 单语句只读白名单、SQLite 只读连接、当前表最小权限、授权器、超时和结果行数限制
- pandas 输出清洗、AST 允许清单、原始数据副本执行
- 类别柱状图、单序列趋势图、多序列折线图和近重合点提示
- 可展开的分析过程与最多 20 行结果预览
- 对话原子写入、损坏 JSON 隔离、无 API Key 只读降级
- 隐私友好的 JSON Lines 运行日志：只记录状态、耗时、来源、结果规模和错误类别
- 无需调用 DeepSeek 的离线测试与 GitHub Actions CI

## 架构

```text
Streamlit UI (app.py)
        │
        ├── analysis_service.py ── AI 生成 → 安全执行 → 回答生成
        │       ├── ai_service.py
        │       ├── python_executor.py
        │       └── sql_executor.py
        │
        ├── data_quality.py ───── 文件校验与字段质量报告
        ├── database.py ───────── SQLite 只读连接、表白名单、结构与预览
        ├── chart_builder.py ───── 图表类型判断与 Altair 构建
        ├── analysis_audit.py ──── 可持久化的分析过程与结果预览
        ├── persistence.py ─────── 聊天记录原子写入与损坏隔离
        ├── observability.py ───── 隐私友好的结构化运行日志
        └── app_config.py ──────── 环境变量与运行路径
```

## 快速启动

建议使用 Python 3.12 或更新版本，并创建独立虚拟环境。

```powershell
cd "D:\Code\AI项目\03-数据问答助手"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

$env:DEEPSEEK_API_KEY="你的 DeepSeek API Key"
python -m streamlit run app.py
```

应用首次进入数据库模式时，会由 `sample_data.csv` 自动生成本地 `sales.db`。也可以手动重建：

```powershell
python init_db.py
```

未配置 API Key 时应用仍可启动并浏览数据，但自然语言提问会被禁用。

## 配置

| 环境变量 | 默认值 | 作用 |
|---|---|---|
| `DEEPSEEK_API_KEY` | 无 | 配置后启用自然语言分析 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 模型名称 |
| `APP_ENV` | `development` | `development` / `test` / `production` |

`.streamlit/config.toml` 统一限制上传体积、隐藏生产界面的内部错误细节，并关闭匿名使用统计。

## 测试

全部测试均使用假 AI 客户端或本地数据，不会调用 DeepSeek：

```powershell
python -m unittest discover -s tests -v
python -m compileall -q .
```

测试覆盖：提示词、应用服务链路、SQL / Python 执行器、数据质量、数据库白名单、图表规则、持久化、配置、错误翻译、示例库初始化和运行日志。

## 演示建议

1. 直接进入数据库模式，展示示例表结构和数据预览。
2. 提问“各商品销售额的波动情况如何？”，展示多序列折线图和近重合点交互。
3. 展开“分析过程”，说明 SQL、执行结果和最终答案如何对应。
4. 切换上传文件，上传 `sample_data.csv`，展示数据质量概览。
5. 介绍 SQL 四层防护与 pandas AST 允许清单。
6. 运行离线测试，说明为什么测试不依赖外部模型服务。

## 运行时文件

下列文件只保存在本机，已通过 `.gitignore` 排除：

- `sales.db`：自动生成的示例数据库
- `data.csv`：上次上传并通过检查的数据
- `chat_history.json`：对话与审计记录
- `analysis_events.jsonl`：不含问题正文和数据内容的运行事件
- `*.corrupt-*.json`：损坏聊天记录的隔离备份

## 安全边界

- 代码执行防护可以降低模型输出误执行的风险，但不等同于容器、虚拟机或操作系统级沙箱。
- 项目适合作品集、教学和受控内部原型，不应直接开放给不受信任的公网用户执行任意输入。
- 当前聊天记录和上传数据按单机单用户保存；多用户部署时需要接入用户身份、权限隔离和外部数据库。
- 大模型可能选错字段或聚合口径，因此页面保留生成逻辑和结果预览，关键业务结论仍需人工复核。
