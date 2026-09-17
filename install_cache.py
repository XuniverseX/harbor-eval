"""在作答前缓存纯软件安装，按容器平台和安装脚本隔离，避免重复 npm 安装。"""

import asyncio
import fcntl
import hashlib
import json
from pathlib import Path
import tempfile
import time

ROOT = Path(__file__).resolve().parent
# 版本变化由安装脚本摘要自动失效；额外验证防止恢复不完整的运行时。
VERIFY = '''export PATH="/opt/harbor-dsh/bin:$PATH"; test "$(node --version)" = v24.13.0 && test "$(node -p "require('/opt/harbor-dsh/lib/node_modules/@deepseek-ai/dsh/package.json').version")" = 0.1.5-rc.1 && DSH_HOME=/tmp/harbor-dsh-cache-check dsh --help >/dev/null'''


def digest(path):
    """流式计算摘要，避免将大型软件归档全部读入内存。"""
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


async def checked(environment, command):
    """安装命令统一以 root 执行，失败时保留容器日志并阻止作答。"""
    result = await environment.exec(command=command, user='root', timeout_sec=900)
    if result.return_code != 0:
        raise RuntimeError('Harness 安装或缓存校验失败，参见 agent/install-dsh.log')
    return result


async def install_harness(environment, cache_dir, *, enabled=True):
    """在主机锁内原子发布缓存；每个题目容器解压独立副本，不共享可写目录。"""
    started = time.monotonic()
    await environment.upload_file(source_path=ROOT / 'install-dsh.sh', target_path='/tmp/harbor-install-dsh.sh')

    async def fresh():
        """只执行公开安装脚本，尚未上传模型配置或开始任何题目作答。"""
        await checked(environment, 'bash /tmp/harbor-install-dsh.sh > /logs/agent/install-dsh.log 2>&1')
        await checked(environment, f'({VERIFY}) >> /logs/agent/install-dsh.log 2>&1')

    if not enabled:
        await fresh()
        return {'status': 'disabled', 'elapsed_seconds': time.monotonic() - started}
    # 先准备基础工具，保证冷、热安装不会改变题目可用的系统工具集合。
    await checked(environment, 'bash /tmp/harbor-install-dsh.sh --prepare-only > /logs/agent/install-dsh.log 2>&1')
    probe = await checked(environment, 'uname -s; uname -m; cat /etc/os-release; getconf GNU_LIBC_VERSION')
    key = hashlib.sha256((probe.stdout + digest(ROOT / 'install-dsh.sh') + VERIFY).encode()).hexdigest()
    cache_dir.mkdir(parents=True, exist_ok=True)
    archive, checksum = cache_dir / f'{key}.tar.gz', cache_dir / f'{key}.sha256'
    status = 'miss'
    # 非阻塞轮询不会卡住 Harbor 事件循环；取消等待也会自动释放文件描述符。
    with (cache_dir / f'{key}.lock').open('a') as lock:
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                await asyncio.sleep(0.2)
        if archive.exists() or checksum.exists():
            status = 'rebuilt'
            valid = archive.is_file() and checksum.is_file() and digest(archive) == checksum.read_text().strip()
            if valid:
                await environment.upload_file(source_path=archive, target_path='/tmp/harbor-dsh-cache.tar.gz')
                result = await environment.exec(command=(
                    '(tar -xzf /tmp/harbor-dsh-cache.tar.gz -C /opt && '
                    f'({VERIFY})) >> /logs/agent/install-dsh.log 2>&1'), user='root', timeout_sec=900)
                if result.return_code == 0:
                    status = 'hit'
        if status != 'hit':
            # 缓存仅在安装前恢复；删除的是本适配器拥有的软件目录，不涉及题目文件。
            await checked(environment, 'rm -rf /opt/harbor-dsh')
            await fresh()
            await checked(environment, 'tar -czf /tmp/harbor-dsh-cache.tar.gz -C /opt harbor-dsh')
            with tempfile.TemporaryDirectory(dir=cache_dir) as td:
                temp = Path(td) / 'runtime.tar.gz'
                await environment.download_file(source_path='/tmp/harbor-dsh-cache.tar.gz', target_path=temp)
                stamp = Path(td) / 'runtime.sha256'
                stamp.write_text(digest(temp) + '\n')
                temp.replace(archive)
                stamp.replace(checksum)
    # 归档和启动自检产生的临时目录不参与作答，也不会回写缓存。
    await checked(environment, 'rm -f /tmp/harbor-dsh-cache.tar.gz; rm -rf /tmp/harbor-dsh-cache-check')
    result = {'status': status, 'cache_key': key, 'archive_sha256': checksum.read_text().strip(),
              'elapsed_seconds': time.monotonic() - started}
    with tempfile.TemporaryDirectory() as td:
        report = Path(td) / 'install-cache.json'
        report.write_text(json.dumps(result, indent=2) + '\n')
        await environment.upload_file(source_path=report, target_path='/logs/agent/install-cache.json')
    return result
