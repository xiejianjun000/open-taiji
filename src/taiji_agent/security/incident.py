"""
Incident Response (应急响应)
安全事件响应与应急预案管理模块

基于等保2.0三级要求和数据安全法实现：
- 4级应急响应分级（L1一般/L2较大/L3重大/L4特别重大）
- 应急预案管理
- 事件处置流程

映射生态环境部安全管理制度：规范体系+攻防演练
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Any, Callable


class IncidentLevel(str, Enum):
    """
    应急响应级别
    
    L1 一般: 一般性配置异常、性能波动
    L2 较大: 非核心功能异常、可疑行为告警
    L3 重大: 核心功能降级、安全漏洞被利用
    L4 特别重大: 系统瘫痪、数据泄露、核心功能不可用
    """
    L1_GENERAL = "L1"        # 一般事件
    L2_SIGNIFICANT = "L2"     # 较大事件
    L3_MAJOR = "L3"           # 重大事件
    L4_CRITICAL = "L4"        # 特别重大事件
    
    @property
    def response_time_minutes(self) -> int:
        """响应时间要求（分钟）"""
        mapping = {
            IncidentLevel.L1_GENERAL: 1440,     # 24小时
            IncidentLevel.L2_SIGNIFICANT: 240,  # 4小时
            IncidentLevel.L3_MAJOR: 60,         # 1小时
            IncidentLevel.L4_CRITICAL: 30       # 30分钟
        }
        return mapping.get(self, 1440)
    
    @property
    def resolution_time_hours(self) -> int:
        """处置时限要求（小时）"""
        mapping = {
            IncidentLevel.L1_GENERAL: 168,       # 7天
            IncidentLevel.L2_SIGNIFICANT: 72,    # 72小时
            IncidentLevel.L3_MAJOR: 24,          # 24小时
            IncidentLevel.L4_CRITICAL: 4         # 4小时
        }
        return mapping.get(self, 168)


class IncidentStatus(str, Enum):
    """事件状态"""
    DETECTED = "detected"           # 已检测
    ASSESSING = "assessing"         # 评估中
    CONFIRMED = "confirmed"         # 已确认
    CONTAINING = "containing"       # 遏制中
    ERADICATING = "eradicating"     # 根除中
    RECOVERING = "recovering"       # 恢复中
    RESOLVED = "resolved"           # 已解决
    CLOSED = "closed"               # 已关闭
    FALSE_ALARM = "false_alarm"     # 误报


class IncidentCategory(str, Enum):
    """事件类别"""
    # 数据安全
    DATA_BREACH = "data_breach"           # 数据泄露
    DATA_LOSS = "data_loss"               # 数据丢失
    DATA_TAMPERING = "data_tampering"    # 数据篡改
    
    # 系统安全
    SYSTEM_COMPROMISE = "system_compromise"  # 系统被入侵
    MALWARE_INFECTION = "malware_infection"  # 恶意软件感染
    DDoS_ATTACK = "ddos_attack"              # DDoS攻击
    
    # 应用安全
    UNAUTHORIZED_ACCESS = "unauthorized_access"  # 未授权访问
    PRIVILEGE_ESCALATION = "privilege_escalation"  # 权限提升
    INJECTION_ATTACK = "injection_attack"          # 注入攻击
    
    # 业务安全
    SERVICE_OUTAGE = "service_outage"       # 服务中断
    CONFIG_ERROR = "config_error"           # 配置错误
    PERFORMANCE_DEGRADATION = "performance_degradation"  # 性能降级
    
    # 生态环境场景
    MONITORING_DATA_FABRICATION = "monitoring_data_fabrication"  # 监测数据造假
    POLLUTION_REPORT_FALSIFICATION = "pollution_report_falsification"  # 污染报告造假


@dataclass
class IncidentImpact:
    """事件影响评估"""
    affected_users: int = 0           # 受影响用户数
    affected_systems: list[str] = field(default_factory=list)
    affected_data_level: str = "L1"    # 受影响数据级别
    business_impact: str = ""           # 业务影响描述
    reputational_impact: str = "none"   # 声誉影响：none/low/medium/high/critical
    financial_impact: float = 0.0      # 预估经济损失
    recovery_cost: float = 0.0         # 预估恢复成本


@dataclass
class IncidentHandler:
    """事件处理人员"""
    user_id: str
    name: str
    role: str                          # 角色：lead/analyst/communications/legal
    assigned_at: float
    status: str = "assigned"           # assigned/on_duty/off_duty
    contact: str = ""


@dataclass
class IncidentAction:
    """事件处置动作"""
    action_id: str
    timestamp: float
    handler_id: str
    action_type: str                   # contain/eradicate/recover/communicate
    description: str
    result: str = ""                   # success/partial/failure
    evidence: list[str] = field(default_factory=list)


@dataclass
class Incident:
    """
    安全事件
    
    包含事件的完整生命周期信息：
    - 检测与评估
    - 响应与处置
    - 恢复与总结
    """
    # 基础信息
    incident_id: str
    tenant_id: str
    
    # 分类信息
    level: IncidentLevel
    category: IncidentCategory
    title: str
    description: str
    
    # 时间信息
    detected_at: float
    reported_at: Optional[float] = None
    confirmed_at: Optional[float] = None
    resolved_at: Optional[float] = None
    closed_at: Optional[float] = None
    
    # 状态
    status: IncidentStatus = IncidentStatus.DETECTED
    
    # 影响评估
    impact: Optional[IncidentImpact] = None
    
    # 处置信息
    handlers: list[IncidentHandler] = field(default_factory=list)
    actions: list[IncidentAction] = field(default_factory=list)
    
    # 根因分析
    root_cause: str = ""
    affected_components: list[str] = field(default_factory=list)
    
    # 通知记录
    notifications_sent: list[dict] = field(default_factory=list)
    
    # 关联事件
    related_incidents: list[str] = field(default_factory=list)
    
    # 改进措施
    improvements: list[str] = field(default_factory=list)
    
    # 元数据
    metadata: dict = field(default_factory=dict)
    
    def __post_init__(self):
        if isinstance(self.level, str):
            self.level = IncidentLevel(self.level)
        if isinstance(self.category, str):
            self.category = IncidentCategory(self.category)
        if isinstance(self.status, str):
            self.status = IncidentStatus(self.status)


@dataclass
class EmergencyPlan:
    """应急预案"""
    plan_id: str
    tenant_id: str
    title: str
    description: str
    
    # 适用场景
    applicable_categories: list[IncidentCategory]
    applicable_levels: list[IncidentLevel]
    
    # 响应流程
    steps: list[dict] = field(default_factory=list)  # [{step, action, responsible, timeout}]
    
    # 联系人
    escalation_contacts: list[dict] = field(default_factory=dict)  # [{level, role, name, phone, email}]
    
    # 工具和资源
    required_tools: list[str] = field(default_factory=list)
    runbooks: list[str] = field(default_factory=list)
    
    # 状态
    enabled: bool = True
    version: str = "1.0"
    updated_at: float = field(default_factory=time.time)
    
    def get_escalation_for_level(self, level: IncidentLevel) -> list[dict]:
        """获取指定级别的升级联系人"""
        return [
            contact for contact in self.escalation_contacts
            if level.value in contact.get("levels", [])
        ]


class IncidentResponseManager:
    """
    应急响应管理器
    
    提供安全事件的完整生命周期管理：
    - 事件检测与报告
    - 级别评估与确认
    - 预案匹配与执行
    - 进度跟踪与升级
    - 事件复盘与改进
    
    Usage::
        manager = IncidentResponseManager(tenant_id="org_001")
        
        # 上报事件
        incident = manager.report_incident(
            level=IncidentLevel.L3_MAJOR,
            category=IncidentCategory.DATA_BREACH,
            title="检测到异常数据访问"
        )
        
        # 执行预案
        manager.execute_plan(incident.incident_id, plan_id="plan_001")
        
        # 添加处置动作
        manager.add_action(incident.incident_id, "contain", "隔离受影响系统")
    """
    
    def __init__(
        self,
        tenant_id: str,
        storage_path: str = ".incidents"
    ):
        self.tenant_id = tenant_id
        self.storage_path = storage_path
        self._incidents: dict[str, Incident] = {}
        self._plans: dict[str, EmergencyPlan] = {}
        
        # 确保存储目录存在
        os.makedirs(storage_path, exist_ok=True)
        
        # 加载数据
        self._load()
        
        # 初始化默认预案
        if not self._plans:
            self._init_default_plans()
    
    def _init_default_plans(self) -> None:
        """初始化默认应急预案"""
        # L4特别重大事件预案
        critical_plan = EmergencyPlan(
            plan_id="plan_critical_l4",
            tenant_id=self.tenant_id,
            title="L4特别重大事件应急响应预案",
            description="针对系统瘫痪、数据泄露等特别重大事件的应急响应流程",
            applicable_categories=[
                IncidentCategory.DATA_BREACH,
                IncidentCategory.SYSTEM_COMPROMISE,
                IncidentCategory.MONITORING_DATA_FABRICATION
            ],
            applicable_levels=[IncidentLevel.L4_CRITICAL],
            steps=[
                {
                    "step": 1,
                    "action": "立即隔离受影响系统",
                    "responsible": "安全运维",
                    "timeout_minutes": 15,
                    "description": "网络断开或服务下线"
                },
                {
                    "step": 2,
                    "action": "保留现场证据",
                    "responsible": "安全运维",
                    "timeout_minutes": 30,
                    "description": "日志快照、内存dump"
                },
                {
                    "step": 3,
                    "action": "评估影响范围",
                    "responsible": "安全团队",
                    "timeout_minutes": 60,
                    "description": "用户数、数据量、业务面"
                },
                {
                    "step": 4,
                    "action": "启动备选方案",
                    "responsible": "技术负责人",
                    "timeout_minutes": 120,
                    "description": "灾备切换或降级服务"
                },
                {
                    "step": 5,
                    "action": "通知相关方",
                    "responsible": "公关/法务",
                    "timeout_minutes": 180,
                    "description": "按法规要求通知用户和监管"
                }
            ],
            escalation_contacts=[
                {"levels": ["L4"], "role": "CEO", "name": "", "phone": "", "email": ""},
                {"levels": ["L4", "L3"], "role": "安全总监", "name": "", "phone": "", "email": ""},
                {"levels": ["L4", "L3", "L2"], "role": "运维主管", "name": "", "phone": "", "email": ""}
            ],
            required_tools=["取证工具箱", "备份恢复工具", "监控系统"],
            runbooks=["系统隔离操作手册", "数据备份恢复手册"]
        )
        self._plans[critical_plan.plan_id] = critical_plan
        
        # L3重大事件预案
        major_plan = EmergencyPlan(
            plan_id="plan_major_l3",
            tenant_id=self.tenant_id,
            title="L3重大事件应急响应预案",
            description="针对核心功能降级、安全漏洞被利用等重大事件的应急响应流程",
            applicable_categories=[
                IncidentCategory.MALWARE_INFECTION,
                IncidentCategory.DDoS_ATTACK,
                IncidentCategory.PRIVILEGE_ESCALATION
            ],
            applicable_levels=[IncidentLevel.L3_MAJOR],
            steps=[
                {
                    "step": 1,
                    "action": "确认事件真实性",
                    "responsible": "安全分析师",
                    "timeout_minutes": 30,
                    "description": "排除误报，确认攻击"
                },
                {
                    "step": 2,
                    "action": "启动遏制措施",
                    "responsible": "安全运维",
                    "timeout_minutes": 60,
                    "description": "IP封锁、账号禁用等"
                },
                {
                    "step": 3,
                    "action": "漏洞修复",
                    "responsible": "开发团队",
                    "timeout_minutes": 240,
                    "description": "紧急修复安全漏洞"
                },
                {
                    "step": 4,
                    "action": "服务恢复",
                    "responsible": "运维团队",
                    "timeout_minutes": 480,
                    "description": "恢复受影响服务"
                }
            ],
            escalation_contacts=[
                {"levels": ["L3"], "role": "安全总监", "name": "", "phone": "", "email": ""},
                {"levels": ["L3", "L2"], "role": "运维主管", "name": "", "phone": "", "email": ""}
            ],
            required_tools=["WAF", "IPS", "漏洞扫描器"],
            runbooks=["漏洞修复手册", "服务恢复手册"]
        )
        self._plans[major_plan.plan_id] = major_plan
        
        # 通用事件预案
        general_plan = EmergencyPlan(
            plan_id="plan_general",
            tenant_id=self.tenant_id,
            title="通用事件响应预案",
            description="适用于L1/L2级别事件的通用响应流程",
            applicable_categories=[
                IncidentCategory.CONFIG_ERROR,
                IncidentCategory.PERFORMANCE_DEGRADATION,
                IncidentCategory.SERVICE_OUTAGE
            ],
            applicable_levels=[IncidentLevel.L1_GENERAL, IncidentLevel.L2_SIGNIFICANT],
            steps=[
                {
                    "step": 1,
                    "action": "问题定位",
                    "responsible": "运维工程师",
                    "timeout_minutes": 60,
                    "description": "定位问题根因"
                },
                {
                    "step": 2,
                    "action": "问题修复",
                    "responsible": "运维工程师",
                    "timeout_minutes": 240,
                    "description": "执行修复操作"
                },
                {
                    "step": 3,
                    "action": "验证恢复",
                    "responsible": "运维工程师",
                    "timeout_minutes": 60,
                    "description": "确认服务正常"
                }
            ],
            escalation_contacts=[
                {"levels": ["L2", "L1"], "role": "运维工程师", "name": "", "phone": "", "email": ""}
            ],
            required_tools=["日志分析工具", "监控告警系统"],
            runbooks=["故障排查手册"]
        )
        self._plans[general_plan.plan_id] = general_plan
        
        self._save_plans()
    
    def report_incident(
        self,
        level: IncidentLevel,
        category: IncidentCategory,
        title: str,
        description: str,
        detected_at: Optional[float] = None,
        reported_by: str = "",
        initial_impact: Optional[IncidentImpact] = None
    ) -> Incident:
        """
        上报安全事件
        
        Args:
            level: 事件级别
            category: 事件类别
            title: 事件标题
            description: 事件描述
            detected_at: 检测时间
            reported_by: 上报人
            initial_impact: 初步影响评估
            
        Returns:
            创建的事件
        """
        incident_id = f"INC-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        
        incident = Incident(
            incident_id=incident_id,
            tenant_id=self.tenant_id,
            level=level,
            category=category,
            title=title,
            description=description,
            detected_at=detected_at or time.time(),
            reported_at=time.time(),
            impact=initial_impact or IncidentImpact()
        )
        
        self._incidents[incident_id] = incident
        self._save_incident(incident)
        
        return incident
    
    def assess_incident(
        self,
        incident_id: str,
        confirmed: bool = True,
        level: Optional[IncidentLevel] = None,
        impact: Optional[IncidentImpact] = None,
        assessor_id: str = ""
    ) -> bool:
        """
        评估事件
        
        Args:
            incident_id: 事件ID
            confirmed: 是否确认
            level: 确认级别
            impact: 影响评估
            assessor_id: 评估人ID
            
        Returns:
            是否成功
        """
        incident = self._incidents.get(incident_id)
        if not incident:
            return False
        
        incident.status = IncidentStatus.CONFIRMED if confirmed else IncidentStatus.FALSE_ALARM
        incident.confirmed_at = time.time()
        
        if level:
            incident.level = level
        
        if impact:
            incident.impact = impact
        
        self._save_incident(incident)
        return True
    
    def assign_handler(
        self,
        incident_id: str,
        handler_id: str,
        handler_name: str,
        role: str = "analyst"
    ) -> bool:
        """分配处理人员"""
        incident = self._incidents.get(incident_id)
        if not incident:
            return False
        
        handler = IncidentHandler(
            user_id=handler_id,
            name=handler_name,
            role=role,
            assigned_at=time.time()
        )
        
        incident.handlers.append(handler)
        self._save_incident(incident)
        
        return True
    
    def add_action(
        self,
        incident_id: str,
        action_type: str,
        description: str,
        handler_id: str,
        result: str = ""
    ) -> Optional[str]:
        """
        添加处置动作
        
        Args:
            incident_id: 事件ID
            action_type: 动作类型（contain/eradicate/recover/communicate）
            description: 动作描述
            handler_id: 处理人ID
            result: 执行结果
            
        Returns:
            动作ID
        """
        incident = self._incidents.get(incident_id)
        if not incident:
            return None
        
        action_id = f"{incident_id}-A{len(incident.actions) + 1}"
        
        action = IncidentAction(
            action_id=action_id,
            timestamp=time.time(),
            handler_id=handler_id,
            action_type=action_type,
            description=description,
            result=result
        )
        
        incident.actions.append(action)
        
        # 更新状态
        if action_type == "contain":
            incident.status = IncidentStatus.CONTAINING
        elif action_type == "eradicate":
            incident.status = IncidentStatus.ERADICATING
        elif action_type == "recover":
            incident.status = IncidentStatus.RECOVERING
        
        self._save_incident(incident)
        return action_id
    
    def execute_plan(
        self,
        incident_id: str,
        plan_id: str,
        executor_id: str = ""
    ) -> tuple[bool, list[str]]:
        """
        执行应急预案
        
        Args:
            incident_id: 事件ID
            plan_id: 预案ID
            executor_id: 执行人ID
            
        Returns:
            (是否成功, 执行结果消息)
        """
        incident = self._incidents.get(incident_id)
        plan = self._plans.get(plan_id)
        
        if not incident or not plan:
            return False, ["事件或预案不存在"]
        
        # 检查预案是否适用
        if incident.category not in plan.applicable_categories:
            return False, [f"预案不适用于类别: {incident.category.value}"]
        
        if incident.level not in plan.applicable_levels:
            return False, [f"预案不适用于级别: {incident.level.value}"]
        
        results = []
        
        # 执行每个步骤（实际执行需要外部系统配合）
        for step_info in plan.steps:
            step = step_info.get("step")
            action = step_info.get("action")
            results.append(f"Step {step}: {action} - 待执行")
        
        self._save_incident(incident)
        return True, results
    
    def match_plan(self, incident: Incident) -> Optional[EmergencyPlan]:
        """
        匹配合适的预案
        
        Args:
            incident: 事件
            
        Returns:
            匹配的预案或None
        """
        for plan in self._plans.values():
            if not plan.enabled:
                continue
            
            if incident.category in plan.applicable_categories:
                if incident.level in plan.applicable_levels:
                    return plan
        
        return None
    
    def resolve_incident(
        self,
        incident_id: str,
        root_cause: str,
        improvements: Optional[list[str]] = None,
        resolver_id: str = ""
    ) -> bool:
        """
        解决事件
        
        Args:
            incident_id: 事件ID
            root_cause: 根因分析
            improvements: 改进措施
            resolver_id: 解决人ID
            
        Returns:
            是否成功
        """
        incident = self._incidents.get(incident_id)
        if not incident:
            return False
        
        incident.status = IncidentStatus.RESOLVED
        incident.resolved_at = time.time()
        incident.root_cause = root_cause
        
        if improvements:
            incident.improvements = improvements
        
        self._save_incident(incident)
        return True
    
    def close_incident(
        self,
        incident_id: str,
        close_reason: str = "",
        closer_id: str = ""
    ) -> bool:
        """关闭事件"""
        incident = self._incidents.get(incident_id)
        if not incident:
            return False
        
        incident.status = IncidentStatus.CLOSED
        incident.closed_at = time.time()
        incident.metadata["close_reason"] = close_reason
        
        self._save_incident(incident)
        return True
    
    def get_incident(self, incident_id: str) -> Optional[Incident]:
        """获取事件详情"""
        return self._incidents.get(incident_id)
    
    def list_incidents(
        self,
        status: Optional[IncidentStatus] = None,
        level: Optional[IncidentLevel] = None,
        limit: int = 100
    ) -> list[Incident]:
        """列出事件"""
        results = []
        
        for incident in self._incidents.values():
            if status and incident.status != status:
                continue
            if level and incident.level != level:
                continue
            results.append(incident)
        
        # 按时间倒序
        results.sort(key=lambda x: x.detected_at, reverse=True)
        
        return results[:limit]
    
    def get_active_incidents(self) -> list[Incident]:
        """获取活跃事件"""
        active_statuses = [
            IncidentStatus.DETECTED,
            IncidentStatus.ASSESSING,
            IncidentStatus.CONFIRMED,
            IncidentStatus.CONTAINING,
            IncidentStatus.ERADICATING,
            IncidentStatus.RECOVERING
        ]
        
        return self.list_incidents()[:50]  # 简化实现
    
    def get_incident_statistics(self, days: int = 30) -> dict:
        """获取事件统计"""
        cutoff = time.time() - days * 86400
        
        stats = {
            "total": 0,
            "by_level": {"L1": 0, "L2": 0, "L3": 0, "L4": 0},
            "by_status": {},
            "by_category": {},
            "avg_resolution_time_hours": 0,
            "resolved_within_sla": 0,
            "breached_sla": 0
        }
        
        resolution_times = []
        
        for incident in self._incidents.values():
            if incident.detected_at < cutoff:
                continue
            
            stats["total"] += 1
            
            # 按级别统计
            level_key = incident.level.value
            stats["by_level"][level_key] = stats["by_level"].get(level_key, 0) + 1
            
            # 按状态统计
            status_key = incident.status.value
            stats["by_status"][status_key] = stats["by_status"].get(status_key, 0) + 1
            
            # 按类别统计
            category_key = incident.category.value
            stats["by_category"][category_key] = stats["by_category"].get(category_key, 0) + 1
            
            # 计算解决时间
            if incident.resolved_at:
                resolution_hours = (incident.resolved_at - incident.detected_at) / 3600
                resolution_times.append(resolution_hours)
                
                # SLA合规性
                if resolution_hours <= incident.level.resolution_time_hours:
                    stats["resolved_within_sla"] += 1
                else:
                    stats["breached_sla"] += 1
        
        if resolution_times:
            stats["avg_resolution_time_hours"] = sum(resolution_times) / len(resolution_times)
        
        return stats
    
    def create_plan(
        self,
        title: str,
        description: str,
        applicable_categories: list[IncidentCategory],
        applicable_levels: list[IncidentLevel],
        steps: list[dict],
        escalation_contacts: list[dict]
    ) -> EmergencyPlan:
        """创建应急预案"""
        plan_id = f"plan_{len(self._plans) + 1}"
        
        plan = EmergencyPlan(
            plan_id=plan_id,
            tenant_id=self.tenant_id,
            title=title,
            description=description,
            applicable_categories=applicable_categories,
            applicable_levels=applicable_levels,
            steps=steps,
            escalation_contacts=escalation_contacts
        )
        
        self._plans[plan_id] = plan
        self._save_plans()
        
        return plan
    
    def update_plan(self, plan_id: str, **kwargs) -> bool:
        """更新应急预案"""
        plan = self._plans.get(plan_id)
        if not plan:
            return False
        
        for key, value in kwargs.items():
            if hasattr(plan, key):
                setattr(plan, key, value)
        
        plan.updated_at = time.time()
        self._save_plans()
        
        return True
    
    def _get_storage_file(self, incident_id: str) -> str:
        """获取事件存储文件路径"""
        return os.path.join(self.storage_path, f"{self.tenant_id}_{incident_id}.json")
    
    def _save_incident(self, incident: Incident) -> None:
        """保存事件到磁盘"""
        file_path = self._get_storage_file(incident.incident_id)
        
        # 转换为可序列化格式
        data = {
            "incident_id": incident.incident_id,
            "tenant_id": incident.tenant_id,
            "level": incident.level.value,
            "category": incident.category.value,
            "title": incident.title,
            "description": incident.description,
            "detected_at": incident.detected_at,
            "reported_at": incident.reported_at,
            "confirmed_at": incident.confirmed_at,
            "resolved_at": incident.resolved_at,
            "closed_at": incident.closed_at,
            "status": incident.status.value,
            "impact": {
                "affected_users": incident.impact.affected_users if incident.impact else 0,
                "affected_systems": incident.impact.affected_systems if incident.impact else [],
                "affected_data_level": incident.impact.affected_data_level if incident.impact else "L1",
                "business_impact": incident.impact.business_impact if incident.impact else "",
                "reputational_impact": incident.impact.reputational_impact if incident.impact else "none",
                "financial_impact": incident.impact.financial_impact if incident.impact else 0,
                "recovery_cost": incident.impact.recovery_cost if incident.impact else 0
            } if incident.impact else None,
            "handlers": [
                {
                    "user_id": h.user_id,
                    "name": h.name,
                    "role": h.role,
                    "assigned_at": h.assigned_at,
                    "status": h.status,
                    "contact": h.contact
                }
                for h in incident.handlers
            ],
            "actions": [
                {
                    "action_id": a.action_id,
                    "timestamp": a.timestamp,
                    "handler_id": a.handler_id,
                    "action_type": a.action_type,
                    "description": a.description,
                    "result": a.result,
                    "evidence": a.evidence
                }
                for a in incident.actions
            ],
            "root_cause": incident.root_cause,
            "affected_components": incident.affected_components,
            "notifications_sent": incident.notifications_sent,
            "related_incidents": incident.related_incidents,
            "improvements": incident.improvements,
            "metadata": incident.metadata
        }
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _load(self) -> None:
        """从磁盘加载数据"""
        # 加载事件
        if os.path.exists(self.storage_path):
            for filename in os.listdir(self.storage_path):
                if filename.startswith(self.tenant_id + "_") and filename.endswith(".json"):
                    file_path = os.path.join(self.storage_path, filename)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        
                        # 重建事件对象
                        incident = Incident(
                            incident_id=data["incident_id"],
                            tenant_id=data["tenant_id"],
                            level=IncidentLevel(data["level"]),
                            category=IncidentCategory(data["category"]),
                            title=data["title"],
                            description=data["description"],
                            detected_at=data["detected_at"],
                            reported_at=data.get("reported_at"),
                            confirmed_at=data.get("confirmed_at"),
                            resolved_at=data.get("resolved_at"),
                            closed_at=data.get("closed_at"),
                            status=IncidentStatus(data["status"]),
                            impact=IncidentImpact(**data["impact"]) if data.get("impact") else None,
                            root_cause=data.get("root_cause", ""),
                            affected_components=data.get("affected_components", []),
                            related_incidents=data.get("related_incidents", []),
                            improvements=data.get("improvements", []),
                            metadata=data.get("metadata", {})
                        )
                        
                        # 重建处理人员
                        for h_data in data.get("handlers", []):
                            incident.handlers.append(IncidentHandler(**h_data))
                        
                        # 重建处置动作
                        for a_data in data.get("actions", []):
                            incident.actions.append(IncidentAction(**a_data))
                        
                        self._incidents[incident.incident_id] = incident
                    except Exception:
                        pass
        
        # 加载预案
        plans_file = os.path.join(self.storage_path, f"{self.tenant_id}_plans.json")
        if os.path.exists(plans_file):
            try:
                with open(plans_file, "r", encoding="utf-8") as f:
                    plans_data = json.load(f)
                
                for plan_data in plans_data.get("plans", []):
                    plan = EmergencyPlan(
                        plan_id=plan_data["plan_id"],
                        tenant_id=plan_data["tenant_id"],
                        title=plan_data["title"],
                        description=plan_data["description"],
                        applicable_categories=[IncidentCategory(c) for c in plan_data["applicable_categories"]],
                        applicable_levels=[IncidentLevel(l) for l in plan_data["applicable_levels"]],
                        steps=plan_data["steps"],
                        escalation_contacts=plan_data["escalation_contacts"],
                        required_tools=plan_data.get("required_tools", []),
                        runbooks=plan_data.get("runbooks", []),
                        enabled=plan_data.get("enabled", True),
                        version=plan_data.get("version", "1.0"),
                        updated_at=plan_data.get("updated_at", time.time())
                    )
                    self._plans[plan.plan_id] = plan
            except Exception:
                pass
    
    def _save_plans(self) -> None:
        """保存预案到磁盘"""
        plans_file = os.path.join(self.storage_path, f"{self.tenant_id}_plans.json")
        
        plans_data = {
            "plans": [
                {
                    "plan_id": p.plan_id,
                    "tenant_id": p.tenant_id,
                    "title": p.title,
                    "description": p.description,
                    "applicable_categories": [c.value for c in p.applicable_categories],
                    "applicable_levels": [l.value for l in p.applicable_levels],
                    "steps": p.steps,
                    "escalation_contacts": p.escalation_contacts,
                    "required_tools": p.required_tools,
                    "runbooks": p.runbooks,
                    "enabled": p.enabled,
                    "version": p.version,
                    "updated_at": p.updated_at
                }
                for p in self._plans.values()
            ]
        }
        
        with open(plans_file, "w", encoding="utf-8") as f:
            json.dump(plans_data, f, indent=2, ensure_ascii=False)
