"""
多智能体协同架构 - Multi-Agent Coordination System
融合 Hermes Agent Delegate + 太极哲学
支持并行、串行、层级、广播等多种协同模式
"""

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from taiji_agent.agent.engine import AgentConfig
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class AgentRole(Enum):
    """智能体角色"""

    COORDINATOR = "coordinator"  # 协调者 - 负责任务分解和结果汇总
    EXECUTOR = "executor"  # 执行者 - 负责具体任务执行
    REVIEWER = "reviewer"  # 评审者 - 负责结果审查
    SYNTHESIZER = "synthesizer"  # 综合者 - 负责信息融合
    MONITOR = "monitor"  # 监控者 - 负责进度跟踪


class CoordinationMode(Enum):
    """协同模式"""

    PARALLEL = "parallel"  # 并行 - 所有Agent同时执行
    SEQUENTIAL = "sequential"  # 串行 - 按顺序执行
    HIERARCHICAL = "hierarchical"  # 层级 - 树形结构
    BROADCAST = "broadcast"  # 广播 - 一对多
    DEBATE = "debate"  # 辩论 - 多Agent讨论
    CONSENSUS = "consensus"  # 共识 - 投票决策


@dataclass
class AgentMessage:
    """智能体消息"""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender: str = ""
    receivers: list[str] = field(default_factory=list)  # 空表示广播
    content: Any = None
    message_type: str = "info"  # info, request, response, vote
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    reply_to: Optional[str] = None  # 关联的消息ID


@dataclass
class AgentTask:
    """智能体任务"""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    assigned_agent: Optional[str] = None
    status: str = "pending"  # pending, running, completed, failed
    result: Any = None
    error: Optional[str] = None
    dependencies: list[str] = field(default_factory=list)  # 依赖的任务ID
    priority: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentCapability:
    """智能体能力"""

    name: str
    description: str
    tools: list[str] = field(default_factory=list)
    models: list[str] = field(default_factory=list)


class BaseAgent(ABC):
    """智能体基类"""

    def __init__(
        self,
        agent_id: str,
        role: AgentRole,
        name: Optional[str] = None,
        capabilities: Optional[list[AgentCapability]] = None,
    ):
        self.agent_id = agent_id
        self.role = role
        self.name = name or agent_id
        self.capabilities = capabilities or []
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._parent: Optional[MultiAgentCoordinator] = None

    @abstractmethod
    async def process(self, task: AgentTask) -> Any:
        """处理任务"""
        pass

    async def send_message(self, message: AgentMessage):
        """发送消息"""
        if self._parent:
            await self._parent.route_message(message)

    async def receive_message(self) -> Optional[AgentMessage]:
        """接收消息"""
        try:
            return await asyncio.wait_for(self._message_queue.get(), timeout=1.0)
        except TimeoutError:
            return None

    def receive(self, message: AgentMessage):
        """接收消息（同步）"""
        self._message_queue.put_nowait(message)

    async def start(self):
        """启动智能体"""
        self._running = True
        asyncio.create_task(self._message_loop())

    async def stop(self):
        """停止智能体"""
        self._running = False

    async def _message_loop(self):
        """消息循环"""
        while self._running:
            message = await self.receive_message()
            if message:
                await self._handle_message(message)
            await asyncio.sleep(0.1)

    @abstractmethod
    async def _handle_message(self, message: AgentMessage) -> None:
        """处理消息 - 子类需要实现"""
        raise NotImplementedError


