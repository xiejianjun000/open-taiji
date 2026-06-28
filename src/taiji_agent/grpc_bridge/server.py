"""
gRPC 桥接模块 - Python 服务端实现

基于 grpcio 的异步 gRPC 服务端实现，
提供 Hermes Agent 的各项服务能力。
"""

import asyncio
import logging
import time
from typing import Any, AsyncIterator, Dict, Optional, List

import grpc
from google.protobuf import empty_pb2, timestamp_pb2, struct_pb2

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


# ============================================================
# 服务配置
# ============================================================

class GrpcServerConfig:
    """gRPC 服务端配置"""
    
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 50051,
        max_workers: int = 10,
        max_concurrent_rpcs: int = 100,
        enable_reflection: bool = True,
    ):
        self.host = host
        self.port = port
        self.max_workers = max_workers
        self.max_concurrent_rpcs = max_concurrent_rpcs
        self.enable_reflection = enable_reflection


# ============================================================
# HermesProvider 服务实现
# ============================================================

class HermesProviderServicer:
    """
    HermesProvider 服务实现
    
    提供 LLM 聊天与嵌入服务
    """
    
    def __init__(
        self,
        llm_adapter: Optional[Any] = None,
        default_model: str = "gpt-4",
    ):
        self._llm_adapter = llm_adapter
        self._default_model = default_model
        self._available_models = [
            {
                "id": "gpt-4",
                "name": "GPT-4",
                "provider": "openai",
                "supports_tools": True,
                "supports_streaming": True,
                "supports_embeddings": True,
                "max_tokens": 8192,
            },
            {
                "id": "gpt-3.5-turbo",
                "name": "GPT-3.5 Turbo",
                "provider": "openai",
                "supports_tools": True,
                "supports_streaming": True,
                "supports_embeddings": True,
                "max_tokens": 4096,
            },
            {
                "id": "claude-3-opus",
                "name": "Claude 3 Opus",
                "provider": "anthropic",
                "supports_tools": True,
                "supports_streaming": True,
                "supports_embeddings": False,
                "max_tokens": 200000,
            },
        ]
    
    async def Chat(
        self,
        request: Any,  # ChatRequest
        context: grpc.aio.ServicerContext,
    ) -> Any:  # ChatResponse
        """
        非流式 Chat
        
        Args:
            request: ChatRequest 消息
            context: gRPC 上下文
            
        Returns:
            ChatResponse 消息
        """
        logger.info(f"Chat request with {len(request.messages)} messages")
        
        # 如果有 LLM adapter，使用它
        if self._llm_adapter:
            try:
                result = await self._llm_adapter.chat(
                    messages=self._convert_messages(request.messages),
                    model=request.model or self._default_model,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    tools=self._convert_tools(request.tools),
                )
                
                return self._build_chat_response(result, request.session_id)
            except Exception as e:
                logger.error(f"Chat error: {e}")
                return self._build_error_response(
                    context,
                    grpc.StatusCode.INTERNAL,
                    str(e),
                )
        else:
            # 模拟响应（无 LLM adapter 时）
            return self._build_mock_chat_response(request)
    
    async def StreamChat(
        self,
        request: Any,  # ChatRequest
        context: grpc.aio.ServicerContext,
    ) -> AsyncIterator[Any]:  # stream ChatChunk
        """
        流式 Chat
        
        Args:
            request: ChatRequest 消息
            context: gRPC 上下文
            
        Yields:
            ChatChunk 消息流
        """
        logger.info(f"StreamChat request with {len(request.messages)} messages")
        
        index = 0
        try:
            if self._llm_adapter:
                # 使用 LLM adapter 进行流式生成
                async for chunk in self._llm_adapter.stream_chat(
                    messages=self._convert_messages(request.messages),
                    model=request.model or self._default_model,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    tools=self._convert_tools(request.tools),
                ):
                    # 检查客户端是否已取消
                    if context.is_active() is False:
                        logger.info("Client cancelled stream")
                        return
                    
                    yield self._build_chat_chunk(chunk, index)
                    index += 1
            else:
                # 模拟流式响应
                async for chunk in self._mock_stream_response(request):
                    if context.is_active() is False:
                        logger.info("Client cancelled stream")
                        return
                    yield self._build_chat_chunk(chunk, index)
                    index += 1
                    await asyncio.sleep(0.01)  # 模拟流式延迟
                    
        except Exception as e:
            logger.error(f"StreamChat error: {e}")
            yield self._build_error_chunk(context, str(e))
    
    async def GetEmbedding(
        self,
        request: Any,  # EmbeddingRequest
        context: grpc.aio.ServicerContext,
    ) -> Any:  # EmbeddingResponse
        """
        获取文本嵌入向量
        
        Args:
            request: EmbeddingRequest 消息
            context: gRPC 上下文
            
        Returns:
            EmbeddingResponse 消息
        """
        logger.info(f"GetEmbedding request for text length: {len(request.text)}")
        
        if self._llm_adapter and hasattr(self._llm_adapter, 'get_embedding'):
            try:
                result = await self._llm_adapter.get_embedding(
                    text=request.text,
                    model=request.model or "text-embedding-ada-002",
                )
                return self._build_embedding_response(result)
            except Exception as e:
                logger.error(f"GetEmbedding error: {e}")
                return self._build_error_embedding_response(context, str(e))
        else:
            # 返回模拟嵌入向量
            return self._build_mock_embedding_response(request)
    
    async def GetModels(
        self,
        request: empty_pb2.Empty,
        context: grpc.aio.ServicerContext,
    ) -> Any:  # ModelList
        """
        获取可用模型列表
        
        Args:
            request: 空请求
            context: gRPC 上下文
            
        Returns:
            ModelList 消息
        """
        models = []
        for m in self._available_models:
            model_info = {
                "id": m["id"],
                "name": m["name"],
                "provider": m["provider"],
                "supports_tools": m["supports_tools"],
                "supports_streaming": m["supports_streaming"],
                "supports_embeddings": m["supports_embeddings"],
                "max_tokens": m.get("max_tokens"),
            }
            models.append(model_info)
        
        return self._build_model_list(models)
    
    # ========== 辅助方法 ==========
    
    def _convert_messages(self, messages: List[Any]) -> List[Dict[str, Any]]:
        """转换 Protobuf Message 到字典"""
        result = []
        for msg in messages:
            item = {
                "role": msg.role,
                "content": msg.content,
            }
            if msg.HasField("name"):
                item["name"] = msg.name
            if msg.HasField("tool_call_id"):
                item["tool_call_id"] = msg.tool_call_id
            if msg.tool_calls:
                item["tool_calls"] = [
                    {
                        "id": tc.id,
                        "name": tc.name,
                        "args": dict(tc.args.fields) if tc.args.fields else {},
                    }
                    for tc in msg.tool_calls
                ]
            result.append(item)
        return result
    
    def _convert_tools(self, tools: List[Any]) -> List[Dict[str, Any]]:
        """转换 Protobuf ToolDefinition 到字典"""
        result = []
        for tool in tools:
            item = {
                "name": tool.name,
                "description": tool.description,
                "parameters": dict(tool.parameters.fields) if tool.parameters.fields else {},
            }
            if tool.HasField("type"):
                item["type"] = tool.type
            result.append(item)
        return result
    
    def _build_chat_response(self, result: Dict[str, Any], session_id: Optional[str]) -> Any:
        """构建 ChatResponse"""
        # 注意：实际实现中需要使用生成的 proto 类
        response = {
            "content": result.get("content", ""),
            "tool_calls": result.get("tool_calls", []),
            "finish_reason": result.get("finish_reason", 1),
            "usage": result.get("usage", {"input_tokens": 0, "output_tokens": 0}),
            "model": result.get("model", "unknown"),
            "session_id": session_id,
        }
        return response
    
    def _build_mock_chat_response(self, request: Any) -> Any:
        """构建模拟的 ChatResponse"""
        return {
            "content": f"Echo: {request.messages[-1].content if request.messages else 'Hello'}",
            "tool_calls": [],
            "finish_reason": 1,  # FINISH_REASON_STOP
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "model": request.model or self._default_model,
            "session_id": request.session_id,
        }
    
    async def _mock_stream_response(self, request: Any) -> AsyncIterator[str]:
        """模拟流式响应"""
        base_text = f"Echo: {request.messages[-1].content if request.messages else 'Hello'}"
        words = base_text.split()
        
        for word in words:
            yield word + " "
    
    def _build_chat_chunk(self, chunk: Dict[str, Any], index: int) -> Any:
        """构建 ChatChunk"""
        return {
            "content_delta": chunk.get("content_delta", ""),
            "tool_call_delta": chunk.get("tool_call_delta"),
            "finish_reason": chunk.get("finish_reason"),
            "usage": chunk.get("usage"),
            "index": index,
        }
    
    def _build_embedding_response(self, result: Dict[str, Any]) -> Any:
        """构建 EmbeddingResponse"""
        return {
            "embedding": result.get("embedding", []),
            "dimensions": result.get("dimensions", len(result.get("embedding", []))),
            "model": result.get("model", "unknown"),
            "usage": result.get("usage", {"input_tokens": 0, "output_tokens": 0}),
        }
    
    def _build_mock_embedding_response(self, request: Any) -> Any:
        """构建模拟的 EmbeddingResponse"""
        dimensions = 1536  # OpenAI ada-002 默认维度
        import random
        embedding = [random.random() - 0.5 for _ in range(dimensions)]
        return {
            "embedding": embedding,
            "dimensions": dimensions,
            "model": request.model or "text-embedding-ada-002",
            "usage": {"input_tokens": len(request.text.split()), "output_tokens": 0},
        }
    
    def _build_error_embedding_response(self, context: grpc.aio.ServicerContext, error: str) -> Any:
        """构建错误的 EmbeddingResponse"""
        context.set_code(grpc.StatusCode.INTERNAL)
        context.set_details(error)
        return {
            "embedding": [],
            "dimensions": 0,
            "model": "error",
            "usage": {"input_tokens": 0, "output_tokens": 0},
        }
    
    def _build_model_list(self, models: List[Dict[str, Any]]) -> Any:
        """构建 ModelList"""
        return {"models": models}
    
    def _build_error_response(
        self,
        context: grpc.aio.ServicerContext,
        code: grpc.StatusCode,
        message: str,
    ) -> Any:
        """构建错误响应"""
        context.set_code(code)
        context.set_details(message)
        return {
            "content": "",
            "tool_calls": [],
            "finish_reason": 4,  # FINISH_REASON_ERROR
            "usage": {"input_tokens": 0, "output_tokens": 0},
            "model": "error",
        }
    
    def _build_error_chunk(
        self,
        context: grpc.aio.ServicerContext,
        error: str,
    ) -> Any:
        """构建错误 Chunk"""
        context.set_code(grpc.StatusCode.INTERNAL)
        context.set_details(error)
        return {
            "content_delta": "",
            "finish_reason": 4,  # FINISH_REASON_ERROR
            "index": 0,
        }


