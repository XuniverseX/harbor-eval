"""在 Harbor 生命周期内等待真实 WorkBuddy 桌面作答，由操作者结束后评分。"""

import fcntl
import json
import os
from pathlib import Path
import time

from harbor.agents.base import BaseAgent
from workbuddy_bridge import TrialBridge


ROOT = Path(__file__).resolve().parent
STATE = ROOT / '.local/workbuddy'


def private_json(path: Path, data):
    """原子写入仅当前用户可读的本地连接文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    # 创建时即限制权限，避免先写入凭据再收紧权限的短暂窗口。
    descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


class WorkBuddyDesktop(BaseAgent):
    """不代替桌面产品调用模型；仅准备工具入口并等待人工完成信号。"""

    @staticmethod
    def name():
        """结果明确标识桌面加 MCP 的半自动运行方式。"""
        return 'workbuddy-desktop-mcp'

    def version(self):
        """实际产品版本由启动命令传入，不硬编码用户安装信息。"""
        return self._get_env('WORKBUDDY_VERSION') or 'unknown'

    async def setup(self, environment):
        """保留题目原始环境，不向容器安装其他 Agent。"""
        STATE.mkdir(parents=True, exist_ok=True)

    async def run(self, instruction, environment, context):
        """发布单题连接入口；结束后断开桥接再把控制权交还 Harbor。"""
        with (STATE / 'run.lock').open('w') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError('另一个 WorkBuddy 题目正在运行；仅支持单题串行') from None
            bridge = TrialBridge(environment, self.logs_dir, instruction)
            try:
                await bridge.start()
                private_json(STATE / 'connection.json', bridge.descriptor())
                private_json(STATE / 'control.json', bridge.descriptor(control=True))
                prompt = ('这是独立的 Harbor 评测任务。先调用 harbor_task 获取原始题面和 trial_id。'
                          '只通过 harbor_exec 在当前 Linux 题目容器内完成任务；所有题目路径属于容器。'
                          '不要使用宿主机文件/终端/浏览器工具，不要读取历史记忆、参考解答或评分文件。'
                          '完成后报告结果并停止，不等待额外指示，不调用其他模型。\n\n' + instruction)
                (STATE / 'prompt.txt').write_text(prompt, encoding='utf-8')
                self.logger.info('WorkBuddy 题目已就绪，请使用本地 prompt.txt；结束时执行 finish 并指定 trial_id。')
                await bridge.finished.wait()
            finally:
                await bridge.close()
                context.metadata = {
                    'mode': 'desktop-mcp-semi-automatic', 'workbuddy_version': self.version(),
                    'bridge_trial_id': bridge.trial_id, 'command_count': bridge.command_count,
                    'operator_finished': bridge.finished.is_set(),
                    'elapsed_including_operator_seconds': time.time() - bridge.started_at,
                    'usage_status': 'unavailable',
                    'limitation': 'MCP 限定容器操作；不能强制禁用桌面原生工具或证明记忆隔离。',
                }
                # 结束文件不再允许 MCP 使用；控制描述留给本地排查但端口已关闭。
                (STATE / 'connection.json').unlink(missing_ok=True)
