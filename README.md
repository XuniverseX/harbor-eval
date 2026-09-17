# Harbor × DeepSeek Harness

通过 Harbor 驱动真实 DeepSeek Harness headless CLI，连接自行配置的
Chat Completions 服务，使用 Terminal-Bench 2.0 公共题目及原始验收器评分。
目前仅提供 DeepSeek Harness 适配器。

## 安装

需要可用的 Docker 和 uv。在仓库根目录创建 Python 环境：

```bash
uv venv
uv pip install harbor==0.23.0 python-dotenv
source .venv/bin/activate
```

适配器在题目容器内安装 Node 24.13.0 和
`@deepseek-ai/dsh@0.1.5-rc.1`，不使用宿主机的 Harness 安装。
该版本 headless 不支持 `--json`，适配器使用普通文本输出并保留原生会话记录。

## 本地配置

在仓库根目录创建 `.env.local`，设置以下变量：

| 变量 | 含义 |
| --- | --- |
| `CHAT_BASE_URL` | 模型服务基础地址；只有协议、主机和端口时自动补 `/v1` |
| `CHAT_API_KEY` | 模型服务凭据 |
| `CHAT_MODEL` | 服务实际接受的模型 ID |

`.env.local` 已加入 `.gitignore`。可通过 `--env-file` 指定其他本地文件，
通过 `--model` 覆盖模型选择。不要把真实配置写入代码、测试、文档或提交说明。
模型地址必须从题目容器内可达；如需代理，请仅在本地配置，并按需让模型服务直连。

## 运行

```bash
harbor datasets download terminal-bench@2.0 -o datasets
python -m unittest -v test_adapter
python run.py --task cancel-async-tasks
```

默认只执行一道公共题，确认接入后可显式运行完整题集：

```bash
python run.py --task ALL --attempts 3 --concurrency 2
```

完整评测会产生更多模型请求。使用相同题库版本、模型配置和运行预算比较
不同实验；不要将单题成绩视为完整基准成绩。

## 执行与评分

- 使用原始题目超时和验收脚本，任务通过与否由 Harbor 验收器判定。
- 推理等级为 `high`，每次请求输出上限为 32768 token。
- 每个题目在独立容器内使用独立 DSH_HOME，无人值守文件权限仅作用于该容器。
- 密钥通过进程环境传递，不放入命令行参数或公开配置。
- 模型作答和 Agent 安装分别计时；CLI 非零退出报告为运行异常。
- 当前适配器未聚合 token 和费用，未知指标保持未知。

本地 `jobs/<job-name>/result.json` 保存汇总；每个 trial 目录保存独立结果、
`verifier/reward.txt`、验收输出以及 `agent/` 下的安装日志和原生会话。
`agent/dsh.stdout.log` 保存最终文本，`agent/dsh.stderr.log` 保存推理进度和诊断。
Harbor 进程返回 0 不代表所有题目通过，应检查结果文件及异常。

题库、原始日志、配置和实际评测记录仅保留在被 Git 忽略的目录中。
需要保存个人说明或结果摘要时使用 `.local/`；本项目不自动上传 Harbor Hub。

## 协作

代码使用中文注释；每完成一个有文件改动的任务，执行相应检查后创建 commit。
具体约定见 [AGENTS.md](AGENTS.md)。