# ============================================================
# HermesMemory 服务实现
# ============================================================

class HermesMemoryServicer:
    """
    HermesMemory 服务实现
    
    提供记忆存取服务
    """
    
    def __init__(self, memory_backend: Optional[Any] = None):
        self._memory_backend = memory_backend
        self._local_storage: Dict[str, Dict[str, Any]] = {}  # 模拟本地存储
    
    async def Save(
        self,
        request: Any,  # SaveRequest
        context: grpc.aio.ServicerContext,
    ) -> Any:  # SaveResponse
        """
        保存记忆
        
        Args:
            request: SaveRequest 消息
            context: gRPC 上下文
            
        Returns:
            SaveResponse 消息
        """
        logger.info(f"Save memory: type={request.type}, content_length={len(request.content)}")
        
        import uuid
        memory_id = str(uuid.uuid4())
        
        self._local_storage[memory_id] = {
            "id": memory_id,
            "content": request.content,
            "type": request.type,
            "session_id": request.session_id if request.HasField("session_id") else None,
            "tenant_id": request.tenant_id if request.HasField("tenant_id") else None,
            "metadata": dict(request.metadata),
            "created_at": timestamp_pb2.Timestamp().GetCurrentTime(),
        }
        
        return {
            "memory_id": memory_id,
            "deduplicated": False,
        }
    
    async def Search(
        self,
        request: Any,  # SearchRequest
        context: grpc.aio.ServicerContext,
    ) -> Any:  # SearchResponse
        """
        搜索记忆
        
        Args:
            request: SearchRequest 消息
            context: gRPC 上下文
            
        Returns:
            SearchResponse 消息
        """
        start_time = time.time()
        query = request.query
        
        # 简单的关键词匹配（实际应使用向量相似度）
        results = []
        for memory_id, memory in self._local_storage.items():
            # 类型过滤
            if request.HasField("type") and memory["type"] != request.type:
                continue
            # 会话过滤
            if request.HasField("session_id") and memory["session_id"] != request.session_id:
                continue
            # 简单文本匹配
            if query.lower() in memory["content"].lower():
                score = 0.8  # 模拟相似度分数
                results.append({
                    "id": memory_id,
                    "content": memory["content"],
                    "type": memory["type"],
                    "score": score,
                    "created_at": memory["created_at"],
                    "metadata": memory["metadata"],
                    "session_id": memory["session_id"],
                })
        
        # 排序并限制数量
        results.sort(key=lambda x: x["score"], reverse=True)
        limit = request.limit if request.HasField("limit") else 10
        results = results[:limit]
        
        search_time_ms = (time.time() - start_time) * 1000
        
        return {
            "results": results,
            "total_count": len(results),
            "search_time_ms": search_time_ms,
        }
    
    async def GetContext(
        self,
        request: Any,  # GetContextRequest
        context: grpc.aio.ServicerContext,
    ) -> Any:  # GetContextResponse
        """
        获取上下文
        
        Args:
            request: GetContextRequest 消息
            context: gRPC 上下文
            
        Returns:
            GetContextResponse 消息
        """
        # 先搜索相关记忆
        search_request = {"query": request.query}
        search_response = await self.Search(search_request, context)
        
        # 组装上下文文本
        context_parts = []
        for item in search_response.get("results", []):
            context_parts.append(f"[记忆 {item['id'][:8]}]: {item['content']}")
        
        context_block = "\n\n".join(context_parts)
        
        # 估算 token 数（简单估算）
        total_tokens = len(context_block.split()) * 1.3
        
        return {
            "context_block": context_block,
            "items": search_response.get("results", []),
            "total_tokens": int(total_tokens),
        }
    
    async def Delete(
        self,
        request: Any,  # DeleteRequest
        context: grpc.aio.ServicerContext,
    ) -> Any:  # DeleteResponse
        """
        删除记忆
        
        Args:
            request: DeleteRequest 消息
            context: gRPC 上下文
            
        Returns:
            DeleteResponse 消息
        """
        memory_id = request.memory_id
        success = memory_id in self._local_storage
        
        if success:
            del self._local_storage[memory_id]
            logger.info(f"Deleted memory: {memory_id}")
        
        return {"success": success}
    
    async def ListBackends(
        self,
        request: empty_pb2.Empty,
        context: grpc.aio.ServicerContext,
    ) -> Any:  # MemoryBackendList
        """
        列出可用记忆后端
        
        Args:
            request: 空请求
            context: gRPC 上下文
            
        Returns:
            MemoryBackendList 消息
        """
        backends = [
            {
                "backend": 1,  # MEMORY_BACKEND_HOLOGRAPHIC
                "name": "Holographic",
                "is_available": True,
                "description": "本地 SQLite 存储（默认）",
            },
            {
                "backend": 4,  # MEMORY_BACKEND_MEM0
                "name": "Mem0",
                "is_available": True,
                "description": "Mem0 云服务",
            },
        ]
        return {"backends": backends}


