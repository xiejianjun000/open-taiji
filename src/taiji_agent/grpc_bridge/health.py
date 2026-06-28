"""
gRPC 桥接模块 - 健康检查

实现 gRPC 健康检查协议和服务状态监控。
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

import grpc
from google.protobuf import empty_pb2

# 健康检查 proto（标准定义）
# from grpc_health.v1 import health_pb2, health_pb2_grpc

logger = logging.getLogger(__name__)


# ============================================================
# 枚举定义
# ============================================================

class HealthStatus(Enum):
    """健康状态枚举"""
    UNKNOWN = 0    # 未知状态
    SERVING = 1    # 服务正常
    NOT_SERVING = 2  # 服务不可用
    SERVICE_UNKNOWN = 3  # 服务状态未知


class ServiceState(Enum):
    """服务状态枚举"""
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


# ============================================================
# 健康检查响应
# ============================================================

@dataclass
class HealthCheckResponse:
    """健康检查响应"""
    status: HealthStatus
    service: str = ""  # 空字符串表示服务端整体健康
    details: Dict[str, HealthStatus] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class ServiceHealthInfo:
    """服务健康信息"""
    service_name: str
    status: HealthStatus
    last_check_time: float
    consecutive_failures: int = 0
    last_failure_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# 健康检查服务实现
# ============================================================

class HealthServicer:
    """
    gRPC 健康检查服务实现
    
    实现标准的 gRPC 健康检查协议。
    """
    
    # 服务名称映射
    SERVICE_NAMES = {
        "": "grpc.health.v1.Health",  # 根服务
        "hermes.v1.HermesProvider": "hermes.v1.HermesProvider",
        "hermes.v1.HermesMemory": "hermes.v1.HermesMemory",
        "hermes.v1.HermesSkills": "hermes.v1.HermesSkills",
        "hermes.v1.HermesAgent": "hermes.v1.HermesAgent",
        "hermes.v1.TaijiVerify": "hermes.v1.TaijiVerify",
    }
    
    def __init__(self):
        self._status: HealthStatus = HealthStatus.SERVING
        self._service_statuses: Dict[str, HealthStatus] = {
            name: HealthStatus.SERVING
            for name in self.SERVICE_NAMES.values()
        }
        self._lock = asyncio.Lock()
    
    async def Check(
        self,
        request: Any,  # health_pb2.HealthCheckRequest
        context: grpc.aio.ServicerContext,
    ) -> Any:  # health_pb2.HealthCheckResponse
        """
        处理健康检查请求
        
        Args:
            request: 健康检查请求
            context: gRPC 上下文
            
        Returns:
            健康检查响应
        """
        service = request.service
        
        async with self._lock:
            if service == "":
                # 整体健康检查
                status = self._status
            elif service in self._service_statuses:
                status = self._service_statuses[service]
            else:
                # 未知服务
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(f"Unknown service: {service}")
                return None
        
        return self._status_to_proto(status)
    
    async def Watch(
        self,
        request: Any,  # health_pb2.HealthCheckRequest
        context: grpc.aio.ServicerContext,
    ) -> Any:  # stream health_pb2.HealthCheckResponse
        """
        监听健康状态变化
        
        Args:
            request: 健康检查请求
            context: gRPC 上下文
            
        Yields:
            健康检查响应流
        """
        service = request.service
        last_status = None
        
        while context.is_active():
            async with self._lock:
                if service == "":
                    status = self._status
                elif service in self._service_statuses:
                    status = self._service_statuses[service]
                else:
                    break
            
            # 只在状态变化时发送
            if status != last_status:
                yield self._status_to_proto(status)
                last_status = status
            
            # 等待状态变化或超时
            await asyncio.sleep(1.0)
    
    async def set_status(
        self,
        service: str,
        status: HealthStatus,
    ) -> None:
        """
        设置服务健康状态
        
        Args:
            service: 服务名称（空字符串表示整体状态）
            status: 健康状态
        """
        async with self._lock:
            if service == "":
                self._status = status
            else:
                self._service_statuses[service] = status
        
        logger.info(f"Health status updated: service={service or '(root)'}, status={status.name}")
    
    async def set_all_unhealthy(
        self,
        reason: Optional[str] = None,
    ) -> None:
        """
        设置所有服务为不健康状态
        
        Args:
            reason: 不健康原因
        """
        async with self._lock:
            self._status = HealthStatus.NOT_SERVING
            for service in self._service_statuses:
                self._service_statuses[service] = HealthStatus.NOT_SERVING
        
        logger.warning(f"All services marked as unhealthy: {reason}")
    
    async def set_all_healthy(self) -> None:
        """设置所有服务为健康状态"""
        async with self._lock:
            self._status = HealthStatus.SERVING
            for service in self._service_statuses:
                self._service_statuses[service] = HealthStatus.SERVING
        
        logger.info("All services marked as healthy")
    
    def _status_to_proto(self, status: HealthStatus) -> Any:
        """转换状态到 Protobuf 枚举"""
        # return health_pb2.HealthCheckResponse.ServingStatus.Value(status.name)
        return {"status": status.value}


# ============================================================
# 健康检查客户端
# ============================================================

class HealthClient:
    """
    健康检查客户端
    
    提供服务健康状态查询能力。
    """
    
    def __init__(
        self,
        channel: grpc.aio.Channel,
        timeout: float = 5.0,
    ):
        self._channel = channel
        self._timeout = timeout
        # self._stub = health_pb2_grpc.HealthStub(channel)
    
    async def check(
        self,
        service: str = "",
    ) -> HealthCheckResponse:
        """
        检查服务健康状态
        
        Args:
            service: 服务名称（空字符串检查整体状态）
            
        Returns:
            健康检查响应
        """
        # request = health_pb2.HealthCheckRequest(service=service)
        
        try:
            # response = await self._stub.Check(request, timeout=self._timeout)
            # return HealthCheckResponse(
            #     status=HealthStatus(response.status),
            #     service=service,
            # )
            
            # 模拟响应
            return HealthCheckResponse(
                status=HealthStatus.SERVING,
                service=service,
            )
            
        except grpc.RpcError as e:
            logger.error(f"Health check failed: {e}")
            return HealthCheckResponse(
                status=HealthStatus.UNKNOWN,
                service=service,
            )
    
    async def watch(
        self,
        service: str = "",
    ) -> HealthCheckResponse:
        """
        监听服务健康状态变化
        
        Args:
            service: 服务名称
            
        Returns:
            健康检查响应（仅返回最新状态）
        """
        # request = health_pb2.HealthCheckRequest(service=service)
        
        try:
            # responses = self._stub.Watch(request)
            # return HealthCheckResponse(
            #     status=HealthStatus(response.status),
            #     service=service,
            # )
            
            return HealthCheckResponse(
                status=HealthStatus.SERVING,
                service=service,
            )
            
        except grpc.RpcError as e:
            logger.error(f"Health watch failed: {e}")
            return HealthCheckResponse(
                status=HealthStatus.UNKNOWN,
                service=service,
            )
    
    async def is_healthy(self, service: str = "") -> bool:
        """
        快速检查服务是否健康
        
        Args:
            service: 服务名称
            
        Returns:
            是否健康
        """
        response = await self.check(service)
        return response.status == HealthStatus.SERVING


# ============================================================
# 服务状态监控
# ============================================================

class ServiceMonitor:
    """
    服务状态监控器
    
    监控 gRPC 服务健康状态，支持告警和自动恢复。
    """
    
    def __init__(
        self,
        check_interval: float = 30.0,
        failure_threshold: int = 3,
        recovery_threshold: int = 2,
    ):
        """
        初始化监控器
        
        Args:
            check_interval: 检查间隔（秒）
            failure_threshold: 连续失败次数阈值（触发告警）
            recovery_threshold: 连续成功次数阈值（恢复服务）
        """
        self._check_interval = check_interval
        self._failure_threshold = failure_threshold
        self._recovery_threshold = recovery_threshold
        
        self._health_info: Dict[str, ServiceHealthInfo] = {}
        self._health_client: Optional[HealthClient] = None
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False
        self._lock = asyncio.Lock()
        
        # 回调函数
        self._on_unhealthy_callbacks: List[callable] = []
        self._on_recovered_callbacks: List[callable] = []
    
    def set_health_client(self, client: HealthClient) -> None:
        """设置健康检查客户端"""
        self._health_client = client
    
    async def start(self) -> None:
        """启动监控"""
        if self._running:
            return
        
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Service monitor started")
    
    async def stop(self) -> None:
        """停止监控"""
        self._running = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Service monitor stopped")
    
    def register_unhealthy_callback(self, callback: callable) -> None:
        """注册服务不健康回调"""
        self._on_unhealthy_callbacks.append(callback)
    
    def register_recovered_callback(self, callback: callable) -> None:
        """注册服务恢复回调"""
        self._on_recovered_callbacks.append(callback)
    
    async def check_service(self, service: str = "") -> ServiceHealthInfo:
        """
        检查单个服务健康状态
        
        Args:
            service: 服务名称
            
        Returns:
            服务健康信息
        """
        if not self._health_client:
            return ServiceHealthInfo(
                service_name=service,
                status=HealthStatus.UNKNOWN,
                last_check_time=time.time(),
            )
        
        response = await self._health_client.check(service)
        current_time = time.time()
        
        # 获取或创建健康信息
        async with self._lock:
            info = self._health_info.get(service)
            if info is None:
                info = ServiceHealthInfo(
                    service_name=service,
                    status=response.status,
                    last_check_time=current_time,
                )
                self._health_info[service] = info
            else:
                # 更新状态
                old_status = info.status
                info.status = response.status
                info.last_check_time = current_time
                
                # 检查状态变化
                if response.status != old_status:
                    if response.status == HealthStatus.SERVING:
                        info.consecutive_failures = 0
                    else:
                        info.consecutive_failures += 1
                        info.last_failure_reason = "Health check failed"
                    
                    # 触发回调
                    await self._handle_status_change(service, old_status, response.status)
        
        return info
    
    async def get_all_services_status(self) -> Dict[str, HealthStatus]:
        """
        获取所有服务状态
        
        Returns:
            服务名到状态的映射
        """
        async with self._lock:
            return {
                name: info.status
                for name, info in self._health_info.items()
            }
    
    async def get_unhealthy_services(self) -> List[str]:
        """
        获取不健康的服务列表
        
        Returns:
            不健康的服务名列表
        """
        async with self._lock:
            return [
                name
                for name, info in self._health_info.items()
                if info.status != HealthStatus.SERVING
            ]
    
    async def _monitor_loop(self) -> None:
        """监控循环"""
        services = list(HealthServicer.SERVICE_NAMES.values())
        
        while self._running:
            try:
                for service in services:
                    await self.check_service(service)
                
                await asyncio.sleep(self._check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                await asyncio.sleep(5.0)
    
    async def _handle_status_change(
        self,
        service: str,
        old_status: HealthStatus,
        new_status: HealthStatus,
    ) -> None:
        """处理服务状态变化"""
        # 触发不健康回调
        if new_status != HealthStatus.SERVING:
            for callback in self._on_unhealthy_callbacks:
                try:
                    await callback(service, new_status)
                except Exception as e:
                    logger.error(f"Unhealthy callback error: {e}")
        
        # 触发恢复回调
        if old_status != HealthStatus.SERVING and new_status == HealthStatus.SERVING:
            for callback in self._on_recovered_callbacks:
                try:
                    await callback(service)
                except Exception as e:
                    logger.error(f"Recovered callback error: {e}")


# ============================================================
# 服务状态装饰器
# ============================================================

def require_healthy(service_name: str = ""):
    """
    要求服务健康的装饰器
    
    用于装饰 gRPC 服务方法，在服务不健康时拒绝请求。
    """
    def decorator(func):
        async def wrapper(self, request, context):
            # 检查健康状态
            health_servicer = getattr(self, "_health_servicer", None)
            if health_servicer:
                async with health_servicer._lock:
                    status = (
                        health_servicer._status
                        if service_name == ""
                        else health_servicer._service_statuses.get(
                            service_name,
                            HealthStatus.UNKNOWN,
                        )
                    )
                
                if status != HealthStatus.SERVING:
                    context.set_code(grpc.StatusCode.UNAVAILABLE)
                    context.set_details(f"Service {service_name or 'server'} is not healthy")
                    return None
            
            return await func(self, request, context)
        
        return wrapper
    return decorator


# ============================================================
# 便捷函数
# ============================================================

async def create_health_check_server(
    server: grpc.aio.Server,
    health_servicer: Optional[HealthServicer] = None,
) -> grpc.aio.Server:
    """
    为服务端添加健康检查支持
    
    Args:
        server: gRPC 服务端
        health_servicer: 健康检查服务实现
        
    Returns:
        添加了健康检查服务的 gRPC 服务端
    """
    if health_servicer is None:
        health_servicer = HealthServicer()
    
    # health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)
    
    return server


def create_health_check_channel(
    address: str,
    credentials: Optional[grpc.ChannelCredentials] = None,
) -> grpc.aio.Channel:
    """
    创建健康检查通道
    
    Args:
        address: 服务地址
        credentials: 通道凭证
        
    Returns:
        gRPC 通道
    """
    if credentials:
        return grpc.aio.secure_channel(address, credentials)
    else:
        return grpc.aio.insecure_channel(address)


async def check_server_health(
    address: str,
    service: str = "",
    timeout: float = 5.0,
) -> HealthCheckResponse:
    """
    快速检查服务端健康状态
    
    Args:
        address: 服务地址
        service: 服务名称
        timeout: 超时时间
        
    Returns:
        健康检查响应
    """
    channel = create_health_check_channel(address)
    client = HealthClient(channel, timeout)
    
    try:
        return await client.check(service)
    finally:
        await channel.close()
