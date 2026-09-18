# workbuddy_eval.py：WorkBuddy 半自动评测操作入口

[对应脚本](../../workbuddy_eval.py) · [返回脚本索引](README.md)

## 用途与配置

协调真实 WorkBuddy 桌面和 Harbor 单题容器，不替桌面调用模型。需要 Docker、uv、WorkBuddy 已配置自部署模型与 MCP。默认读取 `.env.local` 的 `CHAT_MODEL` 作为结果标签；真实模型必须在 WorkBuddy 中选择一致。

## 子命令

| 命令 | 参数及作用 |
| --- | --- |
| `config` | 无附加参数；生成 `.local/workbuddy/mcp-config.json`，需合并进应用连接器配置 |
| `start` | `--task` 默认 `log-summary-date-ranges`；必填 `--version`；可选 `--env-file`、`--job-name` |
| `status` | 无附加参数；显示当前 trial ID、接收状态和命令数 |
| `finish` | 必填 `--trial-id`，由操作者确认作答结束后调用 |

## 操作示例

```bash
uv run python workbuddy_eval.py config
uv run python workbuddy_eval.py start --task log-summary-date-ranges --version '<应用实际版本>' --job-name wb-log-01
```

保持启动终端运行。另一个终端执行 `uv run python workbuddy_eval.py status`；在 WorkBuddy 新建独立会话，将 `.local/workbuddy/prompt.txt` 全文发送，并允许题目的 MCP 工具调用。WorkBuddy 报告完成后：

```bash
uv run python workbuddy_eval.py finish --trial-id '<status 返回的 ID>'
```

## 输出与限制

Harbor 在 `jobs/<job>/` 保存 reward 和异常，`agent/workbuddy-commands.jsonl` 保存容器命令。只支持单题串行，没有 `--suite`；12 题需逐题更换 `--task`、job 名和会话。原题预算包含人工操作等待。缺少连接文件表示桥接未就绪或已关闭，不能据此判断是否通过。Token 未接入统计，保持未知。详见 [完整桌面流程](../../WORKBUDDY.md)。
