# test_workbuddy.py：test_workbuddy.py 测试说明

[对应脚本](../../test_workbuddy.py) · [返回脚本索引](README.md)

## 测试范围

HTTP 凭据与容器绑定、finish 与在途命令顺序、真实 stdio MCP 子进程握手，以及 Agent 完成和取消清理。使用模拟题目环境，不操作桌面或调用模型。

## 运行与前提

从仓库根目录运行。Python 测试先 `uv sync --locked`；Node 测试需要可用的 Node.js。

```bash
uv run python -m unittest test_workbuddy -v
```

## 结果与限制

没有额外业务参数。测试结果输出至终端，退出码 0 表示本次测试通过，非零需查看失败断言；不产生功能评测成绩。无需模型凭据，不调用付费模型，也不能证明真实 Agent 的公共题通过率。