# ============================================================
# HermesSkills 服务实现
# ============================================================

class HermesSkillsServicer:
    """
    HermesSkills 服务实现
    
    提供技能管理服务
    """
    
    def __init__(self, skills_registry: Optional[Any] = None):
        self._skills_registry = skills_registry
        self._local_skills: Dict[str, Dict[str, Any]] = {}
    
    async def ListSkills(
        self,
        request: Any,  # ListSkillsRequest
        context: grpc.aio.ServicerContext,
    ) -> Any:  # SkillList
        """
        列出技能
        
        Args:
            request: ListSkillsRequest 消息
            context: gRPC 上下文
            
        Returns:
            SkillList 消息
        """
        skills = list(self._local_skills.values())
        
        # 分类过滤
        if request.HasField("category"):
            skills = [s for s in skills if s.get("category") == request.category]
        
        # 搜索过滤
        if request.HasField("search"):
            search_term = request.search.lower()
            skills = [
                s for s in skills
                if search_term in s.get("name", "").lower()
                or search_term in s.get("description", "").lower()
            ]
        
        # 分页
        offset = request.offset if request.HasField("offset") else 0
        limit = request.limit if request.HasField("limit") else 100
        skills = skills[offset:offset + limit]
        
        return {
            "skills": skills,
            "total_count": len(skills),
        }
    
    async def GetSkill(
        self,
        request: Any,  # GetSkillRequest
        context: grpc.aio.ServicerContext,
    ) -> Any:  # SkillResponse
        """
        获取技能详情
        
        Args:
            request: GetSkillRequest 消息
            context: gRPC 上下文
            
        Returns:
            SkillResponse 消息
        """
        skill_id = request.skill_id
        skill = self._local_skills.get(skill_id)
        
        if not skill:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"Skill not found: {skill_id}")
            return {"success": False}
        
        return {
            "success": True,
            "skill": skill,
        }
    
    async def ExecuteSkill(
        self,
        request: Any,  # ExecuteSkillRequest
        context: grpc.aio.ServicerContext,
    ) -> Any:  # ExecuteSkillResponse
        """
        执行技能
        
        Args:
            request: ExecuteSkillRequest 消息
            context: gRPC 上下文
            
        Returns:
            ExecuteSkillResponse 消息
        """
        start_time = time.time()
        skill_id = request.skill_id
        task = request.task
        
        logger.info(f"ExecuteSkill: {skill_id}, task={task}")
        
        # 检查技能是否存在
        skill = self._local_skills.get(skill_id)
        if not skill:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"Skill not found: {skill_id}")
            return {
                "result": "",
                "success": False,
                "error": f"Skill not found: {skill_id}",
                "execution_time_ms": 0,
            }
        
        # 执行技能（这里应该是实际执行逻辑）
        result = f"Executed skill '{skill.get('name', skill_id)}' with task: {task}"
        execution_time_ms = (time.time() - start_time) * 1000
        
        # 更新使用计数
        skill["usage_count"] = skill.get("usage_count", 0) + 1
        
        return {
            "result": result,
            "success": True,
            "execution_time_ms": execution_time_ms,
        }
    
    async def StreamExecuteSkill(
        self,
        request: Any,  # ExecuteSkillRequest
        context: grpc.aio.ServicerContext,
    ) -> AsyncIterator[Any]:  # stream SkillExecutionChunk
        """
        流式执行技能
        
        Args:
            request: ExecuteSkillRequest 消息
            context: gRPC 上下文
            
        Yields:
            SkillExecutionChunk 消息流
        """
        index = 0
        skill_id = request.skill_id
        task = request.task
        
        logger.info(f"StreamExecuteSkill: {skill_id}, task={task}")
        
        # 模拟流式执行过程
        steps = [
            f"Starting skill execution: {skill_id}",
            f"Analyzing task: {task}",
            "Processing...",
            "Generating result...",
            "Complete!",
        ]
        
        for step in steps:
            if context.is_active() is False:
                logger.info("Client cancelled skill execution")
                return
            
            yield {
                "text_delta": step + "\n",
                "index": index,
                "done": index == len(steps) - 1,
            }
            index += 1
            await asyncio.sleep(0.1)
    
    async def CreateSkill(
        self,
        request: Any,  # CreateSkillRequest
        context: grpc.aio.ServicerContext,
    ) -> Any:  # SkillResponse
        """
        创建技能
        
        Args:
            request: CreateSkillRequest 消息
            context: gRPC 上下文
            
        Returns:
            SkillResponse 消息
        """
        import uuid
        skill_id = str(uuid.uuid4())
        
        now = timestamp_pb2.Timestamp().GetCurrentTime()
        skill = {
            "id": skill_id,
            "name": request.name,
            "description": request.description,
            "version": "1.0.0",
            "content": request.content,
            "category": request.category if request.HasField("category") else None,
            "tags": list(request.tags),
            "metadata": dict(request.metadata),
            "created_at": now,
            "updated_at": now,
            "usage_count": 0,
        }
        
        self._local_skills[skill_id] = skill
        logger.info(f"Created skill: {skill_id}, name={request.name}")
        
        return {
            "success": True,
            "skill": skill,
        }
    
    async def UpdateSkill(
        self,
        request: Any,  # UpdateSkillRequest
        context: grpc.aio.ServicerContext,
    ) -> Any:  # SkillResponse
        """
        更新技能
        
        Args:
            request: UpdateSkillRequest 消息
            context: gRPC 上下文
            
        Returns:
            SkillResponse 消息
        """
        skill_id = request.skill_id
        skill = self._local_skills.get(skill_id)
        
        if not skill:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"Skill not found: {skill_id}")
            return {"success": False}
        
        # 更新字段
        if request.HasField("name"):
            skill["name"] = request.name
        if request.HasField("description"):
            skill["description"] = request.description
        if request.HasField("content"):
            skill["content"] = request.content
        if request.HasField("category"):
            skill["category"] = request.category
        if request.tags:
            skill["tags"] = list(request.tags)
        if request.metadata:
            skill["metadata"] = dict(request.metadata)
        
        skill["updated_at"] = timestamp_pb2.Timestamp().GetCurrentTime()
        
        logger.info(f"Updated skill: {skill_id}")
        
        return {
            "success": True,
            "skill": skill,
        }
    
    async def DeleteSkill(
        self,
        request: Any,  # DeleteSkillRequest
        context: grpc.aio.ServicerContext,
    ) -> Any:  # DeleteSkillResponse
        """
        删除技能
        
        Args:
            request: DeleteSkillRequest 消息
            context: gRPC 上下文
            
        Returns:
            DeleteSkillResponse 消息
        """
        skill_id = request.skill_id
        success = skill_id in self._local_skills
        
        if success:
            del self._local_skills[skill_id]
            logger.info(f"Deleted skill: {skill_id}")
        
        return {"success": success}


