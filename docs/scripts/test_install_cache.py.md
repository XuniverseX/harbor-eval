# test_install_cache.py：test_install_cache.py 测试说明

[对应脚本](../../test_install_cache.py) · [返回脚本索引](README.md)

## 测试范围

同平台复用、平台隔离、归档损坏重建、恢复失败重建、并发发布和显式禁用。模拟容器接口，不测真实下载速度。

## 运行与前提

从仓库根目录运行。Python 测试先 `uv sync --locked`；Node 测试需要可用的 Node.js。

```bash
uv run python -m unittest test_install_cache -v
```

## 结果与限制

没有额外业务参数。测试结果输出至终端，退出码 0 表示本次测试通过，非零需查看失败断言；不产生功能评测成绩。无需模型凭据，不调用付费模型，也不能证明真实 Agent 的公共题通过率。
