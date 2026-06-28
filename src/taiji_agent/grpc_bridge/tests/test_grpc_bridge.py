"""
gRPC 桥接模块测试

使用 grpcio-testing 进行服务端测试和客户端连接测试。
"""

import asyncio
import logging
import time
import unittest
from typing import Any, AsyncIterator, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 测试配置
TEST_ADDRESS = "localhost:50051"
TEST_TIMEOUT = 10.0

logger = logging.getLogger(__name__)


# ============================================================
# 测试辅助函数
# ============================================================

async def create_test_server(port: int = 50051):
    """
    创建测试用 gRPC 服务端
    
    Args:
        port: 端口号
        
    Returns:
        测试服务端实例
    """
    import grpc
    from taiji_agent.grpc_bridge.server import (
        HermesProviderServicer,
        HermesMemoryServicer,
        HermesSkillsServicer,
        HermesAgentServicer,
        TaijiVerifyServicer,
        GrpcServerConfig,
    )
    
    config = GrpcServerConfig(host="0.0.0.0", port=port)
    
    # 创建服务实现
    provider_servicer = HermesProviderServicer()
    memory_servicer = HermesMemoryServicer()
    skills_servicer = HermesSkillsServicer()
    agent_servicer = HermesAgentServicer()
    verify_servicer = TaijiVerifyServicer()
    
    # 创建服务端
    server = grpc.aio.server()
    server.add_insecure_port(f"{config.host}:{config.port}")
    
    # 注册服务（实际测试中需要取消注释）
    # provider_pb2_grpc.add_HermesProviderServicer_to_server(provider_servicer, server)
    # memory_pb2_grpc.add_HermesMemoryServicer_to_server(memory_servicer, server)
    # skills_pb2_grpc.add_HermesSkillsServicer_to_server(skills_servicer, server)
    # agent_pb2_grpc.add_HermesAgentServicer_to_server(agent_servicer, server)
    # taiji_verify_pb2_grpc.add_TaijiVerifyServicer_to_server(verify_servicer, server)
    
    await server.start()
    
    return server


async def create_test_client(address: str = TEST_ADDRESS):
    """
    创建测试用 gRPC 客户端
    
    Args:
        address: 服务地址
        
    Returns:
        测试客户端实例
    """
    import grpc
    from taiji_agent.grpc_bridge.client import HermesProviderClient, ClientConfig
    
    config = ClientConfig(address=address)
    client = HermesProviderClient(config)
    
    # 模拟通道（不真正连接）
    client._channel = MagicMock()
    client._channel.is_active = MagicMock(return_value=True)
    
    return client


# ============================================================
# 服务端测试
# ============================================================

class TestHermesProviderServicer:
    """HermesProvider 服务测试"""
    
    @pytest.fixture
    def servicer(self):
        """创建服务实例"""
        from taiji_agent.grpc_bridge.server import HermesProviderServicer
        return HermesProviderServicer(default_model="test-model")
    
    @pytest.mark.asyncio
    async def test_chat_with_mock_llm(self, servicer):
        """测试 Chat 方法（使用模拟 LLM）"""
        # 模拟请求
        class MockRequest:
            messages = [
                MagicMock(role="user", content="Hello"),
            ]
            model = ""
            session_id = ""
            metadata = {}
            temperature = None
            max_tokens = None
            tools = []
            
            def HasField(self, name):
                return False
        
        # 模拟上下文
        context = MagicMock()
        context.is_active = MagicMock(return_value=True)
        context.set_code = MagicMock()
        context.set_details = MagicMock()
        
        # 执行
        response = await servicer.Chat(MockRequest(), context)
        
        # 验证
        assert response is not None
        assert "content" in response
    
    @pytest.mark.asyncio
    async def test_stream_chat(self, servicer):
        """测试流式 Chat"""
        # 模拟请求
        class MockRequest:
            messages = [
                MagicMock(role="user", content="Hello world"),
            ]
            model = ""
            session_id = ""
            metadata = {}
            temperature = None
            max_tokens = None
            tools = []
            
            def HasField(self, name):
                return False
        
        # 模拟上下文
        context = MagicMock()
        context.is_active = MagicMock(return_value=True)
        context.set_code = MagicMock()
        context.set_details = MagicMock()
        
        # 收集流式响应
        chunks = []
        async for chunk in servicer.StreamChat(MockRequest(), context):
            chunks.append(chunk)
        
        # 验证
        assert len(chunks) > 0
    
    @pytest.mark.asyncio
    async def test_get_models(self, servicer):
        """测试获取模型列表"""
        # 模拟请求
        from google.protobuf import empty_pb2
        request = empty_pb2.Empty()
        
        # 模拟上下文
        context = MagicMock()
        
        # 执行
        response = await servicer.GetModels(request, context)
        
        # 验证
        assert response is not None
        assert "models" in response
        assert len(response["models"]) > 0


