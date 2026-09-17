"""验证固定选题、内容锁定和预演隔离，不启动容器或调用模型。"""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import run as launcher


class SuiteTests(unittest.TestCase):
    """使用临时题库验证缺题或漂移时阻止运行。"""

    def invoke(self, root, arguments):
        """截获调度边界，读取入口输出和实际传给 Harbor 的参数。"""
        output = io.StringIO()
        with patch.object(launcher, 'ROOT', root), patch('sys.argv', ['run.py', *arguments]), \
                patch.object(launcher.subprocess, 'call', return_value=0) as call, \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(output), \
                self.assertRaises(SystemExit) as result:
            launcher.main()
        return result.exception.code, output.getvalue(), call.call_args

    def fixture(self, root):
        """构造合成清单，测试数据不依赖下载的公共题库。"""
        from suites import task_digest
        tasks = []
        for name in ['example-a', 'example-b']:
            task = root / 'datasets/terminal-bench' / name
            (task / 'environment').mkdir(parents=True)
            (task / 'tests').mkdir()
            (task / 'instruction.md').write_text('完成合成任务')
            (task / 'task.toml').write_text('version = "1.0"\n')
            (task / 'environment/Dockerfile').write_text('FROM scratch\n')
            (task / 'tests/test.sh').write_text('exit 0\n')
            tasks.append({'name': name, 'sha256': task_digest(task), 'smoke': name == 'example-a'})
        (root / 'suites').mkdir()
        (root / 'suites/daily-20-v1.json').write_text(json.dumps({'schema_version': 1, 'tasks': tasks}))

    def test_dry_run_needs_no_credentials_and_starts_no_job(self):
        """预演不读取凭据，不启动 Harbor，并显示确切 trial 数。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'datasets/terminal-bench/example-task').mkdir(parents=True)
            code, output, call = self.invoke(root, ['--task', 'example-task', '--dry-run', '--attempts', '3'])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output)['trial_count'], 3)
            self.assertIsNone(call)

    def test_suite_filters_reach_harbor_and_smoke_is_subset(self):
        """只将清单中的精确题名交给 Harbor，并保留独立运行次数。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.fixture(root)
            (root / '.env.local').write_text('CHAT_BASE_URL=https://example.com\nCHAT_API_KEY=example-key\nCHAT_MODEL=example-model\n')
            code, _, call = self.invoke(root, ['--suite', 'daily-20-v1', '--attempts', '3'])
            self.assertEqual(code, 0)
            command = call.args[0]
            selected = [command[i+1] for i, value in enumerate(command) if value == '--include-task-name']
            self.assertEqual(selected, ['example-a', 'example-b'])
            self.assertEqual(command[command.index('--n-attempts')+1], '3')
            code, output, call = self.invoke(root, ['--suite', 'smoke-5-v1', '--dry-run'])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output)['tasks'], ['example-a'])
            self.assertIsNone(call)

    def test_changed_or_missing_task_blocks_launch(self):
        """题目内容改变、新增环境文件或缺题均不能静默继续。"""
        for mode in ['changed', 'added', 'missing']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                self.fixture(root)
                task = root / 'datasets/terminal-bench/example-a'
                if mode == 'changed':
                    (task / 'instruction.md').write_text('已改变')
                elif mode == 'added':
                    (task / 'environment/extra.txt').write_text('新增依赖')
                else:
                    (task / 'task.toml').unlink()
                code, _, call = self.invoke(root, ['--suite', 'daily-20-v1', '--dry-run'])
                self.assertEqual(code, 2)
                self.assertIsNone(call)

    def test_task_suite_conflict_and_invalid_counts_are_rejected(self):
        """互斥范围或非正运行次数不能触发评测。"""
        for args in [['--task', 'ALL', '--suite', 'daily-20-v1'], ['--attempts', '0'], ['--concurrency', '-1']]:
            with self.subTest(args=args), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                (root / 'datasets/terminal-bench/cancel-async-tasks').mkdir(parents=True)
                (root / '.env.local').write_text('CHAT_BASE_URL=https://example.com\nCHAT_API_KEY=example-key\nCHAT_MODEL=example-model\n')
                code, _, call = self.invoke(root, args)
                self.assertEqual(code, 2)
                self.assertIsNone(call)


if __name__ == '__main__':
    unittest.main()
