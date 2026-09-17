# 固定公共题目集 v1

从 Terminal-Bench 2.0 选择 20 道题用于日常功能对比；这不是官方榜单集合，也不是随机抽样，不能把成绩称为完整 Terminal-Bench 2.0 成绩。
选题依据是能力覆盖和运行成本，没有根据本模型的成功率筛题。`cancel-async-tasks` 已用于接入调试，应披露为已知开发题。

清单见 [daily-20-v1.json](daily-20-v1.json)。源仓库为 [terminal-bench-2](https://github.com/laude-institute/terminal-bench-2/tree/69671fbaac6d67a7ef0dfec016cc38a64ef7a77c)，锁定提交 `69671fbaac6d67a7ef0dfec016cc38a64ef7a77c`。
难度采用题库 metadata：2 道 easy、15 道 medium、3 道 hard，不代表本模型的实际通过难度。

| 题目 | 分组 | 官方难度 | 主要能力 | 5 题验证集 |
| --- | --- | --- | --- | --- |
| `cancel-async-tasks` | 代码实现与修复 | hard | 异步并发、取消与清理 | 是 |
| `cobol-modernization` | 代码实现与修复 | easy | 跨语言迁移和行为一致性 | — |
| `fix-git` | 代码实现与修复 | easy | 恢复 Git 历史并合并改动 | 是 |
| `polyglot-c-py` | 代码实现与修复 | medium | 同一文件跨语言运行与编译 | — |
| `kv-store-grpc` | 代码实现与修复 | medium | 协议定义、代码生成和常驻服务 | — |
| `fix-code-vulnerability` | 代码实现与修复 | hard | 真实仓库漏洞定位与回归修复 | — |
| `large-scale-text-editing` | 命令行与数据处理 | medium | 大文件转换与 Vim 宏约束 | — |
| `log-summary-date-ranges` | 命令行与数据处理 | medium | 日期边界、日志聚合与 CSV | 是 |
| `regex-log` | 命令行与数据处理 | medium | 正则表达式边界与错误匹配控制 | — |
| `multi-source-data-merger` | 命令行与数据处理 | medium | 多格式数据合并与冲突报告 | — |
| `extract-elf` | 命令行与数据处理 | medium | 二进制解析与结构化输出 | — |
| `modernize-scientific-stack` | 环境与构建配置 | medium | 旧 Python 代码迁移与依赖声明 | — |
| `build-pmars` | 环境与构建配置 | medium | 源码获取、编译选项与安装验证 | — |
| `nginx-request-logging` | 环境与构建配置 | medium | 服务配置、限流、日志和进程管理 | — |
| `openssl-selfsigned-cert` | 环境与构建配置 | medium | 证书生成、权限和脚本验证 | 是 |
| `git-multibranch` | 多步综合操作 | medium | SSH、Git hook 与双分支 HTTPS 部署 | — |
| `db-wal-recovery` | 多步综合操作 | medium | 数据库 WAL 修复与数据恢复 | 是 |
| `sqlite-db-truncate` | 多步综合操作 | medium | 截断数据库恢复与结果导出 | — |
| `sanitize-git-repo` | 多步综合操作 | medium | 仓库敏感内容清理与未污染文件保护 | — |
| `configure-git-webserver` | 多步综合操作 | hard | Git push 自动部署和 HTTP 验证 | — |

## 使用

```bash
uv run python run.py --suite smoke-5-v1 --dry-run
uv run python run.py --suite smoke-5-v1 --attempts 1 --concurrency 1
uv run python run.py --suite daily-20-v1 --attempts 3 --concurrency 1 --dry-run
uv run python run.py --suite daily-20-v1 --attempts 3 --concurrency 1
```

20 题各运行 3 次即 60 个独立 trial。默认仍为单题单次；`--suite` 与 `--task` 互斥。`--dry-run` 只核对本地文件和运行范围，不读取模型配置、不调用模型，也不验证网络或容器运行条件。

清单校验覆盖题面、task.toml、环境和验收文件。缺题或内容变化时直接报错，不会减少题目后继续运行。不要为了通过校验而直接刷新摘要；需要更换题目时创建新集合版本。

## 下载锁定版本

普通 registry 下载可能随上游变化。如果校验不通过，可在干净的本地目录按下面的公开提交获取题库；已有题库先自行保留，避免覆盖。

```bash
git clone https://github.com/laude-institute/terminal-bench-2.git datasets/terminal-bench
git -C datasets/terminal-bench checkout --detach 69671fbaac6d67a7ef0dfec016cc38a64ef7a77c
uv run python run.py --suite daily-20-v1 --dry-run
```

文件校验不锁定镜像 digest、软件包源或远程仓库返回内容。各 Agent 应使用相同镜像缓存和下载条件，并保留本地安装记录。

## 环境依赖与评测规则

未选择 GPU、大模型权重下载、视频/图像输入或重型编译任务。仍需要网络拉取镜像、安装 Harness 及验收依赖；不能把本集合称为离线题集。每题的特殊依赖见 JSON 中的 dependency_note。
当前只核对了全部所选题目的题面、环境配置和验收入口，尚未完成这 20 题的容器运行与模型评测。

- 每个 Agent 使用相同清单、模型配置、并发数和原始题目超时；当前适配器仍固定 Harness 0.1.5-rc.1。
- 使用原始验收器和原始 reward，不增加答案提示，也不把参考解答放入 Agent 上下文。
- 主指标为所有计划 trial 中 reward=1 的比例；运行异常计为未成功，并单列异常率。明确缺失、取消和未运行数量。
- 三次结果按独立运行统计平均成功率，不使用三次取最好成绩；固定每题三次时也可先求每题均值再平均。
- 同时报告各分组通过率、作答耗时中位数及 P90、成功任务平均 token；另外报告包含失败任务的已知总用量及 usage 覆盖率。
- 安装/构建时间与作答时间分开；未知 token 不当成零。网络、安装及验收器故障保留原始记录，修复后按明确的新批次重跑。
- 最终正式对比再运行全集；保持该日常集合不因成绩好坏而变动。
- VSCode 插件和 WorkBuddy 需实际完成任务并接受同一验收；CLI 成绩不能替代插件成绩。当前仓库只接入 DeepSeek Harness。

实际结果、服务配置、代理和机器信息仅放在被忽略的本地目录，不进入公开清单。
