"""为 WorkBuddy 提供标准 stdio MCP，只转发当前 Harbor 题目容器的操作。"""

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

import aiohttp
from mcp.server.fastmcp import FastMCP


async def bridge_request(descriptor_path: Path, action: str, payload: dict):
    """读取本地连接凭据；禁止代理转发，并验证地址严格指向本机。"""
    descriptor = json.loads(descriptor_path.read_text())
    url = urlsplit(descriptor['url'])
    if url.scheme != 'http' or url.hostname != '127.0.0.1' or url.username or url.password or url.path or url.query or url.fragment:
        raise ValueError('桥接地址必须是本机 HTTP 服务')
    # 执行必须明确携带题目 ID，过期上下文不能误操作下一题。
    async with aiohttp.ClientSession(trust_env=False, timeout=aiohttp.ClientTimeout(total=135)) as client:
        async with client.post(descriptor['url'] + '/' + action, json=payload,
                               headers={'Authorization': 'Bearer ' + descriptor['token']}) as response:
            data = await response.json()
            if response.status != 200:
                raise RuntimeError(f"桥接请求失败：{response.status} {data.get('error', '')}")
            return data


def create_server(descriptor_path: Path):
    """只向模型提供读题和执行工具，不暴露评分、凭据或容器管理工具。"""
    server = FastMCP('harbor-workbuddy')

    @server.tool()
    async def harbor_task() -> dict:
        """获取当前题目的原始说明和 trial_id；所有题目路径均位于 Linux 容器内。"""
        return await bridge_request(descriptor_path, 'task', {})

    @server.tool()
    async def harbor_exec(trial_id: str, command: str, timeout_sec: int = 60) -> dict:
        """在当前题目容器执行 shell 命令，可读写文件、运行程序；不能操作宿主机。每次是独立 shell，需要 cd 时写在本次命令中。"""
        return await bridge_request(descriptor_path, 'exec', {'trial_id': trial_id, 'command': command, 'timeout_sec': timeout_sec})

    return server


def main():
    """从操作者提供的本地描述文件启动 MCP，标准输出保留给协议。"""
    parser = argparse.ArgumentParser()
    parser.add_argument('--connection', type=Path, required=True)
    args = parser.parse_args()
    create_server(args.connection).run(transport='stdio')


if __name__ == '__main__':
    main()
