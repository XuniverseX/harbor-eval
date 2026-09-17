/** 只记录原生会话中的用量事件，不保存提示词、回复正文、工具参数或凭据。 */
import { appendFileSync, mkdirSync } from 'node:fs';
import { dirname } from 'node:path';

export const name = 'harbor-token-usage';
const eventTypes = new Set(['assistant/message', 'assistant/attempt', 'llm/retry-started', 'turn/start', 'turn/end']);
const usageKeys = ['inputTokens', 'outputTokens', 'cacheReadTokens', 'cacheWriteTokens', 'reasoningTokens'];

/** 按 Harness 原生投影的规则取本次结算的最后一个 usage 样本。 */
function usageOf(event) {
    if (event.type === 'assistant/message' && event.data?.usage != null) return event.data.usage;
    const stream = event.data?.stream;
    if (!Array.isArray(stream)) return null;
    for (let index = stream.length - 1; index >= 0; index--) {
        const record = stream[index];
        if (record?.type === 'chunk' && record.chunk?.type === 'usage') return record.chunk.usage ?? null;
    }
    return null;
}

/** 订阅全局会话事件；构造或恢复时继承的历史不属于本次运行的消耗。 */
export function apply(ctx, config) {
    const outputPath = config.outputPath;
    mkdirSync(dirname(outputPath), { recursive: true });
    // 逐条同步追加，进程异常退出时仍保留已收到的结算；每个 trial 使用独立目录。
    appendFileSync(outputPath, JSON.stringify({ version: 1, type: 'recorder/start' }) + '\n');
    ctx.on('session/event', (session, event) => {
        if (!eventTypes.has(event.type)) return;
        const boundary = Math.max(session.firstLiveSeq ?? 0, session.inheritedEventCount ?? 0);
        if (event.seq < boundary) return;
        const row = {
            version: 1, session_id: String(session.id), seq: event.seq, type: event.type,
            turn: event.data?.turn, step: event.data?.step,
        };
        if (event.type.startsWith('assistant/')) {
            const usage = usageOf(event);
            // 缺失字段保持缺失；只允许用量字段进入日志，防止意外记录其他请求数据。
            row.usage = usage == null ? null : Object.fromEntries(
                usageKeys.filter(key => Object.hasOwn(usage, key)).map(key => [key, usage[key]]),
            );
        }
        appendFileSync(outputPath, JSON.stringify(row) + '\n');
    });
}
