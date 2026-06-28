"""
租户管理器 - Tenant Manager

提供租户CRUD操作、配额管理、组织架构管理等功能
支持从配置文件或数据库加载租户数据
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

from taiji_agent.multi_tenant.isolation import (
    Tenant, TenantContext, TenantTier, TenantStatus,
    Department, TenantUser, TenantContextManager,
    RateLimitConfig, StorageConfig, IsolationStrategy,
    SharedStorageBackend, LogicalStorageBackend, PhysicalStorageBackend,
    create_storage_backend,
)


class TenantStore:
    """
    租户存储基类

    定义租户数据的持久化接口
    """

    def save_tenant(self, tenant: Tenant) -> bool:
        """保存租户"""
        raise NotImplementedError

    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        """获取租户"""
        raise NotImplementedError

    def list_tenants(self) -> List[Tenant]:
        """列出所有租户"""
        raise NotImplementedError

    def delete_tenant(self, tenant_id: str) -> bool:
        """删除租户（软删除）"""
        raise NotImplementedError

    def save_department(self, dept: Department) -> bool:
        """保存部门"""
        raise NotImplementedError

    def get_department(self, dept_id: str) -> Optional[Department]:
        """获取部门"""
        raise NotImplementedError

    def list_departments(self, tenant_id: str) -> List[Department]:
        """列出租户下所有部门"""
        raise NotImplementedError

    def delete_department(self, dept_id: str) -> bool:
        """删除部门"""
        raise NotImplementedError

    def save_user(self, user: TenantUser) -> bool:
        """保存用户"""
        raise NotImplementedError

    def get_user(self, user_id: str) -> Optional[TenantUser]:
        """获取用户"""
        raise NotImplementedError

    def get_user_by_username(self, tenant_id: str, username: str) -> Optional[TenantUser]:
        """根据用户名获取用户"""
        raise NotImplementedError

    def list_users(self, tenant_id: str) -> List[TenantUser]:
        """列出租户下所有用户"""
        raise NotImplementedError

    def delete_user(self, user_id: str) -> bool:
        """删除用户"""
        raise NotImplementedError


class JsonTenantStore(TenantStore):
    """
    JSON文件租户存储

    将租户数据存储在JSON文件中，适用于小规模部署
    """

    def __init__(self, store_path: Path):
        self.store_path = Path(store_path)
        self.store_path.mkdir(parents=True, exist_ok=True)
        self.tenants_file = self.store_path / "tenants.json"
        self.departments_file = self.store_path / "departments.json"
        self.users_file = self.store_path / "users.json"
        self._init_files()

    def _init_files(self):
        """初始化存储文件"""
        if not self.tenants_file.exists():
            self.tenants_file.write_text("[]")
        if not self.departments_file.exists():
            self.departments_file.write_text("[]")
        if not self.users_file.exists():
            self.users_file.write_text("[]")

    def _load_json(self, file_path: Path) -> List[Dict[str, Any]]:
        """加载JSON文件"""
        try:
            return json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save_json(self, file_path: Path, data: List[Dict[str, Any]]) -> None:
        """保存JSON文件"""
        file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _dict_to_tenant(self, d: Dict[str, Any]) -> Tenant:
        """字典转Tenant对象"""
        storage_config = StorageConfig(**d.get("storage_config", {}))
        rate_limits = RateLimitConfig(**d.get("rate_limits", {}))
        return Tenant(
            tenant_id=d["tenant_id"],
            name=d["name"],
            tier=TenantTier(d.get("tier", "free")),
            status=TenantStatus(d.get("status", "active")),
            isolation_strategy=IsolationStrategy(d.get("isolation_strategy", "shared")),
            storage_config=storage_config,
            department_ids=d.get("department_ids", []),
            config_overrides=d.get("config_overrides", {}),
            allowed_providers=d.get("allowed_providers", ["qwen"]),
            rate_limits=rate_limits,
            created_at=datetime.fromisoformat(d.get("created_at", datetime.now().isoformat())),
            updated_at=datetime.fromisoformat(d.get("updated_at", datetime.now().isoformat())),
        )

    def _tenant_to_dict(self, tenant: Tenant) -> Dict[str, Any]:
        """Tenant对象转字典"""
        return {
            "tenant_id": tenant.tenant_id,
            "name": tenant.name,
            "tier": tenant.tier.value,
            "status": tenant.status.value,
            "isolation_strategy": tenant.isolation_strategy.value,
            "storage_config": {
                "base_path": tenant.storage_config.base_path,
                "db_path": tenant.storage_config.db_path,
                "max_storage_mb": tenant.storage_config.max_storage_mb,
                "current_storage_mb": tenant.storage_config.current_storage_mb,
            },
            "department_ids": tenant.department_ids,
            "config_overrides": tenant.config_overrides,
            "allowed_providers": tenant.allowed_providers,
            "rate_limits": {
                "requests_per_minute": tenant.rate_limits.requests_per_minute,
                "requests_per_hour": tenant.rate_limits.requests_per_hour,
                "requests_per_day": tenant.rate_limits.requests_per_day,
                "tokens_per_day": tenant.rate_limits.tokens_per_day,
                "max_concurrent_sessions": tenant.rate_limits.max_concurrent_sessions,
            },
            "created_at": tenant.created_at.isoformat(),
            "updated_at": tenant.updated_at.isoformat(),
        }

    def _dict_to_department(self, d: Dict[str, Any]) -> Department:
        """字典转Department对象"""
        return Department(
            dept_id=d["dept_id"],
            tenant_id=d["tenant_id"],
            name=d["name"],
            parent_dept_id=d.get("parent_dept_id"),
            dept_type=d.get("dept_type", "business"),
            created_at=datetime.fromisoformat(d.get("created_at", datetime.now().isoformat())),
        )

    def _department_to_dict(self, dept: Department) -> Dict[str, Any]:
        """Department对象转字典"""
        return {
            "dept_id": dept.dept_id,
            "tenant_id": dept.tenant_id,
            "name": dept.name,
            "parent_dept_id": dept.parent_dept_id,
            "dept_type": dept.dept_type,
            "created_at": dept.created_at.isoformat(),
        }

    def _dict_to_user(self, d: Dict[str, Any]) -> TenantUser:
        """字典转TenantUser对象"""
        last_login = None
        if d.get("last_login"):
            last_login = datetime.fromisoformat(d["last_login"])
        return TenantUser(
            user_id=d["user_id"],
            tenant_id=d["tenant_id"],
            department_id=d["department_id"],
            username=d["username"],
            display_name=d["display_name"],
            role=d.get("role", "user"),
            phone=d.get("phone", ""),
            email=d.get("email", ""),
            status=d.get("status", "active"),
            created_at=datetime.fromisoformat(d.get("created_at", datetime.now().isoformat())),
            last_login=last_login,
        )

    def _user_to_dict(self, user: TenantUser) -> Dict[str, Any]:
        """TenantUser对象转字典"""
        return {
            "user_id": user.user_id,
            "tenant_id": user.tenant_id,
            "department_id": user.department_id,
            "username": user.username,
            "display_name": user.display_name,
            "role": user.role,
            "phone": user.phone,
            "email": user.email,
            "status": user.status,
            "created_at": user.created_at.isoformat(),
            "last_login": user.last_login.isoformat() if user.last_login else None,
        }

    def save_tenant(self, tenant: Tenant) -> bool:
        """保存租户"""
        tenants = self._load_json(self.tenants_file)
        tenant.updated_at = datetime.now()
        tenant_dict = self._tenant_to_dict(tenant)

        for i, t in enumerate(tenants):
            if t["tenant_id"] == tenant.tenant_id:
                tenants[i] = tenant_dict
                self._save_json(self.tenants_file, tenants)
                return True

        tenants.append(tenant_dict)
        self._save_json(self.tenants_file, tenants)
        return True

    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        """获取租户（过滤deleted状态）"""
        tenants = self._load_json(self.tenants_file)
        for t in tenants:
            if t["tenant_id"] == tenant_id and t.get("status") != "deleted":
                return self._dict_to_tenant(t)
        return None

    def list_tenants(self) -> List[Tenant]:
        """列出所有租户"""
        tenants = self._load_json(self.tenants_file)
        return [self._dict_to_tenant(t) for t in tenants if t.get("status") != "deleted"]

    def delete_tenant(self, tenant_id: str) -> bool:
        """删除租户（软删除）"""
        tenants = self._load_json(self.tenants_file)
        for t in tenants:
            if t["tenant_id"] == tenant_id:
                t["status"] = "deleted"
                t["updated_at"] = datetime.now().isoformat()
                self._save_json(self.tenants_file, tenants)
                return True
        return False

    def save_department(self, dept: Department) -> bool:
        """保存部门"""
        depts = self._load_json(self.departments_file)
        dept_dict = self._department_to_dict(dept)

        for i, d in enumerate(depts):
            if d["dept_id"] == dept.dept_id:
                depts[i] = dept_dict
                self._save_json(self.departments_file, depts)
                return True

        depts.append(dept_dict)
        self._save_json(self.departments_file, depts)
        return True

    def get_department(self, dept_id: str) -> Optional[Department]:
        """获取部门"""
        depts = self._load_json(self.departments_file)
        for d in depts:
            if d["dept_id"] == dept_id:
                return self._dict_to_department(d)
        return None

    def list_departments(self, tenant_id: str) -> List[Department]:
        """列出租户下所有部门"""
        depts = self._load_json(self.departments_file)
        return [self._dict_to_department(d) for d in depts if d["tenant_id"] == tenant_id]

    def delete_department(self, dept_id: str) -> bool:
        """删除部门"""
        depts = self._load_json(self.departments_file)
        depts = [d for d in depts if d["dept_id"] != dept_id]
        self._save_json(self.departments_file, depts)
        return True

    def save_user(self, user: TenantUser) -> bool:
        """保存用户"""
        users = self._load_json(self.users_file)
        user_dict = self._user_to_dict(user)

        for i, u in enumerate(users):
            if u["user_id"] == user.user_id:
                users[i] = user_dict
                self._save_json(self.users_file, users)
                return True

        users.append(user_dict)
        self._save_json(self.users_file, users)
        return True

    def get_user(self, user_id: str) -> Optional[TenantUser]:
        """获取用户"""
        users = self._load_json(self.users_file)
        for u in users:
            if u["user_id"] == user_id:
                return self._dict_to_user(u)
        return None

    def get_user_by_username(self, tenant_id: str, username: str) -> Optional[TenantUser]:
        """根据用户名获取用户"""
        users = self._load_json(self.users_file)
        for u in users:
            if u["tenant_id"] == tenant_id and u["username"] == username:
                return self._dict_to_user(u)
        return None

    def list_users(self, tenant_id: str) -> List[TenantUser]:
        """列出租户下所有用户"""
        users = self._load_json(self.users_file)
        return [self._dict_to_user(u) for u in users if u["tenant_id"] == tenant_id]

    def delete_user(self, user_id: str) -> bool:
        """删除用户"""
        users = self._load_json(self.users_file)
        users = [u for u in users if u["user_id"] != user_id]
        self._save_json(self.users_file, users)
        return True


class TenantManager:
    """
    租户管理器

    提供租户CRUD、配额管理、组织架构管理等功能
    """

    def __init__(
        self,
        store: TenantStore,
        base_path: Optional[Path] = None,
    ):
        self.store = store
        self.base_path = base_path or Path.home() / ".taiji_agent"
        self._storage_backends: Dict[str, Any] = {}

    def create_tenant(
        self,
        name: str,
        tier: TenantTier = TenantTier.FREE,
        isolation_strategy: IsolationStrategy = IsolationStrategy.SHARED,
        base_path: Optional[str] = None,
    ) -> Tenant:
        """
        创建新租户

        Args:
            name: 租户名称
            tier: 租户层级
            isolation_strategy: 隔离策略
            base_path: 基础存储路径

        Returns:
            创建的租户对象
        """
        # 创建租户
        tenant = Tenant.create(
            name=name,
            tier=tier,
            isolation_strategy=isolation_strategy,
        )

        # 设置存储配置
        storage_path = base_path or str(self.base_path / "tenants" / tenant.tenant_id)
        tenant.storage_config = StorageConfig(base_path=storage_path)

        # 根据隔离策略设置配额
        if tier == TenantTier.FREE:
            tenant.rate_limits = RateLimitConfig(
                requests_per_minute=20,
                requests_per_hour=200,
                requests_per_day=1000,
                tokens_per_day=1000000,
                max_concurrent_sessions=2,
            )
            tenant.storage_config.max_storage_mb = 100
        elif tier == TenantTier.PRO:
            tenant.rate_limits = RateLimitConfig(
                requests_per_minute=100,
                requests_per_hour=2000,
                requests_per_day=50000,
                tokens_per_day=10000000,
                max_concurrent_sessions=5,
            )
            tenant.storage_config.max_storage_mb = 1024
        else:  # ENTERPRISE
            tenant.rate_limits = RateLimitConfig(
                requests_per_minute=500,
                requests_per_hour=10000,
                requests_per_day=100000,
                tokens_per_day=100000000,
                max_concurrent_sessions=20,
            )
            tenant.storage_config.max_storage_mb = 10240

        # 初始化存储后端
        storage_backend = create_storage_backend(isolation_strategy, Path(storage_path))
        storage_backend.ensure_tenant_dirs(tenant.tenant_id)
        self._storage_backends[tenant.tenant_id] = storage_backend

        # 保存租户
        self.store.save_tenant(tenant)

        return tenant

    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        """获取租户"""
        return self.store.get_tenant(tenant_id)

    def list_tenants(self) -> List[Tenant]:
        """列出所有租户"""
        return self.store.list_tenants()

    def update_tenant(self, tenant: Tenant) -> bool:
        """更新租户"""
        tenant.updated_at = datetime.now()
        return self.store.save_tenant(tenant)

    def suspend_tenant(self, tenant_id: str) -> bool:
        """暂停租户"""
        tenant = self.store.get_tenant(tenant_id)
        if not tenant:
            return False
        tenant.status = TenantStatus.SUSPENDED
        tenant.updated_at = datetime.now()
        return self.store.save_tenant(tenant)

    def activate_tenant(self, tenant_id: str) -> bool:
        """激活租户"""
        tenant = self.store.get_tenant(tenant_id)
        if not tenant:
            return False
        tenant.status = TenantStatus.ACTIVE
        tenant.updated_at = datetime.now()
        return self.store.save_tenant(tenant)

    def delete_tenant(self, tenant_id: str) -> bool:
        """删除租户（软删除）"""
        return self.store.delete_tenant(tenant_id)

    def get_storage_backend(self, tenant_id: str):
        """获取租户的存储后端"""
        if tenant_id in self._storage_backends:
            return self._storage_backends[tenant_id]

        tenant = self.store.get_tenant(tenant_id)
        if not tenant:
            return None

        storage_backend = create_storage_backend(
            tenant.isolation_strategy,
            Path(tenant.storage_config.base_path or str(self.base_path / "tenants" / tenant_id)),
        )
        self._storage_backends[tenant_id] = storage_backend
        return storage_backend

    # =========================================================================
    # 部门管理
    # =========================================================================

    def create_department(
        self,
        tenant_id: str,
        name: str,
        dept_type: str = "business",
        parent_dept_id: Optional[str] = None,
    ) -> Optional[Department]:
        """创建部门"""
        tenant = self.store.get_tenant(tenant_id)
        if not tenant:
            return None

        dept = Department.create(
            tenant_id=tenant_id,
            name=name,
            dept_type=dept_type,
        )
        dept.parent_dept_id = parent_dept_id
        self.store.save_department(dept)

        # 更新租户的部门列表
        tenant.department_ids.append(dept.dept_id)
        self.store.save_tenant(tenant)

        return dept

    def get_department(self, dept_id: str) -> Optional[Department]:
        """获取部门"""
        return self.store.get_department(dept_id)

    def list_departments(self, tenant_id: str) -> List[Department]:
        """列出租户下所有部门"""
        return self.store.list_departments(tenant_id)

    def update_department(self, dept: Department) -> bool:
        """更新部门"""
        return self.store.save_department(dept)

    def delete_department(self, dept_id: str) -> bool:
        """删除部门"""
        dept = self.store.get_department(dept_id)
        if not dept:
            return False

        # 从租户中移除
        tenant = self.store.get_tenant(dept.tenant_id)
        if tenant and dept_id in tenant.department_ids:
            tenant.department_ids.remove(dept_id)
            self.store.save_tenant(tenant)

        return self.store.delete_department(dept_id)

    # =========================================================================
    # 用户管理
    # =========================================================================

    def create_user(
        self,
        tenant_id: str,
        department_id: str,
        username: str,
        display_name: str,
        role: str = "user",
        phone: str = "",
        email: str = "",
    ) -> Optional[TenantUser]:
        """创建用户"""
        # 检查租户和部门是否存在
        tenant = self.store.get_tenant(tenant_id)
        if not tenant:
            return None

        dept = self.store.get_department(department_id)
        if not dept or dept.tenant_id != tenant_id:
            return None

        # 检查用户名是否已存在
        existing = self.store.get_user_by_username(tenant_id, username)
        if existing:
            return None

        user = TenantUser.create(
            tenant_id=tenant_id,
            department_id=department_id,
            username=username,
            display_name=display_name,
            role=role,
        )
        user.phone = phone
        user.email = email
        self.store.save_user(user)

        return user

    def get_user(self, user_id: str) -> Optional[TenantUser]:
        """获取用户"""
        return self.store.get_user(user_id)

    def get_user_by_username(self, tenant_id: str, username: str) -> Optional[TenantUser]:
        """根据用户名获取用户"""
        return self.store.get_user_by_username(tenant_id, username)

    def list_users(self, tenant_id: str) -> List[TenantUser]:
        """列出租户下所有用户"""
        return self.store.list_users(tenant_id)

    def update_user(self, user: TenantUser) -> bool:
        """更新用户"""
        return self.store.save_user(user)

    def disable_user(self, user_id: str) -> bool:
        """禁用用户"""
        user = self.store.get_user(user_id)
        if not user:
            return False
        user.status = "disabled"
        return self.store.save_user(user)

    def enable_user(self, user_id: str) -> bool:
        """启用用户"""
        user = self.store.get_user(user_id)
        if not user:
            return False
        user.status = "active"
        return self.store.save_user(user)

    def delete_user(self, user_id: str) -> bool:
        """删除用户"""
        return self.store.delete_user(user_id)

    def update_last_login(self, user_id: str) -> bool:
        """更新最后登录时间"""
        user = self.store.get_user(user_id)
        if not user:
            return False
        user.last_login = datetime.now()
        return self.store.save_user(user)

    # =========================================================================
    # 配额管理
    # =========================================================================

    def check_rate_limit(self, tenant_id: str) -> bool:
        """检查速率限制"""
        tenant = self.store.get_tenant(tenant_id)
        if not tenant:
            return False

        # TODO: 实现实际的速率限制检查
        # 当前只是简单检查租户状态
        return tenant.status == TenantStatus.ACTIVE

    def check_storage_quota(self, tenant_id: str, additional_mb: float = 0) -> bool:
        """检查存储配额"""
        tenant = self.store.get_tenant(tenant_id)
        if not tenant:
            return False

        return (tenant.storage_config.current_storage_mb + additional_mb) <= tenant.storage_config.max_storage_mb

    def update_storage_usage(self, tenant_id: str, current_mb: float) -> bool:
        """更新存储使用量"""
        tenant = self.store.get_tenant(tenant_id)
        if not tenant:
            return False

        tenant.storage_config.current_storage_mb = current_mb
        tenant.updated_at = datetime.now()
        return self.store.save_tenant(tenant)

    # =========================================================================
    # 上下文管理
    # =========================================================================

    def create_context(
        self,
        tenant: Tenant,
        user: Optional[TenantUser] = None,
    ) -> TenantContext:
        """创建租户上下文"""
        return TenantContext(tenant=tenant, user=user)

    def set_context(self, context: TenantContext) -> None:
        """设置当前上下文"""
        TenantContextManager.set_context(context)

    def clear_context(self) -> None:
        """清除当前上下文"""
        TenantContextManager.clear_context()

    def with_context(
        self,
        tenant: Tenant,
        user: Optional[TenantUser] = None,
    ) -> TenantContext:
        """使用上下文管理器"""
        context = self.create_context(tenant, user)
        self.set_context(context)
        return context


def create_tenant_manager(base_path: Optional[Path] = None) -> TenantManager:
    """创建租户管理器（便捷函数）"""
    store_path = (base_path or Path.home() / ".taiji_agent") / "data"
    store = JsonTenantStore(store_path)
    return TenantManager(store=store, base_path=base_path)
