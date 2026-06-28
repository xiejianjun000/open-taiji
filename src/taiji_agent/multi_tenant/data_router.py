"""
数据路由器 - Data Router

基于租户ID的数据路由，实现跨租户数据访问控制和数据审计日志
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from taiji_agent.multi_tenant.isolation import (
    Tenant, TenantUser, TenantContext, TenantContextManager,
    IsolationStrategy, TenantStatus,
)


class AccessAction(str, Enum):
    """访问动作枚举"""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    LIST = "list"
    EXPORT = "export"


class AuditLevel(str, Enum):
    """审计级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AccessRequest:
    """访问请求"""
    tenant_id: str                      # 目标租户ID
    resource_type: str                   # 资源类型（session/memory/skill/config等）
    resource_id: str                    # 资源ID
    action: AccessAction                 # 访问动作
    user_id: Optional[str] = None       # 请求用户ID
    ip_address: Optional[str] = None     # IP地址
    user_agent: Optional[str] = None    # User-Agent
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AccessResult:
    """访问结果"""
    allowed: bool                       # 是否允许
    reason: str = ""                    # 原因
    tenant_id: str = ""                  # 实际访问的租户ID
    timestamp: datetime = field(default_factory=datetime.now)
    request: Optional[AccessRequest] = None


@dataclass
class AuditLog:
    """审计日志"""
    log_id: str                         # 日志ID
    tenant_id: str                      # 租户ID
    user_id: Optional[str]              # 用户ID
    action: AccessAction                # 操作类型
    resource_type: str                  # 资源类型
    resource_id: str                   # 资源ID
    result: str                         # 操作结果（success/failure）
    ip_address: Optional[str]          # IP地址
    user_agent: Optional[str]          # User-Agent
    details: Dict[str, Any]             # 详细信息
    level: AuditLevel                   # 审计级别
    timestamp: datetime                # 时间戳

    @classmethod
    def from_access_result(
        cls,
        result: AccessResult,
        resource_type: str,
        resource_id: str,
        level: AuditLevel = AuditLevel.INFO,
    ) -> AuditLog:
        """从访问结果创建审计日志"""
        return cls(
            log_id=f"audit-{uuid.uuid4().hex[:12]}",
            tenant_id=result.tenant_id,
            user_id=result.request.user_id if result.request else None,
            action=result.request.action if result.request else AccessAction.READ,
            resource_type=resource_type,
            resource_id=resource_id,
            result="success" if result.allowed else "failure",
            ip_address=result.request.ip_address if result.request else None,
            user_agent=result.request.user_agent if result.request else None,
            details={"reason": result.reason},
            level=level,
            timestamp=result.timestamp,
        )


class AuditLogger:
    """
    审计日志记录器

    记录所有跨租户数据访问操作
    """

    def __init__(self, log_dir: Path):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def log(self, audit_log: AuditLog) -> None:
        """记录审计日志"""
        log_file = self.log_dir / f"{audit_log.tenant_id}_{datetime.now().strftime('%Y%m%d')}.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "log_id": audit_log.log_id,
                "tenant_id": audit_log.tenant_id,
                "user_id": audit_log.user_id,
                "action": audit_log.action.value,
                "resource_type": audit_log.resource_type,
                "resource_id": audit_log.resource_id,
                "result": audit_log.result,
                "ip_address": audit_log.ip_address,
                "user_agent": audit_log.user_agent,
                "details": audit_log.details,
                "level": audit_log.level.value,
                "timestamp": audit_log.timestamp.isoformat(),
            }, ensure_ascii=False) + "\n")

    def query_logs(
        self,
        tenant_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        action: Optional[AccessAction] = None,
        user_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditLog]:
        """查询审计日志"""
        logs = []
        log_files = sorted(self.log_dir.glob(f"{tenant_id}_*.jsonl"), reverse=True)

        for log_file in log_files:
            if len(logs) >= limit:
                break

            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    if len(logs) >= limit:
                        break

                    try:
                        entry = json.loads(line.strip())

                        # 时间过滤
                        log_time = datetime.fromisoformat(entry["timestamp"])
                        if start_time and log_time < start_time:
                            continue
                        if end_time and log_time > end_time:
                            continue

                        # 动作过滤
                        if action and entry["action"] != action.value:
                            continue

                        # 用户过滤
                        if user_id and entry.get("user_id") != user_id:
                            continue

                        logs.append(AuditLog(
                            log_id=entry["log_id"],
                            tenant_id=entry["tenant_id"],
                            user_id=entry.get("user_id"),
                            action=AccessAction(entry["action"]),
                            resource_type=entry["resource_type"],
                            resource_id=entry["resource_id"],
                            result=entry["result"],
                            ip_address=entry.get("ip_address"),
                            user_agent=entry.get("user_agent"),
                            details=entry.get("details", {}),
                            level=AuditLevel(entry.get("level", "info")),
                            timestamp=log_time,
                        ))
                    except Exception:
                        continue

        return logs


