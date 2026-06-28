"""
gRPC 桥接模块 - 消息序列化

提供 Protobuf 消息与 Python 对象之间的互转，
实现类型安全的序列化/反序列化。
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from google.protobuf import json_format, struct_pb2, timestamp_pb2

logger = logging.getLogger(__name__)


# ============================================================
# 序列化器基类
# ============================================================

class Serializer:
    """
    消息序列化基类
    
    提供 Protobuf 消息与字典之间的转换功能。
    """
    
    @staticmethod
    def proto_to_dict(message: Any) -> Dict[str, Any]:
        """
        Protobuf 消息转字典
        
        Args:
            message: Protobuf 消息对象
            
        Returns:
            Python 字典
        """
        if message is None:
            return {}
        
        try:
            # 使用 protobuf 内置的 json 转换
            return json_format.MessageToDict(
                message,
                preserving_proto_field_name=True,
                use_integers_for_enums=True,
            )
        except Exception as e:
            logger.error(f"Failed to convert proto to dict: {e}")
            return {}
    
    @staticmethod
    def dict_to_proto(data: Dict[str, Any], message_class: type) -> Any:
        """
        字典转 Protobuf 消息
        
        Args:
            data: Python 字典
            message_class: Protobuf 消息类
            
        Returns:
            Protobuf 消息对象
        """
        if data is None:
            data = {}
        
        try:
            message = message_class()
            # 使用 protobuf 内置的 json 解析
            json_format.ParseDict(data, message)
            return message
        except Exception as e:
            logger.error(f"Failed to convert dict to proto: {e}")
            raise
    
    @staticmethod
    def proto_to_json(message: Any) -> str:
        """
        Protobuf 消息转 JSON 字符串
        
        Args:
            message: Protobuf 消息对象
            
        Returns:
            JSON 字符串
        """
        if message is None:
            return "{}"
        
        try:
            return json_format.MessageToJson(message)
        except Exception as e:
            logger.error(f"Failed to convert proto to json: {e}")
            return "{}"
    
    @staticmethod
    def json_to_proto(json_str: str, message_class: type) -> Any:
        """
        JSON 字符串转 Protobuf 消息
        
        Args:
            json_str: JSON 字符串
            message_class: Protobuf 消息类
            
        Returns:
            Protobuf 消息对象
        """
        if not json_str:
            return message_class()
        
        try:
            message = message_class()
            json_format.Parse(json_str, message)
            return message
        except Exception as e:
            logger.error(f"Failed to convert json to proto: {e}")
            raise


# ============================================================
# 消息转换器
# ============================================================

class MessageConverter:
    """
    消息转换器
    
    专门处理对话消息的转换。
    """
    
    @staticmethod
    def dict_to_message(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        转换消息字典（兼容格式）
        
        将各种格式的消息转换为 gRPC 服务需要的格式。
        
        Args:
            data: 消息字典
            
        Returns:
            标准化后的消息字典
        """
        if not data:
            return {}
        
        result = {
            "role": data.get("role", "user"),
            "content": data.get("content", ""),
        }
        
        # 处理可选字段
        if "name" in data:
            result["name"] = data["name"]
        if "tool_call_id" in data:
            result["tool_call_id"] = data["tool_call_id"]
        
        # 处理工具调用
        if "tool_calls" in data:
            result["tool_calls"] = [
                MessageConverter.dict_to_tool_call(tc)
                for tc in data["tool_calls"]
            ]
        
        return result
    
    @staticmethod
    def dict_to_tool_call(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        转换工具调用字典
        
        Args:
            data: 工具调用字典
            
        Returns:
            标准化后的工具调用字典
        """
        if not data:
            return {}
        
        result = {
            "id": data.get("id", ""),
            "name": data.get("name", ""),
        }
        
        # 处理参数
        if "args" in data:
            args = data["args"]
            if isinstance(args, dict):
                result["args"] = args
            elif isinstance(args, str):
                try:
                    result["args"] = json.loads(args)
                except json.JSONDecodeError:
                    result["args"] = {"raw": args}
            else:
                result["args"] = {}
        
        return result
    
    @staticmethod
    def message_to_dict(message: Any) -> Dict[str, Any]:
        """
        Protobuf Message 转字典
        
        Args:
            message: Protobuf Message 对象
            
        Returns:
            Python 字典
        """
        result = {
            "role": message.role,
            "content": message.content,
        }
        
        if message.HasField("name"):
            result["name"] = message.name
        if message.HasField("tool_call_id"):
            result["tool_call_id"] = message.tool_call_id
        if message.tool_calls:
            result["tool_calls"] = [
                MessageConverter.tool_call_to_dict(tc)
                for tc in message.tool_calls
            ]
        
        return result
    
    @staticmethod
    def tool_call_to_dict(tool_call: Any) -> Dict[str, Any]:
        """
        Protobuf ToolCall 转字典
        
        Args:
            tool_call: Protobuf ToolCall 对象
            
        Returns:
            Python 字典
        """
        result = {
            "id": tool_call.id,
            "name": tool_call.name,
        }
        
        if tool_call.args and tool_call.args.fields:
            result["args"] = dict(tool_call.args.fields)
        
        return result


class ToolDefinitionConverter:
    """
    工具定义转换器
    """
    
    @staticmethod
    def dict_to_struct(data: Dict[str, Any]) -> struct_pb2.Struct:
        """
        字典转 Protobuf Struct
        
        Args:
            data: Python 字典
            
        Returns:
            Protobuf Struct
        """
        if not data:
            return struct_pb2.Struct()
        
        result = struct_pb2.Struct()
        for key, value in data.items():
            result[key] = ToolDefinitionConverter._convert_value(value)
        
        return result
    
    @staticmethod
    def _convert_value(value: Any) -> Any:
        """转换单个值到 Protobuf 支持的格式"""
        if isinstance(value, dict):
            return ToolDefinitionConverter.dict_to_struct(value)
        elif isinstance(value, list):
            result = []
            for item in value:
                result.append(ToolDefinitionConverter._convert_value(item))
            return result
        elif isinstance(value, str):
            return value
        elif isinstance(value, bool):
            return value
        elif isinstance(value, (int, float)):
            return value
        else:
            return str(value)
    
    @staticmethod
    def struct_to_dict(struct: struct_pb2.Struct) -> Dict[str, Any]:
        """
        Protobuf Struct 转字典
        
        Args:
            struct: Protobuf Struct
            
        Returns:
            Python 字典
        """
        if not struct or not struct.fields:
            return {}
        
        result = {}
        for key, value in struct.fields.items():
            result[key] = ToolDefinitionConverter._unwrap_value(value)
        
        return result
    
    @staticmethod
    def _unwrap_value(value: Any) -> Any:
        """展开 Protobuf Value"""
        which = value.WhichOneof("kind")
        
        if which is None:
            return None
        elif which == "string_value":
            return value.string_value
        elif which == "number_value":
            return value.number_value
        elif which == "bool_value":
            return value.bool_value
        elif which == "struct_value":
            return ToolDefinitionConverter.struct_to_dict(value.struct_value)
        elif which == "list_value":
            return [
                ToolDefinitionConverter._unwrap_value(item)
                for item in value.list_value.values
            ]
        else:
            return None


class TokenUsageConverter:
    """
    Token 用量转换器
    """
    
    @staticmethod
    def dict_to_usage(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        转换 Token 用量字典
        
        标准化 Token 用量格式。
        
        Args:
            data: Token 用量字典
            
        Returns:
            标准化后的字典
        """
        if not data:
            return {
                "input_tokens": 0,
                "output_tokens": 0,
            }
        
        return {
            "input_tokens": data.get("input_tokens", 0),
            "output_tokens": data.get("output_tokens", 0),
            "total_tokens": data.get("total_tokens", data.get("input_tokens", 0) + data.get("output_tokens", 0)),
            "cached_input_tokens": data.get("cached_input_tokens", 0),
        }


class TimestampConverter:
    """
    时间戳转换器
    """
    
    @staticmethod
    def datetime_to_proto(dt: datetime) -> timestamp_pb2.Timestamp:
        """
        datetime 转 Protobuf Timestamp
        
        Args:
            dt: datetime 对象
            
        Returns:
            Protobuf Timestamp
        """
        result = timestamp_pb2.Timestamp()
        result.FromDatetime(dt)
        return result
    
    @staticmethod
    def proto_to_datetime(ts: timestamp_pb2.Timestamp) -> datetime:
        """
        Protobuf Timestamp 转 datetime
        
        Args:
            ts: Protobuf Timestamp
            
        Returns:
            datetime 对象
        """
        return ts.ToDatetime()
    
    @staticmethod
    def now_proto() -> timestamp_pb2.Timestamp:
        """
        获取当前时间的 Protobuf Timestamp
        
        Returns:
            当前时间的 Protobuf Timestamp
        """
        result = timestamp_pb2.Timestamp()
        result.GetCurrentTime()
        return result
    
    @staticmethod
    def from_unix_timestamp(timestamp: float) -> timestamp_pb2.Timestamp:
        """
        Unix 时间戳转 Protobuf Timestamp
        
        Args:
            timestamp: Unix 时间戳（秒）
            
        Returns:
            Protobuf Timestamp
        """
        result = timestamp_pb2.Timestamp()
        result.FromUnixSeconds(int(timestamp))
        return result


class EnumConverter:
    """
    枚举转换器
    """
    
    # Protobuf 枚举值到字符串的映射
    FINISH_REASON_MAP = {
        0: "UNSPECIFIED",
        1: "STOP",
        2: "LENGTH",
        3: "TOOL_CALLS",
        4: "ERROR",
        5: "CANCELLED",
        6: "CONTENT_FILTERED",
        7: "RECURSION_LIMIT",
    }
    
    AGENT_STATUS_MAP = {
        0: "UNSPECIFIED",
        1: "IDLE",
        2: "RUNNING",
        3: "PAUSED",
        4: "WAITING_FEEDBACK",
        5: "ERROR",
        6: "DONE",
    }
    
    MEMORY_TYPE_MAP = {
        0: "UNSPECIFIED",
        1: "SESSION",
        2: "EPISODIC",
        3: "SEMANTIC",
        4: "PROCEDURAL",
    }
    
    TOOL_TYPE_MAP = {
        0: "UNSPECIFIED",
        1: "FUNCTION",
        2: "CODE_INTERPRETER",
        3: "FILE_SEARCH",
        4: "COMPUTER_USE",
        5: "WEB_SEARCH",
        6: "BROWSER",
    }
    
    @staticmethod
    def finish_reason_to_string(value: int) -> str:
        """完成原因枚举转字符串"""
        return EnumConverter.FINISH_REASON_MAP.get(value, "UNKNOWN")
    
    @staticmethod
    def agent_status_to_string(value: int) -> str:
        """Agent 状态枚举转字符串"""
        return EnumConverter.AGENT_STATUS_MAP.get(value, "UNKNOWN")
    
    @staticmethod
    def memory_type_to_string(value: int) -> str:
        """记忆类型枚举转字符串"""
        return EnumConverter.MEMORY_TYPE_MAP.get(value, "UNKNOWN")
    
    @staticmethod
    def tool_type_to_string(value: int) -> str:
        """工具类型枚举转字符串"""
        return EnumConverter.TOOL_TYPE_MAP.get(value, "UNKNOWN")


# ============================================================
# 验证器
# ============================================================

class MessageValidator:
    """
    消息验证器
    
    验证 Protobuf 消息和字典的有效性。
    """
    
    @staticmethod
    def validate_chat_request(data: Dict[str, Any]) -> List[str]:
        """
        验证 Chat 请求
        
        Args:
            data: Chat 请求字典
            
        Returns:
            验证错误列表（空表示验证通过）
        """
        errors = []
        
        # 检查必填字段
        if "messages" not in data:
            errors.append("messages is required")
        elif not isinstance(data["messages"], list):
            errors.append("messages must be a list")
        elif len(data["messages"]) == 0:
            errors.append("messages cannot be empty")
        else:
            # 验证每条消息
            for i, msg in enumerate(data["messages"]):
                if not isinstance(msg, dict):
                    errors.append(f"messages[{i}] must be an object")
                    continue
                
                if "role" not in msg:
                    errors.append(f"messages[{i}].role is required")
                elif msg["role"] not in ["system", "user", "assistant", "tool"]:
                    errors.append(f"messages[{i}].role must be one of: system, user, assistant, tool")
                
                if "content" not in msg:
                    errors.append(f"messages[{i}].content is required")
        
        # 验证可选字段
        if "temperature" in data:
            temp = data["temperature"]
            if not isinstance(temp, (int, float)):
                errors.append("temperature must be a number")
            elif temp < 0 or temp > 2:
                errors.append("temperature must be between 0 and 2")
        
        if "max_tokens" in data:
            max_tokens = data["max_tokens"]
            if not isinstance(max_tokens, int) or max_tokens <= 0:
                errors.append("max_tokens must be a positive integer")
        
        return errors
    
    @staticmethod
    def validate_message(data: Dict[str, Any]) -> List[str]:
        """
        验证消息
        
        Args:
            data: 消息字典
            
        Returns:
            验证错误列表
        """
        errors = []
        
        required_fields = ["role", "content"]
        for field in required_fields:
            if field not in data:
                errors.append(f"{field} is required")
        
        if "role" in data:
            if data["role"] not in ["system", "user", "assistant", "tool"]:
                errors.append("role must be one of: system, user, assistant, tool")
        
        if "tool_calls" in data:
            if not isinstance(data["tool_calls"], list):
                errors.append("tool_calls must be a list")
            else:
                for i, tc in enumerate(data["tool_calls"]):
                    if not isinstance(tc, dict):
                        errors.append(f"tool_calls[{i}] must be an object")
                    elif "id" not in tc:
                        errors.append(f"tool_calls[{i}].id is required")
                    elif "name" not in tc:
                        errors.append(f"tool_calls[{i}].name is required")
        
        return errors


# ============================================================
# 便捷函数
# ============================================================

def serialize_message(message: Any) -> str:
    """
    序列化消息为 JSON 字符串
    
    Args:
        message: Protobuf 消息对象
        
    Returns:
        JSON 字符串
    """
    return Serializer.proto_to_json(message)


def deserialize_message(json_str: str, message_class: type) -> Any:
    """
    从 JSON 字符串反序列化消息
    
    Args:
        json_str: JSON 字符串
        message_class: 消息类
        
    Returns:
        Protobuf 消息对象
    """
    return Serializer.json_to_proto(json_str, message_class)


def convert_chat_request(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    转换 Chat 请求格式
    
    Args:
        data: 原始请求字典
        
    Returns:
        标准化后的请求字典
    """
    result = {
        "messages": [
            MessageConverter.dict_to_message(m)
            for m in data.get("messages", [])
        ],
    }
    
    # 可选字段
    if "model" in data:
        result["model"] = data["model"]
    if "temperature" in data:
        result["temperature"] = data["temperature"]
    if "max_tokens" in data:
        result["max_tokens"] = data["max_tokens"]
    if "session_id" in data:
        result["session_id"] = data["session_id"]
    if "metadata" in data:
        result["metadata"] = data["metadata"]
    if "tools" in data:
        result["tools"] = data["tools"]
    
    return result


def format_token_usage(usage: Dict[str, Any]) -> str:
    """
    格式化 Token 用量显示
    
    Args:
        usage: Token 用量字典
        
    Returns:
        格式化字符串
    """
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    total = usage.get("total_tokens", input_tokens + output_tokens)
    
    return f"Tokens: {input_tokens} in / {output_tokens} out / {total} total"
