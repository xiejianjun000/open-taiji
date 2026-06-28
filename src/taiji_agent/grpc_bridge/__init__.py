"""
gRPC 桥接模块 - Taiji Agent Hermes Provider

连接 Harness (TypeScript) 和 Hermes Agent (Python) 的 gRPC 通信层。

模块结构:
    - proto/: Protocol Buffer 定义文件
    - server.py: Python gRPC 服务端实现
    - client.py: Python gRPC 客户端实现
    - serialization.py: 消息序列化/反序列化
    - health.py: 健康检查协议实现

主要服务:
    - HermesProvider: LLM 聊天与嵌入服务
    - HermesMemory: 记忆存取服务
    - HermesSkills: 技能管理服务
    - HermesAgent: 完整代理执行服务
    - TaijiVerify: 太极验证服务

使用示例:

    # 服务端
    from grpc_bridge.server import create_server, GrpcServerConfig
    
    config = GrpcServerConfig(host="0.0.0.0", port=50051)
    server = await create_server(config)
    await server.start()
    await server.wait_for_termination()

    # 客户端
    from grpc_bridge.client import HermesProviderClient, ClientConfig
    
    config = ClientConfig(address="localhost:50051")
    async with HermesProviderClient(config) as client:
        response = await client.chat(messages=[{"role": "user", "content": "Hello"}])
        print(response["content"])
"""

__version__ = "1.0.0"
__author__ = "Taiji Agent Team"

# 公开接口
from taiji_agent.grpc_bridge.server import (
    GrpcServerConfig,
    HermesProviderServicer,
    HermesMemoryServicer,
    HermesSkillsServicer,
    HermesAgentServicer,
    TaijiVerifyServicer,
    create_server,
    serve,
)

from taiji_agent.grpc_bridge.client import (
    RetryConfig,
    TimeoutConfig,
    ConnectionPoolConfig,
    ClientConfig,
    HermesProviderClient,
    HermesMemoryClient,
    HermesSkillsClient,
    HermesAgentClient,
    TaijiVerifyClient,
    HermesClientFactory,
)

from taiji_agent.grpc_bridge.serialization import (
    Serializer,
    MessageConverter,
    ToolDefinitionConverter,
    TokenUsageConverter,
    TimestampConverter,
    EnumConverter,
    MessageValidator,
    serialize_message,
    deserialize_message,
    convert_chat_request,
    format_token_usage,
)

from taiji_agent.grpc_bridge.health import (
    HealthStatus,
    ServiceState,
    HealthCheckResponse,
    ServiceHealthInfo,
    HealthServicer,
    HealthClient,
    ServiceMonitor,
    require_healthy,
    create_health_check_server,
    create_health_check_channel,
    check_server_health,
)

# 模块元数据
__all__ = [
    # 版本
    "__version__",
    
    # 服务端
    "GrpcServerConfig",
    "HermesProviderServicer",
    "HermesMemoryServicer",
    "HermesSkillsServicer",
    "HermesAgentServicer",
    "TaijiVerifyServicer",
    "create_server",
    "serve",
    
    # 客户端
    "RetryConfig",
    "TimeoutConfig",
    "ConnectionPoolConfig",
    "ClientConfig",
    "HermesProviderClient",
    "HermesMemoryClient",
    "HermesSkillsClient",
    "HermesAgentClient",
    "TaijiVerifyClient",
    "HermesClientFactory",
    
    # 序列化
    "Serializer",
    "MessageConverter",
    "ToolDefinitionConverter",
    "TokenUsageConverter",
    "TimestampConverter",
    "EnumConverter",
    "MessageValidator",
    "serialize_message",
    "deserialize_message",
    "convert_chat_request",
    "format_token_usage",
    
    # 健康检查
    "HealthStatus",
    "ServiceState",
    "HealthCheckResponse",
    "ServiceHealthInfo",
    "HealthServicer",
    "HealthClient",
    "ServiceMonitor",
    "require_healthy",
    "create_health_check_server",
    "create_health_check_channel",
    "check_server_health",
]
