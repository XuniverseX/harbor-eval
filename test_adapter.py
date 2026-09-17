"""检查适配器的地址处理、配置隔离和进程错误传播，不调用真实模型。"""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from harbor.models.agent.context import AgentContext
from harbor.trial.trial import Trial
from deepseek_agent import DeepSeekHarness, chat_base_url, harness_patch
import run as launcher


class ConfigurationTests(unittest.TestCase):
    """验证模型服务地址与配置覆盖项的生成规则。"""

    def test_origin_and_versioned_urls(self):
        """无路径地址补 /v1，已有版本路径和网关前缀保持不变。"""
        self.assertEqual(chat_base_url('http://localhost:8000/'), 'http://localhost:8000/v1')
        self.assertEqual(chat_base_url('https://example.com/v1'), 'https://example.com/v1')
        self.assertEqual(chat_base_url('https://example.com/proxy/v1/'), 'https://example.com/proxy/v1')

    def test_rejects_credentials_and_non_http_urls(self):
        """拒绝非 HTTP 地址以及可能在日志中暴露凭据的 URL。"""
        for value in ['file:///tmp/a', 'https://user:secret@example.com', 'https://example.com/?key=secret']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                chat_base_url(value)

    def test_config_pins_chat_protocol_and_model(self):
        """确认指定模型走 Chat 协议，且配置覆盖项不携带密钥。"""
        config = {row['id']: row['config'] for row in harness_patch('example-model') if 'id' in row}
        self.assertEqual(config['llm-deepseek']['protocol'], 'chat-completions')
        self.assertEqual(config['agent-default-model']['model'], 'example-model')
        self.assertEqual(config['agent-default-model']['provider'], 'deepseek-official')
        self.assertNotIn('apiKey', json.dumps(config))


