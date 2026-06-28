"""
自我学习闭环 - Honcho 用户建模
来自 Hermes Agent
融合 Taiji Agent Taiji Verify
"""

import json
import logging
import re
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class PeerCard:
    """用户画像"""

    peer_id: str
    peer_type: str
    facts: list[str] = field(default_factory=list)
    preferences: dict = field(default_factory=dict)
    interaction_count: int = 0
    last_interaction: str = ""
    learned_topics: list[str] = field(default_factory=list)
    communication_style: dict = field(default_factory=dict)
    sentiment_history: list[float] = field(default_factory=list)

    def add_fact(self, fact: str):
        """添加事实"""
        if fact not in self.facts:
            self.facts.append(fact)
            self.last_interaction = datetime.now().isoformat()

    def add_preference(self, key: str, value: Any):
        """添加偏好"""
        self.preferences[key] = value

    def update_sentiment(self, sentiment: float):
        """更新情感"""
        self.sentiment_history.append(sentiment)
        if len(self.sentiment_history) > 100:
            self.sentiment_history.pop(0)

    def get_avg_sentiment(self) -> float:
        """获取平均情感"""
        if not self.sentiment_history:
            return 0.5
        return sum(self.sentiment_history) / len(self.sentiment_history)

    def to_dict(self) -> dict:
        return {
            "peer_id": self.peer_id,
            "peer_type": self.peer_type,
            "facts": self.facts,
            "preferences": self.preferences,
            "interaction_count": self.interaction_count,
            "last_interaction": self.last_interaction,
            "learned_topics": self.learned_topics,
            "communication_style": self.communication_style,
            "sentiment_history": self.sentiment_history,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PeerCard":
        return cls(**data)


@dataclass
class LearnedContext:
    """学到的上下文"""

    key: str
    event: str
    conclusion: str
    topics: list[str]
    timestamp: str
    confidence: float = 0.5


class HonchoMemory:
    """
    Honcho 用户建模系统

    来自 Hermes Agent 的跨会话记忆和用户建模
    支持用户画像、语义记忆、偏好学习
    """

    def __init__(self, memory_dir: Optional[Path] = None):
        if memory_dir is None:
            self.memory_dir = Path.home() / ".taiji_agent" / "memory" / "honcho"
        else:
            self.memory_dir = Path(memory_dir)

        self.memory_dir.mkdir(parents=True, exist_ok=True)

        self._peer_cards: dict[str, PeerCard] = {}
        self._contexts: dict[str, LearnedContext] = {}
        self._topic_index: dict[str, set[str]] = defaultdict(set)

        self._load()

    def _load(self):
        """加载数据"""
        peer_cards_file = self.memory_dir / "peer_cards.json"
        if peer_cards_file.exists():
            try:
                data = json.loads(peer_cards_file.read_text())
                self._peer_cards = {k: PeerCard.from_dict(v) for k, v in data.items()}
            except Exception as e:
                logger.error(f"Load peer cards error: {e}")

        contexts_file = self.memory_dir / "contexts.json"
        if contexts_file.exists():
            try:
                data = json.loads(contexts_file.read_text())
                self._contexts = {k: LearnedContext(**v) for k, v in data.items()}
            except Exception as e:
                logger.error(f"Load contexts error: {e}")

    def _save(self):
        """保存数据"""
        peer_cards_file = self.memory_dir / "peer_cards.json"
        peer_cards_file.write_text(
            json.dumps(
                {k: v.to_dict() for k, v in self._peer_cards.items()},
                ensure_ascii=False,
                indent=2,
            )
        )

        contexts_file = self.memory_dir / "contexts.json"
        contexts_file.write_text(
            json.dumps(
                {k: v.__dict__ for k, v in self._contexts.items()},
                ensure_ascii=False,
                indent=2,
            )
        )

    def get_peer_card(self, peer_id: str = "user") -> PeerCard:
        """获取用户画像"""
        if peer_id not in self._peer_cards:
            self._peer_cards[peer_id] = PeerCard(
                peer_id=peer_id,
                peer_type="user" if peer_id == "user" else "unknown",
            )
        return self._peer_cards[peer_id]

    def update_peer_card(
        self,
        peer_id: str,
        facts: Optional[list[str]] = None,
        preferences: Optional[dict[str, Any]] = None,
        sentiment: Optional[float] = None,
        topic: Optional[str] = None,
    ):
        """更新用户画像"""
        card = self.get_peer_card(peer_id)
        card.interaction_count += 1
        card.last_interaction = datetime.now().isoformat()

        if facts:
            for fact in facts:
                card.add_fact(fact)

        if preferences:
            for key, value in preferences.items():
                card.add_preference(key, value)

        if sentiment is not None:
            card.update_sentiment(sentiment)

        if topic and topic not in card.learned_topics:
            card.learned_topics.append(topic)

        self._save()

    def store_context(
        self,
        event: str,
        conclusion: str,
        topics: Optional[list[str]] = None,
        confidence: float = 0.5,
    ) -> str:
        """存储上下文"""
        context_id = f"context_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

        context = LearnedContext(
            key=context_id,
            event=event,
            conclusion=conclusion,
            topics=topics or [],
            timestamp=datetime.now().isoformat(),
            confidence=confidence,
        )

        self._contexts[context_id] = context

        for topic in topics or []:
            self._topic_index[topic.lower()].add(context_id)

        self._save()
        return context_id

    def recall_contexts(
        self,
        query: Optional[str] = None,
        topic: Optional[str] = None,
        limit: int = 10,
    ) -> list[LearnedContext]:
        """回忆相关上下文"""
        if topic:
            context_ids = self._topic_index.get(topic.lower(), set())
            contexts = [self._contexts.get(cid) for cid in context_ids]
        elif query:
            query_lower = query.lower()
            contexts = [
                ctx
                for ctx in self._contexts.values()
                if query_lower in ctx.event.lower() or query_lower in ctx.conclusion.lower()
            ]
        else:
            contexts = list(self._contexts.values())

        non_none: list[LearnedContext] = [c for c in contexts if c is not None]
        non_none.sort(key=lambda c: c.timestamp, reverse=True)

        return non_none[:limit]

    def extract_preferences(self, conversation: list[dict]) -> dict:
        """从对话中提取偏好"""
        preferences = {}

        preference_patterns = {
            "language": r"(?:喜欢|prefer)[:\s]*(中文|Chinese|英文|English)",
            "format": r"(?:喜欢|prefer)[:\s]*(详细|concise|简洁|verbose)",
            "tone": r"(?:喜欢|prefer)[:\s]*(正式|formal| casual|随意)",
        }

        full_text = " ".join(msg.get("content", "") for msg in conversation).lower()

        for pref_type, pattern in preference_patterns.items():
            match = re.search(pattern, full_text)
            if match:
                preferences[pref_type] = match.group(1)

        return preferences

    def get_user_context_prompt(self, peer_id: str = "user") -> str:
        """生成用户上下文提示"""
        card = self.get_peer_card(peer_id)

        if card.interaction_count == 0:
            return ""

        parts = ["## 用户上下文"]

        if card.facts:
            parts.append("\n### 已知事实")
            for fact in card.facts[-5:]:
                parts.append(f"- {fact}")

        if card.learned_topics:
            parts.append("\n### 已讨论主题")
            parts.append(", ".join(card.learned_topics[-10:]))

        if card.preferences:
            parts.append("\n### 偏好")
            for key, value in card.preferences.items():
                parts.append(f"- {key}: {value}")

        avg_sentiment = card.get_avg_sentiment()
        if avg_sentiment != 0.5:
            parts.append(f"\n### 用户情绪: {'积极' if avg_sentiment > 0.5 else '消极'}")

        return "\n".join(parts)


class SelfImprovingLoop:
    """
    自我学习闭环

    融合 Hermes Honcho + Skills + Taiji Agent Taiji Verify
    """

    def __init__(
        self,
        honcho: HonchoMemory,
        skill_manager,  # SkillManager
        wfgy_verifier,  # Taiji VerifyVerifier
    ):
        self.honcho = honcho
        self.skill_manager = skill_manager
        self.wfgy = wfgy_verifier

        self._learning_hooks: list[Callable] = []

    def on_learning(self, handler: Callable[[dict], Awaitable[None]]):
        """注册学习钩子"""
        self._learning_hooks.append(handler)

    async def learn_from_interaction(
        self,
        conversation: list[dict],
        task: str,
        result: str,
        tools_used: list[str],
        user_id: str = "user",
    ) -> dict:
        """从交互中学习"""
        learnings = {}

        # 始终记录交互计数
        self.honcho.update_peer_card(user_id)

        preferences = self.honcho.extract_preferences(conversation)
        if preferences:
            self.honcho.update_peer_card(user_id, preferences=preferences)
            learnings["preferences"] = preferences

        topics = self._extract_topics(task, result)
        if topics:
            self.honcho.update_peer_card(user_id, topic=topics[0])

        sentiment = self._analyze_sentiment(result)
        if sentiment is not None:
            self.honcho.update_peer_card(user_id, sentiment=sentiment)

        self.honcho.store_context(
            event=f"task: {task[:100]}",
            conclusion=result[:500],
            topics=topics,
        )

        if len(conversation) > 10 and tools_used:
            skill = await self._maybe_create_skill(task, result, tools_used)
            if skill:
                learnings["created_skill"] = skill.id

        for hook in self._learning_hooks:
            try:
                await hook(learnings)
            except Exception as e:
                logger.error(f"Learning hook error: {e}")

        return learnings

    def _extract_topics(self, task: str, result: str) -> list[str]:
        """提取主题"""
        topics = []

        topic_keywords = {
            "编程": ["代码", "code", "debug", "function", "class"],
            "文档": ["文档", "document", "write", "readme"],
            "搜索": ["搜索", "search", "find", "研究"],
            "分析": ["分析", "analyze", "数据", "data"],
            "设计": ["设计", "design", "架构", "architecture"],
        }

        full_text = (task + " " + result).lower()

        for topic, keywords in topic_keywords.items():
            if any(kw.lower() in full_text for kw in keywords):
                topics.append(topic)

        return topics

    def _analyze_sentiment(self, text: str) -> Optional[float]:
        """分析情感"""
        positive_words = ["好", "不错", "谢谢", "棒", "perfect", "great", "thanks", "good"]
        negative_words = ["不好", "错误", "失败", "bad", "wrong", "error", "fail"]

        text_lower = text.lower()

        pos_count = sum(1 for w in positive_words if w in text_lower)
        neg_count = sum(1 for w in negative_words if w in text_lower)

        if pos_count == 0 and neg_count == 0:
            return None

        total = pos_count + neg_count
        sentiment = pos_count / total

        return max(0.0, min(1.0, sentiment))

    async def _maybe_create_skill(
        self,
        task: str,
        result: str,
        tools_used: list[str],
    ) -> Optional[Any]:
        """可能创建技能"""
        complexity_score = self._estimate_complexity(task, tools_used)

        if complexity_score < 0.7:
            return None

        skill = await self.skill_manager.create(
            name=task[:50],
            description=f"从任务 '{task[:50]}...' 提取",
            instructions=f"任务: {task}\n\n结果: {result}",
            tools=tools_used,
            category=self._infer_category(task),
            source_task=task,
        )

        return skill

    def _estimate_complexity(self, task: str, tools_used: list[str]) -> float:
        """估算复杂度"""
        score = 0.0

        score += min(len(tools_used) * 0.15, 0.4)

        complex_keywords = ["分析", "设计", "实现", "优化", "analyze", "design", "implement"]
        for kw in complex_keywords:
            if kw.lower() in task.lower():
                score += 0.2

        score += min(len(task) / 500, 0.2)

        return min(score, 1.0)

    def _infer_category(self, task: str) -> str:
        """推断类别"""
        task_lower = task.lower()

        if any(kw in task_lower for kw in ["代码", "code", "debug", "function"]):
            return "开发"
        if any(kw in task_lower for kw in ["搜索", "research", "研究"]):
            return "研究"
        if any(kw in task_lower for kw in ["文档", "document", "写"]):
            return "创作"

        return "general"
