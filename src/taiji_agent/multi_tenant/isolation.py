"""
多租户隔离模型 - Multi-Tenant Isolation Model

实现三种隔离策略：物理隔离(Physical)、逻辑隔离(Logical)、共享隔离(Shared)
基于租户上下文(TenantContext)实现数据隔离

隔离策略层级：
- SHARED: 所有租户共享存储，通过租户ID前缀隔离
- LOGICAL: 租户使用独立数据库schema，通过schema隔离
- PHYSICAL: 租户使用独立数据库实例，通过数据库隔离
"""

from __future__ import annotations

import os
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

# 租户上下文变量 - 使用ContextVar实现线程安全的上下文隔离
_tenant_context_var: ContextVar[Optional["TenantContext"]] = ContextVar(
    "tenant_context", default=None
)


class IsolationStrategy(str, Enum):
    """隔离策略枚举"""
    SHARED = "shared"      # 共享隔离 - 所有租户共享存储，路径前缀隔离
    LOGICAL = "logical"    # 逻辑隔离 - 独立数据库schema
    PHYSICAL = "physical"  # 物理隔离 - 独立数据库实例


class TenantStatus(str, Enum):
    """租户状态"""
    ACTIVE = "active"      # 活跃
    SUSPENDED = "suspended"  # 暂停
    DELETED = "deleted"    # 已删除


class TenantTier(str, Enum):
    """租户层级"""
    FREE = "free"          # 免费版
    PRO = "pro"            # 专业版
    ENTERPRISE = "enterprise"  # 企业版


@dataclass
class RateLimitConfig:
    """速率限制配置"""
    requests_per_minute: int = 60       # 每分钟请求数限制
    requests_per_hour: int = 1000       # 每小时请求数限制
    requests_per_day: int = 10000       # 每天请求数限制
    tokens_per_day: int = 1000000       # 每天Token限制
    max_concurrent_sessions: int = 5   # 最大并发会话数


@dataclass
class StorageConfig:
    """存储配置"""
    base_path: str = ""                  # 基础存储路径
    db_path: Optional[str] = None        # 数据库路径（LOGICAL/PHYSICAL策略）
    max_storage_mb: int = 1024           # 最大存储空间(MB)
    current_storage_mb: float = 0       # 当前使用存储(MB)


@dataclass
class Tenant:
    """租户核心模型"""
    tenant_id: str                       # 租户ID（UUID v4）
    name: str                            # 租户名称
    tier: TenantTier = TenantTier.FREE  # 层级
    status: TenantStatus = TenantStatus.ACTIVE  # 状态
    isolation_strategy: IsolationStrategy = IsolationStrategy.SHARED  # 隔离策略
    storage_config: StorageConfig = field(default_factory=StorageConfig)
    department_ids: List[str] = field(default_factory=list)  # 下属部门ID列表
    config_overrides: Dict[str, Any] = field(default_factory=dict)  # 配置覆盖
    allowed_providers: List[str] = field(default_factory=lambda: ["qwen"])  # 允许的LLM提供商
    rate_limits: RateLimitConfig = field(default_factory=RateLimitConfig)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def create(
        cls,
        name: str,
        tier: TenantTier = TenantTier.FREE,
        isolation_strategy: IsolationStrategy = IsolationStrategy.SHARED,
    ) -> Tenant:
        """创建新租户"""
        return cls(
            tenant_id=f"tenant-{uuid.uuid4().hex[:8]}",
            name=name,
            tier=tier,
            isolation_strategy=isolation_strategy,
            storage_config=StorageConfig(),
            rate_limits=RateLimitConfig(),
        )


@dataclass
class Department:
    """部门模型"""
    dept_id: str                         # 部门ID（UUID）
    tenant_id: str                       # 所属租户
    name: str                            # 部门名称
    parent_dept_id: Optional[str] = None  # 上级部门
    dept_type: str = "business"          # 部门类型
    created_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def create(cls, tenant_id: str, name: str, dept_type: str = "business") -> Department:
        """创建新部门"""
        return cls(
            dept_id=f"dept-{uuid.uuid4().hex[:8]}",
            tenant_id=tenant_id,
            name=name,
            dept_type=dept_type,
        )


@dataclass
class TenantUser:
    """租户用户模型"""
    user_id: str                         # 用户ID（UUID）
    tenant_id: str                       # 所属租户
    department_id: str                   # 所属部门
    username: str                        # 登录名
    display_name: str                   # 显示名称
    role: str = "user"                  # 角色：admin/user/auditor
    phone: str = ""                      # 手机号
    email: str = ""                       # 邮箱
    status: str = "active"               # 状态：active/disabled
    created_at: datetime = field(default_factory=datetime.now)
    last_login: Optional[datetime] = None

    @classmethod
    def create(
        cls,
        tenant_id: str,
        department_id: str,
        username: str,
        display_name: str,
        role: str = "user",
    ) -> TenantUser:
        """创建新用户"""
        return cls(
            user_id=f"user-{uuid.uuid4().hex[:8]}",
            tenant_id=tenant_id,
            department_id=department_id,
            username=username,
            display_name=display_name,
            role=role,
        )


