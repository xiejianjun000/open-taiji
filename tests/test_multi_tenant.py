"""
多租户模块测试 - Multi-Tenant Module Tests

测试覆盖：
- 租户隔离模型（TenantContext、StorageBackend）
- 租户管理（CRUD、配额管理）
- 数据路由（路由、访问控制、审计）
- RBAC权限控制（角色、权限、分配）
"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List
import shutil

from taiji_agent.multi_tenant import (
    # 隔离模型
    IsolationStrategy,
    TenantStatus,
    TenantTier,
    Tenant,
    Department,
    TenantUser,
    TenantContext,
    RateLimitConfig,
    StorageConfig,
    TenantContextManager,
    get_current_tenant_context,
    get_current_tenant,
    get_current_user,
    SharedStorageBackend,
    LogicalStorageBackend,
    PhysicalStorageBackend,
    create_storage_backend,
    # 租户管理
    JsonTenantStore,
    TenantManager,
    create_tenant_manager,
    # 数据路由
    AccessAction,
    AuditLevel,
    AccessRequest,
    AccessResult,
    AuditLogger,
    DataRouter,
    create_data_router,
    # RBAC
    ResourceType,
    Permission,
    RoleType,
    Role,
    RoleAssignment,
    RBACManager,
    create_rbac_manager,
    PermissionDenied,
)


class TestIsolationModel(unittest.TestCase):
    """测试租户隔离模型"""

    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.base_path = Path(self.temp_dir)

    def tearDown(self):
        """测试后清理"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        TenantContextManager.clear_context()

    def test_tenant_creation(self):
        """测试租户创建"""
        tenant = Tenant.create(
            name="测试租户",
            tier=TenantTier.PRO,
            isolation_strategy=IsolationStrategy.SHARED,
        )

        self.assertEqual(tenant.name, "测试租户")
        self.assertEqual(tenant.tier, TenantTier.PRO)
        self.assertEqual(tenant.isolation_strategy, IsolationStrategy.SHARED)
        self.assertEqual(tenant.status, TenantStatus.ACTIVE)
        self.assertTrue(tenant.tenant_id.startswith("tenant-"))

    def test_department_creation(self):
        """测试部门创建"""
        dept = Department.create(
            tenant_id="tenant-123",
            name="测试部门",
            dept_type="business",
        )

        self.assertEqual(dept.tenant_id, "tenant-123")
        self.assertEqual(dept.name, "测试部门")
        self.assertEqual(dept.dept_type, "business")
        self.assertTrue(dept.dept_id.startswith("dept-"))

    def test_user_creation(self):
        """测试用户创建"""
        user = TenantUser.create(
            tenant_id="tenant-123",
            department_id="dept-456",
            username="testuser",
            display_name="测试用户",
            role="user",
        )

        self.assertEqual(user.tenant_id, "tenant-123")
        self.assertEqual(user.department_id, "dept-456")
        self.assertEqual(user.username, "testuser")
        self.assertEqual(user.display_name, "测试用户")
        self.assertEqual(user.role, "user")
        self.assertEqual(user.status, "active")
        self.assertTrue(user.user_id.startswith("user-"))

    def test_tenant_context(self):
        """测试租户上下文"""
        tenant = Tenant.create(name="上下文测试租户")
        user = TenantUser.create(
            tenant_id=tenant.tenant_id,
            department_id="dept-001",
            username="ctxuser",
            display_name="上下文用户",
        )

        context = TenantContext(tenant=tenant, user=user)

        TenantContextManager.set_context(context)

        self.assertEqual(get_current_tenant_context(), context)
        self.assertEqual(get_current_tenant(), tenant)
        self.assertEqual(get_current_user(), user)

    def test_context_clear(self):
        """测试上下文清除"""
        tenant = Tenant.create(name="清除测试")
        context = TenantContext(tenant=tenant)
        TenantContextManager.set_context(context)

        TenantContextManager.clear_context()

        self.assertIsNone(get_current_tenant_context())
        self.assertIsNone(get_current_tenant())
        self.assertIsNone(get_current_user())


