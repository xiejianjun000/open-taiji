"""
MCP Protocol Core - 协议核心定义
参考 modelcontextprotocol.io 规范
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
class StrEnum(str, Enum):
    pass
from typing import Any, Optional


class MCPProtocolVersion(StrEnum):
    LATEST = "2025-03-26"
    V1 = "2024-11-05"


@dataclass
class MCPTool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Optional[Callable] = None

    def to_mcp_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


@dataclass
class MCPResource:
    uri: str
    name: str
    description: str
    mime_type: str = "text/plain"

    def to_mcp_dict(self) -> dict[str, Any]:
        return {
            "uri": self.uri,
            "name": self.name,
            "description": self.description,
            "mimeType": self.mime_type,
        }


@dataclass
class MCPPrompt:
    name: str
    description: str
    arguments: list[dict[str, str]] = field(default_factory=list)

    def to_mcp_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "arguments": self.arguments,
        }


@dataclass
class MCPMessage:
    jsonrpc: str = "2.0"
    method: str = ""
    params: Optional[dict[str, Any]] = None
    id: Optional[Any] = None
    result: Optional[Any] = None
    error: Optional[dict[str, Any]] = None

    def to_json(self) -> str:
        data: dict[str, Any] = {"jsonrpc": self.jsonrpc}
        if self.id is not None:
            data["id"] = self.id
        if self.method:
            data["method"] = self.method
        if self.params:
            data["params"] = self.params
        if self.result is not None:
            data["result"] = self.result
        if self.error:
            data["error"] = self.error
        return json.dumps(data)

    @classmethod
    def from_json(cls, data: str) -> "MCPMessage":
        obj = json.loads(data)
        return cls(
            jsonrpc=obj.get("jsonrpc", "2.0"),
            id=obj.get("id"),
            method=obj.get("method", ""),
            params=obj.get("params"),
            result=obj.get("result"),
            error=obj.get("error"),
        )


class MCPProtocol:
    PROTOCOL_NAME = "idx.jsonrpc"
    CAPABILITIES = {
        "tools": {"listChanged": True},
        "resources": {"subscribe": True, "listChanged": True},
        "prompts": {"listChanged": True},
    }

    @staticmethod
    def initialize_request(
        client_name: str,
        client_version: str,
        protocol_version: str = MCPProtocolVersion.LATEST.value,
    ) -> MCPMessage:
        return MCPMessage(
            method="initialize",
            params={
                "protocolVersion": protocol_version,
                "capabilities": MCPProtocol.CAPABILITIES,
                "clientInfo": {
                    "name": client_name,
                    "version": client_version,
                },
            },
        )

    @staticmethod
    def initialize_response(
        server_name: str,
        server_version: str,
        protocol_version: str = MCPProtocolVersion.LATEST.value,
    ) -> dict[str, Any]:
        return {
            "protocolVersion": protocol_version,
            "capabilities": MCPProtocol.CAPABILITIES,
            "serverInfo": {
                "name": server_name,
                "version": server_version,
            },
        }

    @staticmethod
    def tools_list_changed_notification() -> MCPMessage:
        return MCPMessage(method="notifications/tools/list_changed")

    @staticmethod
    def tools_list() -> MCPMessage:
        return MCPMessage(method="tools/list")

    @staticmethod
    def tools_call(
        name: str,
        arguments: dict[str, Any],
        request_id: Any = None,
    ) -> MCPMessage:
        return MCPMessage(
            method="tools/call",
            params={"name": name, "arguments": arguments},
            id=request_id,
        )

    @staticmethod
    def resources_list() -> MCPMessage:
        return MCPMessage(method="resources/list")

    @staticmethod
    def resources_read(uri: str) -> MCPMessage:
        return MCPMessage(
            method="resources/read",
            params={"uri": uri},
        )

    @staticmethod
    def ping() -> MCPMessage:
        return MCPMessage(method="ping")

    @staticmethod
    def shutdown() -> MCPMessage:
        return MCPMessage(method="shutdown")

    @staticmethod
    def is_error_response(message: MCPMessage) -> bool:
        return message.error is not None

    @staticmethod
    def create_error_response(
        code: int,
        message: str,
        request_id: Any = None,
    ) -> MCPMessage:
        return MCPMessage(
            jsonrpc="2.0",
            id=request_id,
            error={"code": code, "message": message},
        )
