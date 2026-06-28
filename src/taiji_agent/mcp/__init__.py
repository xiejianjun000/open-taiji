"""
Taiji Agent MCP Protocol Module
双向MCP协议集成 - 参考Dify v1.6.0 + OpenAI Agents SDK设计
"""

from .client import MCPClientAdapter, MCPConnectionConfig
from .protocol import MCPProtocol, MCPResource, MCPTool
from .server import MCPServerAdapter, MCPServerConfig

__all__ = [
    "MCPServerAdapter",
    "MCPServerConfig",
    "MCPClientAdapter",
    "MCPConnectionConfig",
    "MCPProtocol",
    "MCPTool",
    "MCPResource",
]
