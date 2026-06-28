"""
Audit (审计日志)
不可篡改审计链模块

基于等保2.0三级要求和SM3国密标准实现：
- 操作审计（谁在什么时间做了什么）
- 数据访问审计
- 合规报告生成

审计链采用SM3哈希实现链式锁定，确保审计记录不可篡改。
映射生态环境部技术保障体系：4A认证+敏感行为拦截+安全围栏
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Any


class AuditAction(str, Enum):
    """审计操作类型"""
    # 审批操作
    APPROVAL_INITIATE = "approval_initiate"
    APPROVAL_PASS = "approval_pass"
    APPROVAL_REJECT = "approval_reject"
    APPROVAL_SKIP = "approval_skip"
    APPROVAL_DELEGATE = "approval_delegate"
    APPROVAL_TRANSFER = "approval_transfer"
    APPROVAL_COUNTER_SIGN = "approval_counter_sign"
    APPROVAL_JOINT_SIGN = "approval_joint_sign"
    
    # 数据操作
    DATA_READ = "data_read"
    DATA_WRITE = "data_write"
    DATA_DELETE = "data_delete"
    DATA_EXPORT = "data_export"
    
    # 配置操作
    CONFIG_CHANGE = "config_change"
    
    # 权限操作
    PERMISSION_CHANGE = "permission_change"
    USER_CREATE = "user_create"
    USER_DELETE = "user_delete"
    USER_ROLE_CHANGE = "user_role_change"
    
    # 安全事件
    LOGIN_SUCCESS = "system_login"
    LOGIN_FAILURE = "system_login_failure"
    LOGOUT = "system_logout"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    SENSITIVE_BEHAVIOR = "sensitive_behavior"
    
    # 系统操作
    SYSTEM_INIT = "system_init"
    KEY_ROTATION = "key_rotation"
    BACKUP = "backup"
    RESTORE = "restore"


class DataLevel(str, Enum):
    """数据敏感级别"""
    L1_PUBLIC = "L1"      # 公开
    L2_INTERNAL = "L2"    # 内部
    L3_SENSITIVE = "L3"  # 敏感
    L4_CONFIDENTIAL = "L4"  # 机密


@dataclass
class AuditResource:
    """被操作资源"""
    type: str                    # 资源类型
    id: str                      # 资源ID
    name: str = ""               # 资源名称
    level: DataLevel = DataLevel.L1_PUBLIC  # 资源敏感级别


@dataclass
class AuditEntry:
    """
    审计记录条目
    
    基于SM3哈希链实现不可篡改：
    current_hash = SM3(prev_hash || timestamp || action || input_hash || output_hash)
    """
    # 基础信息
    id: int                      # 顺序ID
    timestamp: float             # Unix时间戳（微秒精度）
    tenant_id: str               # 租户ID
    user_id: str                 # 操作者ID
    session_id: str = ""         # 会话ID
    
    # 操作信息
    action: AuditAction = AuditAction.SYSTEM_INIT
    resource: Optional[AuditResource] = None
    details: dict = field(default_factory=dict)
    
    # 完整性校验
    prev_hash: str = ""           # 前驱记录的current_hash（64个'0'为创世块）
    current_hash: str = ""        # 本条记录的SM3哈希
    input_hash: str = ""          # 输入数据的SM3哈希
    output_hash: str = ""         # 输出数据的SM3哈希
    
    # 签名（可选）
    signature: str = ""           # SM2签名（高安全场景启用）
    
    def __post_init__(self):
        if isinstance(self.action, str):
            self.action = AuditAction(self.action)
        if isinstance(self.resource, dict):
            self.resource = AuditResource(**self.resource)
        if self.resource and isinstance(self.resource, AuditResource) and isinstance(self.resource.level, str):
            self.resource.level = DataLevel(self.resource.level)


@dataclass
class AuditQuery:
    """审计查询条件"""
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    action: Optional[AuditAction] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    limit: int = 100
    offset: int = 0


@dataclass
class ComplianceReport:
    """合规报告"""
    report_id: str
    generated_at: float
    period_start: float
    period_end: float
    tenant_id: str
    
    # 统计数据
    total_entries: int = 0
    entries_by_action: dict = field(default_factory=dict)
    entries_by_user: dict = field(default_factory=dict)
    entries_by_level: dict = field(default_factory=dict)
    
    # 安全统计
    failed_logins: int = 0
    unauthorized_accesses: int = 0
    sensitive_behaviors: int = 0
    config_changes: int = 0
    
    # 合规性
    chain_integrity_verified: bool = True
    missing_entries: list[int] = field(default_factory=list)
    
    # 详情
    details: list[AuditEntry] = field(default_factory=list)
    
    # 签名
    report_hash: str = ""


class SM3Hasher:
    """
    SM3哈希器
    
    注：生产环境应使用GB/T 32905-2016 SM3算法
    此处使用SHA-256作为占位实现（输出同样是256位）
    """
    
    GENESIS_HASH = "0" * 64  # 创世块哈希
    
    @classmethod
    def hash(cls, data: str) -> str:
        """
        计算哈希值
        
        Args:
            data: 待哈希数据
            
        Returns:
            64字符十六进制哈希
        """
        if isinstance(data, str):
            data = data.encode('utf-8')
        return hashlib.sha256(data).hexdigest()
    
    @classmethod
    def hash_entry(cls, entry: AuditEntry) -> str:
        """
        计算审计记录的哈希
        
        格式: current_hash = SM3(prev_hash || timestamp || action || input_hash || output_hash)
        """
        data = "|".join([
            entry.prev_hash,
            str(entry.timestamp),
            entry.action.value if isinstance(entry.action, AuditAction) else str(entry.action),
            entry.input_hash,
            entry.output_hash
        ])
        return cls.hash(data)
    
    @classmethod
    def hash_dict(cls, data: dict) -> str:
        """对字典数据进行哈希"""
        # 确保字典有序且可序列化
        json_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return cls.hash(json_str)


class AuditChain:
    """
    不可篡改审计链
    
    使用SM3哈希实现链式锁定，确保审计记录不可篡改、不可抵赖。
    
    Usage::
        chain = AuditChain(tenant_id="org_001")
        chain.add_entry(user_id="user_123", action=AuditAction.DATA_READ, 
                       resource=AuditResource(type="document", id="doc_001"))
        
        # 验证完整性
        is_valid = chain.verify()
        
        # 查询审计记录
        entries = chain.query(start_time=time.time() - 86400)
    """
    
    def __init__(
        self,
        tenant_id: str,
        storage_path: str = ".audit",
        salt: Optional[str] = None
    ):
        self.tenant_id = tenant_id
        self.storage_path = storage_path
        self.salt = salt or str(uuid.uuid4())
        
        self._entries: list[AuditEntry] = []
        self._entry_index: dict[int, AuditEntry] = {}  # id -> entry
        self._next_id: int = 1
        
        # 确保存储目录存在
        os.makedirs(storage_path, exist_ok=True)
        
        # 加载已有记录
        self._load()
    
    def add_entry(
        self,
        user_id: str,
        action: AuditAction,
        resource: Optional[AuditResource] = None,
        details: Optional[dict] = None,
        input_data: Optional[dict] = None,
        output_data: Optional[dict] = None,
        session_id: str = "",
        user_signature: str = ""
    ) -> AuditEntry:
        """
        添加审计记录
        
        Args:
            user_id: 操作者ID
            action: 操作类型
            resource: 被操作资源
            details: 操作详情
            input_data: 输入数据（会被哈希存储）
            output_data: 输出数据（会被哈希存储）
            session_id: 会话ID
            user_signature: 用户签名（可选）
            
        Returns:
            审计记录条目
        """
        # 计算输入输出哈希
        input_hash = SM3Hasher.hash_dict(input_data) if input_data else ""
        output_hash = SM3Hasher.hash_dict(output_data) if output_data else ""
        
        # 获取前驱哈希
        prev_hash = self._entries[-1].current_hash if self._entries else SM3Hasher.GENESIS_HASH
        
        # 创建审计记录
        entry = AuditEntry(
            id=self._next_id,
            timestamp=time.time(),
            tenant_id=self.tenant_id,
            user_id=user_id,
            session_id=session_id,
            action=action,
            resource=resource,
            details=details or {},
            prev_hash=prev_hash,
            input_hash=input_hash,
            output_hash=output_hash,
            signature=user_signature
        )
        
        # 计算当前哈希
        entry.current_hash = SM3Hasher.hash_entry(entry)
        
        # 添加到链
        self._entries.append(entry)
        self._entry_index[entry.id] = entry
        self._next_id += 1
        
        # 持久化
        self._save_entry(entry)
        
        return entry
    
    def get_entry(self, entry_id: int) -> Optional[AuditEntry]:
        """获取指定ID的审计记录"""
        return self._entry_index.get(entry_id)
    
    def get_last_entry(self) -> Optional[AuditEntry]:
        """获取最新审计记录"""
        return self._entries[-1] if self._entries else None
    
    def verify(self) -> tuple[bool, list[int]]:
        """
        验证审计链完整性
        
        Returns:
            (是否完整, 损坏的条目ID列表)
        """
        if not self._entries:
            return True, []
        
        broken_entries = []
        
        for i, entry in enumerate(self._entries):
            # 验证哈希链
            expected_hash = SM3Hasher.hash_entry(entry)
            if entry.current_hash != expected_hash:
                broken_entries.append(entry.id)
                continue
            
            # 验证前驱链接
            if i == 0:
                # 创世块检查
                if entry.prev_hash != SM3Hasher.GENESIS_HASH:
                    broken_entries.append(entry.id)
            else:
                # 检查前驱哈希
                prev_entry = self._entries[i - 1]
                if entry.prev_hash != prev_entry.current_hash:
                    broken_entries.append(entry.id)
            
            # 验证ID连续性
            if i > 0:
                prev_entry = self._entries[i - 1]
                if entry.id != prev_entry.id + 1:
                    broken_entries.append(entry.id)
        
        return len(broken_entries) == 0, broken_entries
    
    def query(self, query: AuditQuery) -> list[AuditEntry]:
        """
        查询审计记录
        
        Args:
            query: 查询条件
            
        Returns:
            匹配的审计记录列表
        """
        results = []
        
        for entry in self._entries:
            # 租户过滤
            if query.tenant_id and entry.tenant_id != query.tenant_id:
                continue
            
            # 用户过滤
            if query.user_id and entry.user_id != query.user_id:
                continue
            
            # 操作类型过滤
            if query.action and entry.action != query.action:
                continue
            
            # 时间范围过滤
            if query.start_time and entry.timestamp < query.start_time:
                continue
            if query.end_time and entry.timestamp > query.end_time:
                continue
            
            # 资源类型过滤
            if query.resource_type and entry.resource:
                if entry.resource.type != query.resource_type:
                    continue
            
            # 资源ID过滤
            if query.resource_id and entry.resource:
                if entry.resource.id != query.resource_id:
                    continue
            
            results.append(entry)
        
        # 分页
        return results[query.offset:query.offset + query.limit]
    
    def get_user_activity(
        self,
        user_id: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> list[AuditEntry]:
        """获取用户活动记录"""
        query = AuditQuery(
            user_id=user_id,
            start_time=start_time,
            end_time=end_time,
            limit=1000
        )
        return self.query(query)
    
    def get_resource_history(
        self,
        resource_type: str,
        resource_id: str
    ) -> list[AuditEntry]:
        """获取资源操作历史"""
        query = AuditQuery(
            resource_type=resource_type,
            resource_id=resource_id,
            limit=1000
        )
        return self.query(query)
    
    def get_chain_hash(self) -> str:
        """获取当前链的最新哈希（用于验证）"""
        last = self.get_last_entry()
        return last.current_hash if last else SM3Hasher.GENESIS_HASH
    
    def generate_compliance_report(
        self,
        start_time: float,
        end_time: float
    ) -> ComplianceReport:
        """
        生成合规报告
        
        Args:
            start_time: 报告开始时间
            end_time: 报告结束时间
            
        Returns:
            合规报告
        """
        report_id = f"report_{self.tenant_id}_{int(time.time())}"
        
        # 查询时间范围内的记录
        query = AuditQuery(
            tenant_id=self.tenant_id,
            start_time=start_time,
            end_time=end_time,
            limit=10000
        )
        entries = self.query(query)
        
        # 统计数据
        entries_by_action: dict[str, int] = {}
        entries_by_user: dict[str, int] = {}
        entries_by_level: dict[str, int] = {}
        failed_logins = 0
        unauthorized_accesses = 0
        sensitive_behaviors = 0
        config_changes = 0
        
        for entry in entries:
            # 按操作类型统计
            action_key = entry.action.value if isinstance(entry.action, AuditAction) else str(entry.action)
            entries_by_action[action_key] = entries_by_action.get(action_key, 0) + 1
            
            # 按用户统计
            entries_by_user[entry.user_id] = entries_by_user.get(entry.user_id, 0) + 1
            
            # 按数据级别统计
            if entry.resource:
                level_key = entry.resource.level.value if isinstance(entry.resource.level, DataLevel) else str(entry.resource.level)
                entries_by_level[level_key] = entries_by_level.get(level_key, 0) + 1
            
            # 特殊操作统计
            if entry.action == AuditAction.LOGIN_FAILURE:
                failed_logins += 1
            elif entry.action == AuditAction.UNAUTHORIZED_ACCESS:
                unauthorized_accesses += 1
            elif entry.action == AuditAction.SENSITIVE_BEHAVIOR:
                sensitive_behaviors += 1
            elif entry.action == AuditAction.CONFIG_CHANGE:
                config_changes += 1
        
        # 验证链完整性
        chain_valid, broken = self.verify()
        
        # 生成报告
        report = ComplianceReport(
            report_id=report_id,
            generated_at=time.time(),
            period_start=start_time,
            period_end=end_time,
            tenant_id=self.tenant_id,
            total_entries=len(entries),
            entries_by_action=entries_by_action,
            entries_by_user=entries_by_user,
            entries_by_level=entries_by_level,
            failed_logins=failed_logins,
            unauthorized_accesses=unauthorized_accesses,
            sensitive_behaviors=sensitive_behaviors,
            config_changes=config_changes,
            chain_integrity_verified=chain_valid,
            missing_entries=broken,
            details=entries[:100]  # 只包含前100条详情
        )
        
        # 计算报告哈希
        report_data = f"{report.total_entries}|{report.failed_logins}|{report.unauthorized_accesses}"
        report.report_hash = SM3Hasher.hash(report_data)
        
        return report
    
    def export_chain(self) -> str:
        """导出审计链（JSON格式）"""
        return json.dumps([
            {
                "id": e.id,
                "timestamp": e.timestamp,
                "tenant_id": e.tenant_id,
                "user_id": e.user_id,
                "session_id": e.session_id,
                "action": e.action.value if isinstance(e.action, AuditAction) else str(e.action),
                "resource": {
                    "type": e.resource.type,
                    "id": e.resource.id,
                    "name": e.resource.name,
                    "level": e.resource.level.value if isinstance(e.resource.level, DataLevel) else str(e.resource.level)
                } if e.resource else None,
                "details": e.details,
                "prev_hash": e.prev_hash,
                "current_hash": e.current_hash,
                "input_hash": e.input_hash,
                "output_hash": e.output_hash,
                "signature": e.signature
            }
            for e in self._entries
        ], indent=2, ensure_ascii=False)
    
    def _get_storage_file(self) -> str:
        """获取存储文件路径"""
        return os.path.join(self.storage_path, f"audit_{self.tenant_id}.json")
    
    def _save_entry(self, entry: AuditEntry) -> None:
        """保存单条记录到磁盘"""
        file_path = self._get_storage_file()
        
        # 追加写入
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "id": entry.id,
                "timestamp": entry.timestamp,
                "tenant_id": entry.tenant_id,
                "user_id": entry.user_id,
                "session_id": entry.session_id,
                "action": entry.action.value if isinstance(entry.action, AuditAction) else str(entry.action),
                "resource": {
                    "type": entry.resource.type,
                    "id": entry.resource.id,
                    "name": entry.resource.name,
                    "level": entry.resource.level.value if isinstance(entry.resource.level, DataLevel) else str(entry.resource.level)
                } if entry.resource else None,
                "details": entry.details,
                "prev_hash": entry.prev_hash,
                "current_hash": entry.current_hash,
                "input_hash": entry.input_hash,
                "output_hash": entry.output_hash,
                "signature": entry.signature
            }, ensure_ascii=False) + "\n")
    
    def _load(self) -> None:
        """从磁盘加载审计记录"""
        file_path = self._get_storage_file()
        
        if not os.path.exists(file_path):
            return
        
        self._entries = []
        self._entry_index = {}
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    
                    # 重建审计记录
                    entry = AuditEntry(
                        id=data["id"],
                        timestamp=data["timestamp"],
                        tenant_id=data["tenant_id"],
                        user_id=data["user_id"],
                        session_id=data.get("session_id", ""),
                        action=AuditAction(data["action"]) if isinstance(data["action"], str) else data["action"],
                        resource=AuditResource(**data["resource"]) if data.get("resource") else None,
                        details=data.get("details", {}),
                        prev_hash=data.get("prev_hash", ""),
                        current_hash=data["current_hash"],
                        input_hash=data.get("input_hash", ""),
                        output_hash=data.get("output_hash", ""),
                        signature=data.get("signature", "")
                    )
                    
                    self._entries.append(entry)
                    self._entry_index[entry.id] = entry
            
            # 更新下一个ID
            if self._entries:
                self._next_id = max(e.id for e in self._entries) + 1
                
        except Exception:
            # 文件损坏时重建
            self._entries = []
            self._entry_index = {}
            self._next_id = 1
    
    def get_statistics(self, days: int = 30) -> dict:
        """获取统计数据"""
        cutoff = time.time() - days * 86400
        
        stats = {
            "total_entries": 0,
            "entries_today": 0,
            "unique_users": set(),
            "action_counts": {},
            "security_events": 0
        }
        
        today_start = time.time() - time.time() % 86400
        
        for entry in self._entries:
            if entry.timestamp < cutoff:
                continue
            
            stats["total_entries"] += 1
            stats["unique_users"].add(entry.user_id)
            
            if entry.timestamp >= today_start:
                stats["entries_today"] += 1
            
            action_key = entry.action.value if isinstance(entry.action, AuditAction) else str(entry.action)
            stats["action_counts"][action_key] = stats["action_counts"].get(action_key, 0) + 1
            
            if entry.action in (
                AuditAction.LOGIN_FAILURE,
                AuditAction.UNAUTHORIZED_ACCESS,
                AuditAction.SENSITIVE_BEHAVIOR
            ):
                stats["security_events"] += 1
        
        # 转换set为count
        stats["unique_users"] = len(stats["unique_users"])
        
        return stats


class AuditManager:
    """
    审计管理器
    
    管理多个租户的审计链，提供统一的审计接口。
    
    Usage::
        manager = AuditManager(storage_path=".audit")
        
        # 获取或创建租户审计链
        chain = manager.get_chain("org_001")
        chain.add_entry(user_id="user_1", action=AuditAction.DATA_READ)
        
        # 生成合规报告
        report = manager.generate_report("org_001", start_time, end_time)
    """
    
    def __init__(self, storage_path: str = ".audit"):
        self.storage_path = storage_path
        self._chains: dict[str, AuditChain] = {}
    
    def get_chain(self, tenant_id: str) -> AuditChain:
        """
        获取租户审计链
        
        Args:
            tenant_id: 租户ID
            
        Returns:
            AuditChain 审计链实例
        """
        if tenant_id not in self._chains:
            self._chains[tenant_id] = AuditChain(
                tenant_id=tenant_id,
                storage_path=self.storage_path
            )
        return self._chains[tenant_id]
    
    def generate_report(
        self,
        tenant_id: str,
        start_time: float,
        end_time: float
    ) -> Optional[ComplianceReport]:
        """生成合规报告"""
        chain = self.get_chain(tenant_id)
        return chain.generate_compliance_report(start_time, end_time)
    
    def list_tenants(self) -> list[str]:
        """列出所有有审计记录的租户"""
        tenants = set()
        storage_file = os.path.join(self.storage_path, f"audit_")
        
        if os.path.exists(self.storage_path):
            for filename in os.listdir(self.storage_path):
                if filename.startswith("audit_") and filename.endswith(".json"):
                    tenant_id = filename[6:-5]  # 去掉 "audit_" 和 ".json"
                    tenants.add(tenant_id)
        
        return list(tenants)