class TestHermesMemoryServicer:
    """HermesMemory 服务测试"""
    
    @pytest.fixture
    def servicer(self):
        """创建服务实例"""
        from taiji_agent.grpc_bridge.server import HermesMemoryServicer
        return HermesMemoryServicer()
    
    @pytest.mark.asyncio
    async def test_save_memory(self, servicer):
        """测试保存记忆"""
        # 模拟请求
        class MockRequest:
            content = "Test memory content"
            type = 1  # SESSION
            metadata = {}
            
            def HasField(self, name):
                return name in ["session_id", "tenant_id"]
        
        # 模拟上下文
        context = MagicMock()
        
        # 执行
        response = await servicer.Save(MockRequest(), context)
        
        # 验证
        assert response is not None
        assert "memory_id" in response
        assert response["deduplicated"] == False
    
    @pytest.mark.asyncio
    async def test_search_memory(self, servicer):
        """测试搜索记忆"""
        # 先保存一条记忆
        class MockSaveRequest:
            content = "Searchable content"
            type = 1
            metadata = {}
            
            def HasField(self, name):
                return False
        
        context = MagicMock()
        save_response = await servicer.Save(MockSaveRequest(), context)
        
        # 搜索
        class MockSearchRequest:
            query = "Searchable"
            limit = 10
            min_score = 0.0
            
            def HasField(self, name):
                return name in ["type", "session_id", "tenant_id", "backend"]
        
        search_response = await servicer.Search(MockSearchRequest(), context)
        
        # 验证
        assert search_response is not None
        assert "results" in search_response
    
    @pytest.mark.asyncio
    async def test_delete_memory(self, servicer):
        """测试删除记忆"""
        # 先保存一条记忆
        class MockSaveRequest:
            content = "To be deleted"
            type = 1
            metadata = {}
            
            def HasField(self, name):
                return False
        
        context = MagicMock()
        save_response = await servicer.Save(MockSaveRequest(), context)
        memory_id = save_response["memory_id"]
        
        # 删除
        class MockDeleteRequest:
            memory_id = memory_id
            
            def HasField(self, name):
                return name == "tenant_id"
        
        delete_response = await servicer.Delete(MockDeleteRequest(), context)
        
        # 验证
        assert delete_response is not None
        assert delete_response["success"] == True


