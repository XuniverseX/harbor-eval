# run_claude.py：Claude Code CLI 启动入口

[对应脚本](../../run_claude.py) · [返回脚本索引](README.md)

## 用途与前提

复用 `run.py` 的选题和调度逻辑，默认选择 Harbor 原生 `claude-code` 适配器。测量实际 CLI，不能代替 VSCode 插件测试。需要 uv、Docker 和本地公共题库。

## 本地配置

创建 `.env.claude.local`：

```dotenv
ANTHROPIC_BASE_URL=https://gateway.example.com
ANTHROPIC_API_KEY=replace-with-local-key
ANTHROPIC_MODEL=your-model-id
```

以上为占位示例。地址填写网关基础路径，不是完整 `/v1/messages` 地址；脚本不自动追加路径。凭据通过子进程环境传递。入口会清除继承的 OAuth 和其他云供应商路由选项，使用显式 API key 配置。

## 参数与示例

完整参数、默认题目和输出位置与 [run.py](run.py.md) 一致，唯一区别是默认 Agent 和配置文件。

```bash
uv run python run_claude.py --suite daily-12-v2 --dry-run
uv run python run_claude.py --suite daily-12-v2 --attempts 1
uv run python run_claude.py --task log-summary-date-ranges
uv run python run_claude.py --suite smoke-5-v1 --env-file .env.claude.local --concurrency 2
```

## 输出与限制

结果在 `jobs/<job>/`。脚本退出成功不等于题目通过，查看 reward 和异常。安装及版本由 Harbor 原生适配器管理，不使用本项目的 Harness 安装缓存或用量记录插件。启动脚本测试不证明网关连通性；先用单题验证实际服务和依赖安装。