@dataclass
class TenantContext:
    """租户上下文 - 用于在请求生命周期内传递租户信息"""
    tenant: Tenant                       # 当前租户
    user: Optional[TenantUser] = None    # 当前用户
    request_id: str = ""                 # 请求ID
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.request_id:
            self.request_id = str(uuid.uuid4())


# ============================================================================
# 上下文管理器
# ============================================================================

class TenantContextManager:
    """
    租户上下文管理器

    提供上下文设置、获取、清除等操作
    使用ContextVar实现线程/协程安全的上下文隔离
    """

    @staticmethod
    def set_context(context: TenantContext) -> None:
        """设置当前租户上下文"""
        _tenant_context_var.set(context)

    @staticmethod
    def get_context() -> Optional[TenantContext]:
        """获取当前租户上下文"""
        return _tenant_context_var.get()

    @staticmethod
    def clear_context() -> None:
        """清除当前租户上下文"""
        _tenant_context_var.set(None)

    @staticmethod
    def get_current_tenant() -> Optional[Tenant]:
        """获取当前租户"""
        ctx = _tenant_context_var.get()
        return ctx.tenant if ctx else None

    @staticmethod
    def get_current_user() -> Optional[TenantUser]:
        """获取当前用户"""
        ctx = _tenant_context_var.get()
        return ctx.user if ctx else None

    @staticmethod
    def get_tenant_id() -> Optional[str]:
        """获取当前租户ID"""
        tenant = TenantContextManager.get_current_tenant()
        return tenant.tenant_id if tenant else None


# 便捷函数
def get_current_tenant_context() -> Optional[TenantContext]:
    """获取当前租户上下文"""
    return TenantContextManager.get_context()


def get_current_tenant() -> Optional[Tenant]:
    """获取当前租户"""
    return TenantContextManager.get_current_tenant()


def get_current_user() -> Optional[TenantUser]:
    """获取当前用户"""
    return TenantContextManager.get_current_user()


# ============================================================================
# 存储后端接口
# ============================================================================

class StorageBackend(Protocol):
    """存储后端协议"""

    def get_base_path(self) -> Path:
        """获取基础路径"""
        ...

    def get_tenant_path(self, tenant_id: str) -> Path:
        """获取租户专属路径"""
        ...

    def get_sessions_path(self, tenant_id: str) -> Path:
        """获取会话数据路径"""
        ...

    def get_memories_path(self, tenant_id: str) -> Path:
        """获取记忆数据路径"""
        ...

    def get_skills_path(self, tenant_id: str) -> Path:
        """获取技能数据路径"""
        ...

    def get_configs_path(self, tenant_id: str) -> Path:
        """获取配置文件路径"""
        ...

    def get_logs_path(self, tenant_id: str) -> Path:
        """获取日志路径"""
        ...


class SharedStorageBackend:
    """
    SHARED策略存储后端 - 共享存储 + 路径前缀隔离

    所有租户共享同一存储后端，通过租户ID作为路径前缀实现逻辑隔离
    """

    def __init__(self, base_path: Path):
        self.base_path = Path(base_path)

    def get_base_path(self) -> Path:
        """获取基础路径"""
        return self.base_path

    def get_tenant_path(self, tenant_id: str) -> Path:
        """获取租户专属路径"""
        return self.base_path / "tenants" / tenant_id

    def get_sessions_path(self, tenant_id: str) -> Path:
        """获取会话数据路径"""
        return self.get_tenant_path(tenant_id) / "sessions"

    def get_memories_path(self, tenant_id: str) -> Path:
        """获取记忆数据路径"""
        return self.get_tenant_path(tenant_id) / "memories"

    def get_skills_path(self, tenant_id: str) -> Path:
        """获取技能数据路径"""
        return self.get_tenant_path(tenant_id) / "skills"

    def get_configs_path(self, tenant_id: str) -> Path:
        """获取配置文件路径"""
        return self.get_tenant_path(tenant_id) / "configs"

    def get_logs_path(self, tenant_id: str) -> Path:
        """获取日志路径"""
        return self.get_tenant_path(tenant_id) / "logs"

    def ensure_tenant_dirs(self, tenant_id: str) -> None:
        """确保租户目录结构存在"""
        subdirs = ["sessions", "memories", "skills", "configs", "logs"]
        for subdir in subdirs:
            (self.get_tenant_path(tenant_id) / subdir).mkdir(parents=True, exist_ok=True)

    def get_current_tenant_path(self) -> Path:
        """获取当前上下文的租户路径"""
        tenant_id = TenantContextManager.get_tenant_id()
        if not tenant_id:
            raise RuntimeError("No tenant context available")
        return self.get_tenant_path(tenant_id)


