"""将固定版本的 DeepSeek Harness 无界面命令行接入 Harbor 任务生命周期。"""

import json
import tempfile
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from harbor.agents.base import BaseAgent


# 与安装脚本中的 npm 包版本保持一致，便于追溯每次评测使用的 Agent。
DSH_VERSION = '0.1.5-rc.1'
ROOT = Path(__file__).resolve().parent


def chat_base_url(value: str) -> str:
    """校验服务地址，仅在没有路径时补上 /v1，保留已有的网关路径。"""
    url = urlsplit(value.strip())
    # 凭据只通过环境变量传递，禁止把密钥混入地址或查询参数。
    if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError('CHAT_BASE_URL must be an HTTP(S) URL without embedded credentials, query or fragment')
    path = url.path.rstrip('/') or '/v1'
    return urlunsplit((url.scheme, url.netloc, path, '', ''))


def harness_patch(model: str) -> list[dict]:
    """生成不含凭据的配置覆盖项，固定 Chat 协议、模型和推理参数。"""
    return [
        {'id': 'llm-deepseek', 'config': {'protocol': 'chat-completions', 'maxTokens': 32768, 'reasoningEffort': 'high'}},
        {'id': 'agent-default-model', 'config': {'provider': 'deepseek-official', 'model': model}},
    ]


class DeepSeekHarness(BaseAgent):
    """在 Harbor 提供的独立题目容器中安装并执行真实的 dsh CLI。"""

    @staticmethod
    def name() -> str:
        """返回用于 Harbor 结果归类的 Agent 名称。"""
        return 'deepseek-harness'

    def version(self) -> str:
        """报告实际安装的 Harness 包版本。"""
        return DSH_VERSION

    async def setup(self, environment) -> None:
        """先校验接入配置，再在题目容器内安装运行时并上传配置覆盖文件。"""
        if not self.model_name:
            raise ValueError('An explicit model ID is required')
        if not self._get_env('CHAT_API_KEY') or not self._get_env('CHAT_BASE_URL'):
            raise ValueError('CHAT_API_KEY and CHAT_BASE_URL must be loaded from the supplied env file')
        chat_base_url(self._get_env('CHAT_BASE_URL'))
        # 安装阶段与模型作答阶段分开计时，安装日志保留在 Harbor 日志目录。
        await environment.upload_file(source_path=ROOT / 'install-dsh.sh', target_path='/tmp/harbor-install-dsh.sh')
        result = await environment.exec(
            command='bash /tmp/harbor-install-dsh.sh > /logs/agent/install-dsh.log 2>&1',
            user='root', timeout_sec=900,
        )
        if result.return_code != 0:
            raise RuntimeError(f'dsh installation failed with exit code {result.return_code}; see agent/install-dsh.log')
        with tempfile.TemporaryDirectory() as td:
            # 此文件只包含公开运行参数，服务地址和密钥在执行时单独注入。
            path = Path(td) / 'patch.json'
            path.write_text(json.dumps(harness_patch(self.model_name)))
            await environment.upload_file(source_path=path, target_path='/opt/harbor-dsh.patch.json')

    async def run(self, instruction, environment, context) -> None:
        """通过标准输入提交题目，保存执行记录，并将非零退出报告为运行异常。"""
        # 题目先写入文件，避免把题目中的引号、换行或命令替换交给 shell 解释。
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'instruction.txt'
            path.write_text(instruction)
            await environment.upload_file(source_path=path, target_path='/tmp/harbor-dsh-instruction.txt')
        # 如实记录包来源与参数；未统计的 token 和费用沿用 Harbor 的未知值。
        context.metadata = {
            'dsh_version': DSH_VERSION,
            'dsh_source': 'published npm package; not a local source build',
            'model': self.model_name,
            'protocol': 'chat-completions',
            'reasoning_effort': 'high',
            'max_output_tokens_per_request': 32768,
        }
        result = await environment.exec(
            # 此版本 headless 只输出最终文本，不支持新版的 --json 参数。
            command=(
                'export PATH="/opt/harbor-dsh/bin:$PATH"; '
                'exec /opt/harbor-dsh/bin/dsh --profile headless '
                '--patch /opt/harbor-dsh.patch.json '
                '< /tmp/harbor-dsh-instruction.txt '
                '> /logs/agent/dsh.stdout.log 2> /logs/agent/dsh.stderr.log'
            ),
            env={
                'DEEPSEEK_BASE_URL': chat_base_url(self._get_env('CHAT_BASE_URL') or ''),
                'DEEPSEEK_API_KEY': self._get_env('CHAT_API_KEY') or '',
                # 每个题目使用独立配置和会话目录，避免跨任务上下文污染。
                'DSH_HOME': '/logs/agent/dsh-home',
                # 无人值守权限仅作用于 Harbor 的独立任务容器。
                'DSH_PERMISSION_MODE': 'danger-full-access',
            },
        )
        context.metadata['exit_code'] = result.return_code
        # 进程完成不等于答题通过；退出正常后仍由 Harbor 的原始验收器判分。
        if result.return_code != 0:
            raise RuntimeError(f'dsh exited with exit code {result.return_code}; see agent/dsh.stderr.log and agent/dsh.stdout.log')
