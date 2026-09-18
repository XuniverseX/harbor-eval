# install-dsh.sh：容器内 Harness 在线安装脚本

[对应脚本](../../install-dsh.sh) · [返回脚本索引](README.md)

## 用途与调用

仅用于 Harbor 一次性 Linux 容器。会安装系统软件并写入 `/opt`，不要在宿主机直接执行。适配器将它上传为 `/tmp/harbor-install-dsh.sh` 后运行：

```bash
bash /tmp/harbor-install-dsh.sh
bash /tmp/harbor-install-dsh.sh --prepare-only
```

## 行为与输出

无参数时准备 curl、xz 和证书工具，按容器架构下载固定 Node 24.13.0，校验官方 SHA-256，再安装 `@deepseek-ai/dsh@0.1.5-rc.1`。支持 x86_64 和 arm64，依赖 apt 系统及相关下载地址可达。

`--prepare-only` 只检查、安装基础工具，不下载 Node 或安装 npm 包。软件目录为 `/opt/harbor-dsh`；stdout/stderr 由调用者保存为 `agent/install-dsh.log`。失败立即退出，实际版本写入日志。缓存命中仍运行基础工具准备，见 [安装缓存](install_cache.py.md)。
