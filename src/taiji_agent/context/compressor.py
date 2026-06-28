"""上下文压缩器 — Token 感知的对话压缩，v2 模型感知"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# 模型上下文长度映射表
MODEL_CONTEXT_LENGTHS: dict[str, int] = {
    "deepseek-v4-pro":  1_048_576,  # DeepSeek 直连 1M
    "deepseek-v4-flash": 1_048_576,
    "deepseek-v3":      1_048_576,
    "deepseek-chat":      128_000,
    "deepseek-reasoner":   64_000,
    "gpt-4":             128_000,
    "gpt-4o":            128_000,
    "gpt-4-turbo":       128_000,
    "gpt-3.5-turbo":      16_384,
    "claude-3-opus":     200_000,
    "claude-3-sonnet":   200_000,
    "claude-3-haiku":    200_000,
    "claude-3.5-sonnet": 200_000,
    "qwen-max":           32_768,
    "qwen-plus":         131_072,
    "glm-4":             128_000,
    "moonshot-v1":       128_000,
    "hunyuan-pro":        32_000,
    "kimi-latest":       128_000,
}


def get_model_context_length(model: str, default: int = 128_000) -> int:
    """根据模型名获取上下文长度"""
    # 精确匹配
    if model in MODEL_CONTEXT_LENGTHS:
        return MODEL_CONTEXT_LENGTHS[model]
    # 前缀匹配（支持带版本后缀的模型名）
    for prefix, length in MODEL_CONTEXT_LENGTHS.items():
        if model.startswith(prefix):
            return length
    logger.warning("Unknown model '%s', using default context length %d", model, default)
    return default


class ContextCompressor:
    """上下文压缩器 — v2: 模型感知 + 便捷方法"""

    def __init__(self, threshold_percent=0.75, protect_first_n=3, protect_last_n=6,
                 context_length: int = None, model: str = None):
        self.threshold_percent = threshold_percent
        self.protect_first_n = protect_first_n
        self.protect_last_n = protect_last_n
        self.last_prompt_tokens = 0
        self.last_completion_tokens = 0
        self.compression_count = 0
        # 模型感知的上下文长度
        if context_length is not None:
            self.context_length = context_length
        elif model is not None:
            self.context_length = get_model_context_length(model)
        else:
            self.context_length = 128_000

    def update_from_response(self, usage):
        self.last_prompt_tokens = usage.get("prompt_tokens", 0)
        self.last_completion_tokens = usage.get("completion_tokens", 0)

    def should_compress(self, prompt_tokens=None):
        threshold = int(self.context_length * self.threshold_percent)
        tokens = prompt_tokens or self.last_prompt_tokens
        return tokens > threshold

    def compress(self, messages, focus_topic=None):
        if len(messages) <= self.protect_first_n + self.protect_last_n:
            return messages

        self.compression_count += 1
        logger.info("Compressing context (count=%d, messages=%d)", self.compression_count, len(messages))

        head = messages[:self.protect_first_n]
        tail = messages[-self.protect_last_n:]
        middle = messages[self.protect_first_n:-self.protect_last_n]

        if not middle:
            return head + tail

        summary = self._summarize_middle(middle, focus_topic)
        summary_msg = {
            "role": "user",
            "content": "[Previous conversation summary (%d turns compressed)]\n%s" % (len(middle), summary),
        }
        return head + [summary_msg] + tail

    def _summarize_middle(self, messages, focus_topic=None):
        parts = []
        user_msgs = [m for m in messages if _msg_role(m) == "user"]
        if user_msgs:
            parts.append("用户查询:")
            for msg in user_msgs[:5]:
                content = str(_msg_content(msg))[:200]
                parts.append("  - %s" % content)
        tool_msgs = [m for m in messages if _msg_role(m) == "assistant" and "tool_call" in str(_msg_content(m))]
        if tool_msgs:
            parts.append("工具调用: %d 次" % len(tool_msgs))
        if focus_topic:
            parts.append("关注主题: %s" % focus_topic)
        summary = "\n".join(parts)
        if len(summary) > 2000:
            summary = summary[:1997] + "..."
        return summary

    def estimate_tokens(self, text):
        return len(text) // 4

    def estimate_total_tokens(self, messages):
        return sum(self.estimate_tokens(str(_msg_content(m))) for m in messages)

    def needs_compression(self, messages, threshold_percent=None):
        """检查是否需要压缩（便捷方法）"""
        if len(messages) <= self.protect_first_n + self.protect_last_n:
            return False
        pct = threshold_percent if threshold_percent is not None else self.threshold_percent
        threshold = int(self.context_length * pct)
        est = self.estimate_total_tokens(messages)
        return est > threshold

    def compress_if_needed(self, messages, threshold_percent=None, focus_topic=None):
        """如果需要就压缩，否则原样返回（便捷方法）"""
        if not self.needs_compression(messages, threshold_percent):
            return messages
        old_pct = self.threshold_percent
        if threshold_percent is not None:
            self.threshold_percent = threshold_percent
        try:
            return self.compress(messages, focus_topic)
        finally:
            self.threshold_percent = old_pct


def _msg_role(msg) -> str:
    """获取消息角色，兼容 dict 和 Pydantic 对象"""
    if isinstance(msg, dict):
        return msg.get("role", "")
    return getattr(msg, "role", "")


def _msg_content(msg) -> str:
    """获取消息内容，兼容 dict 和 Pydantic 对象"""
    if isinstance(msg, dict):
        return msg.get("content", "")
    return getattr(msg, "content", "")