class TestHermesSkillsServicer:
    """HermesSkills 服务测试"""
    
    @pytest.fixture
    def servicer(self):
        """创建服务实例"""
        from taiji_agent.grpc_bridge.server import HermesSkillsServicer
        return HermesSkillsServicer()
    
    @pytest.mark.asyncio
    async def test_create_skill(self, servicer):
        """测试创建技能"""
        # 模拟请求
        class MockRequest:
            name = "Test Skill"
            description = "A test skill"
            content = "# Test Skill Content"
            tags = ["test"]
            metadata = {}
            
            def HasField(self, name):
                return name == "category"
        
        # 模拟上下文
        context = MagicMock()
        
        # 执行
        response = await servicer.CreateSkill(MockRequest(), context)
        
        # 验证
        assert response is not None
        assert response["success"] == True
        assert "skill" in response
    
    @pytest.mark.asyncio
    async def test_list_skills(self, servicer):
        """测试列出技能"""
        # 先创建技能
        class MockCreateRequest:
            name = "List Test Skill"
            description = "For listing test"
            content = "# Content"
            tags = []
            metadata = {}
            
            def HasField(self, name):
                return False
        
        context = MagicMock()
        await servicer.CreateSkill(MockCreateRequest(), context)
        
        # 列出
        class MockListRequest:
            limit = 10
            offset = 0
            
            def HasField(self, name):
                return name in ["category", "search"]
        
        response = await servicer.ListSkills(MockListRequest(), context)
        
        # 验证
        assert response is not None
        assert "skills" in response
        assert len(response["skills"]) > 0
    
    @pytest.mark.asyncio
    async def test_execute_skill(self, servicer):
        """测试执行技能"""
        # 先创建技能
        class MockCreateRequest:
            name = "Execute Test Skill"
            description = "For execution test"
            content = "# Content"
            tags = []
            metadata = {}
            
            def HasField(self, name):
                return False
        
        context = MagicMock()
        create_response = await servicer.CreateSkill(MockCreateRequest(), context)
        skill_id = create_response["skill"]["id"]
        
        # 执行
        class MockExecuteRequest:
            skill_id = skill_id
            task = "Test task"
            parameters = {}
            
            def HasField(self, name):
                return name == "session_id"
        
        execute_response = await servicer.ExecuteSkill(MockExecuteRequest(), context)
        
        # 验证
        assert execute_response is not None
        assert execute_response["success"] == True


class TestHermesAgentServicer:
    """HermesAgent 服务测试"""
    
    @pytest.fixture
    def servicer(self):
        """创建服务实例"""
        from taiji_agent.grpc_bridge.server import HermesAgentServicer
        return HermesAgentServicer(max_iterations=10)
    
    @pytest.mark.asyncio
    async def test_run_task(self, servicer):
        """测试运行任务"""
        # 模拟请求
        class MockRequest:
            task = "Test task"
            max_iterations = 5
            session_id = ""
            
            def HasField(self, name):
                return name in ["system_prompt", "model", "temperature", "session_id", "tenant_id", "enable_hitl", "hitl_timeout_seconds"]
        
        # 模拟上下文
        context = MagicMock()
        
        # 执行
        response = await servicer.RunTask(MockRequest(), context)
        
        # 验证
        assert response is not None
        assert "result" in response
        assert response["success"] == True
    
    @pytest.mark.asyncio
    async def test_stream_task(self, servicer):
        """测试流式运行任务"""
        # 模拟请求
        class MockRequest:
            task = "Stream test task"
            max_iterations = 3
            session_id = ""
            
            def HasField(self, name):
                return False
        
        # 模拟上下文
        context = MagicMock()
        context.is_active = MagicMock(return_value=True)
        
        # 收集流式响应
        chunks = []
        async for chunk in servicer.StreamTask(MockRequest(), context):
            chunks.append(chunk)
        
        # 验证
        assert len(chunks) > 0
    
    @pytest.mark.asyncio
    async def test_cancel_task(self, servicer):
        """测试取消任务"""
        # 先运行一个任务
        class MockRunRequest:
            task = "Task to cancel"
            max_iterations = 10
            session_id = "cancel-test-session"
            
            def HasField(self, name):
                return False
        
        context = MagicMock()
        await servicer.RunTask(MockRunRequest(), context)
        
        # 取消
        class MockCancelRequest:
            session_id = "cancel-test-session"
            reason = "Test cancellation"
            
            def HasField(self, name):
                return name == "reason"
        
        cancel_response = await servicer.CancelTask(MockCancelRequest(), context)
        
        # 验证
        assert cancel_response is not None
        assert cancel_response["success"] == True


