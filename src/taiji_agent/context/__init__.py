"""上下文引擎 — 来自 Hermes Agent 的上下文管理

可插拔的上下文压缩策略:
  - compressor: 内置压缩器（默认）
  - safeguard: 安全模式（保留关键上下文）
  - 第三方引擎可通过插件系统扩展
"""

from taiji_agent.context.compressor import ContextCompressor

__all__ = ["ContextCompressor"]
