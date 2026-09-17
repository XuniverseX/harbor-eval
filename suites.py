"""读取固定公共题目清单，在调度前核对影响评测的本地文件。"""

import hashlib
import json
from pathlib import Path
import re


SUITE_NAMES = ('daily-20-v1', 'smoke-5-v1')


def task_digest(task: Path) -> str:
    """锁定题面、配置、环境与验收文件；不复制题库，也不读取参考答案。"""
    files = [task / 'instruction.md', task / 'task.toml']
    for directory in ('environment', 'tests'):
        folder = task / directory
        if not folder.is_dir():
            raise ValueError(f'题目缺少 {directory}：{task.name}')
        files.extend(p for p in folder.rglob('*') if p.is_file())
    digest = hashlib.sha256()
    for path in sorted(files, key=lambda p: p.relative_to(task).as_posix()):
        # 路径与定长内容摘要一起计算，新增、删除和重命名也会导致校验失败。
        digest.update(path.relative_to(task).as_posix().encode('utf-8') + b'\0')
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def select_suite(root: Path, name: str) -> list[str]:
    """校验精确题名及文件摘要；缺题或内容漂移时拒绝静默缩小评测范围。"""
    manifest = json.loads((root / 'suites/daily-20-v1.json').read_text(encoding='utf-8'))
    if name not in SUITE_NAMES or manifest['schema_version'] != 1:
        raise ValueError('不支持的题目集或清单版本')
    entries = manifest['tasks']
    names = [entry['name'] for entry in entries]
    if not names or len(set(names)) != len(names) or any(not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', n) for n in names):
        raise ValueError('清单包含空集合、重复或无效题名')
    selected = [entry for entry in entries if name == 'daily-20-v1' or entry.get('smoke') is True]
    if not selected:
        raise ValueError('接入验证集不能为空')
    for entry in selected:
        task = root / 'datasets/terminal-bench' / entry['name']
        if task_digest(task) != entry['sha256']:
            raise ValueError(f"题目内容与锁定版本不同：{entry['name']}；请恢复指定源码版本，不要直接更新校验值")
    return [entry['name'] for entry in selected]
