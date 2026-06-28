"""
RBAC权限控制 - Role-Based Access Control

基于角色的访问控制模型，支持资源级别权限、权限继承与委派
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class ResourceType(str, Enum):
    """资源类型枚举"""
    AGENT = "agent"                    # 智能体
    KNOWLEDGE = "knowledge"            # 知识库
    SKILL = "skill"                    # 技能
    DATA = "data"                      # 数据
    SESSION = "session"                # 会话
    CONFIG = "config"                  # 配置
    USER = "user"                      # 用户管理
    DEPARTMENT = "department"          # 部门管理
    TENANT = "tenant"                  # 租户管理
    AUDIT = "audit"                    # 审计日志


class Permission(str, Enum):
    """权限枚举"""
    # 基础权限
    READ = "read"                      # 读取
    WRITE = "write"                    # 写入
    DELETE = "delete"                  # 删除
    LIST = "list"                      # 列表

    # 高级权限
    CREATE = "create"                  # 创建
    UPDATE = "update"                  # 更新
    EXECUTE = "execute"                # 执行
    EXPORT = "export"                  # 导出
    IMPORT = "import"                  # 导入
    SHARE = "share"                    # 分享
    ADMIN = "admin"                    # 管理员（所有权限）


class RoleType(str, Enum):
    """系统预定义角色"""
    SUPER_ADMIN = "super_admin"        # 超级管理员
    TENANT_ADMIN = "tenant_admin"     # 租户管理员
    DEPARTMENT_ADMIN = "dept_admin"    # 部门管理员
    AUDITOR = "auditor"                # 审计员
    USER = "user"                      # 普通用户
    GUEST = "guest"                    # 访客


@dataclass
class PermissionGrant:
    """权限授予"""
    grant_id: str                      # 授予ID
    role_id: str                       # 角色ID
    resource_type: ResourceType        # 资源类型
    permissions: Set[Permission]       # 权限集合
    granted_by: str                    # 授予者
    conditions: Dict[str, Any] = field(default_factory=dict)  # 条件限制
    granted_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None  # 过期时间

    @classmethod
    def create(
        cls,
        role_id: str,
        resource_type: ResourceType,
        permissions: Set[Permission],
        granted_by: str,
        conditions: Optional[Dict[str, Any]] = None,
        expires_at: Optional[datetime] = None,
    ) -> PermissionGrant:
        """创建权限授予"""
        return cls(
            grant_id=f"grant-{uuid.uuid4().hex[:12]}",
            role_id=role_id,
            resource_type=resource_type,
            permissions=permissions,
            conditions=conditions or {},
            granted_by=granted_by,
            expires_at=expires_at,
        )


@dataclass
class Role:
    """角色"""
    role_id: str                       # 角色ID
    name: str                          # 角色名称
    description: str = ""              # 角色描述
    role_type: RoleType = RoleType.USER  # 角色类型
    parent_role_id: Optional[str] = None  # 父角色（用于继承）
    permissions: Dict[ResourceType, Set[Permission]] = field(default_factory=dict)  # 权限映射
    is_system: bool = False            # 是否系统预定义角色
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def create(
        cls,
        name: str,
        role_type: RoleType = RoleType.USER,
        description: str = "",
        parent_role_id: Optional[str] = None,
    ) -> Role:
        """创建角色"""
        return cls(
            role_id=f"role-{uuid.uuid4().hex[:8]}",
            name=name,
            role_type=role_type,
            description=description,
            parent_role_id=parent_role_id,
        )

    @classmethod
    def system_role(cls, role_type: RoleType) -> Role:
        """创建系统预定义角色"""
        role = cls(
            role_id=f"role-{role_type.value}",  # 使用固定的role_id
            name=role_type.value.replace("_", " ").title(),
            role_type=role_type,
            description=f"System predefined {role_type.value} role",
            is_system=True,
        )
        role._init_permissions()
        return role

    def _init_permissions(self) -> None:
        """初始化预定义角色的权限"""
        if self.role_type == RoleType.SUPER_ADMIN:
            # 超级管理员：所有资源的所有权限
            for rt in ResourceType:
                self.permissions[rt] = set(Permission)

        elif self.role_type == RoleType.TENANT_ADMIN:
            # 租户管理员：租户下所有资源的所有权限
            for rt in ResourceType:
                if rt not in (ResourceType.TENANT, ResourceType.AUDIT):
                    self.permissions[rt] = set(Permission)
            self.permissions[ResourceType.TENANT] = {Permission.READ, Permission.LIST}
            self.permissions[ResourceType.AUDIT] = {Permission.READ}

        elif self.role_type == RoleType.DEPARTMENT_ADMIN:
            # 部门管理员：本部门资源的管理权限
            for rt in ResourceType:
                self.permissions[rt] = {Permission.READ, Permission.LIST, Permission.CREATE, Permission.UPDATE}
            self.permissions[ResourceType.USER] = {Permission.READ, Permission.LIST, Permission.CREATE, Permission.UPDATE}

        elif self.role_type == RoleType.AUDITOR:
            # 审计员：只读权限
            for rt in ResourceType:
                self.permissions[rt] = {Permission.READ, Permission.LIST}
            self.permissions[ResourceType.AUDIT] = {Permission.READ, Permission.LIST, Permission.EXPORT}

        elif self.role_type == RoleType.USER:
            # 普通用户：基础CRUD权限
            self.permissions = {
                ResourceType.AGENT: {Permission.READ, Permission.LIST, Permission.CREATE, Permission.UPDATE},
                ResourceType.KNOWLEDGE: {Permission.READ, Permission.LIST, Permission.CREATE, Permission.UPDATE},
                ResourceType.SKILL: {Permission.READ, Permission.LIST},
                ResourceType.DATA: {Permission.READ, Permission.LIST, Permission.CREATE, Permission.UPDATE},
                ResourceType.SESSION: {Permission.READ, Permission.WRITE, Permission.DELETE},
            }

        elif self.role_type == RoleType.GUEST:
            # 访客：只读权限
            for rt in ResourceType:
                self.permissions[rt] = {Permission.READ, Permission.LIST}


@dataclass
class RoleAssignment:
    """角色分配"""
    assignment_id: str                 # 分配ID
    user_id: str                       # 用户ID
    role_id: str                       # 角色ID
    scope: str = ""                    # 范围（租户ID或部门ID）
    scope_type: str = "tenant"         # 范围类型：tenant/department
    granted_by: str = ""               # 分配者
    granted_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None

    @classmethod
    def create(
        cls,
        user_id: str,
        role_id: str,
        scope: str,
        scope_type: str = "tenant",
        granted_by: str = "",
    ) -> RoleAssignment:
        """创建角色分配"""
        return cls(
            assignment_id=f"assign-{uuid.uuid4().hex[:12]}",
            user_id=user_id,
            role_id=role_id,
            scope=scope,
            scope_type=scope_type,
            granted_by=granted_by,
        )


class PermissionChecker:
    """
    权限检查器

    实现基于角色的权限检查逻辑
    """

    def __init__(
        self,
        roles: Optional[Dict[str, Role]] = None,
        assignments: Optional[List[RoleAssignment]] = None,
    ):
        self.roles: Dict[str, Role] = roles or {}
        self.assignments: List[RoleAssignment] = assignments or []
        self._init_system_roles()

    def _init_system_roles(self) -> None:
        """初始化系统预定义角色"""
        for role_type in RoleType:
            role = Role.system_role(role_type)
            self.roles[role.role_id] = role

    def add_role(self, role: Role) -> None:
        """添加角色"""
        self.roles[role.role_id] = role

    def get_role(self, role_id: str) -> Optional[Role]:
        """获取角色"""
        return self.roles.get(role_id)

    def list_roles(self, include_system: bool = True) -> List[Role]:
        """列出所有角色"""
        if include_system:
            return list(self.roles.values())
        return [r for r in self.roles.values() if not r.is_system]

    def assign_role(
        self,
        user_id: str,
        role_id: str,
        scope: str,
        scope_type: str = "tenant",
        granted_by: str = "",
    ) -> RoleAssignment:
        """分配角色"""
        assignment = RoleAssignment.create(
            user_id=user_id,
            role_id=role_id,
            scope=scope,
            scope_type=scope_type,
            granted_by=granted_by,
        )
        self.assignments.append(assignment)
        return assignment

    def revoke_role(self, user_id: str, role_id: str, scope: str) -> bool:
        """撤销角色"""
        for assignment in self.assignments:
            if (assignment.user_id == user_id and
                assignment.role_id == role_id and
                assignment.scope == scope):
                self.assignments.remove(assignment)
                return True
        return False

    def get_user_roles(self, user_id: str, scope: Optional[str] = None) -> List[RoleAssignment]:
        """获取用户的角色分配"""
        result = []
        for assignment in self.assignments:
            if assignment.user_id == user_id:
                if scope is None or assignment.scope == scope:
                    result.append(assignment)
        return result

    def get_user_permissions(
        self,
        user_id: str,
        scope: Optional[str] = None,
    ) -> Dict[ResourceType, Set[Permission]]:
        """获取用户的有效权限"""
        permissions: Dict[ResourceType, Set[Permission]] = {}

        # 获取用户的角色分配
        assignments = self.get_user_roles(user_id, scope)

        for assignment in assignments:
            role = self.get_role(assignment.role_id)
            if not role:
                continue

            # 检查是否过期
            if assignment.expires_at and assignment.expires_at < datetime.now():
                continue

            # 合并角色权限
            for resource_type, perms in role.permissions.items():
                if resource_type not in permissions:
                    permissions[resource_type] = set()
                permissions[resource_type].update(perms)

        return permissions

    def check_permission(
        self,
        user_id: str,
        resource_type: ResourceType,
        permission: Permission,
        scope: Optional[str] = None,
    ) -> bool:
        """
        检查用户是否具有特定权限

        Args:
            user_id: 用户ID
            resource_type: 资源类型
            permission: 权限
            scope: 范围（租户ID或部门ID）

        Returns:
            是否具有权限
        """
        # 获取用户权限
        user_permissions = self.get_user_permissions(user_id, scope)

        # 检查是否有所需权限
        if resource_type not in user_permissions:
            return False

        # 检查是否有ADMIN权限（管理员权限包含所有权限）
        if Permission.ADMIN in user_permissions.get(resource_type, set()):
            return True

        return permission in user_permissions[resource_type]

    def check_any_permission(
        self,
        user_id: str,
        resource_type: ResourceType,
        permissions: List[Permission],
        scope: Optional[str] = None,
    ) -> bool:
        """检查是否具有任一权限"""
        for perm in permissions:
            if self.check_permission(user_id, resource_type, perm, scope):
                return True
        return False

    def check_all_permissions(
        self,
        user_id: str,
        resource_type: ResourceType,
        permissions: List[Permission],
        scope: Optional[str] = None,
    ) -> bool:
        """检查是否具有所有权限"""
        for perm in permissions:
            if not self.check_permission(user_id, resource_type, perm, scope):
                return False
        return True

    def require_permission(
        self,
        user_id: str,
        resource_type: ResourceType,
        permission: Permission,
        scope: Optional[str] = None,
    ) -> None:
        """要求权限，失败则抛出异常"""
        if not self.check_permission(user_id, resource_type, permission, scope):
            raise PermissionDenied(
                f"User {user_id} does not have {permission.value} permission on {resource_type.value}"
            )

    def filter_by_permission(
        self,
        user_id: str,
        resource_type: ResourceType,
        permission: Permission,
        resources: List[Any],
        get_resource_scope: callable,
        scope: Optional[str] = None,
    ) -> List[Any]:
        """根据权限过滤资源列表"""
        result = []
        for resource in resources:
            resource_scope = get_resource_scope(resource)
            if self.check_permission(user_id, resource_type, permission, resource_scope):
                result.append(resource)
        return result


class PermissionDenied(Exception):
    """权限不足异常"""

    def __init__(self, message: str = "Permission denied"):
        self.message = message
        super().__init__(self.message)


class RBACManager:
    """
    RBAC权限管理器

    提供完整的RBAC功能，包括角色管理、权限分配、权限检查等
    """

    def __init__(self):
        self.permission_checker = PermissionChecker()
        self._user_cache: Dict[str, Dict[ResourceType, Set[Permission]]] = {}

    def get_role(self, role_id: str) -> Optional[Role]:
        """获取角色"""
        return self.permission_checker.get_role(role_id)

    def create_role(
        self,
        name: str,
        description: str = "",
        parent_role_id: Optional[str] = None,
    ) -> Role:
        """创建自定义角色"""
        role = Role.create(
            name=name,
            description=description,
            parent_role_id=parent_role_id,
        )
        self.permission_checker.add_role(role)
        return role

    def update_role(self, role: Role) -> bool:
        """更新角色"""
        if role.is_system:
            return False  # 系统角色不可修改
        role.updated_at = datetime.now()
        self.permission_checker.roles[role.role_id] = role
        self._clear_cache()
        return True

    def delete_role(self, role_id: str) -> bool:
        """删除角色"""
        role = self.get_role(role_id)
        if not role or role.is_system:
            return False  # 系统角色不可删除

        # 移除角色分配
        self.permission_checker.assignments = [
            a for a in self.permission_checker.assignments
            if a.role_id != role_id
        ]

        del self.permission_checker.roles[role_id]
        self._clear_cache()
        return True

    def grant_permissions(
        self,
        role_id: str,
        resource_type: ResourceType,
        permissions: Set[Permission],
        granted_by: str = "",
    ) -> PermissionGrant:
        """授予权限"""
        grant = PermissionGrant.create(
            role_id=role_id,
            resource_type=resource_type,
            permissions=permissions,
            granted_by=granted_by,
        )

        # 更新角色的权限
        role = self.get_role(role_id)
        if role:
            role.permissions[resource_type] = permissions
            role.updated_at = datetime.now()
            self._clear_cache()

        return grant

    def assign_role(
        self,
        user_id: str,
        role_id: str,
        scope: str,
        scope_type: str = "tenant",
        granted_by: str = "",
    ) -> RoleAssignment:
        """分配角色"""
        assignment = self.permission_checker.assign_role(
            user_id=user_id,
            role_id=role_id,
            scope=scope,
            scope_type=scope_type,
            granted_by=granted_by,
        )
        self._clear_cache()
        return assignment

    def revoke_role(self, user_id: str, role_id: str, scope: str) -> bool:
        """撤销角色"""
        result = self.permission_checker.revoke_role(user_id, role_id, scope)
        if result:
            self._clear_cache()
        return result

    def check_permission(
        self,
        user_id: str,
        resource_type: ResourceType,
        permission: Permission,
        scope: Optional[str] = None,
    ) -> bool:
        """检查权限"""
        return self.permission_checker.check_permission(
            user_id, resource_type, permission, scope
        )

    def require_permission(
        self,
        user_id: str,
        resource_type: ResourceType,
        permission: Permission,
        scope: Optional[str] = None,
    ) -> None:
        """要求权限，失败则抛出异常"""
        return self.permission_checker.require_permission(
            user_id, resource_type, permission, scope
        )

    def get_user_permissions(
        self,
        user_id: str,
        scope: Optional[str] = None,
    ) -> Dict[ResourceType, Set[Permission]]:
        """获取用户权限"""
        cache_key = f"{user_id}:{scope or '*'}"

        if cache_key not in self._user_cache:
            self._user_cache[cache_key] = self.permission_checker.get_user_permissions(
                user_id, scope
            )

        return self._user_cache[cache_key]

    def _clear_cache(self) -> None:
        """清除缓存"""
        self._user_cache.clear()

    def can_manage_users(self, user_id: str, tenant_id: str) -> bool:
        """检查是否可以管理用户"""
        return (
            self.check_permission(user_id, ResourceType.USER, Permission.CREATE, tenant_id) or
            self.check_permission(user_id, ResourceType.USER, Permission.UPDATE, tenant_id) or
            self.check_permission(user_id, ResourceType.USER, Permission.DELETE, tenant_id)
        )

    def can_access_audit(self, user_id: str, tenant_id: str) -> bool:
        """检查是否可以访问审计日志"""
        return self.check_permission(user_id, ResourceType.AUDIT, Permission.READ, tenant_id)

    def can_manage_agents(self, user_id: str, tenant_id: str) -> bool:
        """检查是否可以管理智能体"""
        return (
            self.check_permission(user_id, ResourceType.AGENT, Permission.CREATE, tenant_id) or
            self.check_permission(user_id, ResourceType.AGENT, Permission.UPDATE, tenant_id) or
            self.check_permission(user_id, ResourceType.AGENT, Permission.DELETE, tenant_id)
        )


def create_rbac_manager() -> RBACManager:
    """创建RBAC管理器（便捷函数）"""
    return RBACManager()
