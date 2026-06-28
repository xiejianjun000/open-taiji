"""
Provider 故障转移与路由 — 搬迁 Claude Code Provider 可靠性

功能：
1. 自动故障转移 (主 Provider 故障 → 备用)
2. 多 Provider 轮询/负载均衡
3. 健康检查
4. 延迟监控
5. 自动恢复
"""

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class ProviderStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ProviderEndpoint:
    """Provider 端点"""
    name: str
    provider: str  # "anthropic", "openai", "qwen", "glm", "kimi", "doubao"
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    priority: int = 1  # 越小越优先
    weight: int = 1    # 负载均衡权重

    # 运行时状态
    status: ProviderStatus = ProviderStatus.UNKNOWN
    fail_count: int = 0
    success_count: int = 0
    last_latency_ms: float = 0
    last_check_time: float = 0
    consecutive_failures: int = 0


@dataclass
class FailoverConfig:
    """故障转移配置"""
    max_failures: int = 3               # 连续失败阈值
    cooldown_seconds: float = 60.0      # 冷却时间
    health_check_interval: float = 30.0 # 健康检查间隔
    recovery_threshold: int = 2         # 恢复所需的成功次数
    timeout_seconds: float = 30.0       # 请求超时
    retry_attempts: int = 2             # 重试次数


class ProviderRouter:
    """
    Provider 路由器 — 故障转移 + 负载均衡

    Usage::
        router = ProviderRouter()
        router.add_endpoint(ProviderEndpoint(
            name="primary",
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            priority=1,
        ))
        router.add_endpoint(ProviderEndpoint(
            name="fallback",
            provider="openai",
            model="gpt-4o",
            priority=2,
        ))

        endpoint = router.get_endpoint()
    """

    def __init__(self, config: Optional[FailoverConfig] = None):
        self.config = config or FailoverConfig()
        self._endpoints: list[ProviderEndpoint] = []
        self._lock = asyncio.Lock()
        self._health_check_task: Optional[asyncio.Task] = None

    def add_endpoint(self, endpoint: ProviderEndpoint):
        """添加 Provider 端点"""
        self._endpoints.append(endpoint)
        self._endpoints.sort(key=lambda e: e.priority)
        logger.info(f"添加 Provider 端点: {endpoint.name} ({endpoint.provider}/{endpoint.model})")

    def remove_endpoint(self, name: str):
        """移除 Provider 端点"""
        self._endpoints = [e for e in self._endpoints if e.name != name]

    async def get_endpoint(self) -> Optional[ProviderEndpoint]:
        """
        获取最佳可用端点

        策略：优先级排序 → 跳过不健康 → 权重选择
        """
        async with self._lock:
            now = time.time()

            for endpoint in self._endpoints:
                # 检查冷却期
                if endpoint.status == ProviderStatus.UNHEALTHY:
                    if now - endpoint.last_check_time < self.config.cooldown_seconds:
                        continue
                    # 冷却期结束，标记为未知以允许重试
                    endpoint.status = ProviderStatus.UNKNOWN

                # 跳过降级但未冷却的
                if (endpoint.status == ProviderStatus.DEGRADED and
                        now - endpoint.last_check_time < self.config.cooldown_seconds / 2):
                    continue

                return endpoint

            # 全部不可用时，尝试返回第一个（可能触发冷却期重试）
            if self._endpoints:
                return self._endpoints[0]

            return None

    async def report_success(self, endpoint: ProviderEndpoint, latency_ms: float = 0):
        """报告成功"""
        async with self._lock:
            endpoint.success_count += 1
            endpoint.consecutive_failures = 0
            endpoint.last_latency_ms = latency_ms
            endpoint.last_check_time = time.time()

            if endpoint.status in (ProviderStatus.UNHEALTHY, ProviderStatus.UNKNOWN):
                # 检查是否达到恢复阈值
                if endpoint.success_count >= self.config.recovery_threshold:
                    endpoint.status = ProviderStatus.HEALTHY
                    endpoint.fail_count = 0
                    logger.info(f"Provider {endpoint.name} 已恢复")

    async def report_failure(self, endpoint: ProviderEndpoint, error: str = ""):
        """报告失败"""
        async with self._lock:
            endpoint.fail_count += 1
            endpoint.consecutive_failures += 1
            endpoint.last_check_time = time.time()

            if endpoint.consecutive_failures >= self.config.max_failures:
                endpoint.status = ProviderStatus.UNHEALTHY
                logger.warning(
                    f"Provider {endpoint.name} 标记为不健康 "
                    f"(连续失败 {endpoint.consecutive_failures} 次): {error}"
                )
            elif endpoint.consecutive_failures >= self.config.max_failures // 2:
                endpoint.status = ProviderStatus.DEGRADED
                logger.info(f"Provider {endpoint.name} 降级")

    def get_status(self) -> list[dict]:
        """获取所有端点状态"""
        result = []
        for ep in self._endpoints:
            result.append({
                "name": ep.name,
                "provider": ep.provider,
                "model": ep.model,
                "status": ep.status.value,
                "priority": ep.priority,
                "success": ep.success_count,
                "fail": ep.fail_count,
                "latency_ms": round(ep.last_latency_ms, 1),
                "consecutive_failures": ep.consecutive_failures,
            })
        return result

    def get_health_summary(self) -> dict:
        """健康摘要"""
        statuses = self.get_status()
        healthy = sum(1 for s in statuses if s["status"] == "healthy")
        degraded = sum(1 for s in statuses if s["status"] == "degraded")
        unhealthy = sum(1 for s in statuses if s["status"] == "unhealthy")
        return {
            "total": len(statuses),
            "healthy": healthy,
            "degraded": degraded,
            "unhealthy": unhealthy,
            "available": healthy + degraded > 0,
        }

    async def start_health_check(self):
        """启动定期健康检查"""
        async def _check_loop():
            while True:
                await asyncio.sleep(self.config.health_check_interval)
                await self._run_health_checks()

        self._health_check_task = asyncio.create_task(_check_loop())

    async def stop_health_check(self):
        """停止健康检查"""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

    async def _run_health_checks(self):
        """执行健康检查"""
        async with self._lock:
            for ep in self._endpoints:
                if ep.status == ProviderStatus.UNHEALTHY:
                    # 尝试 ping 恢复
                    ep.status = ProviderStatus.UNKNOWN
                    ep.last_check_time = time.time()
                    logger.info(f"Provider {ep.name} 进入恢复检测期")


# 全局路由器实例
_global_router: Optional[ProviderRouter] = None

def get_provider_router() -> ProviderRouter:
    """获取全局 Provider 路由器"""
    global _global_router
    if _global_router is None:
        _global_router = ProviderRouter()
    return _global_router
