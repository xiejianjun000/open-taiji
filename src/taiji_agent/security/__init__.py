"""
Security & Compliance Module (安全合规模块)
Taiji Agent Phase 3 安全合规模块

基于等保2.0三级要求和GB/T国密标准实现：

子模块：
- Sandbox: Agent执行沙箱隔离与资源限制
- KeyManager: 密钥轮换管理与加密存储
- Audit: 不可篡改审计链
- Incident: 应急响应与预案管理
- Desensitize: 敏感数据识别与脱敏

生态环境部安全4层防护体系映射：
- 应用层安全防护 → 拒答超范围提问 (Sandbox)
- 技术保障体系 → 4A认证+敏感行为拦截+安全围栏 (Sandbox, Desensitize)
- 基础设施自主可控 → 本地化部署+信创适配
- 安全管理制度 → 规范体系+攻防演练 (Incident, Audit)

GovMCP政务合规协议兼容
"""

from taiji_agent.security.sandbox import (
    Sandbox,
    SandboxConfig,
    SandboxResult,
    SandboxStatus,
    SandboxPool,
    SecurityFence,
    ResourceLimit,
)

from taiji_agent.security.key_manager import (
    KeyManager,
    KeyMetadata,
    KeyRotationConfig,
    KeyRotationResult,
    KeyType,
    KeyStatus,
)

from taiji_agent.security.audit import (
    AuditChain,
    AuditEntry,
    AuditResource,
    AuditQuery,
    AuditManager,
    AuditAction,
    DataLevel,
    ComplianceReport,
    SM3Hasher,
)

from taiji_agent.security.incident import (
    IncidentResponseManager,
    Incident,
    IncidentLevel,
    IncidentStatus,
    IncidentCategory,
    IncidentImpact,
    IncidentHandler,
    IncidentAction,
    EmergencyPlan,
)

from taiji_agent.security.desensitize import (
    SensitiveDataDetector,
    DesensitizationEngine,
    DesensitizationPolicy,
    DesensitizationRule,
    DesensitizationResult,
    DetectionResult,
    SensitiveType,
    DesensitizationMethod,
)


__all__ = [
    # Sandbox
    "Sandbox",
    "SandboxConfig",
    "SandboxResult",
    "SandboxStatus",
    "SandboxPool",
    "SecurityFence",
    "ResourceLimit",
    
    # KeyManager
    "KeyManager",
    "KeyMetadata",
    "KeyRotationConfig",
    "KeyRotationResult",
    "KeyType",
    "KeyStatus",
    
    # Audit
    "AuditChain",
    "AuditEntry",
    "AuditResource",
    "AuditQuery",
    "AuditManager",
    "AuditAction",
    "DataLevel",
    "ComplianceReport",
    "SM3Hasher",
    
    # Incident
    "IncidentResponseManager",
    "Incident",
    "IncidentLevel",
    "IncidentStatus",
    "IncidentCategory",
    "IncidentImpact",
    "IncidentHandler",
    "IncidentAction",
    "EmergencyPlan",
    
    # Desensitize
    "SensitiveDataDetector",
    "DesensitizationEngine",
    "DesensitizationPolicy",
    "DesensitizationRule",
    "DesensitizationResult",
    "DetectionResult",
    "SensitiveType",
    "DesensitizationMethod",
]


__version__ = "1.0.0"

# Sandbox (v2.1 升级)
from taiji_agent.security.sandbox import (
    SecuritySandbox,
    CodeSandbox,
    SandboxConfig,
    SandboxResult,
    default_sandbox,
    code_sandbox,
)
