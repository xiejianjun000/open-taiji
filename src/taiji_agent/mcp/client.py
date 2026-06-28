"""
MCP Client Adapter - 连接外部MCP Server作为工具
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional

import aiohttp

from ..tools.registry import Tool, ToolResult
from .protocol import MCPMessage, MCPProtocol, MCPTool

logger = logging.getLogger(__name__)


@dataclass
class MCPConnectionConfig:
    url: str
    name: str = "mcp_server"
    auth_token: Optional[str] = None
    timeout: int = 30
    retry_count: int = 3


class MCPClientAdapter:
    def __init__(
        self,
        config: Optional[MCPConnectionConfig] = None,
    ):
        self.config = config
        self._tools: dict[str, MCPTool] = {}
        self._session: aiohttp.Optional[ClientSession] = None
        self._request_id = 0
        self._initialized = False

    async def connect(self) -> bool:
        if not self.config:
            raise ValueError("MCPConnectionConfig is required")
        try:
            self._session = aiohttp.ClientSession()
            init_response = await self._send_request(
                MCPProtocol.initialize_request(
                    client_name="taiji_agent",
                    client_version="2.0.0",
                )
            )
            if init_response.error:
                logger.error(f"MCP init error: {init_response.error}")
                return False
            self._initialized = True
            await self._load_tools()
            logger.info(f"Connected to MCP server: {self.config.url}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            return False

    async def disconnect(self) -> None:
        if self._session:
            await self._send_request(MCPProtocol.shutdown())
            await self._session.close()
            self._session = None
            self._initialized = False
            self._tools.clear()

    async def _send_request(self, message: MCPMessage) -> MCPMessage:
        if not self._session:
            raise RuntimeError("Not connected to MCP server")
        headers = {"Content-Type": "application/json"}
        if self.config and self.config.auth_token:
            headers["Authorization"] = f"Bearer {self.config.auth_token}"
        self._request_id += 1
        message.id = self._request_id
        config_url = self.config.url if self.config else ""
        async with self._session.post(
            f"{config_url}/message",
            json=json.loads(message.to_json()),
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=self.config.timeout if self.config else 30),
        ) as resp:
            data = await resp.json()
            return MCPMessage.from_json(json.dumps(data))

    async def _load_tools(self) -> None:
        response = await self._send_request(MCPProtocol.tools_list())
        if response.result and "tools" in response.result:
            for tool_data in response.result["tools"]:
                tool = MCPTool(
                    name=tool_data["name"],
                    description=tool_data.get("description", ""),
                    input_schema=tool_data.get("inputSchema", {}),
                )
                self._tools[tool.name] = tool
        logger.info(f"Loaded {len(self._tools)} tools from MCP server")

    def get_tools(self) -> list[MCPTool]:
        return list(self._tools.values())

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        if not self._initialized:
            return ToolResult(success=False, output="", error="Not connected to MCP server")
        try:
            response = await self._send_request(MCPProtocol.tools_call(name, arguments))
            if response.error:
                return ToolResult(success=False, output="", error=str(response.error))
            result = response.result
            if result and "content" in result:
                text_content = ""
                for item in result["content"]:
                    if item.get("type") == "text":
                        text_content += item.get("text", "")
                is_error = result.get("isError", False)
                return ToolResult(
                    success=not is_error,
                    output=text_content,
                    error=None if not is_error else text_content,
                )
            return ToolResult(success=True, output=str(result), error=None)
        except Exception as e:
            logger.error(f"Tool call error: {name}: {e}")
            return ToolResult(success=False, output="", error=str(e))

    def create_tool_wrapper(self, name: str) -> Callable:
        async def wrapper(**kwargs) -> str:
            result = await self.call_tool(name, kwargs)
            if result.success:
                return result.output
            else:
                raise RuntimeError(result.error or "Unknown error")

        return wrapper

    def to_taiji_agent_tools(self) -> list[Tool]:
        tools = []
        for mcp_tool in self._tools.values():
            tool = Tool(
                name=mcp_tool.name,
                description=mcp_tool.description,
                func=self.create_tool_wrapper(mcp_tool.name),
                parameters=mcp_tool.input_schema,
            )
            tools.append(tool)
        return tools