class LogicalStorageBackend:
    """
    LOGICAL策略存储后端 - 独立数据库schema隔离

    每个租户拥有独立的数据库schema，通过schema实现数据隔离
    """

    def __init__(self, base_path: Path):
        self.base_path = Path(base_path)
        self._connections: Dict[str, Any] = {}

    def get_base_path(self) -> Path:
        """获取基础路径"""
        return self.base_path

    def get_tenant_path(self, tenant_id: str) -> Path:
        """获取租户专属路径"""
        return self.base_path / "tenants" / tenant_id

    def get_db_path(self, tenant_id: str) -> Path:
        """获取租户数据库路径"""
        return self.get_tenant_path(tenant_id) / "data.db"

    def get_sessions_path(self, tenant_id: str) -> Path:
        """获取会话数据路径"""
        return self.get_tenant_path(tenant_id) / "sessions"

    def get_memories_path(self, tenant_id: str) -> Path:
        """获取记忆数据路径"""
        return self.get_tenant_path(tenant_id) / "memories"

    def get_skills_path(self, tenant_id: str) -> Path:
        """获取技能数据路径"""
        return self.get_tenant_path(tenant_id) / "skills"

    def get_configs_path(self, tenant_id: str) -> Path:
        """获取配置文件路径"""
        return self.get_tenant_path(tenant_id) / "configs"

    def get_logs_path(self, tenant_id: str) -> Path:
        """获取日志路径"""
        return self.get_tenant_path(tenant_id) / "logs"

    def ensure_tenant_dirs(self, tenant_id: str) -> None:
        """确保租户目录结构存在"""
        subdirs = ["sessions", "memories", "skills", "configs", "logs"]
        for subdir in subdirs:
            (self.get_tenant_path(tenant_id) / subdir).mkdir(parents=True, exist_ok=True)
        # 确保数据库文件存在
        self.get_db_path(tenant_id).parent.mkdir(parents=True, exist_ok=True)

    def get_current_tenant_path(self) -> Path:
        """获取当前上下文的租户路径"""
        tenant_id = TenantContextManager.get_tenant_id()
        if not tenant_id:
            raise RuntimeError("No tenant context available")
        return self.get_tenant_path(tenant_id)


class PhysicalStorageBackend:
    """
    PHYSICAL策略存储后端 - 独立存储桶隔离

    每个租户拥有完全独立的存储区域，实现最高级别的数据隔离
    """

    def __init__(self, base_path: Path):
        self.base_path = Path(base_path)
        self._connections: Dict[str, Any] = {}

    def get_base_path(self) -> Path:
        """获取基础路径"""
        return self.base_path

    def get_tenant_path(self, tenant_id: str) -> Path:
        """获取租户专属路径"""
        return self.base_path / "instances" / tenant_id

    def get_db_path(self, tenant_id: str) -> Path:
        """获取租户数据库路径"""
        return self.get_tenant_path(tenant_id) / "data.db"

    def get_sessions_path(self, tenant_id: str) -> Path:
        """获取会话数据路径"""
        return self.get_tenant_path(tenant_id) / "sessions"

    def get_memories_path(self, tenant_id: str) -> Path:
        """获取记忆数据路径"""
        return self.get_tenant_path(tenant_id) / "memories"

    def get_skills_path(self, tenant_id: str) -> Path:
        """获取技能数据路径"""
        return self.get_tenant_path(tenant_id) / "skills"

    def get_configs_path(self, tenant_id: str) -> Path:
        """获取配置文件路径"""
        return self.get_tenant_path(tenant_id) / "configs"

    def get_logs_path(self, tenant_id: str) -> Path:
        """获取日志路径"""
        return self.get_tenant_path(tenant_id) / "logs"

    def ensure_tenant_dirs(self, tenant_id: str) -> None:
        """确保租户目录结构存在"""
        subdirs = ["sessions", "memories", "skills", "configs", "logs"]
        for subdir in subdirs:
            (self.get_tenant_path(tenant_id) / subdir).mkdir(parents=True, exist_ok=True)
        # 确保数据库文件存在
        self.get_db_path(tenant_id).parent.mkdir(parents=True, exist_ok=True)

    def get_current_tenant_path(self) -> Path:
        """获取当前上下文的租户路径"""
        tenant_id = TenantContextManager.get_tenant_id()
        if not tenant_id:
            raise RuntimeError("No tenant context available")
        return self.get_tenant_path(tenant_id)


def create_storage_backend(
    strategy: IsolationStrategy,
    base_path: Path,
) -> StorageBackend:
    """根据隔离策略创建存储后端"""
    backends = {
        IsolationStrategy.SHARED: SharedStorageBackend,
        IsolationStrategy.LOGICAL: LogicalStorageBackend,
        IsolationStrategy.PHYSICAL: PhysicalStorageBackend,
    }
    backend_class = backends.get(strategy, SharedStorageBackend)
    return backend_class(base_path)
