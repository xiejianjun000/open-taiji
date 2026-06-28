"""
Polaris Compiler (北辰编译器)
任务原子化编译器

将自然语言目标(GOAL)分解为可执行的原子任务(Task Atom)列表。
9步编译管道: GOAL_COMPILATION → TASK_GRAPH → ATOM_TABLE → 
            EXECUTION_TOKEN_BOARD → ROUND_LOCK → CLOSURE_RECORD

数据来源：基于阶段一基线数据推算与行业同类系统对标
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class AtomType(str, Enum):
    """任务原子类型"""
    RETRIEVE = "retrieve"           # 信息检索
    COMPUTE = "compute"             # 计算/推理
    VERIFY = "verify"               # 验证/检查
    GENERATE = "generate"           # 内容生成
    TRANSFORM = "transform"         # 数据转换
    EXTERNAL = "external"           # 外部API调用
    APPROVAL = "approval"           # 人工审批
    NOTIFY = "notify"               # 通知/消息
    AUDIT = "audit"                 # 审计记录


@dataclass
class TaskAtom:
    """任务原子 - 编译产出的最小执行单元"""
    id: str
    atom_type: AtomType
    description: str
    input_refs: list[str] = field(default_factory=list)   # 引用的前置原子ID
    output_key: str = ""
    priority: int = 0                                      # 0=最高优先级
    estimated_cost: float = 1.0                            # 相对计算成本
    requires_human: bool = False
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.id:
            self.id = f"atom_{uuid.uuid4().hex[:8]}"
        if not self.output_key:
            self.output_key = f"out_{self.id}"


@dataclass 
class ExecutionToken:
    """执行令牌 - 控制原子任务的执行权限"""
    atom_id: str
    round_id: str
    holder: str = ""        # 持有者（agent ID）
    acquired_at: float = 0.0
    expires_at: float = 0.0
    status: str = "available"


@dataclass
class CompilationResult:
    """编译结果"""
    atoms: list[TaskAtom]
    goal_text: str
    execution_graph: dict = field(default_factory=dict)
    token_board: list[ExecutionToken] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def atom_count(self) -> int:
        return len(self.atoms)


class PolarisCompiler:
    """
    北辰编译器 - 自然语言目标→原子任务列表

    Usage::
        compiler = PolarisCompiler()
        result = compiler.compile(
            goal="分析这份环评报告的排放数据是否合规",
            context={"document_id": "EIA-2024-001"},
        )
        for atom in result.atoms:
            print(atom.id, atom.atom_type, atom.description)
    """

    # 关键词→原子类型的映射规则
    TYPE_RULES = [
        (AtomType.RETRIEVE, [r'查询', r'检索', r'获取', r'读取', r'查找', r'搜索', r'fetch', r'get', r'read', r'search', r'find']),
        (AtomType.COMPUTE, [r'计算', r'分析', r'对比', r'评估', r'统计', r'compute', r'analyze', r'calculate', r'compare', r'evaluate']),
        (AtomType.VERIFY, [r'验证', r'检查', r'确认', r'核实', r'校验', r'verify', r'check', r'confirm', r'validate']),
        (AtomType.GENERATE, [r'生成', r'编写', r'撰写', r'创建', r'输出', r'generate', r'write', r'create', r'produce', r'output']),
        (AtomType.TRANSFORM, [r'转换', r'格式化', r'映射', r'解析', r'transform', r'format', r'map', r'parse']),
        (AtomType.EXTERNAL, [r'调用', r'请求', r'发送', r'通知', r'call', r'request', r'send', r'invoke']),
        (AtomType.APPROVAL, [r'审批', r'审核', r'批准', r'同意', r'approve', r'review', r'authorize']),
        (AtomType.NOTIFY, [r'告知', r'提醒', r'通知', r'报告', r'notify', r'alert', r'report']),
        (AtomType.AUDIT, [r'记录', r'审计', r'日志', r'归档', r'audit', r'log', r'record']),
    ]

    def __init__(self, max_atoms: int = 20):
        self.max_atoms = max_atoms

    def compile(self, goal: str, context: Optional[dict] = None) -> CompilationResult:
        """
        将自然语言目标编译为原子任务列表
        
        9步管道（简化实现）：
        1. GOAL_COMPILATION: 解析目标，识别动词和对象
        2. TASK_GRAPH: 构建依赖图
        3-6. ATOM/TOKEN/LOCK/CLOSURE: 生成执行元数据
        """
        context = context or {}

        # Step 1: 解析子句
        clauses = self._parse_clauses(goal)

        # Step 2: 为每个子句生成原子
        atoms: list[TaskAtom] = []
        for i, clause in enumerate(clauses):
            atom_type = self._classify_atom(clause)
            atom = TaskAtom(
                id=f"atom_{i+1:02d}",
                atom_type=atom_type,
                description=clause.strip(),
                input_refs=[atoms[-1].id] if atoms else [],
                priority=i,
                metadata={'source_clause': clause, **context},
            )
            atoms.append(atom)

            if len(atoms) >= self.max_atoms:
                break

        # Step 3-6: 构建执行图和令牌板
        graph = self._build_execution_graph(atoms)
        tokens = self._create_token_board(atoms)

        return CompilationResult(
            atoms=atoms,
            goal_text=goal,
            execution_graph=graph,
            token_board=tokens,
            metadata={
                'clause_count': len(clauses),
                'context_keys': list(context.keys()),
            },
        )

    def _parse_clauses(self, goal: str) -> list[str]:
        """将目标文本拆分为子句（按中文逗号/分号/句号或英文标点）"""
        separators = r'[,;，；。\n]+'
        clauses = re.split(separators, goal)
        return [c.strip() for c in clauses if c.strip() and len(c.strip()) > 1]

    def _classify_atom(self, text: str) -> AtomType:
        """根据关键词分类原子类型"""
        text_lower = text.lower()
        best_type = AtomType.COMPUTE  # 默认
        best_score = 0

        for atom_type, patterns in self.TYPE_RULES:
            score = sum(1 for p in patterns if re.search(p, text_lower))
            if score > best_score:
                best_score = score
                best_type = atom_type

        return best_type

    def _build_execution_graph(self, atoms: list[TaskAtom]) -> dict:
        """构建DAG执行图"""
        graph = {'nodes': [], 'edges': []}
        for atom in atoms:
            graph['nodes'].append({
                'id': atom.id,
                'type': atom.atom_type.value,
                'description': atom.description,
            })
            for ref in atom.input_refs:
                graph['edges'].append({'from': ref, 'to': atom.id})
        return graph

    def _create_token_board(self, atoms: list[TaskAtom]) -> list[ExecutionToken]:
        """为每个原子创建执行令牌"""
        return [
            ExecutionToken(atom_id=a.id, round_id="round_01")
            for a in atoms
        ]
