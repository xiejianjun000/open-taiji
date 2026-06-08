"""
Soul 人格系统 v2 — CrewAI 角色模型升级

新增支持：
- role/goal/backstory 三层角色定义
- skills/constraints/knowledge_domains 结构化字段
- workflows 预设工作流（并行+串行 Phase）
- 向后兼容 v1 格式
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import yaml
from pydantic import BaseModel


class SoulRole(BaseModel):
    """CrewAI 风格角色模型"""
    role: str = ""
    goal: str = ""
    backstory: str = ""


class SoulWorkflowPhase(BaseModel):
    phase: int = 0
    title: str = ""
    agents: list[str] = []
    mode: str = "sequential"
    depends_on: list[int] = []


class SoulWorkflow(BaseModel):
    name: str = ""
    trigger: str = ""
    phases: list[SoulWorkflowPhase] = []


class SoulV2(BaseModel):
    """Soul v2 — CrewAI 升级版"""

    id: str
    name: str
    version: int = 2
    role: SoulRole = SoulRole()
    skills: list[str] = []
    constraints: list[str] = []
    knowledge_domains: list[str] = []
    workflows: list[SoulWorkflow] = []
    # 兼容 v1
    boundaries: list[str] = []
    ethics: list[str] = []
    character: dict = {}
    context: dict = {}


class SoulLoaderV2:
    """Soul v2 加载器 — 向前兼容 v1"""

    def __init__(self, souls_dir: Path | None = None):
        if souls_dir is None:
            self.souls_dir = Path(__file__).parent / "yaml"
        else:
            self.souls_dir = Path(souls_dir)
        self._cache: dict[str, SoulV2] = {}

    def load(self, soul_id: str) -> SoulV2:
        if soul_id in self._cache:
            return self._cache[soul_id]

        # Try yaml/ subdirectory first
        soul_path = self.souls_dir / f"{soul_id}.yaml"
        if not soul_path.exists():
            soul_path = self.souls_dir / "yaml" / f"{soul_id}.yaml"
        if not soul_path.exists():
            for path in self.souls_dir.glob("**/*.yaml"):
                if path.stem == soul_id:
                    soul_path = path
                    break
            else:
                raise FileNotFoundError(f"Soul not found: {soul_id}")

        with open(soul_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        soul = self._parse_v2(data) if data.get("version", 1) >= 2 else self._parse_v1(data)
        self._cache[soul_id] = soul
        return soul

    def _parse_v2(self, data: dict) -> SoulV2:
        role_data = data.get("role", {})
        workflows = []
        for wf in data.get("workflows", []):
            phases = [SoulWorkflowPhase(**p) for p in wf.get("phases", [])]
            workflows.append(SoulWorkflow(name=wf.get("name", ""), trigger=wf.get("trigger", ""), phases=phases))

        layers = data.get("layers", {})
        return SoulV2(
            id=data.get("id", "unknown"),
            name=data.get("name", "Unknown"),
            version=data.get("version", 2),
            role=SoulRole(
                role=role_data.get("role", ""),
                goal=role_data.get("goal", ""),
                backstory=role_data.get("backstory", ""),
            ),
            skills=data.get("skills", []),
            constraints=data.get("constraints", []),
            knowledge_domains=data.get("knowledge_domains", []),
            workflows=workflows,
            boundaries=layers.get("boundaries", []),
            ethics=layers.get("ethics", []),
            character=layers.get("character", {}),
            context=layers.get("context", {}),
        )

    def _parse_v1(self, data: dict) -> SoulV2:
        layers = data.get("layers", {})
        return SoulV2(
            id=data.get("id", "unknown"),
            name=data.get("name", "Unknown"),
            version=1,
            boundaries=layers.get("boundaries", []),
            ethics=layers.get("ethics", []),
            character=layers.get("character", {}),
            context=layers.get("context", {}),
        )

    def list_souls(self) -> list[str]:
        ids = []
        for path in self.souls_dir.glob("**/*.yaml"):
            ids.append(path.stem)
        return sorted(set(ids))

    def get_workflow(self, soul_id: str, workflow_name: str) -> Optional[SoulWorkflow]:
        soul = self.load(soul_id)
        for wf in soul.workflows:
            if wf.name == workflow_name or wf.trigger and workflow_name in wf.trigger:
                return wf
        return None

    def get_agents_for_workflow(self, soul_id: str, workflow_name: str) -> list[str]:
        """获取工作流所需的所有 Agent ID"""
        wf = self.get_workflow(soul_id, workflow_name)
        if not wf:
            return []
        agents = set()
        for phase in wf.phases:
            agents.update(phase.agents)
        return list(agents)


def inject_soul_v2(soul: SoulV2) -> str:
    """将 Soul v2 注入到系统提示"""
    lines = [
        f"# {soul.name}",
        "",
        "## 角色定位 (CrewAI)",
        f"- 角色: {soul.role.role}",
        f"- 目标: {soul.role.goal}",
        f"- 背景: {soul.role.backstory}",
        "",
    ]

    if soul.skills:
        lines.append("## 核心技能")
        lines.extend([f"- {s}" for s in soul.skills])
        lines.append("")

    if soul.constraints:
        lines.append("## 行为约束 (最高优先级)")
        lines.extend([f"- {c}" for c in soul.constraints])
        lines.append("")

    if soul.knowledge_domains:
        lines.append("## 知识领域")
        lines.extend([f"- {k}" for k in soul.knowledge_domains])
        lines.append("")

    if soul.boundaries:
        lines.append("## 行为边界")
        lines.extend([f"- {b}" for b in soul.boundaries])
        lines.append("")

    if soul.ethics:
        lines.append("## 核心价值观")
        lines.extend([f"- {e}" for e in soul.ethics])

    if soul.workflows:
        lines.append("\n## 预设工作流")
        for wf in soul.workflows:
            lines.append(f"### {wf.name}")
            lines.append(f"触发: {wf.trigger}")
            for phase in wf.phases:
                mode_icon = "∥" if phase.mode == "parallel" else "→"
                lines.append(f"  Phase {phase.phase}: {phase.title} [{mode_icon} {', '.join(phase.agents)}]")
            lines.append("")

    return "\n".join(lines)
