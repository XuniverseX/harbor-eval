#!/usr/bin/env bash
set -euo pipefail

# 此脚本只在 Harbor 的一次性题目容器内执行，安装下载和解压所需工具。
if ! command -v curl >/dev/null || ! command -v xz >/dev/null; then
    apt-get update
    apt-get install -y --no-install-recommends ca-certificates curl xz-utils
fi
# 根据容器内架构选择 Node，而不是根据运行 Harbor 的宿主机架构选择。
case "$(uname -m)" in
    x86_64) node_arch=x64 ;;
    aarch64|arm64) node_arch=arm64 ;;
    *) echo 'Unsupported CPU architecture' >&2; exit 1 ;;
esac
# 固定 Node 版本，并将运行时安装到独立目录。
node_version=24.13.0
node_archive="node-v${node_version}-linux-${node_arch}.tar.xz"
mkdir -p /opt/harbor-dsh /tmp/harbor-node-download
cd /tmp/harbor-node-download
curl --fail --location --retry 3 --max-time 180 --remote-name "https://nodejs.org/dist/v${node_version}/${node_archive}"
curl --fail --location --retry 3 --max-time 60 --remote-name "https://nodejs.org/dist/v${node_version}/SHASUMS256.txt"
# 从官方校验清单中提取当前压缩包的 SHA-256，校验通过后才解压。
awk -v f="$node_archive" '$2 == f {print}' SHASUMS256.txt > selected.sha256
test -s selected.sha256
sha256sum --check selected.sha256
tar -xJf "$node_archive" -C /opt/harbor-dsh --strip-components=1
# 优先使用刚安装的 Node；Harness 版本须与适配器的 DSH_VERSION 一致。
export PATH="/opt/harbor-dsh/bin:$PATH"
npm install --global --prefix /opt/harbor-dsh --no-audit --no-fund @deepseek-ai/dsh@0.1.6-alpha.1
# 将实际版本写入安装日志，供评测结果追溯。
node --version
node -p "require('/opt/harbor-dsh/lib/node_modules/@deepseek-ai/dsh/package.json').version"