class TaijiAgent(BaseAgent):
    """
    太极智能体 - 基于 Taiji Agent Agent 的子Agent实现
    """

    def __init__(
        self,
        agent_id: str,
        role: AgentRole,
        config: Optional["AgentConfig"] = None,
        allowed_tools: Optional[list[str]] = None,
        blocked_tools: Optional[list[str]] = None,
        max_iterations: int = 25,
    ):
        super().__init__(agent_id, role)

        from taiji_agent.agent.engine import TaijiAgent as CoreAgent

        self.config = config or AgentConfig()
        self.allowed_tools = allowed_tools
        self.blocked_tools = blocked_tools or [
            "delegate_task",  # 禁止递归委托
            "clarify",  # 禁止用户交互
            "send_message",  # 禁止跨平台副作用
        ]
        self.max_iterations = max_iterations

        self._core_agent = CoreAgent(config=self.config)

    async def _handle_message(self, message: AgentMessage) -> None:
        """处理消息"""
        pass

    async def process(self, task: AgentTask) -> Any:
        """处理任务"""
        logger.info(f"[{self.agent_id}] Processing task: {task.description[:50]}...")

        try:
            result = await self._core_agent.run(task.description)

            task.status = "completed"
            task.result = result.content if hasattr(result, "content") else str(result)

            return task.result

        except Exception as e:
            logger.error(f"[{self.agent_id}] Task failed: {e}")
            task.status = "failed"
            task.error = str(e)
            raise

    def _filter_tools(self) -> list[str]:
        """过滤工具列表"""
        if not self.allowed_tools and not self.blocked_tools:
            return []

        all_tools = self._core_agent.tools.list_tools()

        if self.allowed_tools:
            return [t for t in all_tools if t in self.allowed_tools]

        return [t for t in all_tools if t not in self.blocked_tools]


