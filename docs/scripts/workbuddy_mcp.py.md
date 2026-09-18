# workbuddy_mcp.py：WorkBuddy stdio MCP 服务

[对应脚本](../../workbuddy_mcp.py) · [返回脚本索引](README.md)

## 用途与参数

通常由 WorkBuddy 按 `workbuddy_eval.py config` 生成的配置启动，无需在普通终端长期运行。

```bash
uv run python workbuddy_mcp.py --connection .local/workbuddy/connection.json
```

`--connection` 必填，指向当前 trial 的本地连接描述，包含地址和凭据。标准输入输出专供 MCP 协议；直接运行后等待输入是正常行为。

## 工具和边界

`harbor_task()` 返回原题面、trial ID 和状态。`harbor_exec(trial_id, command, timeout_sec=60)` 在绑定的 Linux 容器执行命令，超时范围 1–120 秒。每次为独立 shell，工作目录需在本次命令里设置。

仅连接本机 HTTP 桥接且不使用代理。没有模型可调用的 finish 或评分工具。没有连接文件、过期 trial ID、超时或非成功响应会报错。模块函数 `bridge_request` 也供操作者入口调用，不要公开连接描述文件。