class TestTaijiVerifyServicer:
    """TaijiVerify 服务测试"""
    
    @pytest.fixture
    def servicer(self):
        """创建服务实例"""
        from taiji_agent.grpc_bridge.server import TaijiVerifyServicer
        return TaijiVerifyServicer()
    
    @pytest.mark.asyncio
    async def test_verify(self, servicer):
        """测试验证"""
        # 模拟请求
        class MockRequest:
            content = "Test content to verify"
            content_type = "text"
            context = {}
            
            def HasField(self, name):
                return name == "ruleset"
        
        # 模拟上下文
        context = MagicMock()
        
        # 执行
        response = await servicer.Verify(MockRequest(), context)
        
        # 验证
        assert response is not None
        assert "passed" in response
        assert "score" in response
    
    @pytest.mark.asyncio
    async def test_batch_verify(self, servicer):
        """测试批量验证"""
        # 模拟请求
        class MockItem:
            content = "Batch test content"
            content_type = "text"
            context = {}
            
            def HasField(self, name):
                return False
        
        class MockRequest:
            items = [MockItem(), MockItem()]
            stop_on_first_error = False
            
            def HasField(self, name):
                return False
        
        # 模拟上下文
        context = MagicMock()
        
        # 执行
        response = await servicer.BatchVerify(MockRequest(), context)
        
        # 验证
        assert response is not None
        assert "results" in response
        assert len(response["results"]) == 2
    
    @pytest.mark.asyncio
    async def test_get_rules(self, servicer):
        """测试获取规则"""
        from google.protobuf import empty_pb2
        request = empty_pb2.Empty()
        
        # 模拟上下文
        context = MagicMock()
        
        # 执行
        response = await servicer.GetRules(request, context)
        
        # 验证
        assert response is not None
        assert "rules" in response
        assert len(response["rules"]) > 0


# ============================================================
# 客户端测试
# ============================================================

class TestHermesProviderClient:
    """HermesProvider 客户端测试"""
    
    @pytest.mark.asyncio
    async def test_client_initialization(self):
        """测试客户端初始化"""
        from taiji_agent.grpc_bridge.client import HermesProviderClient, ClientConfig
        
        config = ClientConfig(address="localhost:50051")
        client = HermesProviderClient(config)
        
        assert client._config.address == "localhost:50051"
        assert client._channel is None  # 尚未初始化
    
    @pytest.mark.asyncio
    async def test_client_context_manager(self):
        """测试客户端上下文管理器"""
        from taiji_agent.grpc_bridge.client import HermesProviderClient, ClientConfig
        
        config = ClientConfig(address="localhost:50051")
        
        async with HermesProviderClient(config) as client:
            assert client is not None
    
    @pytest.mark.asyncio
    async def test_chat_request_format(self):
        """测试 Chat 请求格式"""
        from taiji_agent.grpc_bridge.serialization import convert_chat_request, MessageValidator
        
        request = {
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
            ],
            "model": "gpt-4",
            "temperature": 0.7,
        }
        
        # 验证请求
        errors = MessageValidator.validate_chat_request(request)
        assert len(errors) == 0
        
        # 转换格式
        converted = convert_chat_request(request)
        assert "messages" in converted
        assert len(converted["messages"]) == 2


# ============================================================
# 序列化测试
# ============================================================