# ============================================================
# HermesAgent 服务实现
# ============================================================

class HermesAgentServicer:
    """
    HermesAgent 服务实现
    
    提供完整代理执行服务
    """
    
    def __init__(
        self,
        agent_executor: Optional[Any] = None,
        max_iterations: int = 25,
    ):
        self._agent_executor = agent_executor
        self._max_iterations = max_iterations
        self._active_sessions: Dict[str, Dict[str, Any]] = {}
    
    async def RunTask(
        self,
        request: Any,  # TaskRequest
        context: grpc.aio.ServicerContext,
    ) -> Any:  # TaskResponse
        """
        非流式运行任务
        
        Args:
            request: TaskRequest 消息
            context: gRPC 上下文
            
        Returns:
            TaskResponse 消息
        """
        start_time = time.time()
        session_id = request.session_id or f"session_{int(start_time * 1000)}"
        
        logger.info(f"RunTask: session={session_id}, task={request.task[:100]}...")
        
        # 记录活动会话
        self._active_sessions[session_id] = {
            "task": request.task,
            "status": 2,  # RUNNING
            "start_time": start_time,
        }
        
        # 模拟任务执行
        iterations = min(request.max_iterations or self._max_iterations, 5)
        result = f"Task completed: {request.task[:50]}... (simulated)"
        execution_time_ms = (time.time() - start_time) * 1000
        
        # 更新会话状态
        self._active_sessions[session_id]["status"] = 6  # DONE
        self._active_sessions[session_id]["result"] = result
        
        steps = [
            {
                "iteration": i + 1,
                "action": f"Step {i + 1}",
                "thought": f"Thinking about step {i + 1}",
                "duration_ms": 100,
            }
            for i in range(iterations)
        ]
        
        return {
            "result": result,
            "success": True,
            "iterations": iterations,
            "usage": {"input_tokens": 100, "output_tokens": 50},
            "execution_time_ms": execution_time_ms,
            "steps": steps,
            "final_status": 6,  # DONE
        }
    
    async def StreamTask(
        self,
        request: Any,  # TaskRequest
        context: grpc.aio.ServicerContext,
    ) -> AsyncIterator[Any]:  # stream TaskChunk
        """
        流式运行任务
        
        Args:
            request: TaskRequest 消息
            context: gRPC 上下文
            
        Yields:
            TaskChunk 消息流
        """
        session_id = request.session_id or f"session_{int(time.time() * 1000)}"
        index = 0
        
        logger.info(f"StreamTask: session={session_id}")
        
        self._active_sessions[session_id] = {
            "task": request.task,
            "status": 2,  # RUNNING
            "start_time": time.time(),
        }
        
        # 模拟流式任务执行
        thoughts = [
            "Analyzing the task...",
            "Breaking down into steps...",
            "Executing step 1...",
            "Step 1 complete.",
            "Executing step 2...",
            "Step 2 complete.",
            "Finalizing results...",
        ]
        
        for thought in thoughts:
            if context.is_active() is False:
                logger.info("Client cancelled task")
                return
            
            yield {
                "thought": thought,
                "index": index,
                "status": 2,  # RUNNING
            }
            index += 1
            await asyncio.sleep(0.2)
        
        # 完成
        self._active_sessions[session_id]["status"] = 6  # DONE
        
        yield {
            "text_delta": f"Task completed: {request.task[:50]}...",
            "index": index,
            "status": 6,  # DONE
            "done": True,
        }
    
    async def GetStatus(
        self,
        request: Any,  # AgentStatusRequest
        context: grpc.aio.ServicerContext,
    ) -> Any:  # AgentStatus
        """
        获取 Agent 状态
        
        Args:
            request: AgentStatusRequest 消息
            context: gRPC 上下文
            
        Returns:
            AgentStatus 消息
        """
        session_id = request.session_id
        session = self._active_sessions.get(session_id)
        
        if not session:
            return {
                "status": 1,  # IDLE
                "session_id": session_id,
            }
        
        uptime = time.time() - session.get("start_time", time.time())
        
        return {
            "status": session.get("status", 1),
            "current_task": session.get("task"),
            "session_id": session_id,
            "uptime_seconds": uptime,
        }
    
    async def CancelTask(
        self,
        request: Any,  # CancelTaskRequest
        context: grpc.aio.ServicerContext,
    ) -> Any:  # CancelTaskResponse
        """
        取消任务
        
        Args:
            request: CancelTaskRequest 消息
            context: gRPC 上下文
            
        Returns:
            CancelTaskResponse 消息
        """
        session_id = request.session_id
        session = self._active_sessions.get(session_id)
        
        if session:
            session["status"] = 5  # ERROR
            session["cancel_reason"] = request.reason
            logger.info(f"Cancelled task: session={session_id}, reason={request.reason}")
            return {"success": True}
        
        return {"success": False}
    
    async def GetTaskHistory(
        self,
        request: Any,  # TaskHistoryRequest
        context: grpc.aio.ServicerContext,
    ) -> Any:  # TaskHistoryResponse
        """
        获取任务历史
        
        Args:
            request: TaskHistoryRequest 消息
            context: gRPC 上下文
            
        Returns:
            TaskHistoryResponse 消息
        """
        # 返回已完成的任务
        history = [
            {"result": s.get("result", ""), "success": True}
            for s in self._active_sessions.values()
            if s.get("status") == 6  # DONE
        ]
        
        limit = request.limit if request.HasField("limit") else 100
        offset = request.offset if request.HasField("offset") else 0
        history = history[offset:offset + limit]
        
        return {
            "tasks": history,
            "total_count": len(history),
        }


