"""验证桌面适配桥的容器路由、结束边界与凭据隔离，不调用模型。"""

import asyncio
import json
from pathlib import Path
import tempfile
import sys
from unittest.mock import patch
from types import SimpleNamespace
import unittest

from aiohttp import ClientSession
from workbuddy_bridge import TrialBridge


class Environment:
    """模拟 Harbor 容器接口，记录传入参数并允许控制执行完成时机。"""

    def __init__(self):
        """初始化容器调用记录。"""
        self.calls = []
        self.gate = None

    async def exec(self, **kwargs):
        """返回容器结果；测试结束竞争时等待显式放行。"""
        self.calls.append(kwargs)
        if self.gate is not None:
            await self.gate.wait()
        return SimpleNamespace(return_code=0, stdout='container-result', stderr='')


class BridgeTests(unittest.IsolatedAsyncioTestCase):
    """使用真实 HTTP 连接验证访问控制和生命周期，不使用宿主机 shell。"""

    async def asyncSetUp(self):
        """每项测试使用独立目录与随机端口。"""
        self.temp = tempfile.TemporaryDirectory()
        self.env = Environment()
        self.bridge = TrialBridge(self.env, Path(self.temp.name), '原始合成题面')
        await self.bridge.start()
        self.client = ClientSession()

    async def asyncTearDown(self):
        """关闭网络和临时数据。"""
        await self.client.close()
        await self.bridge.close()
        self.temp.cleanup()

    async def request(self, path, data=None, token=None):
        """使用指定凭据访问桥接接口，默认模拟 Agent 权限。"""
        async with self.client.post(self.bridge.url + path, json=data or {},
                                   headers={'Authorization': 'Bearer ' + (token or self.bridge.agent_token)}) as response:
            return response.status, await response.json()

    async def test_commands_reach_only_bound_environment(self):
        """原样转发命令给绑定容器，外部不能指定其他容器或宿主路径。"""
        status, data = await self.request('/exec', {'trial_id': self.bridge.trial_id, 'command': 'printf hello', 'timeout_sec': 12})
        self.assertEqual(status, 200)
        self.assertEqual(data['stdout'], 'container-result')
        self.assertEqual(self.env.calls, [{'command': 'printf hello', 'timeout_sec': 12}])
        status, _ = await self.request('/exec', {'trial_id': 'wrong', 'command': 'pwd'})
        self.assertEqual(status, 409)
        self.assertEqual(len(self.env.calls), 1)

    async def test_agent_cannot_finish_and_stopped_bridge_rejects_work(self):
        """评分只能由操作者触发；结束后到达的命令不得执行。"""
        status, _ = await self.request('/finish', {'trial_id': self.bridge.trial_id})
        self.assertEqual(status, 401)
        status, _ = await self.request('/finish', {'trial_id': self.bridge.trial_id}, self.bridge.control_token)
        self.assertEqual(status, 200)
        self.assertTrue(self.bridge.finished.is_set())
        status, _ = await self.request('/exec', {'trial_id': self.bridge.trial_id, 'command': 'pwd'})
        self.assertEqual(status, 409)
        self.assertEqual(self.env.calls, [])

    async def test_finish_waits_for_inflight_command(self):
        """封闭入口后等待当前命令结束，避免评分和写文件并发。"""
        self.env.gate = asyncio.Event()
        request = asyncio.create_task(self.request('/exec', {'trial_id': self.bridge.trial_id, 'command': 'work'}))
        for _ in range(100):
            if self.env.calls:
                break
            await asyncio.sleep(0.01)
        finish = asyncio.create_task(self.request('/finish', {'trial_id': self.bridge.trial_id}, self.bridge.control_token))
        await asyncio.sleep(0.05)
        self.assertFalse(self.bridge.finished.is_set())
        self.env.gate.set()
        self.assertEqual((await request)[0], 200)
        self.assertEqual((await finish)[0], 200)
        self.assertTrue(self.bridge.finished.is_set())

    async def test_task_and_logs_do_not_expose_control_secret(self):
        """返回题面但不暴露操作者凭据；错误鉴权不能读取题面。"""
        status, data = await self.request('/task')
        self.assertEqual(status, 200)
        self.assertEqual(data['instruction'], '原始合成题面')
        self.assertNotIn(self.bridge.control_token, json.dumps(data))
        status, _ = await self.request('/task', token='wrong')
        self.assertEqual(status, 401)

    async def test_invalid_command_and_timeout_do_not_execute(self):
        """空命令和失控超时不会传给容器执行。"""
        for extra in [{'command': ''}, {'command': 'pwd', 'timeout_sec': -1}, {'command': 'pwd', 'timeout_sec': 10000}]:
            status, _ = await self.request('/exec', {'trial_id': self.bridge.trial_id, **extra})
            self.assertEqual(status, 400)
        self.assertEqual(self.env.calls, [])


