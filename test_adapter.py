"""检查适配器的地址处理、配置隔离和进程错误传播，不调用真实模型。"""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from harbor.models.agent.context import AgentContext
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
        config = {row['id']: row['config'] for row in harness_patch('example-model')}
        self.assertEqual(config['llm-deepseek']['protocol'], 'chat-completions')
        self.assertEqual(config['agent-default-model']['model'], 'example-model')
        self.assertEqual(config['agent-default-model']['provider'], 'deepseek-official')
        self.assertNotIn('apiKey', json.dumps(config))


class RunTests(unittest.IsolatedAsyncioTestCase):
    """使用模拟容器检查运行失败及输入隔离，不消耗模型服务额度。"""

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
