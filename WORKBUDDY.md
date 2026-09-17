# WorkBuddy 桌面半自动评测

使用实际 WorkBuddy 桌面产品调用自部署模型，通过 MCP 在 Harbor 的单题容器里
执行任务，再由原始验收器评分。没有用 CodeBuddy CLI 替代 WorkBuddy，也不需要
WorkBuddy 的 headless 接口。当前入口仅支持单题串行。

## 首次配置

```bash
uv sync --locked
uv run python workbuddy_eval.py config
```

将生成的 `.local/workbuddy/mcp-config.json` 中 `mcpServers.harbor-eval`
合并到 WorkBuddy 的自定义 MCP 连接器配置，保留已有连接器。操作前在本地备份
原配置；按 WorkBuddy 界面提示重新加载。配置引用当前 `.venv` Python 的绝对路径，
移动仓库或重建环境后需重新生成。该配置包含本机路径，不要提交。

连接器只暴露两个工具：

- `harbor_task`：读取当前原始题面和 trial ID。
- `harbor_exec`：在该题的 Linux 容器中执行命令，包括读写文件和运行程序。

题目尚未启动时，工具调用会报告找不到连接文件；这不影响 MCP 握手和工具发现。
工具名可能被客户端加上连接器前缀。

在 WorkBuddy 模型设置中新增自定义 OpenAI 兼容模型，填写本地 `.env.local`
对应的服务和模型 ID，启用工具调用。该界面的 URL 是完整 Chat Completions 地址：
基础地址仅有协议、主机、端口时需加 `/v1/chat/completions`；已有 `/v1` 时只加
`/chat/completions`。API key 只保存在本地应用设置中。务必在新任务中实际选择这个模型。
启动脚本的 `CHAT_MODEL` 仅为 Harbor 结果标签，不能替代桌面端选择或证明实际模型身份。

先完成模型、MCP 和工作区设置再启动计时。每次新建独立会话，选择空的临时工作区，
不要选择评测仓库或题库目录。关闭记忆、技能积累及无关连接器，并记录无法关闭的功能；
不要沿用已看过答案的会话。提示词要求仅使用 MCP，但不能强制禁止 WorkBuddy 原生工具。

## 单题流程

将下面的版本占位符替换为应用显示的实际版本号：

```bash
uv run python workbuddy_eval.py start \
  --task log-summary-date-ranges \
  --version '<实际版本号>' \
  --job-name workbuddy-smoke-01
```

保持该终端运行。在另一个终端检查就绪状态：

```bash
uv run python workbuddy_eval.py status
```

就绪后把 `.local/workbuddy/prompt.txt` 粘贴到 WorkBuddy 的新任务并发送。
文件包含工具使用说明和未改写的题目正文。允许本次题目的 MCP 工具调用，观察其独立
作答；不要提供解法或替它运行解决题目的命令。每次 `harbor_exec` 必须携带当前
`harbor_task` 返回的 trial ID；单次命令超时范围为 1–120 秒，可分多次执行。

WorkBuddy 报告完成后，操作者用 `status` 中的 trial ID 结束本题：

```bash
uv run python workbuddy_eval.py finish --trial-id '<当前 trial ID>'
```

结束入口使用独立凭据，不暴露为模型工具。它停止接收新命令、等待当前命令完成，
再让 Harbor 运行原始验收器。不要在 WorkBuddy 仍在作答时调用 `finish`。
中断或题目超时也会关闭桥接入口。换题时重新启动，使用新的 WorkBuddy 会话；
旧 ID 的命令会被拒绝。不要并行启动多个桌面 trial。

## 结果和口径

查看 `jobs/<job-name>/result.json`、trial 的 `result.json`、
`verifier/reward.txt` 和验收输出，进程退出码为 0 本身不代表答对。
`agent/workbuddy-commands.jsonl` 保存桥接执行的命令和完整结果，工具返回的
stdout、stderr 各最多 32000 字符，截断时带 `truncated: true`。

结果标记为 `workbuddy-desktop-mcp`，记录应用版本、命令次数、人工结束状态。
Token 和费用保持未知，不借用 Harness 的统计，也不从字数估算。
原题超时保持不变，计时包含粘贴、授权和人工等待时间。应将此运行方式与纯 headless
成绩分开标注；它验证的是“桌面产品 + MCP 容器工具”的功能表现。

桥接只监听本机，凭据、提示词、配置、日志均仅存本地被忽略的目录。
它无法强制关闭桌面原生工具或证明记忆隔离，因此不能宣称严格防作弊。
原生工具操作和完整 UI 会话不会自动出现在桥接日志中。结果中没有记录的模型用量、
模型切换和界面操作，需要操作者另行记录在 `.local/`，不能假定不存在。

## 验证范围

```bash
uv run python -m unittest test_workbuddy -v
```

自动测试覆盖桥接边界、执行与结束的先后顺序、真实 stdio MCP 子进程握手与工具调用、
Agent 正常结束和取消时的清理。协议测试使用合成任务，不调用模型，
不能代替实际 WorkBuddy 完成公共题目的端到端验收。
