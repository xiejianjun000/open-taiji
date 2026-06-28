"""
事件总线 - 来自 cgast/harness
"""

import asyncio
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Event:
    """事件"""

    name: str
    data: dict = field(default_factory=dict)


@dataclass
class Hook:
    """钩子"""

    handler: Callable
    priority: int = 0


class EventBus:
    """
    事件总线

    来自 cgast/harness 的事件驱动系统
    每个操作都会发出事件，插件可以订阅这些事件
    """

    def __init__(self):
        self._hooks: dict[str, list[Hook]] = defaultdict(list)
        self._event_history: list[Event] = []
        self._max_history = 1000

    def on(self, event_name: str, handler: Callable, priority: int = 0):
        """订阅事件"""
        hook = Hook(handler=handler, priority=priority)
        self._hooks[event_name].append(hook)
        # 按优先级排序
        self._hooks[event_name].sort(key=lambda h: -h.priority)

    def off(self, event_name: str, handler: Callable):
        """取消订阅"""
        self._hooks[event_name] = [h for h in self._hooks[event_name] if h.handler != handler]

    async def emit(self, event_name: str, data: Optional[dict[str, Any]] = None) -> Any:
        """发出事件"""
        event = Event(name=event_name, data=data or {})

        # 记录历史
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)

        # 调用所有钩子
        results = []
        for hook in self._hooks.get(event_name, []):
            try:
                if asyncio.iscoroutinefunction(hook.handler):
                    result = await hook.handler(event)
                else:
                    result = hook.handler(event)
                results.append(result)

                # 检查是否中止
                if isinstance(result, dict) and result.get("abort"):
                    return {"abort": True, "results": results}

            except Exception as e:
                results.append({"error": str(e)})

        return {"results": results}

    def emit_sync(self, event_name: str, data: Optional[dict[str, Any]] = None) -> Any:
        """同步发出事件"""
        event = Event(name=event_name, data=data or {})

        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)

        results = []
        for hook in self._hooks.get(event_name, []):
            try:
                result = hook.handler(event)
                results.append(result)

                if isinstance(result, dict) and result.get("abort"):
                    return {"abort": True, "results": results}
            except Exception as e:
                results.append({"error": str(e)})

        return {"results": results}

    def get_history(self, event_name: Optional[str] = None, limit: int = 100) -> list[Event]:
        """获取事件历史"""
        if event_name:
            return [e for e in self._event_history[-limit:] if e.name == event_name]
        return self._event_history[-limit:]


# 预定义事件
class Events:
    """预定义事件名称"""

    AGENT_START = "agent:start"
    AGENT_END = "agent:end"
    LLM_REQUEST = "llm:request"
    LLM_RESPONSE = "llm:response"
    TOOL_REQUEST = "tool:request"
    TOOL_RESULT = "tool:result"
    PROMPT_ASSEMBLE = "prompt:assemble"
    STATE_CHANGE = "state:change"
    ERROR = "error"
    LOOP_START = "loop:start"
    USER_INPUT = "user:input"
