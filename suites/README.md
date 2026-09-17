# 固定公共题目集

日常功能对比推荐 `daily-12-v2`：从原 20 题减少到 12 题，保留代码修复、数据处理、环境构建、多步操作四类能力。5 题接入验证集保持不变，且全部包含在这 12 题内。
这不是官方榜单集合或随机抽样，不能将成绩称为完整 Terminal-Bench 2.0 成绩。
选题按功能覆盖和任务类型去重，未依据模型成绩筛题，也没有实测证明耗时会按题数同比下降。

新清单见 [daily-12-v2.json](daily-12-v2.json)。旧 [daily-20-v1.json](daily-20-v1.json) 保留用于历史复现，旧命令仍运行原 20 题，避免同名集合的成绩口径改变。比较不同 Agent 时须统一使用新清单，12 题与 20 题的总体通过率不能直接比较。

源仓库为 [terminal-bench-2](https://github.com/laude-institute/terminal-bench-2/tree/69671fbaac6d67a7ef0dfec016cc38a64ef7a77c)，锁定提交 `69671fbaac6d67a7ef0dfec016cc38a64ef7a77c`。保留题目的内容、摘要和验收器均未改变。
新集合按官方 metadata 为 2 道 easy、8 道 medium、2 道 hard。`cancel-async-tasks` 已用于接入调试，应披露为已知开发题。

| 题目 | 分组 | 主要能力 | 5 题验证集 |
| --- | --- | --- | --- |
| `cancel-async-tasks` | 代码实现与修复 | 异步并发、取消与清理 | 是 |
| `cobol-modernization` | 代码实现与修复 | 跨语言迁移和行为一致性 | — |
| `fix-git` | 代码实现与修复 | 恢复 Git 历史并合并改动 | 是 |
| `kv-store-grpc` | 代码实现与修复 | 协议定义、代码生成和常驻服务 | — |
| `fix-code-vulnerability` | 代码实现与修复 | 真实仓库漏洞定位与回归修复 | — |
| `log-summary-date-ranges` | 命令行与数据处理 | 日期边界、日志聚合与 CSV | 是 |
| `multi-source-data-merger` | 命令行与数据处理 | 多格式数据合并与冲突报告 | — |
| `build-pmars` | 环境与构建配置 | 源码获取、编译选项与安装验证 | — |
| `nginx-request-logging` | 环境与构建配置 | 服务配置、限流、日志和进程管理 | — |
| `openssl-selfsigned-cert` | 环境与构建配置 | 证书生成、权限和脚本验证 | 是 |
| `db-wal-recovery` | 多步综合操作 | 数据库 WAL 修复与数据恢复 | 是 |
| `sanitize-git-repo` | 多步综合操作 | 仓库敏感内容清理与未污染文件保护 | — |

## 删减依据

这里的“重复”指功能覆盖重叠，不是题目完全相同。另有少量专项题因日常覆盖优先级较低移出，因此精简版有意减少专项覆盖。

| 移出的题目 | 原因及保留的覆盖 |
| --- | --- |
| `git-multibranch`、`configure-git-webserver` | 两题都涉及 Git 服务与自动部署；日常保留 `fix-git` 的 Git 操作、`nginx-request-logging` 的 HTTP 服务配置。精简版不再测试 SSH/hook 自动部署链路。 |
| `sqlite-db-truncate` | 与 `db-wal-recovery` 同属数据库损坏恢复，保留 WAL 恢复；不再单测截断恢复。 |
| `regex-log` | 日志解析类别与 `log-summary-date-ranges` 重叠；保留完整日志聚合，放弃专门的正则边界覆盖。 |
| `large-scale-text-editing` | 文本转换与数据处理已有覆盖；去掉百万行和 Vim 宏专项约束。 |
| `modernize-scientific-stack` | 迁移能力由 `cobol-modernization` 保留，依赖安装由 gRPC/构建题保留；去掉科学计算栈专项。 |
| `polyglot-c-py` | 单文件双语言运行较特殊；保留跨语言迁移和源码构建，不再覆盖 polyglot 技巧。 |
| `extract-elf` | 二进制解析是独立专项，非重复题；为控制日常规模移出，数据库恢复仍保留排查能力。 |

## 使用

```bash
uv run python run.py --suite smoke-5-v1 --dry-run
uv run python run.py --suite smoke-5-v1 --attempts 1 --concurrency 1
uv run python run.py --suite daily-12-v2 --attempts 1 --concurrency 1 --dry-run
uv run python run.py --suite daily-12-v2 --attempts 1 --concurrency 1
```

12 题单次为 12 个独立 trial，较原 20 题少 40%；稳定性复测可设 `--attempts 3`，共 36 次。实际耗时取决于题目和模型，不保证减少 40%。默认仍为单题单次；`--suite` 与 `--task` 互斥。`--dry-run` 只核对本地文件和运行范围，不读取模型配置、不调用模型，也不验证网络或容器运行条件。

清单校验覆盖题面、task.toml、环境和验收文件。缺题或内容变化时直接报错，不会减少题目后继续运行。不要为了通过校验而直接刷新摘要；需要更换题目时创建新集合版本。

## 下载锁定版本

普通 registry 下载可能随上游变化。如果校验不通过，可在干净的本地目录按下面的公开提交获取题库；已有题库先自行保留，避免覆盖。

```bash
git clone https://github.com/laude-institute/terminal-bench-2.git datasets/terminal-bench
git -C datasets/terminal-bench checkout --detach 69671fbaac6d67a7ef0dfec016cc38a64ef7a77c
uv run python run.py --suite daily-12-v2 --dry-run
```

文件校验不锁定镜像 digest、软件包源或远程仓库返回内容。各 Agent 应使用相同镜像缓存和下载条件，并保留本地安装记录。

## 环境依赖与评测规则

未选择 GPU、大模型权重下载、视频/图像输入或重型编译任务。仍需要网络拉取镜像、安装 Harness 及验收依赖；不能把本集合称为离线题集。每题的特殊依赖见 JSON 中的 dependency_note。
当前只核对了全部所选题目的题面、环境配置和验收入口，尚未完成新集合全部 12 题的容器运行与模型评测。

- 每个 Agent 使用相同清单、模型配置、并发数和原始题目超时；当前适配器仍固定 Harness 0.1.5-rc.1。
- 使用原始验收器和原始 reward，不增加答案提示，也不把参考解答放入 Agent 上下文。
- 主指标为所有计划 trial 中 reward=1 的比例；运行异常计为未成功，并单列异常率。明确缺失、取消和未运行数量。
- 三次结果按独立运行统计平均成功率，不使用三次取最好成绩；固定每题三次时也可先求每题均值再平均。
- 同时报告各分组通过率、作答耗时中位数及 P90、成功任务平均 token；另外报告包含失败任务的已知总用量及 usage 覆盖率。
- 安装/构建时间与作答时间分开；未知 token 不当成零。网络、安装及验收器故障保留原始记录，修复后按明确的新批次重跑。
- 最终正式对比再运行全集；保持该日常集合不因成绩好坏而变动。
- VSCode 插件和 WorkBuddy 需实际完成任务并接受同一验收；CLI 成绩不能替代插件成绩。当前仓库提供 DeepSeek Harness 自动适配器及 WorkBuddy MCP 半自动适配器。

实际结果、服务配置、代理和机器信息仅放在被忽略的本地目录，不进入公开清单。