class DesktopLifecycleTests(unittest.IsolatedAsyncioTestCase):
    """验证真实 MCP 子进程及 Harbor Agent 的完成、取消和清理边界。"""

    async def test_stdio_mcp_routes_to_bridge(self):
        """通过官方客户端握手并调用工具，覆盖桌面实际采用的标准输入输出协议。"""
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from workbuddy_agent import private_json
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = Environment()
            bridge = TrialBridge(env, root, '合成题目')
            await bridge.start()
            try:
                descriptor = root / 'connection.json'
                private_json(descriptor, bridge.descriptor())
                parameters = StdioServerParameters(command=sys.executable, args=[
                    str(Path(__file__).with_name('workbuddy_mcp.py')), '--connection', str(descriptor)])
                async with stdio_client(parameters) as (reader, writer):
                    async with ClientSession(reader, writer) as session:
                        await session.initialize()
                        listing = await session.list_tools()
                        self.assertEqual({tool.name for tool in listing.tools}, {'harbor_task', 'harbor_exec'})
                        task = await session.call_tool('harbor_task', {})
                        self.assertFalse(task.isError)
                        response = await session.call_tool('harbor_exec', {
                            'trial_id': bridge.trial_id, 'command': 'printf synthetic', 'timeout_sec': 5})
                        self.assertFalse(response.isError)
                        self.assertIn('container-result', str(response.content))
                        self.assertEqual(env.calls, [{'command': 'printf synthetic', 'timeout_sec': 5}])
            finally:
                await bridge.close()

    async def test_completion_and_cancellation_cleanup(self):
        """结束或 Harbor 超时取消均删除 MCP 描述，释放锁并保留准确元数据。"""
        from workbuddy_agent import WorkBuddyDesktop
        from workbuddy_mcp import bridge_request
        for cancelled in (False, True):
            with self.subTest(cancelled=cancelled), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                with patch('workbuddy_agent.STATE', root):
                    agent = WorkBuddyDesktop(logs_dir=root / 'logs')
                    env = Environment()
                    context = SimpleNamespace(metadata=None)
                    await agent.setup(env)
                    run = asyncio.create_task(agent.run('合成题目', env, context))
                    try:
                        async with asyncio.timeout(5):
                            while not (root / 'connection.json').exists():
                                await asyncio.sleep(0.01)
                        current = await bridge_request(root / 'connection.json', 'task', {})
                        if cancelled:
                            run.cancel()
                            with self.assertRaises(asyncio.CancelledError):
                                await run
                        else:
                            await bridge_request(root / 'control.json', 'finish', {'trial_id': current['trial_id']})
                            await run
                        self.assertFalse((root / 'connection.json').exists())
                        self.assertEqual(context.metadata['operator_finished'], not cancelled)
                        self.assertEqual(context.metadata['usage_status'], 'unavailable')
                        self.assertEqual(env.calls, [])
                    finally:
                        if not run.done():
                            run.cancel()
                            await asyncio.gather(run, return_exceptions=True)


if __name__ == '__main__':
    unittest.main()
