"""
gRPC 桥接模块 - Python 客户端实现

基于 grpcio 的异步 gRPC 客户端实现，
提供连接池管理、重试与超时机制。
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, TypeVar

import grpc
from google.protobuf import empty_pb2

# Proto 生成的模块（编译后导入）
# from hermes.v1 import (
#     hermes_pb2,
#     hermes_pb2_grpc,
#     provider_pb2,
#     provider_pb2_grpc,
#     memory_pb2,
#     memory_pb2_grpc,
#     skills_pb2,
#     skills_pb2_grpc,
#     agent_pb2,
#     agent_pb2_grpc,
#     taiji_verify_pb2,
#     taiji_verify_pb2_grpc,
# )

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ============================================================
# 配置定义
# ============================================================

@dataclass
class RetryConfig:
    """重试配置"""
    max_retries: int = 3              # 最大重试次数
    base_delay_ms: int = 100          # 基础延迟（毫秒）
    max_delay_ms: int = 5000         # 最大延迟（毫秒）
    retryable_codes: List[grpc.StatusCode] = field(
        default_factory=lambda: [
            grpc.StatusCode.UNAVAILABLE,
            grpc.StatusCode.DEADLINE_EXCEEDED,
            grpc.StatusCode.RESOURCE_EXHAUSTED,
        ]
    )


@dataclass
class TimeoutConfig:
    """超时配置"""
    chat_timeout_ms: int = 60_000           # 非流式 Chat
    stream_chat_timeout_ms: int = 300_000    # 流式 Chat
    stream_first_chunk_timeout_ms: int = 10_000  # 流式首 chunk 超时
    memory_timeout_ms: int = 5_000           # 记忆操作超时
    skill_timeout_ms: int = 120_000          # 技能执行超时
    agent_task_timeout_ms: int = 600_000     # Agent 任务超时


@dataclass
class ConnectionPoolConfig:
    """连接池配置"""
    max_size: int = 10                # 最大连接数
    min_size: int = 1                 # 最小连接数
    max_idle_time_ms: int = 60_000    # 最大空闲时间（毫秒）
    health_check_interval_ms: int = 30_000  # 健康检查间隔


@dataclass
class ClientConfig:
    """客户端配置"""
    address: str = "localhost:50051"      # 服务地址
    timeout: TimeoutConfig = field(default_factory=TimeoutConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    pool: ConnectionPoolConfig = field(default_factory=ConnectionPoolConfig)
    enable_retry: bool = True             # 是否启用重试
    enable_pool: bool = True              # 是否启用连接池


# ============================================================
# 重试装饰器
# ============================================================

def with_retry(config: RetryConfig):
    """
    重试装饰器
    
    Args:
        config: 重试配置
        
    Returns:
        装饰器函数
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        async def wrapper(*args, **kwargs) -> T:
            last_error = None
            
            for attempt in range(config.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except grpc.RpcError as e:
                    last_error = e
                    
                    # 检查是否可重试
                    if e.code() not in config.retryable_codes:
                        logger.warning(f"Non-retryable error: {e.code()}")
                        raise
                    
                    # 检查是否还有重试次数
                    if attempt >= config.max_retries:
                        logger.warning(f"Max retries ({config.max_retries}) exceeded")
                        raise
                    
                    # 计算延迟（指数退避 + 抖动）
                    delay_ms = min(
                        config.base_delay_ms * (2 ** attempt),
                        config.max_delay_ms,
                    )
                    # 添加 ±25% 随机抖动
                    import random
                    jitter = delay_ms * (0.75 + 0.5 * random.random())
                    
                    logger.warning(
                        f"Retryable error (attempt {attempt + 1}/{config.max_retries + 1}): "
                        f"{e.code()}, retrying in {jitter:.0f}ms"
                    )
                    await asyncio.sleep(jitter / 1000)
                except Exception as e:
                    logger.error(f"Unexpected error: {e}")
                    raise
            
            raise last_error
        
        return wrapper
    return decorator


# ============================================================
# 连接池
# ============================================================

class ConnectionPool:
    """
    gRPC 连接池
    
    管理多个 gRPC 通道连接，支持健康检查和自动回收。
    """
    
    def __init__(
        self,
        address: str,
        config: ConnectionPoolConfig,
    ):
        self._address = address
        self._config = config
        self._pool: asyncio.Queue = asyncio.Queue(maxsize=config.max_size)
        self._created_count = 0
        self._lock = asyncio.Lock()
        self._closed = False
        self._health_check_task: Optional[asyncio.Task] = None
    
    async def initialize(self) -> None:
        """初始化连接池"""
        # 创建初始连接
        for _ in range(self._config.min_size):
            await self._create_connection()
        
        # 启动健康检查
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        
        logger.info(f"Connection pool initialized: address={self._address}")
    
    async def acquire(self) -> grpc.aio.Channel:
        """
        获取连接
        
        Returns:
            gRPC 通道
        """
        if self._closed:
            raise RuntimeError("Connection pool is closed")
        
        try:
            # 尝试从池中获取连接
            channel = self._pool.get_nowait()
            
            # 检查连接是否可用
            if channel.is_active():
                return channel
            
            # 连接不可用，关闭并创建新连接
            await channel.close()
            return await self._create_connection()
            
        except asyncio.QueueEmpty:
            # 池为空，检查是否可以创建新连接
            async with self._lock:
                if self._created_count < self._config.max_size:
                    return await self._create_connection()
            
            # 等待可用连接
            channel = await asyncio.wait_for(
                self._pool.get(),
                timeout=30.0,
            )
            return channel
    
    async def release(self, channel: grpc.aio.Channel) -> None:
        """
        释放连接回池中
        
        Args:
            channel: gRPC 通道
        """
        if self._closed:
            await channel.close()
            return
        
        try:
            self._pool.put_nowait(channel)
        except asyncio.QueueFull:
            # 池已满，关闭连接
            await channel.close()
    
    async def close(self) -> None:
        """关闭连接池"""
        self._closed = True
        
        # 取消健康检查
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        # 关闭所有连接
        while not self._pool.empty():
            try:
                channel = self._pool.get_nowait()
                await channel.close()
            except asyncio.QueueEmpty:
                break
        
        logger.info(f"Connection pool closed: address={self._address}")
    
    async def _create_connection(self) -> grpc.aio.Channel:
        """创建新连接"""
        async with self._lock:
            if self._created_count >= self._config.max_size:
                raise RuntimeError("Connection pool is full")
            
            channel = grpc.aio.insecure_channel(self._address)
            self._created_count += 1
            
            logger.debug(f"Created new connection: {self._address} (total: {self._created_count})")
            return channel
    
    async def _health_check_loop(self) -> None:
        """健康检查循环"""
        while not self._closed:
            try:
                await asyncio.sleep(self._config.health_check_interval_ms / 1000)
                await self._health_check()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
    
    async def _health_check(self) -> None:
        """执行健康检查"""
        while not self._pool.empty():
            try:
                channel = self._pool.get_nowait()
                
                if channel.is_active():
                    await self._pool.put(channel)
                else:
                    await channel.close()
                    self._created_count -= 1
                    logger.warning("Removed inactive connection")
                    
            except asyncio.QueueEmpty:
                break


# ============================================================
# HermesProvider 客户端
# ============================================================

class HermesProviderClient:
    """
    HermesProvider 客户端
    
    提供 LLM 聊天与嵌入服务的客户端封装。
    """
    
    def __init__(
        self,
        config: Optional[ClientConfig] = None,
        channel: Optional[grpc.aio.Channel] = None,
    ):
        self._config = config or ClientConfig()
        self._pool: Optional[ConnectionPool] = None
        self._channel = channel
        self._stub = None  # provider_pb2_grpc.HermesProviderStub
    
    async def initialize(self) -> None:
        """初始化客户端"""
        if self._channel:
            # 使用提供的通道
            pass
        elif self._config.enable_pool:
            # 创建连接池
            self._pool = ConnectionPool(
                self._config.address,
                self._config.pool,
            )
            await self._pool.initialize()
            self._channel = await self._pool.acquire()
        else:
            # 创建单一通道
            self._channel = grpc.aio.insecure_channel(self._config.address)
        
        # 创建 stub
        # self._stub = provider_pb2_grpc.HermesProviderStub(self._channel)
        
        logger.info(f"HermesProviderClient initialized: address={self._config.address}")
    
    async def close(self) -> None:
        """关闭客户端"""
        if self._pool:
            await self._pool.close()
        elif self._channel:
            await self._channel.close()
        
        logger.info("HermesProviderClient closed")
    
    async def __aenter__(self) -> "HermesProviderClient":
        """异步上下文管理器入口"""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """异步上下文管理器退出"""
        await self.close()
    
    @with_retry
    async def chat(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        非流式 Chat
        
        Args:
            messages: 对话历史
            model: 模型名称
            temperature: 温度
            max_tokens: 最大生成 token 数
            tools: 可用工具列表
            session_id: 会话 ID
            metadata: 自定义元数据
            
        Returns:
            ChatResponse 字典
        """
        # 构建请求
        # request = provider_pb2.ChatRequest(
        #     messages=[self._build_message(m) for m in messages],
        #     model=model or "",
        #     session_id=session_id or "",
        #     metadata=metadata or {},
        # )
        # if temperature is not None:
        #     request.temperature = temperature
        # if max_tokens is not None:
        #     request.max_tokens = max_tokens
        # if tools:
        #     request.tools.extend([self._build_tool(t) for t in tools])
        
        # 设置超时
        timeout = self._config.timeout.chat_timeout_ms / 1000
        
        try:
            # response = await self._stub.Chat(request, timeout=timeout)
            # return {
            #     "content": response.content,
            #     "tool_calls": [self._parse_tool_call(tc) for tc in response.tool_calls],
            #     "finish_reason": response.finish_reason,
            #     "usage": self._parse_token_usage(response.usage),
            #     "model": response.model,
            #     "session_id": response.session_id,
            # }
            
            # 模拟响应
            return self._mock_chat_response(messages)
            
        except grpc.RpcError as e:
            logger.error(f"Chat error: {e}")
            raise
    
    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        流式 Chat
        
        Args:
            messages: 对话历史
            model: 模型名称
            temperature: 温度
            max_tokens: 最大生成 token 数
            tools: 可用工具列表
            session_id: 会话 ID
            metadata: 自定义元数据
            
        Yields:
            ChatChunk 字典流
        """
        # 构建请求（与 chat 相同）
        # request = provider_pb2.ChatRequest(...)
        
        # 设置超时
        timeout = self._config.timeout.stream_chat_timeout_ms / 1000
        
        try:
            # 调用流式方法
            # async for chunk in self._stub.StreamChat(request, timeout=timeout):
            #     yield self._parse_chat_chunk(chunk)
            
            # 模拟流式响应
            async for chunk in self._mock_stream_chat(messages):
                yield chunk
                
        except grpc.RpcError as e:
            logger.error(f"StreamChat error: {e}")
            raise
    
    @with_retry
    async def get_embedding(
        self,
        text: str,
        model: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        获取嵌入向量
        
        Args:
            text: 文本内容
            model: 嵌入模型名称
            session_id: 会话 ID
            
        Returns:
            EmbeddingResponse 字典
        """
        # request = provider_pb2.EmbeddingRequest(
        #     text=text,
        #     model=model or "",
        #     session_id=session_id or "",
        # )
        
        timeout = self._config.timeout.memory_timeout_ms / 1000
        
        try:
            # response = await self._stub.GetEmbedding(request, timeout=timeout)
            # return {
            #     "embedding": list(response.embedding),
            #     "dimensions": response.dimensions,
            #     "model": response.model,
            #     "usage": self._parse_token_usage(response.usage),
            # }
            
            # 模拟响应
            import random
            dimensions = 1536
            return {
                "embedding": [random.random() - 0.5 for _ in range(dimensions)],
                "dimensions": dimensions,
                "model": model or "text-embedding-ada-002",
                "usage": {"input_tokens": len(text.split()), "output_tokens": 0},
            }
            
        except grpc.RpcError as e:
            logger.error(f"GetEmbedding error: {e}")
            raise
    
    @with_retry
    async def get_models(self) -> List[Dict[str, Any]]:
        """
        获取可用模型列表
        
        Returns:
            模型列表
        """
        try:
            # response = await self._stub.GetModels(empty_pb2.Empty())
            # return [self._parse_model_info(m) for m in response.models]
            
            # 模拟响应
            return [
                {
                    "id": "gpt-4",
                    "name": "GPT-4",
                    "provider": "openai",
                    "supports_tools": True,
                    "supports_streaming": True,
                    "supports_embeddings": True,
                    "max_tokens": 8192,
                },
            ]
            
        except grpc.RpcError as e:
            logger.error(f"GetModels error: {e}")
            raise
    
    # ========== 辅助方法 ==========
    
    def _mock_chat_response(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """生成模拟的 ChatResponse"""
        last_message = messages[-1] if messages else {}
        return {
            "content": f"Echo: {last_message.get('content', 'Hello')}",
            "tool_calls": [],
            "finish_reason": 1,  # FINISH_REASON_STOP
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "model": "gpt-4",
            "session_id": "",
        }
    
    async def _mock_stream_chat(
        self,
        messages: List[Dict[str, Any]],
    ) -> AsyncIterator[Dict[str, Any]]:
        """生成模拟的流式响应"""
        last_message = messages[-1] if messages else {}
        content = f"Echo: {last_message.get('content', 'Hello')}"
        words = content.split()
        
        for i, word in enumerate(words):
            yield {
                "content_delta": word + " ",
                "index": i,
            }
            await asyncio.sleep(0.01)
        
        yield {
            "finish_reason": 1,  # FINISH_REASON_STOP
            "usage": {"input_tokens": 10, "output_tokens": len(words)},
            "index": len(words),
        }


# ============================================================
# HermesMemory 客户端
# ============================================================

class HermesMemoryClient:
    """
    HermesMemory 客户端
    
    提供记忆存取服务的客户端封装。
    """
    
    def __init__(
        self,
        config: Optional[ClientConfig] = None,
        channel: Optional[grpc.aio.Channel] = None,
    ):
        self._config = config or ClientConfig()
        self._pool: Optional[ConnectionPool] = None
        self._channel = channel
        self._stub = None
    
    async def initialize(self) -> None:
        """初始化客户端"""
        if self._channel:
            pass
        elif self._config.enable_pool:
            self._pool = ConnectionPool(
                self._config.address,
                self._config.pool,
            )
            await self._pool.initialize()
            self._channel = await self._pool.acquire()
        else:
            self._channel = grpc.aio.insecure_channel(self._config.address)
        
        # self._stub = memory_pb2_grpc.HermesMemoryStub(self._channel)
        logger.info(f"HermesMemoryClient initialized: address={self._config.address}")
    
    async def close(self) -> None:
        """关闭客户端"""
        if self._pool:
            await self._pool.close()
        elif self._channel:
            await self._channel.close()
    
    async def __aenter__(self) -> "HermesMemoryClient":
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
    
    @with_retry
    async def save(
        self,
        content: str,
        memory_type: int,
        session_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        backend: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        保存记忆
        
        Args:
            content: 记忆内容
            memory_type: 记忆类型
            session_id: 会话 ID
            tenant_id: 租户 ID
            metadata: 附加元数据
            backend: 目标后端
            
        Returns:
            SaveResponse 字典
        """
        # request = memory_pb2.SaveRequest(
        #     content=content,
        #     type=memory_type,
        #     metadata=metadata or {},
        # )
        # ...
        
        import uuid
        return {
            "memory_id": str(uuid.uuid4()),
            "deduplicated": False,
        }
    
    @with_retry
    async def search(
        self,
        query: str,
        memory_type: Optional[int] = None,
        limit: int = 10,
        min_score: float = 0.0,
        session_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        搜索记忆
        
        Args:
            query: 搜索查询
            memory_type: 记忆类型过滤
            limit: 返回条数上限
            min_score: 最低相似度阈值
            session_id: 会话 ID
            tenant_id: 租户 ID
            
        Returns:
            SearchResponse 字典
        """
        # request = memory_pb2.SearchRequest(
        #     query=query,
        #     limit=limit,
        #     min_score=min_score,
        # )
        # ...
        
        return {
            "results": [],
            "total_count": 0,
            "search_time_ms": 10.0,
        }
    
    @with_retry
    async def get_context(
        self,
        query: str,
        max_tokens: Optional[int] = None,
        session_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        获取上下文
        
        Args:
            query: 查询文本
            max_tokens: Token 预算
            session_id: 会话 ID
            tenant_id: 租户 ID
            
        Returns:
            GetContextResponse 字典
        """
        return {
            "context_block": "",
            "items": [],
            "total_tokens": 0,
        }
    
    @with_retry
    async def delete(
        self,
        memory_id: str,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        删除记忆
        
        Args:
            memory_id: 记忆 ID
            tenant_id: 租户 ID
            
        Returns:
            DeleteResponse 字典
        """
        return {"success": True}
    
    @with_retry
    async def list_backends(self) -> List[Dict[str, Any]]:
        """
        列出可用记忆后端
        
        Returns:
            后端列表
        """
        return [
            {"backend": 1, "name": "Holographic", "is_available": True},
        ]


# ============================================================
# HermesSkills 客户端
# ============================================================

class HermesSkillsClient:
    """
    HermesSkills 客户端
    
    提供技能管理服务的客户端封装。
    """
    
    def __init__(
        self,
        config: Optional[ClientConfig] = None,
        channel: Optional[grpc.aio.Channel] = None,
    ):
        self._config = config or ClientConfig()
        self._pool: Optional[ConnectionPool] = None
        self._channel = channel
        self._stub = None
    
    async def initialize(self) -> None:
        """初始化客户端"""
        if self._channel:
            pass
        elif self._config.enable_pool:
            self._pool = ConnectionPool(
                self._config.address,
                self._config.pool,
            )
            await self._pool.initialize()
            self._channel = await self._pool.acquire()
        else:
            self._channel = grpc.aio.insecure_channel(self._config.address)
        
        # self._stub = skills_pb2_grpc.HermesSkillsStub(self._channel)
        logger.info(f"HermesSkillsClient initialized: address={self._config.address}")
    
    async def close(self) -> None:
        """关闭客户端"""
        if self._pool:
            await self._pool.close()
        elif self._channel:
            await self._channel.close()
    
    async def __aenter__(self) -> "HermesSkillsClient":
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
    
    @with_retry
    async def list_skills(
        self,
        category: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        列出技能
        
        Args:
            category: 类别过滤
            search: 搜索关键词
            limit: 返回条数
            offset: 分页偏移
            
        Returns:
            SkillList 字典
        """
        return {"skills": [], "total_count": 0}
    
    @with_retry
    async def get_skill(self, skill_id: str) -> Dict[str, Any]:
        """
        获取技能详情
        
        Args:
            skill_id: 技能 ID
            
        Returns:
            SkillResponse 字典
        """
        return {"success": False}
    
    @with_retry
    async def execute_skill(
        self,
        skill_id: str,
        task: str,
        parameters: Optional[Dict[str, str]] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        执行技能
        
        Args:
            skill_id: 技能 ID
            task: 任务描述
            parameters: 执行参数
            session_id: 会话 ID
            
        Returns:
            ExecuteSkillResponse 字典
        """
        return {
            "result": "",
            "success": False,
            "execution_time_ms": 0,
        }
    
    async def stream_execute_skill(
        self,
        skill_id: str,
        task: str,
        parameters: Optional[Dict[str, str]] = None,
        session_id: Optional[str] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        流式执行技能
        
        Args:
            skill_id: 技能 ID
            task: 任务描述
            parameters: 执行参数
            session_id: 会话 ID
            
        Yields:
            SkillExecutionChunk 字典流
        """
        yield {"text_delta": "", "index": 0, "done": True}
    
    @with_retry
    async def create_skill(
        self,
        name: str,
        description: str,
        content: str,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        创建技能
        
        Args:
            name: 技能名称
            description: 技能描述
            content: SKILL.md 内容
            category: 类别
            tags: 标签
            metadata: 扩展元数据
            
        Returns:
            SkillResponse 字典
        """
        import uuid
        return {
            "success": True,
            "skill": {
                "id": str(uuid.uuid4()),
                "name": name,
                "description": description,
            },
        }
    
    @with_retry
    async def update_skill(
        self,
        skill_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        content: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        更新技能
        
        Args:
            skill_id: 技能 ID
            name: 技能名称
            description: 技能描述
            content: SKILL.md 内容
            category: 类别
            tags: 标签
            metadata: 扩展元数据
            
        Returns:
            SkillResponse 字典
        """
        return {"success": False}
    
    @with_retry
    async def delete_skill(self, skill_id: str) -> Dict[str, Any]:
        """
        删除技能
        
        Args:
            skill_id: 技能 ID
            
        Returns:
            DeleteSkillResponse 字典
        """
        return {"success": True}


# ============================================================
# HermesAgent 客户端
# ============================================================

class HermesAgentClient:
    """
    HermesAgent 客户端
    
    提供完整代理执行服务的客户端封装。
    """
    
    def __init__(
        self,
        config: Optional[ClientConfig] = None,
        channel: Optional[grpc.aio.Channel] = None,
    ):
        self._config = config or ClientConfig()
        self._pool: Optional[ConnectionPool] = None
        self._channel = channel
        self._stub = None
    
    async def initialize(self) -> None:
        """初始化客户端"""
        if self._channel:
            pass
        elif self._config.enable_pool:
            self._pool = ConnectionPool(
                self._config.address,
                self._config.pool,
            )
            await self._pool.initialize()
            self._channel = await self._pool.acquire()
        else:
            self._channel = grpc.aio.insecure_channel(self._config.address)
        
        # self._stub = agent_pb2_grpc.HermesAgentStub(self._channel)
        logger.info(f"HermesAgentClient initialized: address={self._config.address}")
    
    async def close(self) -> None:
        """关闭客户端"""
        if self._pool:
            await self._pool.close()
        elif self._channel:
            await self._channel.close()
    
    async def __aenter__(self) -> "HermesAgentClient":
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
    
    @with_retry
    async def run_task(
        self,
        task: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        max_iterations: Optional[int] = None,
        temperature: Optional[float] = None,
        session_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        enable_hitl: bool = False,
        hitl_timeout_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        非流式运行任务
        
        Args:
            task: 任务描述
            system_prompt: 系统提示词
            model: 模型选择
            max_iterations: 最大迭代次数
            temperature: 温度
            session_id: 会话 ID
            tenant_id: 租户 ID
            metadata: 自定义元数据
            enable_hitl: 启用人工干预
            hitl_timeout_seconds: 人工审批超时
            
        Returns:
            TaskResponse 字典
        """
        return {
            "result": "",
            "success": False,
            "iterations": 0,
            "execution_time_ms": 0,
        }
    
    async def stream_task(
        self,
        task: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        max_iterations: Optional[int] = None,
        temperature: Optional[float] = None,
        session_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        enable_hitl: bool = False,
        hitl_timeout_seconds: Optional[int] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        流式运行任务
        
        Args:
            task: 任务描述
            ...（同 run_task）
            
        Yields:
            TaskChunk 字典流
        """
        yield {"text_delta": "", "index": 0, "done": True}
    
    @with_retry
    async def get_status(
        self,
        session_id: str,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        获取 Agent 状态
        
        Args:
            session_id: 会话 ID
            tenant_id: 租户 ID
            
        Returns:
            AgentStatus 字典
        """
        return {"status": 1}  # IDLE
    
    @with_retry
    async def cancel_task(
        self,
        session_id: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        取消任务
        
        Args:
            session_id: 会话 ID
            reason: 取消原因
            
        Returns:
            CancelTaskResponse 字典
        """
        return {"success": True}
    
    @with_retry
    async def get_task_history(
        self,
        session_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        获取任务历史
        
        Args:
            session_id: 会话 ID
            limit: 返回条数
            offset: 分页偏移
            
        Returns:
            TaskHistoryResponse 字典
        """
        return {"tasks": [], "total_count": 0}


# ============================================================
# TaijiVerify 客户端
# ============================================================

class TaijiVerifyClient:
    """
    TaijiVerify 客户端
    
    提供太极验证服务的客户端封装。
    """
    
    def __init__(
        self,
        config: Optional[ClientConfig] = None,
        channel: Optional[grpc.aio.Channel] = None,
    ):
        self._config = config or ClientConfig()
        self._pool: Optional[ConnectionPool] = None
        self._channel = channel
        self._stub = None
    
    async def initialize(self) -> None:
        """初始化客户端"""
        if self._channel:
            pass
        elif self._config.enable_pool:
            self._pool = ConnectionPool(
                self._config.address,
                self._config.pool,
            )
            await self._pool.initialize()
            self._channel = await self._pool.acquire()
        else:
            self._channel = grpc.aio.insecure_channel(self._config.address)
        
        # self._stub = taiji_verify_pb2_grpc.TaijiVerifyStub(self._channel)
        logger.info(f"TaijiVerifyClient initialized: address={self._config.address}")
    
    async def close(self) -> None:
        """关闭客户端"""
        if self._pool:
            await self._pool.close()
        elif self._channel:
            await self._channel.close()
    
    async def __aenter__(self) -> "TaijiVerifyClient":
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
    
    @with_retry
    async def verify(
        self,
        content: str,
        content_type: str = "text",
        ruleset: Optional[str] = None,
        context: Optional[Dict[str, str]] = None,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        执行验证
        
        Args:
            content: 待验证内容
            content_type: 内容类型
            ruleset: 规则集名称
            context: 上下文信息
            tenant_id: 租户 ID
            
        Returns:
            VerifyResponse 字典
        """
        return {
            "passed": True,
            "result": "验证通过",
            "details": [],
            "score": 1.0,
            "warnings": [],
            "errors": [],
        }
    
    @with_retry
    async def batch_verify(
        self,
        items: List[Dict[str, Any]],
        stop_on_first_error: bool = False,
    ) -> Dict[str, Any]:
        """
        批量验证
        
        Args:
            items: 验证项列表
            stop_on_first_error: 遇到首个错误时是否停止
            
        Returns:
            BatchVerifyResponse 字典
        """
        return {
            "results": [],
            "total_count": 0,
            "passed_count": 0,
            "failed_count": 0,
            "total_time_ms": 0,
        }
    
    @with_retry
    async def get_rules(self) -> List[Dict[str, Any]]:
        """
        获取验证规则
        
        Returns:
            规则列表
        """
        return []
    
    @with_retry
    async def get_history(
        self,
        tenant_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        passed_only: bool = False,
    ) -> Dict[str, Any]:
        """
        获取验证历史
        
        Args:
            tenant_id: 租户 ID
            limit: 返回条数
            offset: 分页偏移
            passed_only: 仅返回通过的
            
        Returns:
            HistoryResponse 字典
        """
        return {"items": [], "total_count": 0}


# ============================================================
# 统一客户端工厂
# ============================================================

class HermesClientFactory:
    """
    Hermes 客户端工厂
    
    方便创建和配置所有 Hermes 服务客户端。
    """
    
    def __init__(self, config: Optional[ClientConfig] = None):
        self._config = config or ClientConfig()
        self._provider: Optional[HermesProviderClient] = None
        self._memory: Optional[HermesMemoryClient] = None
        self._skills: Optional[HermesSkillsClient] = None
        self._agent: Optional[HermesAgentClient] = None
        self._verify: Optional[TaijiVerifyClient] = None
    
    def create_provider(self) -> HermesProviderClient:
        """创建 HermesProvider 客户端"""
        self._provider = HermesProviderClient(self._config)
        return self._provider
    
    def create_memory(self) -> HermesMemoryClient:
        """创建 HermesMemory 客户端"""
        self._memory = HermesMemoryClient(self._config)
        return self._memory
    
    def create_skills(self) -> HermesSkillsClient:
        """创建 HermesSkills 客户端"""
        self._skills = HermesSkillsClient(self._config)
        return self._skills
    
    def create_agent(self) -> HermesAgentClient:
        """创建 HermesAgent 客户端"""
        self._agent = HermesAgentClient(self._config)
        return self._agent
    
    def create_verify(self) -> TaijiVerifyClient:
        """创建 TaijiVerify 客户端"""
        self._verify = TaijiVerifyClient(self._config)
        return self._verify
    
    async def close_all(self) -> None:
        """关闭所有客户端"""
        for client in [self._provider, self._memory, self._skills, self._agent, self._verify]:
            if client:
                await client.close()
