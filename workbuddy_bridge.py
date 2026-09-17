"""将桌面 Agent 的操作限定到一个 Harbor 环境，提供独立的人工作答结束入口。"""

import asyncio
import json
from pathlib import Path
import secrets
import time

from aiohttp import web


class TrialBridge:
    """只监听本机随机端口；执行凭据与操作者结束凭据相互独立。"""

    def __init__(self, environment, logs_dir: Path, instruction: str):
        """绑定环境对象，不接受调用方传入容器名称或宿主机执行器。"""
        self.environment = environment
        self.logs_dir = logs_dir
        self.instruction = instruction
        self.trial_id = secrets.token_hex(12)
        self.agent_token = secrets.token_urlsafe(32)
        self.control_token = secrets.token_urlsafe(32)
        self.finished = asyncio.Event()
        self.lock = asyncio.Lock()
        self.accepting = True
        self.command_count = 0
        self.started_at = time.time()
        self.runner = None
        self.url = ''

    async def start(self):
        """启动本机接口，禁止跨来源浏览器页面访问；服务不启用请求访问日志。"""
        app = web.Application(client_max_size=1024 * 1024)
        app.router.add_post('/{action}', self.handle)
        self.runner = web.AppRunner(app, access_log=None, shutdown_timeout=10)
        await self.runner.setup()
        site = web.TCPSite(self.runner, '127.0.0.1', 0)
        await site.start()
        self.url = f'http://127.0.0.1:{self.runner.addresses[0][1]}'

    def descriptor(self, *, control=False):
        """生成本地连接描述，MCP 配置不包含操作者凭据。"""
        return {'url': self.url, 'trial_id': self.trial_id,
                'token': self.control_token if control else self.agent_token}

    async def handle(self, request):
        """鉴权、校验任务身份并转发操作；停止接收后排空正在执行的命令。"""
        action = request.match_info['action']
        token = self.control_token if action == 'finish' else self.agent_token
        if request.headers.get('Origin') or not secrets.compare_digest(
                request.headers.get('Authorization', ''), 'Bearer ' + token):
            return web.json_response({'error': 'unauthorized'}, status=401)
        try:
            data = await request.json()
            if not isinstance(data, dict):
                raise ValueError()
        except (ValueError, TypeError):
            return web.json_response({'error': 'invalid JSON object'}, status=400)
        if action == 'task':
            return web.json_response({'trial_id': self.trial_id, 'instruction': self.instruction,
                                      'accepting': self.accepting, 'command_count': self.command_count})
        if data.get('trial_id') != self.trial_id:
            return web.json_response({'error': 'wrong trial'}, status=409)
        if action == 'finish':
            self.accepting = False
            async with self.lock:
                self.finished.set()
            return web.json_response({'status': 'finished'})
        if action != 'exec':
            return web.json_response({'error': 'unknown action'}, status=404)
        command, timeout = data.get('command'), data.get('timeout_sec', 60)
        if not isinstance(command, str) or not command.strip() or type(timeout) is not int or not 1 <= timeout <= 120:
            return web.json_response({'error': 'command required; timeout_sec must be 1..120'}, status=400)
        async with self.lock:
            if not self.accepting:
                return web.json_response({'error': 'trial closed'}, status=409)
            self.command_count += 1
            record = {'number': self.command_count, 'started_at': time.time(), 'command': command}
            try:
                result = await self.environment.exec(command=command, timeout_sec=timeout)
                output = {'return_code': result.return_code, 'stdout': result.stdout or '', 'stderr': result.stderr or ''}
                record['result'] = output.copy()
                # 完整输出仅落本地日志，控制单次工具返回的上下文体积。
                output['truncated'] = any(len(output[k]) > 32000 for k in ('stdout', 'stderr'))
                for key in ('stdout', 'stderr'):
                    output[key] = output[key][:32000]
                return web.json_response(output)
            except Exception as error:
                record['error_type'] = type(error).__name__
                return web.json_response({'error': type(error).__name__}, status=500)
            finally:
                record['finished_at'] = time.time()
                self.logs_dir.mkdir(parents=True, exist_ok=True)
                with (self.logs_dir / 'workbuddy-commands.jsonl').open('a', encoding='utf-8') as stream:
                    stream.write(json.dumps(record, ensure_ascii=False) + '\n')

    async def close(self):
        """任务完成、异常或超时后关闭入口，防止验收期间继续调用。"""
        self.accepting = False
        if self.runner is not None:
            await self.runner.cleanup()
            self.runner = None
