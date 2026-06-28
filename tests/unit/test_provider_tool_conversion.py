"""
Providers 工具转换测试
测试 OpenAI 格式工具定义与 Anthropic 格式的相互转换
"""
import pytest
from taiji_agent.providers.anthropic import AnthropicProvider


class TestAnthropicToolConversion:
    """Anthropic 工具格式转换测试"""

    def test_convert_single_openai_function(self):
        """转换单个 OpenAI 格式函数定义（不含 type 包装）"""
        openai_function = {
            "name": "file_read",
            "description": "Read a file from the filesystem",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file"},
                },
                "required": ["path"]
            }
        }
        converted = AnthropicProvider._convert_tools([openai_function])
        assert len(converted) == 1
        assert converted[0]["name"] == "file_read"
        assert "input_schema" in converted[0]

    def test_convert_multiple_openai_functions(self):
        """转换多个 OpenAI 格式函数定义"""
        functions = [
            {
                "name": "file_read",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "file_write",
                "parameters": {"type": "object", "properties": {}}
            }
        ]
        converted = AnthropicProvider._convert_tools(functions)
        assert len(converted) == 2
        assert {t["name"] for t in converted} == {"file_read", "file_write"}

    def test_convert_preserves_description(self):
        """转换保留描述"""
        function = {
            "name": "test",
            "description": "Test description",
            "parameters": {"type": "object", "properties": {}}
        }
        converted = AnthropicProvider._convert_tools([function])
        assert converted[0]["description"] == "Test description"

    def test_convert_already_anthropic_format(self):
        """已经是 Anthropic 格式的工具不需要转换"""
        anthropic_tool = {
            "name": "test",
            "input_schema": {"type": "object", "properties": {}}
        }
        converted = AnthropicProvider._convert_tools([anthropic_tool])
        assert len(converted) == 1
        assert converted[0]["name"] == "test"
        assert "input_schema" in converted[0]
