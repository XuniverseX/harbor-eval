"""在内存中加载私有配置并启动 Harbor，避免将密钥放入命令行参数。"""

import argparse
import json
import os
from pathlib import Path
import subprocess

from dotenv import dotenv_values
from suites import SUITE_NAMES, select_suite

ROOT = Path(__file__).resolve().parent


def main(default_agent='deepseek-harness'):
    """解析评测范围、读取凭据，再交由 Harbor 执行并返回其退出码。"""
    parser = argparse.ArgumentParser()
    parser.add_argument('--agent', choices=('deepseek-harness', 'claude-code'), default=default_agent)
    parser.add_argument('--env-file', type=Path, help='本地配置文件；默认根据 Agent 选择')
    parser.add_argument('--model', help='模型 ID；覆盖所选 Agent 的本地模型配置')
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument('--task', help='Public task name; use ALL for the full downloaded dataset')
    scope.add_argument('--suite', choices=SUITE_NAMES, help='固定公共题目集')
    parser.add_argument('--dry-run', action='store_true', help='校验题目并显示运行范围；不读取凭据、不启动评测')
    parser.add_argument('--install-only', action='store_true', help='只准备环境和 Agent 安装，不调用模型或评分')
    parser.add_argument('--attempts', type=int, default=1)
    parser.add_argument('--concurrency', type=int, default=1)
    parser.add_argument('--job-name')
    args = parser.parse_args()
    if args.attempts < 1 or args.concurrency < 1:
        parser.error('attempts 和 concurrency 必须为正整数')
    dataset = ROOT / 'datasets' / 'terminal-bench'
    selected = []
    if args.suite:
        try:
            selected = select_suite(ROOT, args.suite)
        except (OSError, ValueError, KeyError, TypeError) as error:
            parser.error(f'固定题目集校验失败：{error}')
        target = dataset
        tasks = selected
    else:
        task = args.task or 'cancel-async-tasks'
        target = dataset if task == 'ALL' else dataset / task
        tasks = sorted(p.parent.name for p in dataset.glob('*/task.toml')) if task == 'ALL' else [task]
    if not target.is_dir():
        parser.error('Dataset missing. Run harbor datasets download terminal-bench@2.0 -o datasets first.')
    if args.dry_run:
        print(json.dumps({'agent': args.agent, 'suite': args.suite, 'tasks': tasks, 'task_count': len(tasks),
                          'attempts': args.attempts, 'trial_count': len(tasks) * args.attempts,
                          'concurrency': args.concurrency}, ensure_ascii=False, indent=2))
        raise SystemExit(0)
    # 保留调用者已有环境，仅覆盖配置文件明确提供的两个模型服务变量。
    env = os.environ.copy()
    # Claude Code 使用独立配置，避免将 Chat 接口误当成 Messages 网关。
    is_claude = args.agent == 'claude-code'
    prefix = 'ANTHROPIC' if is_claude else 'CHAT'
    config_path = args.env_file or ROOT / ('.env.claude.local' if is_claude else '.env.local')
    values = dotenv_values(config_path)
    for key in (f'{prefix}_BASE_URL', f'{prefix}_API_KEY'):
        if not values.get(key):
            parser.error(f'Missing {key} in env file')
        env[key] = values[key]
    # 部署标识只来自调用参数或被 Git 忽略的本地配置，不写入源码默认值。
    model = args.model or values.get(f'{prefix}_MODEL')
    if not model or not model.strip():
        parser.error(f'请通过 --model 或本地配置中的 {prefix}_MODEL 指定模型 ID')
    if is_claude:
        # 自定义网关明确使用 API key，避免继承其他登录方式或云供应商路由。
        for key in ('CLAUDE_CODE_OAUTH_TOKEN', 'CLAUDE_FORCE_OAUTH', 'CLAUDE_CODE_USE_BEDROCK',
                    'CLAUDE_CODE_USE_VERTEX', 'CLAUDE_CODE_USE_FOUNDRY', 'ANTHROPIC_AUTH_TOKEN'):
            env.pop(key, None)
        env['ANTHROPIC_MODEL'] = model
    # 使独立安装的 Harbor 可以按模块路径加载本仓库的自定义适配器。
    env['PYTHONPATH'] = str(ROOT) + (os.pathsep + env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
    # 凭据不出现在参数中；不自动重试，并单独放宽首次 Agent 安装的时间预算。
    command = [
        'harbor', 'run', '--path', str(target),
        '--agent', 'claude-code' if is_claude else 'deepseek_agent:DeepSeekHarness', '--model', model,
        '--jobs-dir', str(ROOT / 'jobs'), '--n-concurrent', str(args.concurrency),
        '--n-attempts', str(args.attempts), '--max-retries', '0',
        '--agent-setup-timeout-multiplier', '3',
    ]
    # 使用 Harbor 原生预安装模式预热缓存，不进入作答和验收阶段。
    if args.install_only:
        command += ['--install-only']
    # 使用 Harbor 原生的精确题名过滤，不创建修改过的题库副本。
    for name in selected:
        command += ['--include-task-name', name]
    if args.job_name:
        command += ['--job-name', args.job_name]
    # Harbor 返回 0 仅说明调度进程正常结束，实际成绩须查看结果文件。
    raise SystemExit(subprocess.call(command, env=env, cwd=ROOT))


if __name__ == '__main__':
    main()
