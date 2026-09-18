# workbuddy_bridge.py：绑定单题容器的本机执行桥

[对应脚本](../../workbuddy_bridge.py) · [返回脚本索引](README.md)

## 使用方式

内部模块，无独立 CLI。`WorkBuddyDesktop` 创建 `TrialBridge(environment, logs_dir, instruction)`，调用 `start()`、等待 `finished`，最后 `close()`。

## 接口与输入

只监听本机随机端口，POST `/task` 读题，`/exec` 执行，`/finish` 结束。使用 Bearer 凭据；执行和结束凭据不同。exec 与 finish 必须匹配 trial ID，拒绝带 Origin 的请求。命令仅交给构造时绑定的 Harbor environment，调用方不能选择容器。

## 输出与边界

命令串行执行；finish 停止接收后等待在途命令结束。单次超时 1–120 秒，默认 60 秒；stdout/stderr 各截断至 32000 字符并标记 truncated。完整命令及结果写入 `agent/workbuddy-commands.jsonl`，仅保留本地。鉴权、参数错误、过期 ID 或执行异常会返回非成功 HTTP 状态，不能作为任务通过的依据。