class RunTests(unittest.IsolatedAsyncioTestCase):
    """使用模拟容器检查运行失败及输入隔离，不消耗模型服务额度。"""

    async def test_release_candidate_accepts_plain_headless_invocation(self):
        """旧版 headless 拒绝 --json；正确的启动方式应能正常记录退出状态。"""
        class ReleaseCandidateEnvironment:
            """模拟指定发行版不支持结构化输出参数的命令行约束。"""

            async def upload_file(self, **kwargs):
                """本测试只检查命令行兼容性，不实际上传文件。"""
                pass

            async def exec(self, command, **kwargs):
                """遇到旧版不支持的参数时返回命令行解析失败。"""
                return SimpleNamespace(return_code=1 if '--json' in command else 0,
                                       stdout='', stderr='')

        with tempfile.TemporaryDirectory() as td:
            agent = DeepSeekHarness(logs_dir=Path(td), model_name='example-model',
                                   extra_env={'CHAT_BASE_URL': 'https://example.com', 'CHAT_API_KEY': 'test-secret'})
            context = AgentContext()
            await agent.run('完成示例任务', ReleaseCandidateEnvironment(), context)
            # 模拟 Harbor 在日志下载后调用的真实回填入口，防止元数据过早阻塞统计。
            self.assertTrue(context.is_empty())
            Trial._populate_agent_context(SimpleNamespace(user_agent=None, agent=agent), context)
            self.assertEqual(context.metadata['exit_code'], 0)

    async def test_task_is_passed_as_literal_positional_argument(self):
        """执行真实 shell，确认旧版要求的题目参数完整且不会触发二次命令解释。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            stub = root / 'dsh'
            stub.write_text('#!/usr/bin/env python3\nimport json, sys\nprint(json.dumps(sys.argv[1:]))\n')
            stub.chmod(0o755)
            instruction = """--help\n引号 " 和 ' 与 $(exit 91) `exit 92` $HOME"""

            class ShellEnvironment:
                """将容器路径映射到临时目录，通过本地假 CLI 检查实际参数。"""

                async def upload_file(self, source_path, target_path):
                    """保留题目的原始字节，模拟文件上传。"""
                    (root / 'instruction.txt').write_bytes(Path(source_path).read_bytes())

                async def exec(self, command, **kwargs):
                    """只替换固定路径，保持适配器的 shell 引用方式原样运行。"""
                    command = command.replace('/opt/harbor-dsh/bin/dsh', str(stub))
                    command = command.replace('/tmp/harbor-dsh-instruction.txt', str(root / 'instruction.txt'))
                    command = command.replace('/logs/agent', str(root))
                    result = subprocess.run(command, shell=True, capture_output=True, text=True)
                    return SimpleNamespace(return_code=result.returncode)

            agent = DeepSeekHarness(logs_dir=root, model_name='example-model',
                                   extra_env={'CHAT_BASE_URL': 'https://example.com', 'CHAT_API_KEY': 'test-secret'})
            await agent.run(instruction, ShellEnvironment(), AgentContext())
            argv = json.loads((root / 'dsh.stdout.log').read_text())
            self.assertEqual(argv[-2:], ['--', instruction])

    async def test_harbor_post_run_hook_populates_tokens_after_failure(self):
        """失败任务也在日志同步后回填已上报用量，重复回填不累加两次。"""
        class FailedEnvironment:
            """模拟容器内命令已经运行、产生用量，然后非零退出。"""

            async def upload_file(self, **kwargs):
                """省略与本次回填测试无关的文件传输。"""
                pass

            async def exec(self, command, **kwargs):
                """返回失败状态，用量日志由测试预先放入本地收集目录。"""
                return SimpleNamespace(return_code=1, stdout='', stderr='')

        with tempfile.TemporaryDirectory() as td:
            directory = Path(td)
            rows = [{'version': 1, 'type': 'recorder/start'},
                    {'version': 1, 'session_id': 'example', 'seq': 1, 'type': 'assistant/message',
                     'turn': 1, 'step': 1, 'usage': {'inputTokens': 10, 'outputTokens': 4, 'cacheReadTokens': 3}},
                    {'version': 1, 'session_id': 'example', 'seq': 2, 'type': 'turn/end', 'turn': 1}]
            (directory / 'token-usage.jsonl').write_text('\n'.join(map(json.dumps, rows)) + '\n')
            agent = DeepSeekHarness(logs_dir=directory, model_name='example-model',
                                   extra_env={'CHAT_BASE_URL': 'https://example.com', 'CHAT_API_KEY': 'test-secret'})
            context = AgentContext()
            with self.assertRaises(RuntimeError):
                await agent.run('示例任务', FailedEnvironment(), context)
            self.assertTrue(context.is_empty())
            trial = SimpleNamespace(user_agent=None, agent=agent)
            Trial._populate_agent_context(trial, context)
            self.assertEqual(context.n_input_tokens, 13)
            self.assertEqual(context.n_output_tokens, 4)
            self.assertEqual(context.n_cache_tokens, 3)
            self.assertEqual(context.metadata['exit_code'], 1)
            self.assertIsNone(context.cost_usd)
            agent.populate_context_post_run(context)
            self.assertEqual(context.n_input_tokens, 13)

    def test_unavailable_usage_keeps_harbor_counts_unknown(self):
        """尚无日志时仍可记录配置，但不得把未观测到的 token 写成零。"""
        with tempfile.TemporaryDirectory() as td:
            agent = DeepSeekHarness(logs_dir=Path(td), model_name='example-model')
            context = AgentContext()
            Trial._populate_agent_context(SimpleNamespace(user_agent=None, agent=agent), context)
            self.assertIsNone(context.n_input_tokens)
            self.assertIsNone(context.n_cache_tokens)
            self.assertEqual(context.metadata['token_usage']['status'], 'unavailable')

    async def test_cli_failure_is_not_silently_scored_as_completion(self):
        """模拟 CLI 失败，验证异常向上传递且题目、密钥没有拼入命令。"""
        class Environment:
            """只实现本测试需要的容器接口，并记录执行参数供断言使用。"""

            async def upload_file(self, **kwargs):
                """接受上传操作；本测试不需要实际保存容器文件。"""
                pass

            async def exec(self, command, **kwargs):
                """记录命令和环境，返回非零退出码模拟 Agent 运行失败。"""
                self.command = command
                self.env = kwargs.get('env', {})
                return SimpleNamespace(return_code=1, stdout='', stderr='')

        with tempfile.TemporaryDirectory() as td:
            agent = DeepSeekHarness(logs_dir=Path(td), model_name='example-model',
                                   extra_env={'CHAT_BASE_URL': 'http://example.com:8000', 'CHAT_API_KEY': 'test-secret'})
            environment = Environment()
            with self.assertRaisesRegex(RuntimeError, 'exit code 1'):
                await agent.run('literal $(do-not-execute) task', environment, AgentContext())
            self.assertNotIn('test-secret', environment.command)
            self.assertNotIn('$(do-not-execute)', environment.command)
            self.assertEqual(environment.env['DEEPSEEK_BASE_URL'], 'http://example.com:8000/v1')


