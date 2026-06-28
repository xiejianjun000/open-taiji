# -*- coding: utf-8 -*-
"""
钩子系统模块。

提供事件总线、生命周期钩子和钩子管理功能。
支持发布/订阅模式、钩子优先级和中断机制。
"""

import asyncio
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set


class HookPhase(Enum):
    """钩子执行阶段"""
    PRE = auto()      # 前置钩子
    POST = auto()     # 后置钩子


@dataclass
class HookResult:
    """
    钩子执行结果。
    
    Attributes:
        hook_id: 钩子 ID
        event: 事件名称
        success: 是否成功
        data: 处理后的数据
        aborted: 是否中断后续处理
        error: 错误信息（如果有）
        duration_ms: 执行耗时（毫秒）
    """
    hook_id: str
    event: str
    success: bool
    data: Any = None
    aborted: bool = False
    error: Optional[str] = None
    duration_ms: float = 0.0


@dataclass
class HookInfo:
    """
    钩子信息。
    
    Attributes:
        hook_id: 钩子唯一标识
        event: 订阅的事件名称
        handler: 异步处理函数
        priority: 优先级（越小越先执行）
        plugin_id: 所属插件 ID
        description: 钩子描述
    """
    hook_id: str
    event: str
    handler: Callable[..., Any]
    priority: int = 100
    plugin_id: Optional[str] = None
    description: str = ""


class EventBus:
    """
    事件总线。
    
    提供发布/订阅功能，支持：
    - 同步/异步事件处理
    - 钩子优先级排序
    - 中断机制（通过返回 {"abort": True}）
    - 生命周期事件发射
    
    使用示例:
        event_bus = EventBus()
        
        # 订阅事件
        await event_bus.subscribe("tool:request", my_handler, priority=50)
        
        # 发布事件
        result = await event_bus.emit("tool:request", {"tool_name": "search"})
    """
    
    def __init__(self):
        """初始化事件总线"""
        # event -> List[HookInfo]
        self._subscriptions: Dict[str, List[HookInfo]] = defaultdict(list)
        # 事件统计
        self._stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {
            "total": 0, "success": 0, "failed": 0, "aborted": 0
        })
        # 全局事件锁（防止并发问题）
        self._lock = asyncio.Lock()
    
    async def subscribe(
        self,
        event: str,
        handler: Callable[..., Any],
        priority: int = 100,
        plugin_id: Optional[str] = None,
        description: str = "",
    ) -> str:
        """
        订阅事件。
        
        Args:
            event: 事件名称
            handler: 异步处理函数，接收 data，返回处理后的 data 或 {"abort": True}
            priority: 优先级，越小越先执行
            plugin_id: 插件 ID（用于追踪）
            description: 钩子描述
            
        Returns:
            钩子 ID
        """
        hook_id = str(uuid.uuid4())
        
        async with self._lock:
            hook_info = HookInfo(
                hook_id=hook_id,
                event=event,
                handler=handler,
                priority=priority,
                plugin_id=plugin_id,
                description=description,
            )
            self._subscriptions[event].append(hook_info)
            # 按优先级排序
            self._subscriptions[event].sort(key=lambda h: h.priority)
        
        return hook_id
    
    async def unsubscribe(self, hook_id: str) -> bool:
        """
        取消订阅。
        
        Args:
            hook_id: 钩子 ID
            
        Returns:
            是否成功取消
        """
        async with self._lock:
            for event_hooks in self._subscriptions.values():
                for i, hook in enumerate(event_hooks):
                    if hook.hook_id == hook_id:
                        event_hooks.pop(i)
                        return True
        return False
    
    async def unsubscribe_all(self, plugin_id: str) -> int:
        """
        取消指定插件的所有订阅。
        
        Args:
            plugin_id: 插件 ID
            
        Returns:
            取消的订阅数量
        """
        count = 0
        async with self._lock:
            for event in list(self._subscriptions.keys()):
                self._subscriptions[event] = [
                    h for h in self._subscriptions[event]
                    if h.plugin_id != plugin_id
                ]
                count += len([
                    h for h in self._subscriptions[event]
                    if h.plugin_id == plugin_id
                ])
        return count
    
    async def emit(
        self,
        event: str,
        data: Any = None,
        sync: bool = False,
    ) -> Any:
        """
        发布事件。
        
        按优先级顺序执行所有注册的钩子。
        如果某个钩子返回 {"abort": True}，后续钩子将不再执行。
        
        Args:
            event: 事件名称
            data: 事件数据
            sync: 是否同步执行（默认异步）
            
        Returns:
            最终处理后的数据
        """
        import time
        start_time = time.time()
        
        hooks = list(self._subscriptions.get(event, []))
        
        if not hooks:
            return data
        
        result = data
        aborted = False
        hook_results = []
        
        for hook in hooks:
            if aborted:
                break
            
            hook_result = await self._execute_hook(hook, event, result)
            hook_results.append(hook_result)
            
            if hook_result.aborted:
                aborted = True
                self._stats[event]["aborted"] += 1
            
            if hook_result.data is not None:
                result = hook_result.data
            
            if not hook_result.success:
                self._stats[event]["failed"] += 1
        
        duration_ms = (time.time() - start_time) * 1000
        self._stats[event]["total"] += 1
        
        # 统计成功
        if all(r.success for r in hook_results):
            self._stats[event]["success"] += 1
        
        return result
    
    async def _execute_hook(
        self,
        hook: HookInfo,
        event: str,
        data: Any,
    ) -> HookResult:
        """执行单个钩子"""
        import time
        start_time = time.time()
        
        try:
            # 支持同步和异步处理函数
            if asyncio.iscoroutinefunction(hook.handler):
                result_data = await hook.handler(data)
            else:
                result_data = hook.handler(data)
            
            # 检查是否需要中断
            aborted = False
            if isinstance(result_data, dict) and result_data.get("abort"):
                aborted = True
                if "data" in result_data:
                    result_data = result_data["data"]
            
            duration_ms = (time.time() - start_time) * 1000
            
            return HookResult(
                hook_id=hook.hook_id,
                event=event,
                success=True,
                data=result_data,
                aborted=aborted,
                duration_ms=duration_ms,
            )
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return HookResult(
                hook_id=hook.hook_id,
                event=event,
                success=False,
                data=data,
                error=str(e),
                duration_ms=duration_ms,
            )
    
    def get_hooks(self, event: str) -> List[HookInfo]:
        """
        获取指定事件的钩子列表。
        
        Args:
            event: 事件名称
            
        Returns:
            钩子信息列表
        """
        return list(self._subscriptions.get(event, []))
    
    def get_stats(self, event: Optional[str] = None) -> Dict[str, Any]:
        """
        获取事件统计。
        
        Args:
            event: 事件名称，None 表示所有事件
            
        Returns:
            统计信息字典
        """
        if event:
            return dict(self._stats.get(event, {}))
        return {event: dict(stats) for event, stats in self._stats.items()}
    
    def clear(self) -> None:
        """清空所有订阅"""
        self._subscriptions.clear()
        self._stats.clear()


