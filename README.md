# Harbor × DeepSeek Harness

通过 Harbor 驱动真实 DeepSeek Harness headless CLI，连接自行配置的
Chat Completions 服务，使用 Terminal-Bench 2.0 公共题目及原始验收器评分。
提供 DeepSeek Harness 自动适配器和 [WorkBuddy 桌面 MCP 半自动适配器](WORKBUDDY.md)。

## 安装

需要可用的 Docker 和 uv。在仓库根目录创建 Python 环境：

```bash
uv sync --locked
```

项目使用 Python 3.12，`uv sync --locked` 按 `uv.lock` 创建本地 `.venv`。
后续使用 `uv run`，无需激活环境，也不依赖全局安装的 Harbor。
`.venv` 不提交；`pyproject.toml`、`.python-version` 和 `uv.lock` 随代码提交。

适配器在题目容器内安装 Node 24.13.0 和
`@deepseek-ai/dsh@0.1.5-rc.1`，不使用宿主机的 Harness 安装。
该版本 headless 不支持 `--json` 或从标准输入读取题目；适配器安全地将题目作为
位置参数传入，使用普通文本输出并保留原生会话记录。

## 本地配置

在仓库根目录创建 `.env.local`，设置以下变量：

| 变量 | 含义 |
| --- | --- |
| `CHAT_BASE_URL` | 模型服务基础地址；只有协议、主机和端口时自动补 `/v1` |
| `CHAT_API_KEY` | 模型服务凭据 |
| `CHAT_MODEL` | 服务实际接受的模型 ID |

`.env.local` 已加入 `.gitignore`。可通过 `--env-file` 指定其他本地文件，
通过 `--model` 覆盖模型选择。不要把真实配置写入代码、测试、文档或提交说明。
模型地址必须从题目容器内可达；如需代理，请仅在本地配置，并按需让模型服务直连。

## 运行

```bash
uv run harbor datasets download terminal-bench@2.0 -o datasets
uv run python -m unittest discover -v
node --test test_usage_recorder.mjs
uv run python run.py --task cancel-async-tasks
```

记录器测试需要本地 Node.js。默认只执行一道公共题，确认接入后可显式运行完整题集：

```bash
uv run python run.py --task ALL --attempts 3 --concurrency 2
```

完整评测会产生更多模型请求。使用相同题库版本、模型配置和运行预算比较
不同实验；不要将单题成绩视为完整基准成绩。

日常对比使用已锁定的 12 题精简集合，另有其中 5 题用于接入验证。
具体题名、选题依据和环境依赖见 [固定题目集](suites/README.md)。

```bash
uv run python run.py --suite smoke-5-v1 --dry-run
uv run python run.py --suite smoke-5-v1
uv run python run.py --suite daily-12-v2 --attempts 3 --dry-run
uv run python run.py --suite daily-12-v2 --attempts 3
```

12 题各运行 3 次共 36 个 trial；日常可使用 `--attempts 1`，只运行 12 次。
旧 `daily-20-v1` 保留用于复现历史结果。`--dry-run` 不读取凭据、不调用模型；
固定集合会校验本地题库文件，缺题或内容漂移即停止。默认并发为 1。

## 执行与评分

- 使用原始题目超时和验收脚本，任务通过与否由 Harbor 验收器判定。
- 推理等级为 `high`，每次请求输出上限为 32768 token。
- 每个题目在独立容器内使用独立 DSH_HOME，无人值守文件权限仅作用于该容器。
- 密钥通过进程环境传递，不放入命令行参数或公开配置。
- 模型作答和 Agent 安装分别计时；CLI 非零退出报告为运行异常。
- Token 从 Harness 原生 usage 事件汇总并回填 Harbor；缺失指标保持未知，费用不估算。

本地 `jobs/<job-name>/result.json` 保存汇总；每个 trial 目录保存独立结果、
`verifier/reward.txt`、验收输出以及 `agent/` 下的安装日志和原生会话。
`agent/dsh.stdout.log` 保存最终文本，`agent/dsh.stderr.log` 保存推理进度和诊断。
Harbor 进程返回 0 不代表所有题目通过，应检查结果文件及异常。

题库、原始日志、配置和实际评测记录仅保留在被 Git 忽略的目录中。
需要保存个人说明或结果摘要时使用 `.local/`；本项目不自动上传 Harbor Hub。

## Token 统计

适配器通过旁路插件订阅原生会话事件，仅写入用量、轮次和会话标识，不保存
请求正文或凭据。Harbor 下载日志后自动填充：

| Harbor 字段 | 统计口径 |
| --- | --- |
| `n_input_tokens` | 未缓存输入 + 缓存读取 + 缓存写入 |
| `n_cache_tokens` | 缓存读取，已经包含在输入总量中 |
| `n_output_tokens` | 服务上报的输出；推理 token 不重复相加 |
| `cost_usd` | 保持未知，不套用其他模型的价格 |

同次尝试的 usage 更新取最后一个样本；真正重试另算一次。多个会话分别计算，
fork 或恢复时继承的历史不参与本次运行累计。费用和按模型拆分的用量不推测。

`agent/token-usage.jsonl` 保存统计事件，`agent/token-usage-summary.json` 保存摘要；
相同摘要也写入 trial 的 `agent_result.metadata.token_usage`。其中 `status`：

- `complete`：观测到的会话已结束，结算记录均含有效 usage。
- `partial`：只统计已知部分，例如日志中断、调用缺少 usage 或使用旧缓存。
- `unavailable`：没有可用的 usage，Harbor token 字段保持 `null`。

完整性仅指记录到的会话调用；没有被服务上报或没有进入会话事件的消耗无法估算。
部分统计的 token 数不能当作全量消耗。可在不调用模型的情况下读取旧日志：

```bash
uv run python usage_stats.py jobs/<job-name>/<trial-name>/agent
```

旧日志没有统计事件时，退回原生 `tokenUsage` 投影缓存；缓存可能滞后且会把
缺失缓存分项默认成零，因此标记为 `partial`。带继承历史的旧投影无法可靠扣除
父会话用量，跳过并给出提示；不会同时累加新事件与旧投影。

## 协作

代码使用中文注释；每完成一个有文件改动的任务，执行相应检查后创建 commit。
具体约定见 [AGENTS.md](AGENTS.md)。