class LauncherTests(unittest.TestCase):
    """确保部署模型来自本地配置或显式参数，不内置任何私有部署标识。"""

    def invoke(self, configured_model=None, override=None):
        """使用临时配置运行入口，并拦截 Harbor 进程以检查实际启动参数。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'datasets/terminal-bench/example-task').mkdir(parents=True)
            env_file = root / '.env.local'
            contents = 'CHAT_BASE_URL=https://example.com\nCHAT_API_KEY=test-secret\n'
            if configured_model:
                contents += f'CHAT_MODEL={configured_model}\n'
            env_file.write_text(contents)
            argv = ['run.py', '--env-file', str(env_file), '--task', 'example-task']
            if override:
                argv += ['--model', override]
            with patch.object(launcher, 'ROOT', root), patch('sys.argv', argv), \
                    patch.object(launcher.subprocess, 'call', return_value=0) as call, \
                    patch('sys.stderr'), self.assertRaises(SystemExit) as outcome:
                launcher.main()
            return outcome.exception.code, call.call_args

    def test_install_only_is_forwarded_to_harbor(self):
        """预热通过 Harbor 安装阶段结束，不进入模型作答。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'datasets/terminal-bench/example-task').mkdir(parents=True)
            (root / '.env.local').write_text('CHAT_BASE_URL=https://example.com\nCHAT_API_KEY=test-secret\nCHAT_MODEL=example-model\n')
            with patch.object(launcher, 'ROOT', root), \
                    patch('sys.argv', ['run.py', '--task', 'example-task', '--install-only']), \
                    patch.object(launcher.subprocess, 'call', return_value=0) as call, \
                    self.assertRaises(SystemExit) as result:
                launcher.main()
            self.assertEqual(result.exception.code, 0)
            self.assertIn('--install-only', call.call_args.args[0])

    def test_model_is_read_from_local_configuration(self):
        """没有命令行覆盖时使用本地 env 中配置的模型。"""
        code, call = self.invoke(configured_model='example-model')
        self.assertEqual(code, 0)
        command = call.args[0]
        self.assertEqual(command[command.index('--model') + 1], 'example-model')

    def test_explicit_model_overrides_local_configuration(self):
        """允许调用者显式选择其他模型，优先级高于本地配置。"""
        code, call = self.invoke(configured_model='example-model', override='other-model')
        self.assertEqual(code, 0)
        command = call.args[0]
        self.assertEqual(command[command.index('--model') + 1], 'other-model')

    def test_missing_model_does_not_start_harbor(self):
        """缺少模型配置时明确报错，不能回退到某个私有默认部署。"""
        code, call = self.invoke()
        self.assertEqual(code, 2)
        self.assertIsNone(call)


if __name__ == '__main__':
    unittest.main()