# ============================================================
# TaijiVerify 服务实现
# ============================================================

class TaijiVerifyServicer:
    """
    TaijiVerify 服务实现
    
    提供太极验证服务
    """
    
    def __init__(self, verify_engine: Optional[Any] = None):
        self._verify_engine = verify_engine
        self._rules = [
            {
                "id": "taiji_balance",
                "name": "太极平衡",
                "description": "验证内容是否符合阴阳平衡原则",
                "category": "core",
                "is_active": True,
                "weight": 0.3,
                "tags": ["太极", "平衡", "阴阳"],
            },
            {
                "id": "thirteen_gods_compliance",
                "name": "十三神合规",
                "description": "验证内容是否符合十三神规则",
                "category": "governance",
                "is_active": True,
                "weight": 0.4,
                "tags": ["十三神", "合规", "治理"],
            },
            {
                "id": "safety_check",
                "name": "安全检查",
                "description": "验证内容是否存在安全隐患",
                "category": "safety",
                "is_active": True,
                "weight": 0.3,
                "tags": ["安全", "风险", "检查"],
            },
        ]
        self._verify_history: List[Dict[str, Any]] = []
    
    async def Verify(
        self,
        request: Any,  # VerifyRequest
        context: grpc.aio.ServicerContext,
    ) -> Any:  # VerifyResponse
        """
        执行太极验证
        
        Args:
            request: VerifyRequest 消息
            context: gRPC 上下文
            
        Returns:
            VerifyResponse 消息
        """
        logger.info(f"TaijiVerify: content_type={request.content_type}")
        
        # 模拟验证过程
        details = []
        warnings = []
        errors = []
        total_score = 0.0
        passed_count = 0
        
        for rule in self._rules:
            if not rule["is_active"]:
                continue
            
            # 模拟验证结果
            score = 0.7 + (hash(rule["id"]) % 30) / 100  # 0.7-1.0
            passed = score >= 0.6
            
            details.append({
                "rule_id": rule["id"],
                "rule_name": rule["name"],
                "passed": passed,
                "score": score,
                "message": "验证通过" if passed else "需要改进",
            })
            
            total_score += score * rule.get("weight", 0.25)
            if passed:
                passed_count += 1
            else:
                errors.append(f"{rule['name']} 未通过验证")
        
        # 综合评分
        final_score = total_score / len([r for r in self._rules if r["is_active"]]) if self._rules else 0
        passed = passed_count == len([r for r in self._rules if r["is_active"]])
        
        now = timestamp_pb2.Timestamp()
        now.GetCurrentTime()
        
        result = "验证通过" if passed else "验证未通过"
        
        response = {
            "passed": passed,
            "result": result,
            "details": details,
            "score": final_score,
            "warnings": warnings,
            "errors": errors,
            "verified_at": now,
        }
        
        # 记录历史
        self._verify_history.append(response)
        
        return response
    
    async def BatchVerify(
        self,
        request: Any,  # BatchVerifyRequest
        context: grpc.aio.ServicerContext,
    ) -> Any:  # BatchVerifyResponse
        """
        批量验证
        
        Args:
            request: BatchVerifyRequest 消息
            context: gRPC 上下文
            
        Returns:
            BatchVerifyResponse 消息
        """
        start_time = time.time()
        results = []
        passed_count = 0
        failed_count = 0
        
        for item in request.items:
            if request.stop_on_first_error:
                response = await self.Verify(item, context)
                results.append(response)
                if response["passed"]:
                    passed_count += 1
                else:
                    failed_count += 1
                    break
            else:
                response = await self.Verify(item, context)
                results.append(response)
                if response["passed"]:
                    passed_count += 1
                else:
                    failed_count += 1
        
        total_time_ms = (time.time() - start_time) * 1000
        
        return {
            "results": results,
            "total_count": len(results),
            "passed_count": passed_count,
            "failed_count": failed_count,
            "total_time_ms": total_time_ms,
        }
    
    async def GetRules(
        self,
        request: empty_pb2.Empty,
        context: grpc.aio.ServicerContext,
    ) -> Any:  # RuleList
        """
        获取验证规则
        
        Args:
            request: 空请求
            context: gRPC 上下文
            
        Returns:
            RuleList 消息
        """
        return {"rules": self._rules}
    
    async def GetHistory(
        self,
        request: Any,  # HistoryRequest
        context: grpc.aio.ServicerContext,
    ) -> Any:  # HistoryResponse
        """
        获取验证历史
        
        Args:
            request: HistoryRequest 消息
            context: gRPC 上下文
            
        Returns:
            HistoryResponse 消息
        """
        items = self._verify_history
        
        # 过滤
        if request.HasField("passed_only") and request.passed_only:
            items = [i for i in items if i["passed"]]
        
        # 分页
        limit = request.limit if request.HasField("limit") else 100
        offset = request.offset if request.HasField("offset") else 0
        items = items[offset:offset + limit]
        
        return {
            "items": items,
            "total_count": len(items),
        }