class TestStorageBackends(unittest.TestCase):
    """测试存储后端"""

    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.base_path = Path(self.temp_dir)

    def tearDown(self):
        """测试后清理"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_shared_storage_backend(self):
        """测试共享存储后端"""
        backend = SharedStorageBackend(self.base_path)

        tenant_id = "tenant-test-001"
        backend.ensure_tenant_dirs(tenant_id)

        # 验证目录创建
        self.assertTrue(backend.get_tenant_path(tenant_id).exists())
        self.assertTrue(backend.get_sessions_path(tenant_id).exists())
        self.assertTrue(backend.get_memories_path(tenant_id).exists())
        self.assertTrue(backend.get_skills_path(tenant_id).exists())
        self.assertTrue(backend.get_configs_path(tenant_id).exists())
        self.assertTrue(backend.get_logs_path(tenant_id).exists())

        # 验证路径结构
        expected_base = self.base_path / "tenants" / tenant_id
        self.assertEqual(backend.get_tenant_path(tenant_id), expected_base)
        self.assertEqual(backend.get_sessions_path(tenant_id), expected_base / "sessions")

    def test_logical_storage_backend(self):
        """测试逻辑隔离存储后端"""
        backend = LogicalStorageBackend(self.base_path)

        tenant_id = "tenant-logical-001"
        backend.ensure_tenant_dirs(tenant_id)

        # 验证数据库路径
        self.assertTrue(backend.get_db_path(tenant_id).parent.exists())
        self.assertTrue(backend.get_sessions_path(tenant_id).exists())

    def test_physical_storage_backend(self):
        """测试物理隔离存储后端"""
        backend = PhysicalStorageBackend(self.base_path)

        tenant_id = "tenant-physical-001"
        backend.ensure_tenant_dirs(tenant_id)

        # 验证独立路径
        expected_path = self.base_path / "instances" / tenant_id
        self.assertEqual(backend.get_tenant_path(tenant_id), expected_path)
        self.assertTrue(backend.get_sessions_path(tenant_id).exists())

    def test_create_storage_backend(self):
        """测试创建存储后端工厂函数"""
        shared = create_storage_backend(IsolationStrategy.SHARED, self.base_path)
        self.assertIsInstance(shared, SharedStorageBackend)

        logical = create_storage_backend(IsolationStrategy.LOGICAL, self.base_path)
        self.assertIsInstance(logical, LogicalStorageBackend)

        physical = create_storage_backend(IsolationStrategy.PHYSICAL, self.base_path)
        self.assertIsInstance(physical, PhysicalStorageBackend)


class TestTenantManager(unittest.TestCase):
    """测试租户管理器"""

    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.store_path = Path(self.temp_dir) / "data"
        self.base_path = Path(self.temp_dir)

        self.store = JsonTenantStore(self.store_path)
        self.manager = TenantManager(store=self.store, base_path=self.base_path)

    def tearDown(self):
        """测试后清理"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        TenantContextManager.clear_context()

    def test_create_tenant(self):
        """测试创建租户"""
        tenant = self.manager.create_tenant(
            name="测试租户",
            tier=TenantTier.PRO,
            isolation_strategy=IsolationStrategy.SHARED,
        )

        self.assertIsNotNone(tenant.tenant_id)
        self.assertEqual(tenant.name, "测试租户")
        self.assertEqual(tenant.tier, TenantTier.PRO)
        self.assertEqual(tenant.status, TenantStatus.ACTIVE)

    def test_get_tenant(self):
        """测试获取租户"""
        created = self.manager.create_tenant(name="获取测试租户")
        retrieved = self.manager.get_tenant(created.tenant_id)

        self.assertEqual(created.tenant_id, retrieved.tenant_id)
        self.assertEqual(created.name, retrieved.name)

    def test_list_tenants(self):
        """测试列出租户"""
        self.manager.create_tenant(name="租户1")
        self.manager.create_tenant(name="租户2")
        self.manager.create_tenant(name="租户3")

        tenants = self.manager.list_tenants()
        self.assertEqual(len(tenants), 3)

    def test_update_tenant(self):
        """测试更新租户"""
        tenant = self.manager.create_tenant(name="更新前名称")
        tenant.name = "更新后名称"
        result = self.manager.update_tenant(tenant)

        self.assertTrue(result)
        updated = self.manager.get_tenant(tenant.tenant_id)
        self.assertEqual(updated.name, "更新后名称")

    def test_suspend_tenant(self):
        """测试暂停租户"""
        tenant = self.manager.create_tenant(name="暂停测试")
        result = self.manager.suspend_tenant(tenant.tenant_id)

        self.assertTrue(result)
        updated = self.manager.get_tenant(tenant.tenant_id)
        self.assertEqual(updated.status, TenantStatus.SUSPENDED)

    def test_delete_tenant(self):
        """测试删除租户（软删除）"""
        tenant = self.manager.create_tenant(name="删除测试")
        result = self.manager.delete_tenant(tenant.tenant_id)

        self.assertTrue(result)
        # 软删除后仍能获取到租户（状态为deleted）
        deleted = self.manager.get_tenant(tenant.tenant_id)
        self.assertIsNone(deleted)  # JsonTenantStore的get_tenant会过滤deleted状态

    def test_create_department(self):
        """测试创建部门"""
        tenant = self.manager.create_tenant(name="部门测试租户")
        dept = self.manager.create_department(
            tenant_id=tenant.tenant_id,
            name="环评科",
            dept_type="business",
        )

        self.assertIsNotNone(dept)
        self.assertEqual(dept.tenant_id, tenant.tenant_id)
        self.assertEqual(dept.name, "环评科")

    def test_list_departments(self):
        """测试列出部门"""
        tenant = self.manager.create_tenant(name="部门列表测试")
        self.manager.create_department(tenant_id=tenant.tenant_id, name="部门1")
        self.manager.create_department(tenant_id=tenant.tenant_id, name="部门2")

        depts = self.manager.list_departments(tenant.tenant_id)
        self.assertEqual(len(depts), 2)

    def test_create_user(self):
        """测试创建用户"""
        tenant = self.manager.create_tenant(name="用户测试租户")
        dept = self.manager.create_department(tenant_id=tenant.tenant_id, name="测试部门")

        user = self.manager.create_user(
            tenant_id=tenant.tenant_id,
            department_id=dept.dept_id,
            username="testuser",
            display_name="测试用户",
            role="user",
        )

        self.assertIsNotNone(user)
        self.assertEqual(user.username, "testuser")
        self.assertEqual(user.tenant_id, tenant.tenant_id)

    def test_get_user_by_username(self):
        """测试根据用户名获取用户"""
        tenant = self.manager.create_tenant(name="用户名查询测试")
        dept = self.manager.create_department(tenant_id=tenant.tenant_id, name="部门")
        self.manager.create_user(
            tenant_id=tenant.tenant_id,
            department_id=dept.dept_id,
            username="uniqueuser",
            display_name="唯一用户",
        )

        user = self.manager.get_user_by_username(tenant.tenant_id, "uniqueuser")
        self.assertIsNotNone(user)
        self.assertEqual(user.username, "uniqueuser")

    def test_duplicate_username(self):
        """测试重复用户名"""
        tenant = self.manager.create_tenant(name="重复用户名测试")
        dept = self.manager.create_department(tenant_id=tenant.tenant_id, name="部门")

        self.manager.create_user(
            tenant_id=tenant.tenant_id,
            department_id=dept.dept_id,
            username="duplicate",
            display_name="用户1",
        )

        # 尝试创建同名用户应该失败
        duplicate = self.manager.create_user(
            tenant_id=tenant.tenant_id,
            department_id=dept.dept_id,
            username="duplicate",
            display_name="用户2",
        )

        self.assertIsNone(duplicate)

    def test_disable_user(self):
        """测试禁用用户"""
        tenant = self.manager.create_tenant(name="禁用用户测试")
        dept = self.manager.create_department(tenant_id=tenant.tenant_id, name="部门")
        user = self.manager.create_user(
            tenant_id=tenant.tenant_id,
            department_id=dept.dept_id,
            username="disableuser",
            display_name="禁用用户",
        )

        result = self.manager.disable_user(user.user_id)
        self.assertTrue(result)

        updated = self.manager.get_user(user.user_id)
        self.assertEqual(updated.status, "disabled")

    def test_rate_limit_check(self):
        """测试速率限制检查"""
        tenant = self.manager.create_tenant(name="速率限制测试")
        self.assertTrue(self.manager.check_rate_limit(tenant.tenant_id))

    def test_storage_quota_check(self):
        """测试存储配额检查"""
        tenant = self.manager.create_tenant(name="配额测试")
        self.assertTrue(self.manager.check_storage_quota(tenant.tenant_id, 50))

        # 超出配额
        self.assertFalse(self.manager.check_storage_quota(tenant.tenant_id, 1000000))

    def test_context_management(self):
        """测试上下文管理"""
        tenant = self.manager.create_tenant(name="上下文测试")
        dept = self.manager.create_department(tenant_id=tenant.tenant_id, name="部门")
        user = self.manager.create_user(
            tenant_id=tenant.tenant_id,
            department_id=dept.dept_id,
            username="ctxuser",
            display_name="上下文用户",
        )

        context = self.manager.create_context(tenant, user)
        self.manager.set_context(context)

        self.assertEqual(get_current_tenant(), tenant)
        self.assertEqual(get_current_user(), user)


