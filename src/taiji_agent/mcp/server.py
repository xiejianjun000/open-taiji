"""
MCP Server Adapter - 将Taiji Agent Agent发布为MCP Server
参考Dify v1.6.0双向MCP集成设计
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional

from aiohttp import web

from .protocol import (
    MCPMessage,
    MCPProtocol,
    MCPProtocolVersion,
    MCPResource,
    MCPTool,
)

logger = logging.getLogger(__name__)


@dataclass
class MCPServerConfig:
    host: str = "0.0.0.0"
    port: int = 8080
    server_name: str = "taiji_agent"
    server_version: str = "2.0.0"
    protocol_version: str = MCPProtocolVersion.LATEST.value
    enable_cors: bool = True
    auth_token: Optional[str] = None


class MCPServerAdapter:
    def __init__(
        self,
        agent: Any,
        config: Optional[MCPServerConfig] = None,
    ):
        self.agent = agent
        self.config = config or MCPServerConfig()
        self._tools: dict[str, MCPTool] = {}
        self._resources: dict[str, MCPResource] = {}
        self._app: web.Optional[Application] = None
        self._runner: web.Optional[AppRunner] = None
        self._initialized = False

    def register_tool(self, tool: MCPTool) -> None:
        self._tools[tool.name] = tool
        logger.info(f"Registered MCP tool: {tool.name}")

    def register_tool_from_function(
        self,
        name: str,
        description: str,
        func: Callable,
        input_schema: Optional[dict[str, Any]] = None,
    ) -> None:
        if input_schema is None:
            input_schema = self._generate_schema_from_function(func)
        tool = MCPTool(
            name=name,
            description=description,
            input_schema=input_schema,
            handler=func,
        )
        self.register_tool(tool)

    def register_agent_as_tool(self) -> None:
        self.register_tool_from_function(
            name="taiji_agent_run",
            description="Run Taiji Agent agent task",
            func=self._agent_execute_handler,
            input_schema={
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "Task description for the agent",
                    },
                    "system_message": {
                        "type": "string",
                        "description": "Optional system message",
                    },
                },
                "required": ["task"],
            },
        )

    def register_resource(self, resource: MCPResource) -> None:
        self._resources[resource.uri] = resource
        logger.info(f"Registered MCP resource: {resource.uri}")

    def _generate_schema_from_function(self, func: Callable) -> dict[str, Any]:
        import inspect

        sig = inspect.signature(func)
        properties = {}
        required = []
        for param_name, param in sig.parameters.items():
            param_type = "string"
            if param.annotation is int:
                param_type = "integer"
            elif param.annotation is float:
                param_type = "number"
            elif param.annotation is bool:
                param_type = "boolean"
            elif param.annotation is list:
                param_type = "array"
            elif param.annotation is dict:
                param_type = "object"
            properties[param_name] = {"type": param_type}
            if param.default is inspect.Parameter.empty:
                required.append(param_name)
        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }

    async def _agent_execute_handler(self, **kwargs) -> str:
        task = kwargs.get("task", "")
        system_message = kwargs.get("system_message")
        try:
            result = await self.agent.run(task, system_message)
            return result.final_output if hasattr(result, "final_output") else str(result)
        except Exception as e:
            logger.error(f"Agent execution error: {e}")
            return f"Error: {str(e)}"

    async def _handle_initialize(self, message: MCPMessage) -> MCPMessage:
        server_info = MCPProtocol.initialize_response(
            server_name=self.config.server_name,
            server_version=self.config.server_version,
            protocol_version=self.config.protocol_version,
        )
        return MCPMessage(id=message.id, result=server_info)

    async def _handle_tools_list(self, message: MCPMessage) -> MCPMessage:
        tools = [tool.to_mcp_dict() for tool in self._tools.values()]
        return MCPMessage(
            id=message.id,
            result={"tools": tools},
        )

    async def _handle_tools_call(self, message: MCPMessage) -> MCPMessage:
        params = message.params or {}
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        if tool_name not in self._tools:
            return MCPProtocol.create_error_response(
                code=-32602,
                message=f"Tool not found: {tool_name}",
                request_id=message.id,
            )
        tool = self._tools[tool_name]
        try:
            if tool.handler:
                if asyncio.iscoroutinefunction(tool.handler):
                    result = await tool.handler(**arguments)
                else:
                    result = tool.handler(**arguments)
            else:
                result = f"Tool {tool_name} has no handler"
            content = [{"type": "text", "text": str(result)}]
            return MCPMessage(
                id=message.id,
                result={"content": content, "isError": False},
            )
        except Exception as e:
            logger.error(f"Tool call error: {e}")
            return MCPMessage(
                id=message.id,
                result={
                    "content": [{"type": "text", "text": f"Error: {str(e)}"}],
                    "isError": True,
                },
            )

    async def _handle_resources_list(self, message: MCPMessage) -> MCPMessage:
        resources = [res.to_mcp_dict() for res in self._resources.values()]
        return MCPMessage(
            id=message.id,
            result={"resources": resources},
        )

    async def _handle_ping(self, message: MCPMessage) -> MCPMessage:
        return MCPMessage(id=message.id, result={})

    async def _handle_shutdown(self, message: MCPMessage) -> MCPMessage:
        self._initialized = False
        return MCPMessage(id=message.id, result=None)

    async def _process_message(self, message: MCPMessage) -> MCPMessage:
        method_handlers = {
            "initialize": self._handle_initialize,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "resources/list": self._handle_resources_list,
            "ping": self._handle_ping,
            "shutdown": self._handle_shutdown,
        }
        handler = method_handlers.get(message.method)
        if handler:
            return await handler(message)
        return MCPProtocol.create_error_response(
            code=-32601,
            message=f"Method not found: {message.method}",
            request_id=message.id,
        )

    async def _handle_sse(self, request: web.Request) -> web.StreamResponse:
        if self._initialized:
            return web.Response(status=400, text="Already initialized")
        try:
            body = await request.text()
            message = MCPMessage.from_json(body)
            response = await self._process_message(message)
            if message.method == "initialize":
                self._initialized = True
            return web.json_response(json.loads(response.to_json()))
        except Exception as e:
            logger.error(f"SSE handler error: {e}")
            return web.json_response(
                {"jsonrpc": "2.0", "error": {"code": -32603, "message": str(e)}},
                status=500,
            )

    async def _handle_message(self, request: web.Request) -> web.StreamResponse:
        try:
            body = await request.text()
            message = MCPMessage.from_json(body)
            response = await self._process_message(message)
            return web.json_response(json.loads(response.to_json()))
        except Exception as e:
            logger.error(f"Message handler error: {e}")
            return web.json_response(
                {"jsonrpc": "2.0", "error": {"code": -32603, "message": str(e)}},
                status=500,
            )

    async def start(self) -> str:
        self._app = web.Application()
        if self.config.enable_cors:
            self._app.router.add_post("/message", self._handle_message)
            self._app.router.add_post("/sse", self._handle_sse)
        else:
            self._app.router.add_post("/message", self._handle_message)
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.config.host, self.config.port)
        await site.start()
        url = f"http://{self.config.host}:{self.config.port}"
        logger.info(f"MCP Server started at {url}")
        return url

    async def stop(self) -> None:
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
            self._app = None
            logger.info("MCP Server stopped")

    @property
    def server_url(self) -> str:
        return f"http://{self.config.host}:{self.config.port}"