class MultiAgentCoordinator:
    """
    多智能体协调器

    支持多种协同模式：
    - PARALLEL: 并行执行，最大并发可配置
    - SEQUENTIAL: 串行执行，按依赖顺序
    - HIERARCHICAL: 层级结构，树形委托
    - BROADCAST: 广播模式，一对多
    - DEBATE: 辩论模式，多Agent讨论
    - CONSENSUS: 共识模式，投票决策
    """

    def __init__(
        self,
        max_concurrent: int = 3,
        max_depth: int = 2,
        timeout: float = 300.0,
    ):
        self.agents: dict[str, BaseAgent] = {}
        self.max_concurrent = max_concurrent
        self.max_depth = max_depth
        self.timeout = timeout
        self._message_bus: dict[str, list[AgentMessage]] = {}
        self._tasks: dict[str, AgentTask] = {}
        self._running = False
        self._current_depth = 0

    def register_agent(self, agent: BaseAgent):
        """注册智能体"""
        agent._parent = self
        self.agents[agent.agent_id] = agent
        logger.info(f"Registered agent: {agent.agent_id} (role: {agent.role.value})")

    def unregister_agent(self, agent_id: str):
        """注销智能体"""
        if agent_id in self.agents:
            agent = self.agents[agent_id]
            agent._parent = None
            del self.agents[agent_id]

    async def route_message(self, message: AgentMessage):
        """路由消息"""
        message.sender = message.sender or "system"

        if message.id not in self._message_bus:
            self._message_bus[message.id] = []
        self._message_bus[message.id].append(message)

        if not message.receivers:
            for agent in self.agents.values():
                if agent.agent_id != message.sender:
                    agent.receive(message)
        else:
            for receiver in message.receivers:
                if receiver in self.agents:
                    self.agents[receiver].receive(message)

    async def create_task(
        self,
        description: str,
        assigned_agent: Optional[str] = None,
        dependencies: Optional[list[str]] = None,
        priority: int = 0,
    ) -> AgentTask:
        """创建任务"""
        task = AgentTask(
            description=description,
            assigned_agent=assigned_agent,
            dependencies=dependencies or [],
            priority=priority,
        )
        self._tasks[task.id] = task
        return task

    async def execute_parallel(
        self,
        tasks: list[AgentTask],
        agent_factory: Optional[Callable] = None,
    ) -> list[AgentTask]:
        """并行执行"""
        logger.info(f"[Coordinator] Executing {len(tasks)} tasks in parallel")

        async def execute_single(task: AgentTask) -> AgentTask:
            agent = self._get_or_create_agent(task, agent_factory)
            try:
                task.assigned_agent = agent.agent_id
                task.status = "running"

                result = await asyncio.wait_for(agent.process(task), timeout=self.timeout)

                task.status = "completed"
                task.result = result

            except TimeoutError:
                task.status = "failed"
                task.error = "Task timeout"
            except Exception as e:
                task.status = "failed"
                task.error = str(e)

            return task

        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def bounded_execute(task: AgentTask) -> AgentTask:
            async with semaphore:
                return await execute_single(task)

        results = await asyncio.gather(*[bounded_execute(t) for t in tasks], return_exceptions=True)

        return [r for r in results if isinstance(r, AgentTask)]

    async def execute_sequential(
        self,
        tasks: list[AgentTask],
        agent_factory: Optional[Callable] = None,
    ) -> list[AgentTask]:
        """串行执行"""
        logger.info(f"[Coordinator] Executing {len(tasks)} tasks sequentially")

        results = []
        for task in tasks:
            if task.dependencies:
                await self._wait_dependencies(task)

            agent = self._get_or_create_agent(task, agent_factory)
            task.assigned_agent = agent.agent_id
            task.status = "running"

            try:
                result = await asyncio.wait_for(agent.process(task), timeout=self.timeout)
                task.status = "completed"
                task.result = result

            except TimeoutError:
                task.status = "failed"
                task.error = "Task timeout"
            except Exception as e:
                task.status = "failed"
                task.error = str(e)

            results.append(task)

        return results

    async def execute_hierarchical(
        self,
        root_task: AgentTask,
        agent_factory: Optional[Callable] = None,
        decomposer: Optional[Callable] = None,
    ) -> AgentTask:
        """
        层级执行

        协调者分解任务，子Agent执行叶子任务
        """
        logger.info(f"[Coordinator] Hierarchical execution, depth: {self._current_depth}")

        if self._current_depth >= self.max_depth:
            logger.warning("Max delegation depth reached")
            root_task.status = "failed"
            root_task.error = "Max delegation depth reached"
            return root_task

        self._current_depth += 1

        try:
            if decomposer:
                subtasks = await decomposer(root_task)
            else:
                subtasks = await self._default_decompose(root_task)

            if len(subtasks) == 1:
                result = await self._execute_subtask(subtasks[0], agent_factory)
                root_task.result = result
                root_task.status = "completed"
            else:
                subtask_results = await self.execute_parallel(subtasks, agent_factory)

                root_task.result = self._synthesize_results(subtask_results)
                root_task.status = "completed"

        except Exception as e:
            logger.error(f"Hierarchical execution error: {e}")
            root_task.status = "failed"
            root_task.error = str(e)

        finally:
            self._current_depth -= 1

        return root_task

    async def execute_debate(
        self,
        topic: str,
        agents: list[BaseAgent],
        rounds: int = 3,
    ) -> dict[str, Any]:
        """
        辩论模式

        多个Agent讨论同一话题，最终达成共识
        """
        logger.info(f"[Coordinator] Debate on: {topic[:50]}... ({rounds} rounds)")

        statements: dict[str, list[str]] = {}
        votes: dict[str, int] = {agent.agent_id: 0 for agent in agents}

        for round_num in range(rounds):
            logger.info(f"[Coordinator] Debate round {round_num + 1}/{rounds}")

            round_statements = await asyncio.gather(
                *[self._debate_statement(agent, topic, statements, round_num) for agent in agents],
                return_exceptions=True,
            )

            for agent, statement in zip(agents, round_statements, strict=True):
                if isinstance(statement, Exception):
                    logger.error(f"Agent {agent.agent_id} debate error: {statement}")
                    continue

                if not isinstance(statement, str):
                    continue

                if agent.agent_id not in statements:
                    statements[agent.agent_id] = []
                statements[agent.agent_id].append(statement)

                votes[agent.agent_id] += self._count_votes(statement)

            await asyncio.sleep(0.5)

        winner_id = max(votes.keys(), key=lambda k: votes[k])

        return {
            "winner": winner_id,
            "winner_votes": votes.get(winner_id, 0),
            "all_votes": votes,
            "statements": statements,
            "consensus": votes.get(winner_id, 0) > len(agents) / 2,
        }

    async def execute_consensus(
        self,
        topic: str,
        agents: list[BaseAgent],
        threshold: float = 0.7,
    ) -> dict[str, Any]:
        """
        共识模式

        多个Agent投票，达到阈值则达成共识
        """
        logger.info(f"[Coordinator] Consensus on: {topic[:50]}...")

        proposals = await asyncio.gather(
            *[agent.process(AgentTask(description=f"提出对 '{topic}' 的解决方案")) for agent in agents],
            return_exceptions=True,
        )

        votes = dict.fromkeys(range(len(agents)), 0)

        for i, _agent in enumerate(agents):
            agent_proposal = proposals[i]
            if isinstance(agent_proposal, Exception):
                continue

            for j, other_proposal in enumerate(proposals):
                if i != j and not isinstance(other_proposal, Exception):
                    similarity = self._calculate_similarity(str(agent_proposal), str(other_proposal))
                    if similarity >= threshold:
                        votes[i] += 1

        max_votes = max(votes.values())
        consensus_idx = max(votes.keys(), key=lambda k: votes[k])
        consensus_rate = max_votes / len(agents)

        return {
            "consensus_reached": consensus_rate >= threshold,
            "consensus_rate": consensus_rate,
            "consensus_proposal": str(proposals[consensus_idx])
            if not isinstance(proposals[consensus_idx], Exception)
            else None,
            "votes": votes,
        }

    async def broadcast(
        self,
        message: AgentMessage,
        agents: Optional[list[str]] = None,
    ) -> list[AgentMessage]:
        """广播消息"""
        if agents:
            target_agents = [self.agents[a] for a in agents if a in self.agents]
        else:
            target_agents = list(self.agents.values())

        message.receivers = [a.agent_id for a in target_agents]

        await asyncio.gather(*[self.route_message(message) for _ in target_agents], return_exceptions=True)

        responses = []
        for agent in target_agents:
            response = await agent.receive_message()
            if response:
                responses.append(response)

        return responses

    async def _wait_dependencies(self, task: AgentTask):
        """等待依赖任务完成"""
        for dep_id in task.dependencies:
            dep_task = self._tasks.get(dep_id)
            if dep_task and dep_task.status != "completed":
                while dep_task.status not in ("completed", "failed"):
                    await asyncio.sleep(0.1)

                if dep_task.status == "failed":
                    raise RuntimeError(f"Dependency {dep_id} failed")

    async def _execute_subtask(
        self,
        task: AgentTask,
        factory: Optional[Callable],
    ) -> Any:
        """执行单个子任务"""
        agent = self._get_or_create_agent(task, factory)
        task.assigned_agent = agent.agent_id
        task.status = "running"
        try:
            result = await asyncio.wait_for(agent.process(task), timeout=self.timeout)
            task.status = "completed"
            task.result = result
            return result
        except TimeoutError:
            task.status = "failed"
            task.error = "Task timeout"
            return None
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            return None

    def _get_or_create_agent(
        self,
        task: AgentTask,
        factory: Optional[Callable[..., BaseAgent]],
    ) -> BaseAgent:
        """获取或创建Agent"""
        if task.assigned_agent and task.assigned_agent in self.agents:
            return self.agents[task.assigned_agent]

        if factory is not None:
            return factory(task)

        return TaijiAgent(
            agent_id=f"auto_{uuid.uuid4().hex[:8]}",
            role=AgentRole.EXECUTOR,
        )

    async def _default_decompose(self, task: AgentTask) -> list[AgentTask]:
        """默认任务分解"""
        keywords: dict[str, list[str]] = {
            "分析": ["数据分析", "代码分析", "市场分析"],
            "实现": ["设计", "编码", "测试"],
            "研究": ["搜索", "整理", "总结"],
        }

        for key, subs in keywords.items():
            if key in task.description:
                return [AgentTask(description=sub, dependencies=[task.id]) for sub in subs]

        return [task]

    def _synthesize_results(self, tasks: list[AgentTask]) -> dict[str, Any]:
        """综合结果"""
        successful = [t for t in tasks if t.status == "completed"]
        failed = [t for t in tasks if t.status == "failed"]

        return {
            "summary": f"Completed {len(successful)}/{len(tasks)} tasks",
            "successful": len(successful),
            "failed": len(failed),
            "results": [t.result for t in successful],
            "errors": [t.error for t in failed],
        }

    async def _debate_statement(
        self,
        agent: BaseAgent,
        topic: str,
        previous_statements: dict[str, list],
        round_num: int,
    ) -> str:
        """辩论发言"""
        context = ""
        for agent_id, statements in previous_statements.items():
            if statements:
                context += f"\n{agent_id}: {statements[-1]}"

        task = AgentTask(
            description=f"辩论话题 '{topic}'，第 {round_num + 1} 轮发言。"
            + (f"\n其他观点: {context}" if context else "")
        )

        result = await agent.process(task)
        return str(result)

    def _count_votes(self, statement: str) -> int:
        """计算得票"""
        score = 1
        positive_words = ["同意", "支持", "正确", "合理", "agree", "support"]
        negative_words = ["反对", "错误", "不对", "disagree", "wrong"]

        for word in positive_words:
            if word in statement:
                score += 1
        for word in negative_words:
            if word in statement:
                score -= 1

        return max(0, score)

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度"""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union)


class AgentSwarm:
    """
    智能体蜂群 - 动态多智能体系统

    根据任务需求动态创建和销毁Agent
    """

    def __init__(self, coordinator: MultiAgentCoordinator):
        self.coordinator = coordinator
        self._agent_templates: dict[str, Callable] = {}
        self._active_agents: dict[str, BaseAgent] = {}

    def register_template(
        self,
        template_id: str,
        factory: Callable[[str], BaseAgent],
    ):
        """注册Agent模板"""
        self._agent_templates[template_id] = factory

    async def spawn(
        self,
        template_id: str,
        agent_id: Optional[str] = None,
    ) -> BaseAgent:
        """生成Agent"""
        if template_id not in self._agent_templates:
            raise ValueError(f"Unknown template: {template_id}")

        agent_id = agent_id or f"{template_id}_{uuid.uuid4().hex[:8]}"
        agent = self._agent_templates[template_id](agent_id)

        self._active_agents[agent_id] = agent
        self.coordinator.register_agent(agent)
        await agent.start()

        logger.info(f"[Swarm] Spawned agent: {agent_id}")
        return agent  # type: ignore[no-any-return]

    async def despawn(self, agent_id: str):
        """销毁Agent"""
        if agent_id in self._active_agents:
            agent = self._active_agents[agent_id]
            await agent.stop()
            self.coordinator.unregister_agent(agent_id)
            del self._active_agents[agent_id]

            logger.info(f"[Swarm] Despawned agent: {agent_id}")

    async def despawn_all(self):
        """销毁所有Agent"""
        for agent_id in list(self._active_agents.keys()):
            await self.despawn(agent_id)

    def get_active_count(self) -> int:
        """获取活跃Agent数量"""
        return len(self._active_agents)


class MessageBus:
    """
    消息总线

    支持发布-订阅模式
    """

    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = {}
        self._history: list[AgentMessage] = []
        self._max_history = 1000

    def subscribe(self, topic: str, handler: Callable[[AgentMessage], Awaitable]):
        """订阅主题"""
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        self._subscribers[topic].append(handler)

    def unsubscribe(self, topic: str, handler: Callable):
        """取消订阅"""
        if topic in self._subscribers:
            self._subscribers[topic] = [h for h in self._subscribers[topic] if h != handler]

    async def publish(self, message: AgentMessage, topic: Optional[str] = None):
        """发布消息"""
        self._history.append(message)
        if len(self._history) > self._max_history:
            self._history.pop(0)

        if topic and topic in self._subscribers:
            for handler in self._subscribers[topic]:
                try:
                    await handler(message)
                except Exception as e:
                    logger.error(f"Message handler error: {e}")

    def get_history(self, limit: int = 100) -> list[AgentMessage]:
        """获取消息历史"""
        return self._history[-limit:]
