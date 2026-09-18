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

## 安装缓存与预热

默认将作答前安装好的 Node 与 Harness 软件目录缓存到本地 `.cache/dsh-install/`。
后续题目复制并解压独立软件副本，跳过 Node 下载和 npm 安装。
缓存不包含题面、服务配置、API key、DSH_HOME、会话或题目产物；模型作答后不会更新缓存。
系统基础工具仍按原安装脚本准备，因此缓存命中也可能需要 apt 网络访问。

缓存按容器操作系统发行信息、CPU 架构、glibc 版本、安装脚本摘要和验证命令隔离。
归档恢复前校验 SHA-256，恢复后检查固定 Node/Harness 版本并运行 CLI 帮助自检。
损坏或启动验证失败时重新在线安装；同平台并发请求使用主机文件锁，避免重复构建。
该缓存面向当前 Linux glibc 容器，不保证任意第三方系统库组合都兼容。

可先预热，命令读取本地配置进行接入校验，但不向模型发送请求、不评分：

```bash
uv run python run.py --suite daily-12-v2 --install-only
uv run python run.py --suite daily-12-v2 --attempts 1
```

首次预热仍需下载和安装，不会消除冷启动成本；不同平台分别预热。
不预热也可以直接运行，首道同平台题目会自动填充缓存。
预热的 job 仅为安装记录，不应计入功能通过率。`--dry-run` 仍只预演，不执行预热。

需要对照原在线安装路径时，在命令前设置环境变量：

```bash
DSH_INSTALL_CACHE=0 uv run python run.py --task log-summary-date-ranges
```

正常评测的 `agent_result.metadata.install_cache` 记录 `miss`、`hit`、`rebuilt` 或 `disabled`
及安装耗时，并在启用缓存时记录软件归档摘要；启用缓存时另有 `agent/install-cache.json`。安装日志仍为
`agent/install-dsh.log`。Harbor 预热模式不生成 Agent 作答结果，需查看
`agent/install-cache.json`，不能期待 `agent_result.metadata`。缓存目录被 Git 忽略，不自动上传。

Harness 固定为 0.1.5-rc.1，Node 固定为 24.13.0；npm 的传递依赖仍由首次安装解析，
缓存冻结的是该次安装的软件内容。不同日期重建可能解析不同传递依赖，因此正式对比
建议复用同一份缓存并保留其 SHA-256 文件；缓存校验值用于完整性检查，不是软件签名。

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

## Claude Code CLI

使用独立入口 `run_claude.py`，支持相同的 `--suite`、`--task`、`--attempts`、
`--concurrency`、`--job-name`、`--model`、`--env-file`、`--dry-run` 和 `--install-only`。
也可使用 `run.py --agent claude-code`。原 `run.py` 默认仍是 DeepSeek Harness。

在本地创建 `.env.claude.local`（已被 Git 忽略），填入 Messages 网关配置：

```dotenv
ANTHROPIC_BASE_URL=https://gateway.example.com
ANTHROPIC_API_KEY=replace-with-local-key
ANTHROPIC_MODEL=your-model-id
```

地址使用网关要求的基础路径，不填写完整 `/v1/messages` 请求地址；脚本原样传递，
不自动补 `/v1`。配置从指定文件读取；`--model` 可覆盖模型 ID。
凭据只通过子进程环境传递，不拼进命令行。此入口使用 API key 鉴权，清除继承的
OAuth、Bedrock 等路由选项，避免误用其他模型服务。

```bash
uv run python run_claude.py --suite daily-12-v2 --dry-run
uv run python run_claude.py --suite daily-12-v2 --attempts 1
uv run python run_claude.py --task log-summary-date-ranges
```

使用 Harbor 原生 `claude-code` 适配器安装和运行真实 CLI；结果仍在 `jobs/`。
本项目的 Harness 软件缓存仅适用于 Harness，不会用于 Claude Code。
Claude Code 版本及安装行为由 Harbor 原生适配器管理，正式比较时应核对实际安装版本。
此入口测试覆盖选题和参数传递；网关连通、内网依赖安装和真实模型作答需在实际环境验证。
CLI 评测不等同于 VSCode 插件评测。下文 Harness 的推理设置和 token 统计口径不套用于 Claude Code。

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