class TestSerialization:
    """序列化测试"""
    
    def test_message_conversion(self):
        """测试消息转换"""
        from taiji_agent.grpc_bridge.serialization import MessageConverter
        
        # 测试字典转消息格式
        msg_dict = {
            "role": "user",
            "content": "Test message",
            "name": "test-user",
        }
        
        converted = MessageConverter.dict_to_message(msg_dict)
        
        assert converted["role"] == "user"
        assert converted["content"] == "Test message"
        assert converted["name"] == "test-user"
    
    def test_tool_call_conversion(self):
        """测试工具调用转换"""
        from taiji_agent.grpc_bridge.serialization import MessageConverter
        
        # 测试字典转工具调用
        tc_dict = {
            "id": "call_123",
            "name": "get_weather",
            "args": {"city": "Beijing"},
        }
        
        converted = MessageConverter.dict_to_tool_call(tc_dict)
        
        assert converted["id"] == "call_123"
        assert converted["name"] == "get_weather"
        assert converted["args"]["city"] == "Beijing"
    
    def test_struct_conversion(self):
        """测试 Struct 转换"""
        from taiji_agent.grpc_bridge.serialization import ToolDefinitionConverter
        from google.protobuf import struct_pb2
        
        # 字典转 Struct
        data = {
            "name": "test",
            "value": 123,
            "nested": {"key": "value"},
        }
        
        struct = ToolDefinitionConverter.dict_to_struct(data)
        
        assert struct["name"] == "test"
        assert struct["value"] == 123
        assert struct["nested"]["key"] == "value"
        
        # Struct 转字典
        result = ToolDefinitionConverter.struct_to_dict(struct)
        
        assert result["name"] == "test"
        assert result["value"] == 123
    
    def test_token_usage_format(self):
        """测试 Token 用量格式化"""
        from taiji_agent.grpc_bridge.serialization import format_token_usage
        
        usage = {
            "input_tokens": 100,
            "output_tokens": 50,
        }
        
        formatted = format_token_usage(usage)
        
        assert "100" in formatted
        assert "50" in formatted
    
    def test_enum_conversion(self):
        """测试枚举转换"""
        from taiji_agent.grpc_bridge.serialization import EnumConverter
        
        assert EnumConverter.finish_reason_to_string(1) == "STOP"
        assert EnumConverter.agent_status_to_string(2) == "RUNNING"
        assert EnumConverter.memory_type_to_string(1) == "SESSION"
        assert EnumConverter.tool_type_to_string(1) == "FUNCTION"


# ============================================================
# 健康检查测试
# ============================================================

class TestHealthCheck:
    """健康检查测试"""
    
    @pytest.mark.asyncio
    async def test_health_servicer(self):
        """测试健康检查服务"""
        from taiji_agent.grpc_bridge.health import HealthServicer, HealthStatus
        
        servicer = HealthServicer()
        
        # 测试设置状态
        await servicer.set_status("", HealthStatus.SERVING)
        
        # 测试获取状态
        # 注意：实际测试需要 mock protobuf
        assert servicer._status == HealthStatus.SERVING
    
    @pytest.mark.asyncio
    async def test_service_monitor(self):
        """测试服务监控器"""
        from taiji_agent.grpc_bridge.health import ServiceMonitor, HealthStatus
        
        monitor = ServiceMonitor(
            check_interval=1.0,
            failure_threshold=2,
            recovery_threshold=1,
        )
        
        # 注册回调
        unhealthy_calls = []
        
        async def on_unhealthy(service, status):
            unhealthy_calls.append((service, status))
        
        monitor.register_unhealthy_callback(on_unhealthy)
        
        await monitor.start()
        await asyncio.sleep(0.1)
        await monitor.stop()
        
        # 验证监控器已停止
        assert monitor._running == False


# ============================================================
# 集成测试
# ============================================================

class TestIntegration:
    """集成测试"""
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(True, reason="需要真实 gRPC 服务")
    async def test_end_to_end_chat(self):
        """端到端 Chat 测试"""
        import grpc
        
        # 启动服务端
        server = await create_test_server(port=50052)
        
        try:
            # 创建客户端
            async with grpc.aio.insecure_channel("localhost:50052") as channel:
                # 实际测试中需要使用生成的 stub
                pass
        finally:
            await server.stop(0)


# ============================================================
# 运行测试
# ============================================================

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    # 运行测试
    pytest.main([__file__, "-v", "-s"])
