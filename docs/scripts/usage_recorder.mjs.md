# usage_recorder.mjs：Harness 原生用量事件插件

[对应脚本](../../usage_recorder.mjs) · [返回脚本索引](README.md)

## 使用方式

内部插件，由 `deepseek_agent.py` 上传到 `/opt/harbor-usage-recorder.mjs` 并通过 Harness patch 加载。没有独立 CLI 参数，直接用 Node 执行不会启动评测。

## 输入输出

导出 `apply(ctx, config)`，配置 `outputPath` 指定 JSONL 位置；适配器使用 `/logs/agent/token-usage.jsonl`。订阅原生 session/event，记录轮次、序号、会话标识、结束和重试事件及允许的 usage 字段。

跳过 fork/恢复时继承的历史；缺失 usage 保持空值。插件不记录消息正文、工具参数和凭据，也不修改请求。由 [usage_stats.py](usage_stats.py.md) 进行最终汇总，不直接累计费用。需要通过 `node --test test_usage_recorder.mjs` 检查时使用宿主机 Node。
