"""半自动桌面评测的操作入口：生成连接配置、启动单题、查看状态和结束作答。"""

import argparse
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys

import aiohttp
from dotenv import dotenv_values
from workbuddy_agent import ROOT, STATE, private_json
from workbuddy_mcp import bridge_request


def main():
    """串行运行单题，保持界面操作和实际评分之间的明确边界。"""
    parser = argparse.ArgumentParser(description='WorkBuddy + Harbor 单题半自动评测')
    actions = parser.add_subparsers(dest='action', required=True)
    actions.add_parser('config', help='生成本地 MCP 配置片段，不覆盖 WorkBuddy 配置')
    start = actions.add_parser('start')
    start.add_argument('--task', default='log-summary-date-ranges')
    start.add_argument('--version', required=True, help='本地 WorkBuddy 显示的版本号')
    start.add_argument('--env-file', type=Path, default=ROOT / '.env.local')
    start.add_argument('--job-name')
    actions.add_parser('status')
    finish = actions.add_parser('finish')
    finish.add_argument('--trial-id', required=True)
    args = parser.parse_args()
    if args.action == 'config':
        config = {'mcpServers': {'harbor-eval': {'command': sys.executable,
                  'args': [str(ROOT / 'workbuddy_mcp.py'), '--connection', str(STATE / 'connection.json')]}}}
        private_json(STATE / 'mcp-config.json', config)
        print('已生成 .local/workbuddy/mcp-config.json；合并到 WorkBuddy 的自定义连接器配置。')
    elif args.action == 'start':
        task = ROOT / 'datasets/terminal-bench' / args.task
        if task.parent != ROOT / 'datasets/terminal-bench' or not (task / 'task.toml').is_file():
            parser.error('请指定本地题库中的单个题名')
        model = dotenv_values(args.env_file).get('CHAT_MODEL')
        if not model:
            parser.error('本地配置缺少 CHAT_MODEL；此值仅用于结果标识，需在 WorkBuddy 中选择同一模型')
        env = os.environ.copy()
        env['PYTHONPATH'] = str(ROOT)
        env['WORKBUDDY_VERSION'] = args.version
        command = ['harbor', 'run', '--path', str(task), '--agent', 'workbuddy_agent:WorkBuddyDesktop',
                   '--model', model, '--n-attempts', '1', '--n-concurrent', '1', '--max-retries', '0',
                   '--jobs-dir', str(ROOT / 'jobs')]
        if args.job_name:
            command += ['--job-name', args.job_name]
        raise SystemExit(subprocess.call(command, env=env, cwd=ROOT))
    else:
        try:
            if args.action == 'status':
                result = asyncio.run(bridge_request(STATE / 'connection.json', 'task', {}))
                result.pop('instruction', None)
            else:
                result = asyncio.run(bridge_request(STATE / 'control.json', 'finish', {'trial_id': args.trial_id}))
            print(json.dumps(result, ensure_ascii=False, indent=2))
        except (OSError, ValueError, RuntimeError, aiohttp.ClientError, TimeoutError) as error:
            parser.error(str(error))


if __name__ == '__main__':
    main()
