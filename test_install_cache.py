"""验证安装缓存复用、兼容性隔离和损坏恢复，不调用模型。"""

import tempfile
import asyncio
import unittest
from pathlib import Path
from types import SimpleNamespace

from install_cache import install_harness


class Container:
    """模拟跨容器文件传输和安装边界，归档字节仅为测试数据。"""

    def __init__(self, fingerprint='linux-x64-example', fail_restore=False):
        """记录安装次数，并允许模拟目标平台变化或恢复验证失败。"""
        self.fingerprint = fingerprint
        self.fail_restore = fail_restore
        self.installs = 0
        self.uploaded = []

    async def upload_file(self, source_path, target_path):
        """记录上传内容，确认恢复使用已验证的独立副本。"""
        self.uploaded.append((target_path, Path(source_path).read_bytes()))

    async def download_file(self, source_path, target_path):
        """模拟在作答前导出纯软件安装包。"""
        Path(target_path).write_bytes(b'synthetic-runtime')

    async def exec(self, command, **kwargs):
        """按安装协议模拟平台探测、在线安装和恢复验证。"""
        if 'getconf' in command:
            return SimpleNamespace(return_code=0, stdout=self.fingerprint)
        if 'bash /tmp/harbor-install-dsh.sh >' in command:
            self.installs += 1
        return SimpleNamespace(return_code=int(self.fail_restore and 'tar -xzf' in command), stdout='')


class CacheTests(unittest.IsolatedAsyncioTestCase):
    """同平台复用软件，损坏、失效与主动禁用不能静默命中。"""

    async def test_reuse_and_platform_isolation(self):
        """第二个容器跳过在线安装，另一平台独立创建缓存。"""
        with tempfile.TemporaryDirectory() as td:
            cache = Path(td)
            first, second, other = Container(), Container(), Container('other-platform')
            a = await install_harness(first, cache)
            b = await install_harness(second, cache)
            c = await install_harness(other, cache)
            self.assertEqual((a['status'], b['status'], c['status']), ('miss', 'hit', 'miss'))
            self.assertEqual((first.installs, second.installs, other.installs), (1, 0, 1))

    async def test_corruption_and_failed_restore_rebuild(self):
        """摘要不匹配或容器启动验证失败时重装，不能用损坏安装继续作答。"""
        for corrupt in (True, False):
            with tempfile.TemporaryDirectory() as td:
                cache = Path(td)
                await install_harness(Container(), cache)
                if corrupt:
                    next(cache.glob('*.tar.gz')).write_bytes(b'broken')
                target = Container(fail_restore=not corrupt)
                result = await install_harness(target, cache)
                self.assertEqual(target.installs, 1)
                self.assertEqual(result['status'], 'rebuilt')

    async def test_concurrent_containers_publish_only_once(self):
        """并发安装共享同平台锁，第二个容器等待原子发布后恢复独立副本。"""
        with tempfile.TemporaryDirectory() as td:
            cache = Path(td)
            first, second = Container(), Container()
            original = first.download_file

            async def slow_download(**kwargs):
                """模拟冷安装尚未完成归档传输，暴露并发竞争窗口。"""
                await asyncio.sleep(0.05)
                await original(**kwargs)

            first.download_file = slow_download
            a, b = await asyncio.gather(install_harness(first, cache), install_harness(second, cache))
            self.assertEqual((a['status'], b['status']), ('miss', 'hit'))
            self.assertEqual(first.installs + second.installs, 1)

    async def test_disabled_cache_does_not_publish(self):
        """禁用缓存时保持在线安装，不读写可复用归档。"""
        with tempfile.TemporaryDirectory() as td:
            cache = Path(td) / 'unused'
            target = Container()
            result = await install_harness(target, cache, enabled=False)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(target.installs, 1)
            self.assertFalse(cache.exists())