# ============================================================
# gRPC 服务端启动
# ============================================================

async def create_server(
    config: Optional[GrpcServerConfig] = None,
    llm_adapter: Optional[Any] = None,
    memory_backend: Optional[Any] = None,
    skills_registry: Optional[Any] = None,
    agent_executor: Optional[Any] = None,
    verify_engine: Optional[Any] = None,
) -> grpc.aio.Server:
    """
    创建并配置 gRPC 服务端
    
    Args:
        config: 服务端配置
        llm_adapter: LLM 适配器
        memory_backend: 记忆后端
        skills_registry: 技能注册表
        agent_executor: Agent 执行器
        verify_engine: 验证引擎
        
    Returns:
        配置好的 gRPC 服务端
    """
    if config is None:
        config = GrpcServerConfig()
    
    # 创建服务端
    server = grpc.aio.server(
        options=[
            ("grpc.max_workers", config.max_workers),
            ("grpc.max_concurrent_rpcs", config.max_concurrent_rpcs),
        ],
    )
    
    # 添加服务实现
    # 注意：实际实现中需要使用生成的 grpc.add_*_servicer_to_server 函数
    
    # HermesProvider
    provider_servicer = HermesProviderServicer(llm_adapter=llm_adapter)
    # provider_pb2_grpc.add_HermesProviderServicer_to_server(provider_servicer, server)
    
    # HermesMemory
    memory_servicer = HermesMemoryServicer(memory_backend=memory_backend)
    # memory_pb2_grpc.add_HermesMemoryServicer_to_server(memory_servicer, server)
    
    # HermesSkills
    skills_servicer = HermesSkillsServicer(skills_registry=skills_registry)
    # skills_pb2_grpc.add_HermesSkillsServicer_to_server(skills_servicer, server)
    
    # HermesAgent
    agent_servicer = HermesAgentServicer(agent_executor=agent_executor)
    # agent_pb2_grpc.add_HermesAgentServicer_to_server(agent_servicer, server)
    
    # TaijiVerify
    verify_servicer = TaijiVerifyServicer(verify_engine=verify_engine)
    # taiji_verify_pb2_grpc.add_TaijiVerifyServicer_to_server(verify_servicer, server)
    
    # 绑定端口
    listen_addr = f"{config.host}:{config.port}"
    server.add_insecure_port(listen_addr)
    
    logger.info(f"gRPC server will listen on {listen_addr}")
    
    return server


async def serve(
    config: Optional[GrpcServerConfig] = None,
    **kwargs,
) -> None:
    """
    启动 gRPC 服务端
    
    Args:
        config: 服务端配置
        **kwargs: 传递给 create_server 的其他参数
    """
    server = await create_server(config, **kwargs)
    
    await server.start()
    logger.info("gRPC server started")
    
    # 等待终止信号
    await server.wait_for_termination()
