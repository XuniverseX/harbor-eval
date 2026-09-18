"""验证 Claude Code 入口的选题转发及本地凭据隔离，不调用真实模型。"""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import run as launcher


class ClaudeLauncherTests(unittest.TestCase):
    """检查同一启动流程能够选择原生 Claude Code 适配器。"""

    def invoke(self, extra=(), config=True):
        """构造无私有信息的临时配置，截获 Harbor 启动边界。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'datasets/terminal-bench/example').mkdir(parents=True)
            if config:
                (root / '.env.claude.local').write_text('ANTHROPIC_BASE_URL=https://example.com/gateway\nANTHROPIC_API_KEY=test-secret\nANTHROPIC_MODEL=example-model\n')
            output = io.StringIO()
            with patch.object(launcher, 'ROOT', root), patch('sys.argv', ['run.py', '--agent', 'claude-code', '--task', 'example', *extra]), \
                    patch.object(launcher.subprocess, 'call', return_value=0) as call, \
                    contextlib.redirect_stdout(output), contextlib.redirect_stderr(output), self.assertRaises(SystemExit) as result:
                launcher.main()
            return result.exception.code, call.call_args, output.getvalue()

    def test_gateway_credentials_stay_in_environment(self):
        """地址保留网关路径，凭据只进入子进程环境，不出现在启动参数。"""
        code, call, _ = self.invoke(['--attempts', '2', '--concurrency', '2'])
        self.assertEqual(code, 0)
        command = call.args[0]
        self.assertEqual(command[command.index('--agent') + 1], 'claude-code')
        self.assertEqual(command[command.index('--model') + 1], 'example-model')
        self.assertEqual(command[command.index('--n-attempts') + 1], '2')
        self.assertNotIn('test-secret', ' '.join(command))
        self.assertEqual(call.kwargs['env']['ANTHROPIC_BASE_URL'], 'https://example.com/gateway')
        self.assertEqual(call.kwargs['env']['ANTHROPIC_API_KEY'], 'test-secret')

    def test_dry_run_without_gateway_and_missing_config_rejected(self):
        """预演无需配置，正式运行缺少网关配置则不能启动。"""
        code, call, _ = self.invoke(['--dry-run'], config=False)
        self.assertEqual(code, 0)
        self.assertIsNone(call)
        code, call, _ = self.invoke(config=False)
        self.assertEqual(code, 2)
        self.assertIsNone(call)

    def test_explicit_model_override(self):
        """模型覆盖参数对 Claude Code 同样生效。"""
        code, call, _ = self.invoke(['--model', 'other-model'])
        self.assertEqual(code, 0)
        command = call.args[0]
        self.assertEqual(command[command.index('--model') + 1], 'other-model')