class TestDataRouter(unittest.TestCase):
    """测试数据路由器"""

    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.log_dir = Path(self.temp_dir) / "logs"
        self.base_path = Path(self.temp_dir)

        self.audit_logger = AuditLogger(self.log_dir)
        self.router = DataRouter(audit_logger=self.audit_logger, base_path=self.base_path)

    def tearDown(self):
        """测试后清理"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        TenantContextManager.clear_context()

    def test_route_path(self):
        """测试路径路由"""
        tenant_id = "tenant-route-001"

        sessions_path = self.router.route_path(tenant_id, "sessions")
        self.assertEqual(sessions_path, self.base_path / "tenants" / tenant_id / "sessions")

        memories_path = self.router.route_path(tenant_id, "memories", "mem-001")
        self.assertEqual(memories_path, self.base_path / "tenants" / tenant_id / "memories" / "mem-001")

    def test_check_access_without_context(self):
        """测试无上下文时的访问检查"""
        request = AccessRequest(
            tenant_id="tenant-access-001",
            resource_type="sessions",
            resource_id="session-001",
            action=AccessAction.READ,
        )

        result = self.router.check_access(request)
        self.assertTrue(result.allowed)

    def test_check_access_with_context(self):
        """测试有上下文时的访问检查"""
        tenant = Tenant.create(name="上下文访问测试")
        context = TenantContext(tenant=tenant)
        TenantContextManager.set_context(context)

        request = AccessRequest(
            tenant_id=tenant.tenant_id,
            resource_type="sessions",
            resource_id="session-001",
            action=AccessAction.READ,
        )

        result = self.router.check_access(request)
        self.assertTrue(result.allowed)

    def test_cross_tenant_access_denied(self):
        """测试跨租户访问被拒绝"""
        tenant = Tenant.create(name="租户A")
        context = TenantContext(tenant=tenant)
        TenantContextManager.set_context(context)

        # 尝试访问租户B的资源
        request = AccessRequest(
            tenant_id="tenant-other",
            resource_type="sessions",
            resource_id="session-001",
            action=AccessAction.READ,
        )

        result = self.router.check_access(request)
        self.assertFalse(result.allowed)

    def test_suspended_tenant_access_denied(self):
        """测试暂停租户访问被拒绝"""
        tenant = Tenant.create(name="暂停测试")
        tenant.status = TenantStatus.SUSPENDED
        context = TenantContext(tenant=tenant)
        TenantContextManager.set_context(context)

        request = AccessRequest(
            tenant_id=tenant.tenant_id,
            resource_type="sessions",
            resource_id="session-001",
            action=AccessAction.READ,
        )

        result = self.router.check_access(request)
        self.assertFalse(result.allowed)

    def test_audit_log_write(self):
        """测试写操作审计日志"""
        request = AccessRequest(
            tenant_id="tenant-audit-001",
            resource_type="sessions",
            resource_id="session-001",
            action=AccessAction.WRITE,
        )

        result = self.router.check_access(request)
        self.assertTrue(result.allowed)

        # 验证审计日志文件
        log_files = list(self.log_dir.glob("tenant-audit-001_*.jsonl"))
        self.assertEqual(len(log_files), 1)


class TestRBAC(unittest.TestCase):
    """测试RBAC权限控制"""

    def setUp(self):
        """测试前准备"""
        self.rbac = create_rbac_manager()

    def test_system_roles_exist(self):
        """测试系统预定义角色存在"""
        roles = self.rbac.get_role

        self.assertIsNotNone(self.rbac.get_role("role-super_admin"))
        self.assertIsNotNone(self.rbac.get_role("role-tenant_admin"))
        self.assertIsNotNone(self.rbac.get_role("role-user"))
        self.assertIsNotNone(self.rbac.get_role("role-guest"))

    def test_create_custom_role(self):
        """测试创建自定义角色"""
        role = self.rbac.create_role(
            name="自定义角色",
            description="这是一个自定义测试角色",
        )

        self.assertIsNotNone(role)
        self.assertEqual(role.name, "自定义角色")
        self.assertFalse(role.is_system)

    def test_assign_role(self):
        """测试分配角色"""
        role = self.rbac.get_role("role-user")
        assignment = self.rbac.assign_role(
            user_id="user-001",
            role_id=role.role_id,
            scope="tenant-001",
            scope_type="tenant",
        )

        self.assertIsNotNone(assignment)
        self.assertEqual(assignment.user_id, "user-001")

    def test_check_permission(self):
        """测试权限检查"""
        # 获取user角色的role_id
        user_role = self.rbac.get_role("role-user")
        self.rbac.assign_role(
            user_id="user-001",
            role_id=user_role.role_id,
            scope="tenant-001",
        )

        # 普通用户应该可以读取agent
        self.assertTrue(
            self.rbac.check_permission(
                user_id="user-001",
                resource_type=ResourceType.AGENT,
                permission=Permission.READ,
                scope="tenant-001",
            )
        )

        # 普通用户不应该可以删除租户
        self.assertFalse(
            self.rbac.check_permission(
                user_id="user-001",
                resource_type=ResourceType.TENANT,
                permission=Permission.DELETE,
                scope="tenant-001",
            )
        )

    def test_super_admin_permissions(self):
        """测试超级管理员权限"""
        super_admin_role = self.rbac.get_role("role-super_admin")
        self.rbac.assign_role(
            user_id="admin-001",
            role_id=super_admin_role.role_id,
            scope="system",
        )

        # 超级管理员应该有所有权限
        for resource_type in ResourceType:
            self.assertTrue(
                self.rbac.check_permission(
                    user_id="admin-001",
                    resource_type=resource_type,
                    permission=Permission.ADMIN,
                    scope="system",
                )
            )

    def test_tenant_admin_permissions(self):
        """测试租户管理员权限"""
        tenant_admin_role = self.rbac.get_role("role-tenant_admin")
        self.rbac.assign_role(
            user_id="tenant-admin-001",
            role_id=tenant_admin_role.role_id,
            scope="tenant-001",
        )

        # 租户管理员可以管理agent
        self.assertTrue(
            self.rbac.check_permission(
                user_id="tenant-admin-001",
                resource_type=ResourceType.AGENT,
                permission=Permission.CREATE,
                scope="tenant-001",
            )
        )

        # 租户管理员只能读取租户信息
        self.assertTrue(
            self.rbac.check_permission(
                user_id="tenant-admin-001",
                resource_type=ResourceType.TENANT,
                permission=Permission.READ,
                scope="tenant-001",
            )
        )

        self.assertFalse(
            self.rbac.check_permission(
                user_id="tenant-admin-001",
                resource_type=ResourceType.TENANT,
                permission=Permission.DELETE,
                scope="tenant-001",
            )
        )

    def test_revoke_role(self):
        """测试撤销角色"""
        user_role = self.rbac.get_role("role-user")
        assignment = self.rbac.assign_role(
            user_id="user-002",
            role_id=user_role.role_id,
            scope="tenant-001",
        )

        # 撤销角色
        result = self.rbac.revoke_role(
            user_id="user-002",
            role_id=user_role.role_id,
            scope="tenant-001",
        )

        self.assertTrue(result)

        # 验证权限已被撤销
        self.assertFalse(
            self.rbac.check_permission(
                user_id="user-002",
                resource_type=ResourceType.AGENT,
                permission=Permission.READ,
                scope="tenant-001",
            )
        )

    def test_get_user_permissions(self):
        """测试获取用户权限"""
        user_role = self.rbac.get_role("role-user")
        self.rbac.assign_role(
            user_id="user-003",
            role_id=user_role.role_id,
            scope="tenant-001",
        )

        permissions = self.rbac.get_user_permissions(user_id="user-003", scope="tenant-001")

        self.assertIn(ResourceType.AGENT, permissions)
        self.assertIn(Permission.READ, permissions[ResourceType.AGENT])
        self.assertIn(Permission.LIST, permissions[ResourceType.AGENT])

    def test_require_permission_exception(self):
        """测试require_permission抛出异常"""
        user_role = self.rbac.get_role("role-guest")
        self.rbac.assign_role(
            user_id="guest-001",
            role_id=user_role.role_id,
            scope="tenant-001",
        )

        with self.assertRaises(PermissionDenied):
            self.rbac.require_permission(
                user_id="guest-001",
                resource_type=ResourceType.USER,
                permission=Permission.DELETE,
                scope="tenant-001",
            )

    def test_delete_custom_role(self):
        """测试删除自定义角色"""
        role = self.rbac.create_role(name="待删除角色")

        # 删除自定义角色应该成功
        result = self.rbac.delete_role(role.role_id)
        self.assertTrue(result)

        # 验证角色已被删除
        self.assertIsNone(self.rbac.get_role(role.role_id))

    def test_cannot_delete_system_role(self):
        """测试无法删除系统角色"""
        result = self.rbac.delete_role("role-user")
        self.assertFalse(result)


class TestQuotaManagement(unittest.TestCase):
    """测试配额管理"""

    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.store_path = Path(self.temp_dir) / "data"
        self.base_path = Path(self.temp_dir)

        self.store = JsonTenantStore(self.store_path)
        self.manager = TenantManager(store=self.store, base_path=self.base_path)

    def tearDown(self):
        """测试后清理"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_free_tier_quotas(self):
        """测试免费版配额"""
        tenant = self.manager.create_tenant(
            name="免费版租户",
            tier=TenantTier.FREE,
        )

        self.assertEqual(tenant.rate_limits.requests_per_minute, 20)
        self.assertEqual(tenant.rate_limits.requests_per_day, 1000)
        self.assertEqual(tenant.rate_limits.max_concurrent_sessions, 2)
        self.assertEqual(tenant.storage_config.max_storage_mb, 100)

    def test_pro_tier_quotas(self):
        """测试专业版配额"""
        tenant = self.manager.create_tenant(
            name="专业版租户",
            tier=TenantTier.PRO,
        )

        self.assertEqual(tenant.rate_limits.requests_per_minute, 100)
        self.assertEqual(tenant.rate_limits.requests_per_day, 50000)
        self.assertEqual(tenant.rate_limits.max_concurrent_sessions, 5)
        self.assertEqual(tenant.storage_config.max_storage_mb, 1024)

    def test_enterprise_tier_quotas(self):
        """测试企业版配额"""
        tenant = self.manager.create_tenant(
            name="企业版租户",
            tier=TenantTier.ENTERPRISE,
        )

        self.assertEqual(tenant.rate_limits.requests_per_minute, 500)
        self.assertEqual(tenant.rate_limits.requests_per_day, 100000)
        self.assertEqual(tenant.rate_limits.max_concurrent_sessions, 20)
        self.assertEqual(tenant.storage_config.max_storage_mb, 10240)


if __name__ == "__main__":
    unittest.main()
