# install_cache.py：Harness 软件安装缓存

[对应脚本](../../install_cache.py) · [返回脚本索引](README.md)

## 使用方式

内部模块，无独立 CLI。适配器调用 `install_harness(environment, cache_dir, enabled=True)`；通过 `run.py --install-only` 预热，通过进程环境 `DSH_INSTALL_CACHE=0` 禁用缓存。

## 输入、缓存与输出

缓存键包括容器系统发行信息、架构、glibc、安装脚本摘要和验证命令。默认主机缓存目录 `.cache/dsh-install/` 保存归档、SHA-256 和锁文件。冷安装完成且尚未上传模型配置、开始作答时，仅归档 `/opt/harbor-dsh`；不缓存题目、凭据或会话。

恢复前检查归档摘要，恢复后验证 Node/Harness 版本和 CLI 帮助启动。损坏或启动失败则重建。同平台通过文件锁串行发布，每题解压独立副本，作答后不回写。未知平台不保证兼容；缓存命中仍可能安装系统基础工具。

返回 `miss`、`hit`、`rebuilt`、`disabled` 和耗时；启用缓存时输出 `agent/install-cache.json`，含键和归档摘要。正常评测还记录到 `agent_result.metadata.install_cache`；预热不产生该作答元数据。首次 npm 解析的传递依赖随归档固定，重建可能不同，比较实验需保留摘要。
