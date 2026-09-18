# workbuddy_agent.py：WorkBuddy 桌面的 Harbor 生命周期适配器

[对应脚本](../../workbuddy_agent.py) · [返回脚本索引](README.md)

## 使用方式

内部模块，由 `workbuddy_eval.py start` 以 `workbuddy_agent:WorkBuddyDesktop` 加载，不直接执行。

## 输入与流程

Harbor 提供原题面和容器；`WORKBUDDY_VERSION` 由启动入口传入。`setup` 创建本地状态目录；`run` 获取单题运行锁、启动桥接、写入凭据描述和提示词，等待操作者 finish 后交还 Harbor 验收。

## 输出与限制

`.local/workbuddy/` 下生成 `connection.json`、`control.json`、`prompt.txt` 和运行锁。连接 JSON 原子写入且权限为 600。结束或取消时关闭服务并移除模型连接描述。结果元数据包含版本、命令数、人工完成状态、含人工等待的耗时；Token 未知。

MCP 绑定当前容器，但无法强制禁止 WorkBuddy 原生宿主机工具或证明记忆隔离。每题需新会话和当前 ID；不能并行启动多个桌面 trial。
