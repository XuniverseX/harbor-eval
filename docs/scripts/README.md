# 脚本说明索引

每个 Python、Shell 和 JavaScript 脚本各有一份对应说明。所有命令从仓库根目录执行，先用 `uv sync --locked` 准备 Python 环境。私有配置、日志、缓存和成绩只保留在被 Git 忽略的本地目录。

日常主要使用前三个评测入口；内部模块由入口或 Harbor 加载，不需要逐个执行。

| 脚本 | 用途与说明 |
| --- | --- |
| [`run.py`](../../run.py) | [DeepSeek Harness 默认启动入口](run.py.md) |
| [`run_claude.py`](../../run_claude.py) | [Claude Code CLI 启动入口](run_claude.py.md) |
| [`workbuddy_eval.py`](../../workbuddy_eval.py) | [WorkBuddy 半自动评测操作入口](workbuddy_eval.py.md) |
| [`usage_stats.py`](../../usage_stats.py) | [读取 Harness 用量摘要](usage_stats.py.md) |
| [`workbuddy_mcp.py`](../../workbuddy_mcp.py) | [WorkBuddy stdio MCP 服务](workbuddy_mcp.py.md) |
| [`deepseek_agent.py`](../../deepseek_agent.py) | [DeepSeek Harness 的 Harbor 适配器](deepseek_agent.py.md) |
| [`install-dsh.sh`](../../install-dsh.sh) | [容器内 Harness 在线安装脚本](install-dsh.sh.md) |
| [`install_cache.py`](../../install_cache.py) | [Harness 软件安装缓存](install_cache.py.md) |
| [`suites.py`](../../suites.py) | [固定公共题集加载与内容校验](suites.py.md) |
| [`usage_recorder.mjs`](../../usage_recorder.mjs) | [Harness 原生用量事件插件](usage_recorder.mjs.md) |
| [`workbuddy_agent.py`](../../workbuddy_agent.py) | [WorkBuddy 桌面的 Harbor 生命周期适配器](workbuddy_agent.py.md) |
| [`workbuddy_bridge.py`](../../workbuddy_bridge.py) | [绑定单题容器的本机执行桥](workbuddy_bridge.py.md) |
| [`test_adapter.py`](../../test_adapter.py) | [test_adapter.py 测试说明](test_adapter.py.md) |
| [`test_claude_launcher.py`](../../test_claude_launcher.py) | [test_claude_launcher.py 测试说明](test_claude_launcher.py.md) |
| [`test_install_cache.py`](../../test_install_cache.py) | [test_install_cache.py 测试说明](test_install_cache.py.md) |
| [`test_suites.py`](../../test_suites.py) | [test_suites.py 测试说明](test_suites.py.md) |
| [`test_usage_stats.py`](../../test_usage_stats.py) | [test_usage_stats.py 测试说明](test_usage_stats.py.md) |
| [`test_workbuddy.py`](../../test_workbuddy.py) | [test_workbuddy.py 测试说明](test_workbuddy.py.md) |
| [`test_usage_recorder.mjs`](../../test_usage_recorder.mjs) | [test_usage_recorder.mjs 测试说明](test_usage_recorder.mjs.md) |
