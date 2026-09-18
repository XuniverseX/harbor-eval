# usage_stats.py：读取 Harness 用量摘要

[对应脚本](../../usage_stats.py) · [返回脚本索引](README.md)

## 用途与运行

只读分析一个 trial 的 Agent 日志，不调用模型、不修改结果文件。

```bash
uv run python usage_stats.py jobs/<job>/<trial>/agent
```

唯一位置参数 `agent_logs` 是 trial 下的 `agent` 目录，不是整个 job 目录。

## 输入输出

优先读取 `token-usage.jsonl`；不存在时读取 `dsh-home/storages/session_projcache/sessions/` 中可识别的旧投影。stdout 输出 JSON 摘要，含输入、输出、缓存 token、来源和完整性状态。输入包含缓存读取与写入；缓存读取已经包含于输入，推理 token 不重复加到输出。

`complete` 表示已观测事件满足结算条件，`partial` 表示仅统计已知部分，`unavailable` 表示没有可用统计。未知值不是零；旧投影无法可靠扣除继承历史时会跳过。该工具适用于 Harness，不为 WorkBuddy 或 Claude Code 推算用量。函数 `summarize_usage(Path)` 也供适配器调用。
