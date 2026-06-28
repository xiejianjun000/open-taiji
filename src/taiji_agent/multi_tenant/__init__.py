"""
多租户数据模型模块 - Multi-Tenant Data Model Module

实现多租户隔离模型、租户管理、数据路由和RBAC权限控制

主要组件：
- isolation: 多租户隔离模型（TenantContext、StorageBackend）
- tenant_manager: 租户管理器（CRUD、配额管理）
- data_router: 数据路由器（路由、访问控制、审计）
- rbac: RBAC权限控制（角色、权限、分配）

Usage::
    # 创建租户管理器
    from taiji_agent.multi_tenant import create_tenant_manager, TenantContextManager

    manager = create_tenant_manager()

    # 创建租户
    tenant = manager.create_tenant(
        name="生态环境局",
        tier=TenantTier.ENTERPRISE,
        isolation_strategy=IsolationStrategy.SHARED,
    )

    # 创建部门
    dept = manager.create_department(
        tenant_id=tenant.tenant_id,
        name="环评科",
    )

    # 创建用户
    user = manager.create_user(
        tenant_id=tenant.tenant_id,
        department_id=dept.dept_id,
        username="admin",
        display_name="管理员",
        role="admin",
    )

    # 设置租户上下文
    context = manager.create_context(tenant, user)
    manager.set_context(context)

    # 使用数据路由器
    from taiji_agent.multi_tenant import create_data_router

    router = create_data_router()

    # 路由数据路径
    sessions_path = router.route_path(tenant.tenant_id, "sessions")
    memories_path = router.route_path(tenant.tenant_id, "memories")
"""

from __future__ import annotations

from taiji_agent.multi_tenant.isolation import (
    # 枚举
    IsolationStrategy,
    TenantStatus,
    TenantTier,
    # 数据模型
    Tenant,
    Department,
    TenantUser,
    TenantContext,
    RateLimitConfig,
    StorageConfig,
    # 上下文管理
    TenantContextManager,
    get_current_tenant_context,
    get_current_tenant,
    get_current_user,
    # 存储后端
    StorageBackend,
    SharedStorageBackend,
    LogicalStorageBackend,
    PhysicalStorageBackend,
    create_storage_backend,
)

from taiji_agent.multi_tenant.tenant_manager import (
    TenantStore,
    JsonTenantStore,
    TenantManager,
    create_tenant_manager,
)

from taiji_agent.multi_tenant.data_router import (
    AccessAction,
    AuditLevel,
    AccessRequest,
    AccessResult,
    AuditLog,
    AuditLogger,
    DataAccessPolicy,
    DataRouter,
    TenantAwareMiddleware,
    create_data_router,
)

from taiji_agent.multi_tenant.rbac import (
    ResourceType,
    Permission,
    RoleType,
    PermissionGrant,
    Role,
    RoleAssignment,
    PermissionChecker,
    PermissionDenied,
    RBACManager,
    create_rbac_manager,
)

__all__ = [
    # Isolation - 隔离模型
    "IsolationStrategy",
    "TenantStatus",
    "TenantTier",
    "Tenant",
    "Department",
    "TenantUser",
    "TenantContext",
    "RateLimitConfig",
    "StorageConfig",
    "TenantContextManager",
    "get_current_tenant_context",
    "get_current_tenant",
    "get_current_user",
    "StorageBackend",
    "SharedStorageBackend",
    "LogicalStorageBackend",
    "PhysicalStorageBackend",
    "create_storage_backend",
    # TenantManager - 租户管理
    "TenantStore",
    "JsonTenantStore",
    "TenantManager",
    "create_tenant_manager",
    # DataRouter - 数据路由
    "AccessAction",
    "AuditLevel",
    "AccessRequest",
    "AccessResult",
    "AuditLog",
    "AuditLogger",
    "DataAccessPolicy",
    "DataRouter",
    "TenantAwareMiddleware",
    "create_data_router",
    # RBAC - 权限控制
    "ResourceType",
    "Permission",
    "RoleType",
    "PermissionGrant",
    "Role",
    "RoleAssignment",
    "PermissionChecker",
    "PermissionDenied",
    "RBACManager",
    "create_rbac_manager",
]

__version__ = "1.0.0"
