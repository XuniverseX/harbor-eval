"""汇总 Harness 原生 usage 事件，支持只读检查已有日志目录。"""

import argparse
import json
from pathlib import Path


OPTIONAL_KEYS = ('cacheReadTokens', 'cacheWriteTokens', 'reasoningTokens')


def _counter(value):
    """只接受非负安全整数，避免将布尔值、负数或浮点数当作 token。"""
    return type(value) is int and 0 <= value <= 2**53 - 1


def _valid_usage(value):
    """必需的输入输出缺失则不计数；缓存及推理分项允许未知。"""
    if not isinstance(value, dict) or not all(_counter(value.get(k)) for k in ('inputTokens', 'outputTokens')):
        return False
    return all(value.get(k) is None or _counter(value[k]) for k in OPTIONAL_KEYS)


def _summary(samples, *, source, sessions, warnings, requests=None):
    """统一生成 Harbor 口径；推理已包含在输出中，缓存已包含在输入中。"""
    def optional_total(key):
        """任何一次请求没有报告该分项时，汇总仍保持未知。"""
        return sum(u[key] for u in samples) if samples and all(u.get(key) is not None for u in samples) else None

    known = bool(samples)
    return {
        'schema_version': 1,
        'source': source,
        'status': ('partial' if warnings else 'complete') if known else 'unavailable',
        'n_input_tokens': sum(u['inputTokens'] + (u.get('cacheReadTokens') or 0)
                              + (u.get('cacheWriteTokens') or 0) for u in samples) if known else None,
        'n_output_tokens': sum(u['outputTokens'] for u in samples) if known else None,
        'n_cache_tokens': optional_total('cacheReadTokens'),
        'uncached_input_tokens': sum(u['inputTokens'] for u in samples) if known else None,
        'cache_write_tokens': optional_total('cacheWriteTokens'),
        'reasoning_tokens': optional_total('reasoningTokens'),
        'session_count': sessions,
        'request_count': requests,
        'warnings': sorted(set(warnings)),
    }


def _from_events(path):
    """逐会话折叠记录：同次尝试后值覆盖，重试边界之后另计消耗。"""
    warnings, slots, states, seen = [], [], {}, {}
    started = False
    try:
        lines = path.read_text(encoding='utf-8').splitlines()
    except (OSError, UnicodeError):
        return _summary([], source='events', sessions=0, warnings=['用量事件文件不可读取。'])
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except (ValueError, TypeError):
            warnings.append('存在不完整或损坏的用量记录，结果可能缺少尾部消耗。')
            continue
        if not isinstance(row, dict) or row.get('version') != 1:
            warnings.append('存在不支持的用量记录版本。')
            continue
        kind = row.get('type')
        if kind == 'recorder/start':
            if started:
                warnings.append('同一日志含多个运行起点，结果可能跨越多次启动。')
            started = True
            continue
        sid, seq = row.get('session_id'), row.get('seq')
        if not isinstance(sid, str) or not sid or not _counter(seq):
            warnings.append('存在无效的会话标识或事件序号。')
            continue
        if (sid, seq) in seen:
            if seen[sid, seq] != row:
                warnings.append('同一事件出现矛盾副本，无法确认完整用量。')
            continue
        seen[sid, seq] = row
        state = states.setdefault(sid, {'seq': -1, 'last': None, 'ended': False})
        if seq < state['seq']:
            warnings.append('存在乱序事件，未将其加入汇总。')
            continue
        state['seq'] = seq
        if kind == 'turn/end':
            state['ended'] = True
            continue
        state['ended'] = False
        turn, step = row.get('turn'), row.get('step')
        if kind == 'turn/start':
            state['last'] = None
            continue
        if not _counter(turn) or not _counter(step):
            warnings.append('用量事件缺少有效轮次或步骤。')
            continue
        key = (turn, step)
        if kind == 'llm/retry-started':
            # 与原生 tokenUsage 投影一致：只有对应尝试的重试才结束覆盖窗口。
            if state['last'] is not None and state['last'][0] == key:
                state['last'] = None
            continue
        if kind not in ('assistant/message', 'assistant/attempt'):
            warnings.append('存在不支持的用量事件类型。')
            continue
        usage = row.get('usage')
        sample = usage if _valid_usage(usage) else None
        if usage is not None and sample is None:
            warnings.append('存在无效的 token 数值。')
        last = state['last']
        if last is not None and last[0] == key:
            # 无 usage 的后续结算不能抹去之前已上报的有效样本。
            if sample is not None:
                slots[last[1]] = sample
        else:
            slots.append(sample)
            state['last'] = (key, len(slots) - 1)
    if not started:
        return _summary([], source='events', sessions=len(states), warnings=['缺少记录器起点，无法确认事件格式。'])
    if any(not state['ended'] for state in states.values()):
        warnings.append('存在尚未结束的会话，只包含已落盘的 usage。')
    if any(sample is None for sample in slots):
        warnings.append('部分调用没有返回可用的 usage，汇总不代表全部请求。')
    return _summary([u for u in slots if u is not None], source='events', sessions=len(states),
                    warnings=warnings, requests=len(slots))


def _from_projections(logs_dir):
    """兼容旧日志的原生投影；缺少完整性证据时始终标记为部分统计。"""
    folder = logs_dir / 'dsh-home/storages/session_projcache/sessions'
    files = sorted(folder.glob('*.json'))
    samples, warnings = [], []
    if files:
        warnings.append('旧投影可能滞后且会将缺失缓存字段置零，无法证明请求覆盖完整。')
    for path in files:
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            if data.get('version') not in (3, 4, 5, 6, 7):
                raise ValueError('unsupported projection version')
            record = data['record']
            identity = record['identity']
            # 缓存只有累计值，没有继承前缀的基线；直接相加会重复计算父会话。
            if identity.get('isSeeded') is not False or identity.get('inheritedEventCount') != 0:
                warnings.append('跳过带继承历史或无法确认来源的会话投影。')
                continue
            row = record['rows']['tokenUsage']
            if row['ver'] != 2 or not isinstance(row['val'], dict):
                raise ValueError('unsupported tokenUsage version')
            value = row['val']
            totals = value['totals']
            if value.get('last') is None and not any(totals.values()):
                warnings.append('部分会话没有有效的 usage 样本。')
                continue
            sample = {'inputTokens': totals['uncachedInputTokens'], 'outputTokens': totals['outputTokens'],
                      'cacheReadTokens': totals['cacheReadTokens'], 'cacheWriteTokens': totals['cacheWriteTokens']}
            if not _valid_usage(sample) or value.get('last') is None:
                raise ValueError('invalid usage projection')
            samples.append(sample)
        except (OSError, UnicodeError, ValueError, TypeError, KeyError, AttributeError):
            warnings.append('部分会话投影损坏或格式不受支持，未计入汇总。')
    return _summary(samples, source='projection-cache' if files else 'none',
                    sessions=len(files), warnings=warnings)


def summarize_usage(logs_dir: Path) -> dict:
    """优先读取本次运行事件；仅在事件文件不存在时退回旧投影，避免重复相加。"""
    path = Path(logs_dir) / 'token-usage.jsonl'
    return _from_events(path) if path.exists() else _from_projections(Path(logs_dir))


def main():
    """只读输出某个 trial 的用量摘要，不修改原始日志或评测结果。"""
    parser = argparse.ArgumentParser(description='汇总一个 Harbor trial 的本地 Agent 用量日志')
    parser.add_argument('agent_logs', type=Path, help='trial 下的 agent 日志目录')
    args = parser.parse_args()
    print(json.dumps(summarize_usage(args.agent_logs), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
