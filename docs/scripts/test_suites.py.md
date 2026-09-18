# test_suites.py：test_suites.py 测试说明

[对应脚本](../../test_suites.py) · [返回脚本索引](README.md)

## 测试范围

固定题名过滤、精简与历史清单隔离、缺题或内容漂移拒绝、运行次数和预演不调用模型。使用合成题库。

## 运行与前提

从仓库根目录运行。Python 测试先 `uv sync --locked`；Node 测试需要可用的 Node.js。

```bash
uv run python -m unittest test_suites -v
```

## 结果与限制

没有额外业务参数。测试结果输出至终端，退出码 0 表示本次测试通过，非零需查看失败断言；不产生功能评测成绩。无需模型凭据，不调用付费模型，也不能证明真实 Agent 的公共题通过率。
