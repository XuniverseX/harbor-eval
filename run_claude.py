"""Claude Code CLI 评测入口，复用统一选题、预演及调度流程。"""

from run import main


if __name__ == '__main__':
    # 默认选择 Harbor 原生适配器，其余参数与 Harness 入口完全一致。
    main(default_agent='claude-code')
