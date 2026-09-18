# suites.py：固定公共题集加载与内容校验

[对应脚本](../../suites.py) · [返回脚本索引](README.md)

## 使用方式

内部模块，无独立 CLI。启动脚本调用 `select_suite(root, name)` 获取精确题名，`task_digest(task)` 计算内容摘要。

## 输入输出

支持 `daily-12-v2`、历史 `daily-20-v1` 和 `smoke-5-v1`。读取 `suites/` 清单并校验本地 `datasets/terminal-bench/`；5 题验证集从旧 20 题清单的 smoke 标记选择。

返回题名列表；清单异常、缺题或文件变化时停止，不静默缩减数量。摘要覆盖题面、task.toml、environment 和 tests，不锁定远程软件源或镜像 digest。

通过入口检查：

```bash
uv run python run.py --suite daily-12-v2 --dry-run
```

具体覆盖和删减理由见 [题集说明](../../suites/README.md)。变更集合应创建新版本，避免修改旧版成绩口径。