class DataAccessPolicy:
    """
    数据访问策略

    定义跨租户数据访问的规则
    """

    # 允许跨租户访问的资源类型
    ALLOWED_CROSS_TENANT_TYPES = {"system_config", "global_skill"}

    # 管理员可访问的资源类型
    ADMIN_ACCESSIBLE_TYPES = {"*"}  # * 表示所有类型

    @classmethod
    def can_access_cross_tenant(cls, resource_type: str) -> bool:
        """判断资源类型是否允许跨租户访问"""
        return resource_type in cls.ALLOWED_CROSS_TENANT_TYPES

    @classmethod
    def requires_audit(cls, action: AccessAction, resource_type: str) -> bool:
        """判断操作是否需要审计"""
        # 写操作和删除操作都需要审计
        if action in (AccessAction.WRITE, AccessAction.DELETE):
            return True
        # 导出操作需要审计
        if action == AccessAction.EXPORT:
            return True
        # 敏感资源类型的读取也需要审计
        sensitive_types = {"config", "user_data", "billing"}
        if action == AccessAction.READ and resource_type in sensitive_types:
            return True
        return False

    @classmethod
    def get_audit_level(cls, action: AccessAction, allowed: bool) -> AuditLevel:
        """获取审计级别"""
        if not allowed:
            if action == AccessAction.DELETE:
                return AuditLevel.CRITICAL
            return AuditLevel.WARNING

        if action == AccessAction.DELETE:
            return AuditLevel.WARNING
        return AuditLevel.INFO


