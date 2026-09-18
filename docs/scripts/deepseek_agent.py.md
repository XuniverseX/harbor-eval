# deepseek_agent.py：DeepSeek Harness 的 Harbor 适配器

[对应脚本](../../deepseek_agent.py) · [返回脚本索引](README.md)

## 使用方式

内部模块，不提供独立命令行参数。由 `run.py` 以 `deepseek_agent:DeepSeekHarness` 加载；日常使用 [启动入口](run.py.md)。

## 输入与职责

Harbor 提供环境、原始题面和日志目录；模型来自启动参数，服务配置来自 `CHAT_BASE_URL`、`CHAT_API_KEY`。`setup` 安装或恢复固定版本软件、上传用量插件和配置；`run` 以安全引用的位置参数传入题目，运行真实 headless CLI；日志同步后 `populate_context_post_run` 回填统计。

## 输出和约束

固定 Harness 0.1.5-rc.1、Node 24.13.0，Chat Completions 协议、high 推理等级、单次输出上限 32768。每题独立 DSH_HOME。输出包括 `agent/dsh.stdout.log`、`dsh.stderr.log`、用量事件和摘要，及 Harbor 的 Agent 元数据。非零 CLI 退出抛出异常；是否答对由原验收器决定。适配器不单独计算费用。