class HookManager:
    """
    钩子管理器。
    
    管理系统级别的生命周期钩子，包括：
    - pre_process: 处理前钩子
    - post_process: 处理后钩子
    - pre_response: 响应前钩子
    - post_response: 响应后钩子
    """
    
    # 标准生命周期钩子名称
    PRE_PROCESS = "pre_process"
    POST_PROCESS = "post_process"
    PRE_RESPONSE = "pre_response"
    POST_RESPONSE = "post_response"
    
    def __init__(self, event_bus: EventBus):
        """
        初始化钩子管理器。
        
        Args:
            event_bus: 事件总线实例
        """
        self._event_bus = event_bus
        self._registered_hooks: Dict[str, Set[str]] = defaultdict(set)
    
    async def register_lifecycle_hooks(
        self,
        plugin_id: str,
        pre_process: Optional[Callable] = None,
        post_process: Optional[Callable] = None,
        pre_response: Optional[Callable] = None,
        post_response: Optional[Callable] = None,
    ) -> None:
        """
        注册生命周期钩子。
        
        Args:
            plugin_id: 插件 ID
            pre_process: 处理前钩子
            post_process: 处理后钩子
            pre_response: 响应前钩子
            post_response: 响应后钩子
        """
        if pre_process:
            hook_id = await self._event_bus.subscribe(
                self.PRE_PROCESS,
                pre_process,
                priority=100,
                plugin_id=plugin_id,
                description=f"{plugin_id}_pre_process",
            )
            self._registered_hooks[plugin_id].add(hook_id)
        
        if post_process:
            hook_id = await self._event_bus.subscribe(
                self.POST_PROCESS,
                post_process,
                priority=100,
                plugin_id=plugin_id,
                description=f"{plugin_id}_post_process",
            )
            self._registered_hooks[plugin_id].add(hook_id)
        
        if pre_response:
            hook_id = await self._event_bus.subscribe(
                self.PRE_RESPONSE,
                pre_response,
                priority=100,
                plugin_id=plugin_id,
                description=f"{plugin_id}_pre_response",
            )
            self._registered_hooks[plugin_id].add(hook_id)
        
        if post_response:
            hook_id = await self._event_bus.subscribe(
                self.POST_RESPONSE,
                post_response,
                priority=100,
                plugin_id=plugin_id,
                description=f"{plugin_id}_post_response",
            )
            self._registered_hooks[plugin_id].add(hook_id)
    
    async def unregister_hooks(self, plugin_id: str) -> int:
        """
        取消注册指定插件的所有钩子。
        
        Args:
            plugin_id: 插件 ID
            
        Returns:
            取消的钩子数量
        """
        hook_ids = self._registered_hooks.get(plugin_id, set())
        count = 0
        for hook_id in hook_ids:
            if await self._event_bus.unsubscribe(hook_id):
                count += 1
        del self._registered_hooks[plugin_id]
        return count


# 预定义的事件名称
class SystemEvents:
    """系统事件名称常量"""
    # 插件生命周期事件
    PLUGIN_BEFORE_LOAD = "plugin:before_load"
    PLUGIN_AFTER_LOAD = "plugin:after_load"
    PLUGIN_BEFORE_ACTIVATE = "plugin:before_activate"
    PLUGIN_AFTER_ACTIVATE = "plugin:after_activate"
    PLUGIN_BEFORE_DEACTIVATE = "plugin:before_deactivate"
    PLUGIN_AFTER_DEACTIVATE = "plugin:after_deactivate"
    PLUGIN_ERROR = "plugin:error"
    PLUGIN_HEALTH_CHANGE = "plugin:health_change"
    
    # 工具处理事件
    TOOL_REQUEST = "tool:request"
    TOOL_RESPONSE = "tool:response"
    
    # LLM 事件
    LLM_REQUEST = "llm:request"
    LLM_RESPONSE = "llm:response"
    
    # Prompt 组装事件
    PROMPT_ASSEMBLE = "prompt:assemble"
    
    # 验证相关事件
    VERIFY_COMPLIANCE_CHECK = "verify:compliance_check"
    
    # 环保领域事件
    ECO_LAW_QUERY = "eco:law_query"
    EMISSION_DATA_QUERY = "eco:emission_query"
    ASSESSMENT_GENERATE = "eco:assessment_generate"