class DataRouter:
    """
    数据路由器

    实现基于租户ID的数据路由、访问控制和审计
    """

    def __init__(
        self,
        audit_logger: Optional[AuditLogger] = None,
        base_path: Optional[Path] = None,
    ):
        self.audit_logger = audit_logger
        self.base_path = base_path or Path.home() / ".taiji_agent"
        self._path_hooks: List[Callable[[str, str], Optional[Path]]] = []

    def register_path_hook(self, hook: Callable[[str, str], Optional[Path]]) -> None:
        """注册路径钩子"""
        self._path_hooks.append(hook)

    def route_path(
        self,
        tenant_id: str,
        resource_type: str,
        resource_id: str = "",
    ) -> Path:
        """
        根据租户ID和资源类型路由获取存储路径

        Args:
            tenant_id: 租户ID
            resource_type: 资源类型（sessions/memories/skills/configs/logs）
            resource_id: 资源ID（可选）

        Returns:
            资源存储路径
        """
        # 调用注册的路径钩子
        for hook in self._path_hooks:
            result = hook(tenant_id, resource_type)
            if result:
                return result / resource_id if resource_id else result

        # 默认路径
        base = self.base_path / "tenants" / tenant_id / resource_type
        if resource_id:
            return base / resource_id
        return base

    def check_access(self, request: AccessRequest) -> AccessResult:
        """
        检查数据访问权限

        Args:
            request: 访问请求

        Returns:
            访问结果
        """
        # 获取当前上下文
        current_context = TenantContextManager.get_context()

        # 检查请求是否来自正确的租户上下文
        if current_context:
            # 如果有上下文，检查租户ID是否匹配
            if current_context.tenant.tenant_id != request.tenant_id:
                # 允许跨租户访问某些资源
                if not DataAccessPolicy.can_access_cross_tenant(request.resource_type):
                    result = AccessResult(
                        allowed=False,
                        reason="Tenant context mismatch",
                        tenant_id=request.tenant_id,
                        request=request,
                    )
                    self._log_access(result, request.resource_type, request.resource_id)
                    return result

            # 检查租户状态
            if current_context.tenant.status != TenantStatus.ACTIVE:
                result = AccessResult(
                    allowed=False,
                    reason=f"Tenant is {current_context.tenant.status.value}",
                    tenant_id=request.tenant_id,
                    request=request,
                )
                self._log_access(result, request.resource_type, request.resource_id)
                return result

        # 允许访问
        result = AccessResult(
            allowed=True,
            reason="Access granted",
            tenant_id=request.tenant_id,
            request=request,
        )
        self._log_access(result, request.resource_type, request.resource_id)
        return result

    def check_own_resource(self, tenant_id: str, resource_tenant_id: str) -> bool:
        """检查资源是否属于请求的租户"""
        return tenant_id == resource_tenant_id

    def _log_access(
        self,
        result: AccessResult,
        resource_type: str,
        resource_id: str,
    ) -> None:
        """记录访问日志"""
        if not self.audit_logger:
            return

        # 判断是否需要审计
        if not result.request:
            return

        if not DataAccessPolicy.requires_audit(result.request.action, resource_type):
            return

        level = DataAccessPolicy.get_audit_level(
            result.request.action,
            result.allowed,
        )

        audit_log = AuditLog.from_access_result(
            result=result,
            resource_type=resource_type,
            resource_id=resource_id,
            level=level,
        )
        self.audit_logger.log(audit_log)

    # =========================================================================
    # 便捷方法
    # =========================================================================

    def read(
        self,
        tenant_id: str,
        resource_type: str,
        resource_id: str,
        user_id: Optional[str] = None,
    ) -> AccessResult:
        """读取数据（带权限检查）"""
        return self.check_access(AccessRequest(
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=AccessAction.READ,
            user_id=user_id,
        ))

    def write(
        self,
        tenant_id: str,
        resource_type: str,
        resource_id: str,
        user_id: Optional[str] = None,
    ) -> AccessResult:
        """写入数据（带权限检查）"""
        return self.check_access(AccessRequest(
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=AccessAction.WRITE,
            user_id=user_id,
        ))

    def delete(
        self,
        tenant_id: str,
        resource_type: str,
        resource_id: str,
        user_id: Optional[str] = None,
    ) -> AccessResult:
        """删除数据（带权限检查）"""
        return self.check_access(AccessRequest(
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=AccessAction.DELETE,
            user_id=user_id,
        ))

    def list(
        self,
        tenant_id: str,
        resource_type: str,
        user_id: Optional[str] = None,
    ) -> AccessResult:
        """列出数据（带权限检查）"""
        return self.check_access(AccessRequest(
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id="*",
            action=AccessAction.LIST,
            user_id=user_id,
        ))


class TenantAwareMiddleware:
    """
    租户感知中间件

    用于在请求处理前注入租户上下文
    """

    def __init__(self, tenant_manager):
        self.tenant_manager = tenant_manager

    def set_context_from_request(
        self,
        tenant_id: str,
        user_id: Optional[str] = None,
    ) -> Optional[TenantContext]:
        """
        从请求设置租户上下文

        Args:
            tenant_id: 租户ID
            user_id: 用户ID（可选）

        Returns:
            设置的上下文，失败返回None
        """
        tenant = self.tenant_manager.get_tenant(tenant_id)
        if not tenant:
            return None

        user = None
        if user_id:
            user = self.tenant_manager.get_user(user_id)
            if not user or user.tenant_id != tenant_id:
                return None

        context = TenantContext(tenant=tenant, user=user)
        TenantContextManager.set_context(context)
        return context

    def clear_context(self) -> None:
        """清除租户上下文"""
        TenantContextManager.clear_context()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.clear_context()


def create_data_router(log_dir: Optional[Path] = None) -> DataRouter:
    """创建数据路由器（便捷函数）"""
    audit_logger = None
    if log_dir:
        audit_logger = AuditLogger(log_dir)
    return DataRouter(audit_logger=audit_logger)
