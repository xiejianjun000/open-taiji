# gRPC 桥接模块

连接 Harness (TypeScript) 和 Hermes Agent (Python) 的 gRPC 通信层。

## 架构概览

```
┌─────────────────────────────────────────────────────┐
│                Harness (TypeScript)                   │
│                                                       │
│  ┌──────────────────────────────────────────────────┐│
│  │            HermesProvider 客户端                   ││
│  │  ┌─────────────┐ ┌──────────────┐ ┌───────────┐ ││
│  │  │ ChatClient  │ │ MemoryClient  │ │SkillsClient│ ││
│  │  └──────┬──────┘ └──────┬───────┘ └─────┬─────┘ ││
│  └─────────┼───────────────┼───────────────┼───────┘│
│            │               │               │         │
└────────────┼───────────────┼───────────────┼─────────┘
             │               │               │
             │    gRPC (HTTP/2, Protobuf)    │
             │               │               │
┌────────────┼───────────────┼───────────────┼─────────┐
│            ▼               ▼               ▼         │
│  ┌──────────────────────────────────────────────────┐│
│  │           Hermes Agent (Python) gRPC Server       ││
│  │                                                   ││
│  │  ┌──────────────┐ ┌───────────┐ ┌────────────┐ ││
│  │  │HermesProvider│ │HermesMem  │ │HermesSkills│ ││
│  │  │Service       │ │Service    │ │Service     │ ││
│  │  │(chat/stream) │ │(save/srch)│ │(list/exec) │ ││
│  │  └──────────────┘ └───────────┘ └────────────┘ ││
│  └──────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────┘
```

## 目录结构

```
grpc_bridge/
├── proto/                    # Protocol Buffer 定义
│   ├── common.proto          # 公共类型（枚举、错误）
│   ├── hermes_provider.proto # LLM 聊天服务
│   ├── memory.proto          # 记忆存取服务
│   ├── skills.proto          # 技能管理服务
│   ├── agent.proto           # Agent 执行服务
│   ├── taiji_verify.proto    # 太极验证服务
│   ├── hermes.proto          # 主 proto 文件
│   ├── buf.yaml              # Buf lint 配置
│   └── buf.gen.yaml          # 代码生成配置
├── server.py                 # Python gRPC 服务端
├── client.py                 # Python gRPC 客户端
├── serialization.py          # 消息序列化
├── health.py                 # 健康检查
├── __init__.py               # 包初始化
├── requirements.txt          # 依赖列表
├── pytest.ini               # Pytest 配置
└── tests/                   # 测试目录
    ├── __init__.py
    ├── conftest.py          # Pytest fixtures
    └── test_grpc_bridge.py  # 测试用例
```

## 服务定义

### HermesProvider
- `Chat`: 非流式聊天
- `StreamChat`: 流式聊天
- `GetEmbedding`: 获取嵌入向量
- `GetModels`: 获取可用模型列表

### HermesMemory
- `Save`: 保存记忆
- `Search`: 搜索记忆
- `GetContext`: 获取上下文
- `Delete`: 删除记忆
- `ListBackends`: 列出记忆后端

### HermesSkills
- `ListSkills`: 列出技能
- `GetSkill`: 获取技能详情
- `ExecuteSkill`: 执行技能
- `StreamExecuteSkill`: 流式执行技能
- `CreateSkill`: 创建技能
- `UpdateSkill`: 更新技能
- `DeleteSkill`: 删除技能

### HermesAgent
- `RunTask`: 运行任务
- `StreamTask`: 流式运行任务
- `GetStatus`: 获取 Agent 状态
- `CancelTask`: 取消任务
- `GetTaskHistory`: 获取任务历史

### TaijiVerify
- `Verify`: 执行太极验证
- `BatchVerify`: 批量验证
- `GetRules`: 获取验证规则
- `GetHistory`: 获取验证历史

## 安装

```bash
# 安装依赖
pip install -r requirements.txt

# 编译 proto 文件
python -m grpc_tools.protoc \
    -I./proto \
    --python_out=. \
    --grpc_python_out=. \
    ./proto/*.proto
```

## 使用示例

### 服务端

```python
import asyncio
from grpc_bridge.server import (
    create_server,
    GrpcServerConfig,
    HermesProviderServicer,
    HermesMemoryServicer,
)

async def main():
    config = GrpcServerConfig(
        host="0.0.0.0",
        port=50051,
    )
    
    server = await create_server(config)
    await server.start()
    print("gRPC server started on port 50051")
    await server.wait_for_termination()

asyncio.run(main())
```

### 客户端

```python
import asyncio
from grpc_bridge.client import HermesProviderClient, ClientConfig

async def main():
    config = ClientConfig(address="localhost:50051")
    
    async with HermesProviderClient(config) as client:
        response = await client.chat(
            messages=[
                {"role": "user", "content": "Hello!"}
            ],
            model="gpt-4",
        )
        print(response["content"])

asyncio.run(main())
```

### 流式聊天

```python
async def stream_example():
    config = ClientConfig(address="localhost:50051")
    
    async with HermesProviderClient(config) as client:
        async for chunk in client.stream_chat(
            messages=[
                {"role": "user", "content": "Tell me a story"}
            ]
        ):
            if chunk.get("content_delta"):
                print(chunk["content_delta"], end="", flush=True)
```

## 测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试类
pytest tests/test_grpc_bridge.py::TestHermesProviderServicer -v

# 运行并显示详细输出
pytest tests/ -v -s

# 生成覆盖率报告
pytest tests/ --cov=grpc_bridge --cov-report=html
```

## 配置说明

### 服务端配置

```python
config = GrpcServerConfig(
    host="0.0.0.0",
    port=50051,
    max_workers=10,
    max_concurrent_rpcs=100,
    enable_reflection=True,
)
```

### 客户端配置

```python
config = ClientConfig(
    address="localhost:50051",
    timeout=TimeoutConfig(
        chat_timeout_ms=60000,
        stream_chat_timeout_ms=300000,
        memory_timeout_ms=5000,
        skill_timeout_ms=120000,
        agent_task_timeout_ms=600000,
    ),
    retry=RetryConfig(
        max_retries=3,
        base_delay_ms=100,
        max_delay_ms=5000,
    ),
    pool=ConnectionPoolConfig(
        max_size=10,
        min_size=1,
    ),
)
```

## 错误处理

gRPC 使用标准错误码：

| 错误码 | 含义 | 处理建议 |
|--------|------|----------|
| INVALID_ARGUMENT | 参数无效 | 检查请求参数 |
| NOT_FOUND | 资源不存在 | 创建或使用正确 ID |
| DEADLINE_EXCEEDED | 超时 | 重试或增加超时时间 |
| RESOURCE_EXHAUSTED | 资源耗尽 | 等待后重试 |
| UNAVAILABLE | 服务不可用 | 检查服务状态，重试 |
| INTERNAL | 内部错误 | 联系开发人员 |

## 健康检查

```bash
# 使用 grpcurl 检查健康状态
grpcurl -plaintext localhost:50051 grpc.health.v1.Health/Check

# 检查特定服务
grpcurl -plaintext -d '{"service": "hermes.v1.HermesProvider"}' \
    localhost:50051 grpc.health.v1.Health/Check
```

## 许可证

MIT License
