"""使用合成事件验证 token 口径、重试去重和旧日志兼容，不包含真实评测数据。"""

import json
import tempfile
import unittest
from pathlib import Path

from usage_stats import summarize_usage


def event(seq, usage=None, *, session='example-session', kind='assistant/message', step=1):
    """生成只含统计字段的事件；示例数值与任何真实模型调用无关。"""
    row = {'version': 1, 'session_id': session, 'seq': seq, 'type': kind, 'turn': 1, 'step': step}
    if kind.startswith('assistant/'):
        row['usage'] = usage
    return row


class UsageTests(unittest.TestCase):
    """按请求计算 token，避免把缓存或重试更新重复累加。"""

    def summarize(self, rows, tail=''):
        """将合成记录写入临时日志目录，再调用实际解析入口。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            text = '\n'.join(json.dumps(row) for row in [{'version': 1, 'type': 'recorder/start'}, *rows])
            (root / 'token-usage.jsonl').write_text(text + '\n' + tail)
            return summarize_usage(root)

    def test_cache_and_reasoning_are_not_added_twice(self):
        """输入包含缓存；推理是输出的组成部分，不能再加到输出总数。"""
        summary = self.summarize([
            event(1, {'inputTokens': 100, 'outputTokens': 20, 'cacheReadTokens': 40,
                      'cacheWriteTokens': 10, 'reasoningTokens': 8}),
            event(2, kind='turn/end'),
        ])
        self.assertEqual(summary['n_input_tokens'], 150)
        self.assertEqual(summary['n_output_tokens'], 20)
        self.assertEqual(summary['n_cache_tokens'], 40)
        self.assertEqual(summary['cache_write_tokens'], 10)
        self.assertEqual(summary['reasoning_tokens'], 8)
        self.assertEqual(summary['status'], 'complete')

    def test_last_sample_replaces_same_attempt_and_retry_adds(self):
        """同次尝试的更新取最后值，重复行不计数，真正重试则另算一次。"""
        first = event(1, {'inputTokens': 100, 'outputTokens': 5})
        summary = self.summarize([
            first, first, event(2, {'inputTokens': 100, 'outputTokens': 10}),
            event(3, kind='llm/retry-started'),
            event(4, {'inputTokens': 110, 'outputTokens': 20}), event(5, kind='turn/end'),
        ])
        self.assertEqual(summary['n_input_tokens'], 210)
        self.assertEqual(summary['n_output_tokens'], 30)
        self.assertEqual(summary['request_count'], 2)
        self.assertIsNone(summary['n_cache_tokens'])

    def test_multiple_sessions_are_summed_independently(self):
        """不同会话可以使用相同序号和轮次，不能误去重或覆盖。"""
        rows = []
        for session in ['parent', 'child']:
            rows.extend([event(1, {'inputTokens': 10, 'outputTokens': 3}, session=session),
                         event(2, kind='turn/end', session=session)])
        summary = self.summarize(rows)
        self.assertEqual(summary['n_input_tokens'], 20)
        self.assertEqual(summary['session_count'], 2)

    def test_missing_usage_stays_unknown(self):
        """没有 usage 的调用不是零消耗，缺失缓存字段也不能伪装成零。"""
        summary = self.summarize([event(1), event(2, kind='turn/end')])
        self.assertIsNone(summary['n_input_tokens'])
        self.assertIsNone(summary['n_output_tokens'])
        self.assertEqual(summary['status'], 'unavailable')

    def test_partial_log_retains_known_usage_with_warning(self):
        """中断日志仍可报告已知用量，但必须标记为不完整。"""
        summary = self.summarize([event(1, {'inputTokens': 10, 'outputTokens': 2})], tail='{"version":')
        self.assertEqual(summary['n_input_tokens'], 10)
        self.assertEqual(summary['status'], 'partial')
        self.assertTrue(summary['warnings'])

    def test_invalid_numbers_and_conflicting_duplicates_are_not_trusted(self):
        """负数、布尔值和同一事件的矛盾副本都不能进入正常统计。"""
        for value in [-1, True, 1.5]:
            with self.subTest(value=value):
                summary = self.summarize([event(1, {'inputTokens': value, 'outputTokens': 2}),
                                          event(2, kind='turn/end')])
                self.assertIsNone(summary['n_input_tokens'])
        summary = self.summarize([event(1, {'inputTokens': 10, 'outputTokens': 2}),
                                  event(1, {'inputTokens': 50, 'outputTokens': 9}), event(2, kind='turn/end')])
        self.assertEqual(summary['status'], 'partial')

    def test_unknown_recorder_schema_is_not_silently_accepted(self):
        """未来格式必须明确拒绝，不能套用旧口径给出看似可靠的数字。"""
        summary = self.summarize([{'version': 99, 'session_id': 'example', 'seq': 1,
                                  'type': 'assistant/message', 'usage': {'inputTokens': 10, 'outputTokens': 2}}])
        self.assertEqual(summary['status'], 'unavailable')


class ProjectionFallbackTests(unittest.TestCase):
    """兼容已有原生投影缓存，遇到继承历史时拒绝直接相加。"""

    def write_projection(self, root, session, *, seeded=False, sampled=True):
        """生成与指定 Harness 版本结构一致、但数值完全合成的投影记录。"""
        folder = root / 'dsh-home/storages/session_projcache/sessions'
        folder.mkdir(parents=True, exist_ok=True)
        record = {'version': 7, 'record': {
            'identity': {'formatVersion': 3, 'createdAt': 1, 'isSeeded': seeded,
                         'inheritedEventCount': 2 if seeded else 0},
            'rows': {'tokenUsage': {'ver': 2, 'seq': 4, 'val': {
                'totals': {'uncachedInputTokens': 10, 'outputTokens': 2,
                           'cacheReadTokens': 5, 'cacheWriteTokens': 0},
                'last': {'turn': 1, 'step': 1} if sampled else None}}}}}
        (folder / f'{session}.json').write_text(json.dumps(record))

    def test_plain_sessions_fallback_to_projection_totals(self):
        """旧日志没有事件采集文件时，使用原生去重后的会话投影。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write_projection(root, 'first')
            self.write_projection(root, 'second')
            summary = summarize_usage(root)
            self.assertEqual(summary['n_input_tokens'], 30)
            self.assertEqual(summary['n_cache_tokens'], 10)
            self.assertEqual(summary['n_output_tokens'], 4)
            self.assertEqual(summary['source'], 'projection-cache')
            self.assertEqual(summary['status'], 'partial')

    def test_event_file_takes_precedence_over_cached_totals(self):
        """同时存在新事件和旧投影时只选择一个来源，不重复计算同一调用。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write_projection(root, 'example')
            rows = [{'version': 1, 'type': 'recorder/start'},
                    event(1, {'inputTokens': 1, 'outputTokens': 1}), event(2, kind='turn/end')]
            (root / 'token-usage.jsonl').write_text('\n'.join(map(json.dumps, rows)) + '\n')
            summary = summarize_usage(root)
            self.assertEqual(summary['source'], 'events')
            self.assertEqual(summary['n_input_tokens'], 1)

    def test_seeded_cache_and_unsampled_zero_are_not_counted(self):
        """投影无法证明父历史增量时标记缺失，不把继承总数重复计入。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write_projection(root, 'child', seeded=True)
            self.write_projection(root, 'empty', sampled=False)
            summary = summarize_usage(root)
            self.assertIsNone(summary['n_input_tokens'])
            self.assertEqual(summary['status'], 'unavailable')


if __name__ == '__main__':
    unittest.main()
