"""
Soul 人格系统 - 基于 cgast/harness
"""

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import yaml
from pydantic import BaseModel

if TYPE_CHECKING:
    pass


@dataclass
class SoulLayer:
    """Soul 分层结构"""

    boundaries: list[str]
    ethics: list[str]
    character_traits: list[str]
    character_style: dict
    context_domain: str
    special_instructions: list[str]


class Soul(BaseModel):
    """Soul 文档"""

    id: str
    name: str
    version: int = 1
    boundaries: list[str] = []
    ethics: list[str] = []
    character: dict = {}
    context: dict = {}
    evolution: dict = {}
    taiji_aspect: dict = {}


class SoulLoader:
    """
    Soul 加载器

    从 YAML 文件加载人格定义
    """

    def __init__(self, souls_dir: Optional[Path] = None):
        if souls_dir is None:
            self.souls_dir = Path.home() / ".taiji_agent" / "souls"
        else:
            self.souls_dir = Path(souls_dir)

        self._cache: dict[str, Soul] = {}
        self._ensure_default_souls()

    def _ensure_default_souls(self):
        """确保默认 souls 存在"""
        self.souls_dir.mkdir(parents=True, exist_ok=True)

        # 默认太极人格
        default_path = self.souls_dir / "default.yaml"
        if not default_path.exists():
            default_soul = """id: default
name: "太极助手"
version: 1

layers:
  boundaries:
    - "不产生有害、违法或不道德内容"
    - "永远坦诚承认不确定性"
    - "不捏造事实或引用不存在的来源"
    - "不冒充人类身份"

  ethics:
    - "追求阴阳平衡，避免极端"
    - "以用户为中心，尊重隐私"
    - "持续学习，追求智慧"
    - "客观中立，不偏不倚"

  character:
    traits:
      - "深思熟虑，言行审慎"
      - "善于分析，化繁为简"
      - "幽默风趣，平易近人"
    style:
      verbosity: "适中"
      tone: "专业而亲切"
      language: "中文优先，英文辅助"
    taiji_aspect:
      阳: "分析、推理、逻辑"
      阴: "直觉、创造、共情"

context:
  domain: "通用助手，专业领域涵盖技术、创意、分析"
  special_instructions:
    - "运用太极思维，全面分析问题"
    - "在确定性和创造性之间找到平衡"
    - "主动识别并标注不确定性"
"""
            default_path.write_text(default_soul)

    def load(self, soul_id: str) -> Soul:
        """加载指定 ID 的 Soul"""
        if soul_id in self._cache:
            return self._cache[soul_id]

        soul_path = self.souls_dir / f"{soul_id}.yaml"
        if not soul_path.exists():
            # 尝试查找
            for path in self.souls_dir.glob("*.yaml"):
                if path.stem == soul_id:
                    soul_path = path
                    break
            else:
                # 使用默认
                soul_path = self.souls_dir / "default.yaml"

        with open(soul_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        soul = self._parse_soul_data(data)
        self._cache[soul_id] = soul

        return soul

    def _parse_soul_data(self, data: dict) -> Soul:
        """解析 Soul 数据"""
        layers = data.get("layers", {})
        character = layers.get("character", {})
        context = layers.get("context", {})

        return Soul(
            id=data.get("id", "unknown"),
            name=data.get("name", "Unknown"),
            version=data.get("version", 1),
            boundaries=layers.get("boundaries", []),
            ethics=layers.get("ethics", []),
            character=character,
            context=context,
            evolution=data.get("evolution", {}),
            taiji_aspect=character.get("taiji_aspect", {}),
        )

    def list_souls(self) -> list[str]:
        """列出所有可用的 Soul"""
        return [p.stem for p in self.souls_dir.glob("*.yaml")]

    def save(self, soul: Soul):
        """保存 Soul 到文件"""
        data = {
            "id": soul.id,
            "name": soul.name,
            "version": soul.version,
            "layers": {
                "boundaries": soul.boundaries,
                "ethics": soul.ethics,
                "character": soul.character,
                "context": soul.context,
            },
        }

        soul_path = self.souls_dir / f"{soul.id}.yaml"
        with open(soul_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True)

        self._cache[soul.id] = soul


def inject_soul(soul: Soul) -> str:
    """
    将 Soul 注入到系统提示

    按照优先级：boundaries > ethics > character > context
    """
    lines = [
        f"# {soul.name}",
        "",
        "## 行为边界 (最高优先级)",
        *[f"- {b}" for b in soul.boundaries],
        "",
        "## 核心价值观",
        *[f"- {e}" for e in soul.ethics],
        "",
        "## 性格特征",
    ]

    if soul.character:
        traits = soul.character.get("traits", [])
        style = soul.character.get("style", {})

        lines.append("### 特质")
        lines.extend([f"- {t}" for t in traits])

        lines.append("### 风格")
        for key, value in style.items():
            lines.append(f"- {key}: {value}")

        # 太极特色
        if "taiji_aspect" in soul.character:
            lines.append("")
            lines.append("### 太极特质")
            for aspect, desc in soul.character["taiji_aspect"].items():
                lines.append(f"- {aspect}: {desc}")

    lines.extend(
        [
            "",
            "## 应用场景",
            f"- 领域: {soul.context.get('domain', '通用')}",
        ]
    )

    special = soul.context.get("special_instructions", [])
    if special:
        lines.append("")
        lines.append("### 特殊指令")
        lines.extend([f"- {s}" for s in special])

    return "\n".join(lines)
