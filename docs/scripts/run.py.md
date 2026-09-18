# run.py：DeepSeek Harness 默认启动入口

[对应脚本](../../run.py) · [返回脚本索引](README.md)

## 用途与前提

使用 uv 环境中的 Harbor 调度公共题库，默认执行 DeepSeek Harness。需要先运行 `uv sync --locked`，准备 Docker 和 `datasets/terminal-bench/`。从仓库根目录执行以下命令。

## 本地配置

默认读取 `.env.local` 中的 `CHAT_BASE_URL`、`CHAT_API_KEY`、`CHAT_MODEL`。服务基础地址只有协议和主机时，Harness 适配器补 `/v1`。模型可由 `--model` 覆盖。实际配置只存本地被忽略的文件。

## 参数

| 参数 | 默认值与作用 |
| --- | --- |
| `--agent` | `deepseek-harness`；也可选 `claude-code` |
| `--task` | 未指定范围时为 `cancel-async-tasks`；`ALL` 运行整个本地题库 |
| `--suite` | 与 `--task` 互斥；支持 `daily-12-v2`、`daily-20-v1`、`smoke-5-v1` |
| `--attempts` | 1，每题尝试次数，必须为正整数 |
| `--concurrency` | 1，并发 trial 数，必须为正整数 |
| `--job-name` | 未指定时由 Harbor 生成；使用未占用的名称 |
| `--env-file` | 默认随 Agent 选择；可指定另一份本地配置 |
| `--model` | 覆盖配置文件中的模型 ID |
| `--dry-run` | 校验范围并打印 JSON，不读取凭据、不运行容器或模型 |
| `--install-only` | 只准备环境、安装 Agent，不作答、不评分 |

## 示例

```bash
uv run python run.py --suite daily-12-v2 --dry-run
uv run python run.py --suite daily-12-v2 --attempts 1
uv run python run.py --suite daily-12-v2 --install-only
uv run python run.py --task log-summary-date-ranges --job-name harness-log-01
```

选择 `--agent claude-code` 时改读 `.env.claude.local`，见 [Claude Code 说明](run_claude.py.md)。

## 输出与排查

预演打印题名、trial 数和 Agent。正式结果在 `jobs/<job>/`；查看汇总和每题 `result.json`、`verifier/reward.txt`。退出码 0 不代表题目通过。固定清单校验失败应恢复对应题库版本；不要直接修改摘要。Harness 安装缓存默认开启，关闭方式为 `DSH_INSTALL_CACHE=0 uv run python run.py ...`。参见 [缓存说明](install_cache.py.md)。
