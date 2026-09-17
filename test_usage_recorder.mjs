/** 使用模拟会话事件验证记录器，不加载模型、凭据或完整 Harness。 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { apply } from './usage_recorder.mjs';

test('提取最后一个 usage，跳过继承历史且不写入正文和凭据', () => {
    const directory = mkdtempSync(join(tmpdir(), 'usage-recorder-'));
    try {
        const handlers = new Map();
        const outputPath = join(directory, 'usage.jsonl');
        apply({ on: (name, callback) => handlers.set(name, callback) }, { outputPath });
        const emit = handlers.get('session/event');
        const session = { id: 'example-child', inheritedEventCount: 10, firstLiveSeq: 10 };
        const data = { turn: 1, step: 1, content: 'PRIVATE_PROMPT', apiKey: 'PRIVATE_KEY', stream: [
            { type: 'chunk', chunk: { type: 'usage', usage: { inputTokens: 10, outputTokens: 1 } } },
            { type: 'chunk', chunk: { type: 'usage', usage: { inputTokens: 10, outputTokens: 4 } } },
        ] };
        emit(session, { type: 'assistant/message', seq: 2, data });
        emit(session, { type: 'assistant/message', seq: 11, data });
        emit(session, { type: 'tool/result', seq: 12, data: { content: 'PRIVATE_TOOL_OUTPUT' } });
        emit(session, { type: 'turn/end', seq: 13, data: { turn: 1 } });
        const raw = readFileSync(outputPath, 'utf8');
        const rows = raw.trim().split('\n').map(JSON.parse);
        assert.equal(rows.length, 3);
        assert.equal(rows[1].usage.outputTokens, 4);
        assert.equal(rows[1].session_id, 'example-child');
        assert.equal(raw.includes('PRIVATE_'), false);
    } finally {
        rmSync(directory, { recursive: true, force: true });
    }
});

test('缺失 usage 保留为空，显式零和缓存分项保持原值', () => {
    const directory = mkdtempSync(join(tmpdir(), 'usage-recorder-'));
    try {
        let emit;
        const outputPath = join(directory, 'usage.jsonl');
        apply({ on: (_name, callback) => { emit = callback; } }, { outputPath });
        const session = { id: 'example', inheritedEventCount: 0 };
        emit(session, { type: 'assistant/attempt', seq: 1, data: { turn: 1, step: 1, stream: [] } });
        emit(session, { type: 'llm/retry-started', seq: 2, data: { turn: 1, step: 1 } });
        emit(session, { type: 'assistant/message', seq: 3, data: { turn: 1, step: 1,
            usage: { inputTokens: 0, outputTokens: 0, cacheReadTokens: 8, reasoningTokens: 0 } } });
        const rows = readFileSync(outputPath, 'utf8').trim().split('\n').map(JSON.parse);
        assert.equal(rows[1].usage, null);
        assert.equal(rows[2].type, 'llm/retry-started');
        assert.deepEqual(rows[3].usage, { inputTokens: 0, outputTokens: 0, cacheReadTokens: 8, reasoningTokens: 0 });
    } finally {
        rmSync(directory, { recursive: true, force: true });
    }
});

test('恢复会话只统计当前进程追加的事件', () => {
    const directory = mkdtempSync(join(tmpdir(), 'usage-recorder-'));
    try {
        let emit;
        const outputPath = join(directory, 'usage.jsonl');
        apply({ on: (_name, callback) => { emit = callback; } }, { outputPath });
        const session = { id: 'example-resumed', inheritedEventCount: 0, firstLiveSeq: 20 };
        const data = { turn: 2, step: 1, usage: { inputTokens: 3, outputTokens: 1 } };
        emit(session, { type: 'assistant/message', seq: 5, data });
        emit(session, { type: 'assistant/message', seq: 20, data });
        const rows = readFileSync(outputPath, 'utf8').trim().split('\n').map(JSON.parse);
        assert.equal(rows.length, 2);
        assert.equal(rows[1].seq, 20);
    } finally {
        rmSync(directory, { recursive: true, force: true });
    }
});
