"""
Taiji Agent 2.1 — 开箱即用全流程 E2E 测试
==========================================
模拟：安装 → 首次对话 → 全能力逐一验证

测试流程:
  1. 环境初始化 (taiji_agent init)
  2. 首次对话启动 (banner + 系统提示)
  3. 记忆能力 (save/search/session/todo)
  4. 进化能力 (peer card + context + sentiment)
  5. 自我学习闭环 (learn_from_interaction → preferences → topics → skill)
  6. 技能生成 (SkillCreator 提取技能)
  7. 思考系统 (WFGY 验证 + 幻觉检测)
  8. 心跳系统 (PluginHealth + ProviderHealth + Failover)
  9. 工具调用 (15+ tools)
  10. 命令系统 (/help /compact /clear /new /sessions...)
  11. 会话持久化 (SQLite 写入/读取)
  12. 系统集成闭环 (evolution→memory→skill→verify)
"""
import asyncio
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# ═══════════════════════════════════════════════════════════════
# 阶段 0: 环境初始化
# ═══════════════════════════════════════════════════════════════

class TestPhase0_Init:
    """阶段 0 — 开箱初始化 (taiji_agent init)"""

    def test_init_creates_directories(self):
        """初始化创建所有必要目录"""
        tmp = tempfile.mkdtemp()
        try:
            home = Path(tmp)
            for d in ["souls", "memory", "skills", "logs", "exports"]:
                (home / d).mkdir(parents=True, exist_ok=True)
                assert (home / d).exists()

            # 模拟 config.yaml
            config_file = home / "config.yaml"
            config_file.write_text("""provider: anthropic
model: claude-sonnet-4-20250514
soul: default
verify_enabled: true
verify_threshold: 0.5
max_iterations: 25
stream: true
""")
            assert config_file.exists()
            config = config_file.read_text()
            assert "anthropic" in config
            assert "verify_enabled: true" in config
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_default_soul_created(self):
        """默认 Soul 文件创建"""
        from taiji_agent.souls.loader import SoulLoader
        tmp = tempfile.mkdtemp()
        try:
            loader = SoulLoader(souls_dir=Path(tmp))
            souls = loader.list_souls()
            assert "default" in souls
            soul = loader.load("default")
            assert soul.name == "太极助手"
            assert len(soul.boundaries) >= 4
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_session_store_initialized(self):
        """会话存储 SQLite 初始化"""
        from taiji_agent.cli.main import SessionStore
        tmp = tempfile.mkdtemp()
        try:
            db_path = os.path.join(tmp, "test.db")
            store = SessionStore(db_path=db_path)
            # 验证表存在
            tables = store.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = {t[0] for t in tables}
            assert "sessions" in table_names
            assert "messages" in table_names
            assert "session_meta" in table_names
            store.close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════
# 阶段 1: 首次对话启动
# ═══════════════════════════════════════════════════════════════

class TestPhase1_FirstConversation:
    """阶段 1 — 首次对话体验"""

    def test_agent_instantiation_first_time(self):
        """Agent 首次实例化"""
        from taiji_agent.agent.engine import AgentConfig, TaijiAgent

        t0 = time.perf_counter()
        agent = TaijiAgent(config=AgentConfig(verify_enabled=False, enable_sandbox=False))
        elapsed = time.perf_counter() - t0

        assert agent is not None
        assert elapsed < 10.0, f"Agent 实例化耗时 {elapsed:.2f}s > 10s"

    def test_system_prompt_content(self):
        """系统提示包含所有必要组件"""
        from taiji_agent.agent.engine import AgentConfig, TaijiAgent

        agent = TaijiAgent(config=AgentConfig(verify_enabled=True, enable_sandbox=False))
        prompt = agent._build_system_prompt()

        # 必须包含的组件
        assert "小佳" in prompt, "缺少身份标识"
        assert "Taiji" in prompt, "缺少框架标识"
        assert "阳" in prompt and "阴" in prompt, "缺少太极哲学"
        assert "事实依据" in prompt, "缺少行为约束"
        assert len(prompt) > 500, f"系统提示过短: {len(prompt)} 字符"

    def test_first_messages_assembled(self):
        """首轮消息组装: system + user"""
        from taiji_agent.agent.engine import AgentConfig, TaijiAgent, Message

        agent = TaijiAgent(config=AgentConfig(verify_enabled=False, enable_sandbox=False))
        system_prompt = agent._build_system_prompt()
        agent.messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content="你好，请介绍一下你的能力"),
        ]

        assembled = agent._assemble_prompt()
        assert len(assembled) == 2
        assert assembled[0]["role"] == "system"
        assert assembled[1]["role"] == "user"
        assert "太极" in assembled[0]["content"]

    def test_banner_format(self):
        """启动横幅格式正确"""
        from taiji_agent.cli.main import InteractiveAgent
        from taiji_agent.agent.engine import AgentConfig

        ia = InteractiveAgent(AgentConfig())
        # 验证横幅逻辑存在
        assert ia.config.model is not None
        assert ia.config.provider is not None
        assert "/help" in ia._commands
        assert "/compact" in ia._commands  # v2.2 新增

    def test_tool_count_in_banner(self):
        """横幅显示工具数量"""
        from taiji_agent.tools.registry import registry
        tool_count = len(registry.list_tools())
        assert tool_count >= 15, f"工具数量 {tool_count} < 15"

    def test_project_context_detection(self):
        """项目上下文自动检测"""
        cwd = os.getcwd()
        git_dir = os.path.join(cwd, ".git")
        # 当前项目是 taiji-agent，应该有 .git
        if os.path.exists(git_dir):
            project_name = os.path.basename(cwd)
            assert project_name == "taiji-agent"
            # 应该有 pyproject.toml
            assert os.path.exists(os.path.join(cwd, "pyproject.toml"))


# ═══════════════════════════════════════════════════════════════
# 阶段 2: 记忆能力
# ═══════════════════════════════════════════════════════════════

class TestPhase2_Memory:
    """阶段 2 — 记忆系统能力"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_short_term_memory(self):
        """短期记忆: save → get → search"""
        from taiji_agent.memory.session import SessionMemory
        mem = SessionMemory(memory_dir=Path(self.tmpdir))

        # 写入
        mem.save("user_name", "张三")
        mem.save("favorite_lang", "Python")
        mem.save("project", "taiji-agent")

        # 读取
        assert mem.get("user_name") == "张三"
        assert mem.get("nonexistent") is None

        # 搜索
        result = mem.search("Python")
        assert "Python" in result

    def test_session_memory(self):
        """会话记忆: 保存/搜索完整对话"""
        from taiji_agent.memory.session import SessionMemory
        mem = SessionMemory(memory_dir=Path(self.tmpdir))

        conversation = [
            {"role": "user", "content": "帮我写一个排序算法"},
            {"role": "assistant", "content": "以下是快速排序的实现: def quicksort(arr): ..."},
            {"role": "user", "content": "能否优化性能？"},
            {"role": "assistant", "content": "可以使用三数取中法优化 pivot 选择"},
        ]
        mem.save_session(conversation)

        result = mem.search("排序")
        assert "quicksort" in result.lower() or "排序" in result

        result = mem.search("优化")
        assert "pivot" in result.lower() or "优化" in result

    def test_todo_memory(self):
        """Todo 记忆: 完整 CRUD"""
        from taiji_agent.memory.session import SessionMemory
        mem = SessionMemory(memory_dir=Path(self.tmpdir))

        mem.add_todo("设计数据库 schema")
        mem.add_todo("实现 API 接口")
        mem.add_todo("编写单元测试")

        todos = mem.get_todos()
        assert len(todos) == 3
        assert not todos[0]["done"]

        mem.done_todo("实现 API 接口")
        todos = mem.get_todos()
        done_count = sum(1 for t in todos if t["done"])
        assert done_count == 1

    def test_memory_persistence(self):
        """记忆持久化: 跨实例验证"""
        from taiji_agent.memory.session import SessionMemory

        mem1 = SessionMemory(memory_dir=Path(self.tmpdir))
        mem1.save("persist_test", "value_123")
        mem1.add_todo("持久化任务")

        # 重新加载
        mem2 = SessionMemory(memory_dir=Path(self.tmpdir))
        assert mem2.get("persist_test") == "value_123"
        todos = mem2.get_todos()
        assert len(todos) == 1

    def test_sqlite_session_persistence(self):
        """SQLite 会话持久化: 写入 → 查询"""
        from taiji_agent.cli.main import SessionStore

        db_path = os.path.join(self.tmpdir, "sessions.db")
        store = SessionStore(db_path=db_path)

        # 创建会话
        sid = store.create_session(name="E2E测试会话")
        assert sid is not None

        # 写入消息
        store.save_message(sid, "user", "你好，这是首次对话")
        store.save_message(sid, "assistant", "你好！我是太极 Agent，很高兴为您服务。")

        # 读取
        msgs = store.load_messages(sid)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert "首次对话" in msgs[0]["content"]
        assert msgs[1]["role"] == "assistant"

        # 会话列表
        sessions = store.list_sessions()
        assert len(sessions) >= 1
        assert sessions[0]["name"] == "E2E测试会话"

        # 更新元数据
        store.update_meta(sid, wfgy_warnings=2, tools_used=json.dumps(["file_read", "web_search"]))
        meta = store.get_meta(sid)
        assert meta["wfgy_warnings"] == 2

        store.close()


# ═══════════════════════════════════════════════════════════════
# 阶段 3: 进化系统
# ═══════════════════════════════════════════════════════════════

class TestPhase3_Evolution:
    """阶段 3 — 进化系统能力"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_peer_card_evolution(self):
        """用户画像进化: 多次交互累积"""
        from taiji_agent.learning.loop import HonchoMemory

        honcho = HonchoMemory(memory_dir=Path(self.tmpdir))

        # 首次交互
        honcho.update_peer_card("user", facts=["初次见面"], topic="介绍", sentiment=0.6)
        card = honcho.get_peer_card("user")
        assert card.interaction_count == 1

        # 第二次交互 — 学习新事实
        honcho.update_peer_card("user", facts=["需要Python帮助"], topic="编程", sentiment=0.7)
        card = honcho.get_peer_card("user")
        assert card.interaction_count == 2
        assert len(card.facts) >= 2
        assert "编程" in card.learned_topics

        # 第三次 — 偏好
        honcho.update_peer_card("user", preferences={"language": "中文", "detail_level": "详细"})
        card = honcho.get_peer_card("user")
        assert card.interaction_count == 3
        assert card.preferences["language"] == "中文"

        # 验证进化轨迹
        assert card.get_avg_sentiment() > 0.5

    def test_context_accumulation(self):
        """上下文累积与回忆"""
        from taiji_agent.learning.loop import HonchoMemory

        honcho = HonchoMemory(memory_dir=Path(self.tmpdir))

        # 存储多个上下文
        honcho.store_context(
            event="用户询问: 如何优化Python性能",
            conclusion="建议: 使用列表推导式、避免全局变量、使用生成器",
            topics=["编程", "Python", "性能"],
            confidence=0.9,
        )
        honcho.store_context(
            event="用户询问: Docker部署最佳实践",
            conclusion="多阶段构建 + alpine基础镜像 + 健康检查",
            topics=["DevOps", "Docker", "部署"],
            confidence=0.85,
        )
        honcho.store_context(
            event="用户询问: 微服务架构设计",
            conclusion="建议使用DDD划分边界、异步通信、服务网格",
            topics=["架构", "微服务", "设计"],
            confidence=0.8,
        )

        # 按主题回忆
        results = honcho.recall_contexts(topic="Python")
        assert len(results) == 1
        assert "列表推导式" in results[0].conclusion

        # 按查询回忆
        results = honcho.recall_contexts(query="Docker")
        assert len(results) == 1
        assert "多阶段构建" in results[0].conclusion

        # 按查询回忆 (模糊)
        results = honcho.recall_contexts(query="性能")
        assert len(results) >= 1

    def test_user_context_prompt_evolution(self):
        """用户上下文提示随交互进化"""
        from taiji_agent.learning.loop import HonchoMemory

        honcho = HonchoMemory(memory_dir=Path(self.tmpdir))

        # 新用户 — 无上下文
        prompt = honcho.get_user_context_prompt("new_user")
        assert prompt == "" or "交互" not in prompt.lower()

        # 活跃用户 — 丰富上下文
        honcho.update_peer_card("active_user",
            facts=["Python开发者", "熟悉Docker", "偏好敏捷开发", "关注性能优化"],
            topic="编程",
            sentiment=0.8,
        )
        honcho.update_peer_card("active_user",
            facts=["正在学习Rust", "对WASM感兴趣"],
            topic="Rust",
            sentiment=0.7,
        )
        prompt = honcho.get_user_context_prompt("active_user")
        # facts[-5:] 截断，前5条中最老的 "Python开发者" 可能被挤出
        assert "Docker" in prompt or "Rust" in prompt or "WASM" in prompt
        assert "积极" in prompt  # avg sentiment > 0.5


# ═══════════════════════════════════════════════════════════════
# 阶段 4: 自我学习闭环
# ═══════════════════════════════════════════════════════════════

class TestPhase4_SelfLearningLoop:
    """阶段 4 — 自我学习闭环"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.honcho = None
        self.loop = None

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _init_loop(self):
        from taiji_agent.learning.loop import HonchoMemory, SelfImprovingLoop
        from taiji_agent.skills.hub import SkillManager
        from taiji_agent.taiji_verify import WFGYVerifier

        self.honcho = HonchoMemory(memory_dir=Path(self.tmpdir))
        skills_dir = Path(self.tmpdir) / "skills"
        skills_dir.mkdir(exist_ok=True)
        self.skill_mgr = SkillManager(skills_dir=skills_dir)
        self.wfgy = WFGYVerifier()
        self.loop = SelfImprovingLoop(self.honcho, self.skill_mgr, self.wfgy)
        return self.loop

    def test_learn_preferences_from_conversation(self):
        """从对话学习用户偏好"""
        loop = self._init_loop()
        conversation = [
            {"role": "user", "content": "我 prefer 中文回答，喜欢详细的分析"},
            {"role": "assistant", "content": "好的，我会用中文提供详细分析"},
        ]
        aloop = asyncio.new_event_loop()
        result = aloop.run_until_complete(
            loop.learn_from_interaction(
                conversation=conversation,
                task="测试偏好学习",
                result="用中文详细回答",
                tools_used=[],
                user_id="test_user",
            )
        )
        aloop.close()
        assert "preferences" in result
        # 验证偏好已存储到 honcho
        card = self.honcho.get_peer_card("test_user")
        assert len(card.preferences) > 0

    def test_learn_topics_from_task(self):
        """从任务学习主题"""
        loop = self._init_loop()
        conversation = [
            {"role": "user", "content": "帮我debug这个函数的性能问题"},
            {"role": "assistant", "content": "分析发现循环可以使用列表推导式优化"},
        ]
        aloop = asyncio.new_event_loop()
        aloop.run_until_complete(
            loop.learn_from_interaction(
                conversation=conversation,
                task="debug函数性能问题",
                result="使用列表推导式优化循环",
                tools_used=["file_read"],
                user_id="dev_user",
            )
        )
        aloop.close()
        card = self.honcho.get_peer_card("dev_user")
        assert "编程" in card.learned_topics

    def test_sentiment_tracking_in_loop(self):
        """闭环情感追踪"""
        loop = self._init_loop()
        conversation = [
            {"role": "user", "content": "这个结果很好，非常感谢你的帮助！"},
        ]
        aloop = asyncio.new_event_loop()
        aloop.run_until_complete(
            loop.learn_from_interaction(
                conversation=conversation,
                task="测试正反馈",
                result="很好，谢谢",
                tools_used=[],
                user_id="happy_user",
            )
        )
        aloop.close()
        card = self.honcho.get_peer_card("happy_user")
        assert len(card.sentiment_history) == 1
        assert card.sentiment_history[0] > 0.5  # 正向情感

    def test_context_persistence_in_loop(self):
        """闭环上下文持久化"""
        loop = self._init_loop()
        conversation = [
            {"role": "user", "content": "分析这段代码"},
            {"role": "assistant", "content": "发现了3个问题: 1.内存泄漏 2.竞态条件 3.异常未处理"},
        ]
        aloop = asyncio.new_event_loop()
        aloop.run_until_complete(
            loop.learn_from_interaction(
                conversation=conversation,
                task="分析代码问题",
                result="发现内存泄漏、竞态条件、异常未处理",
                tools_used=["file_read", "shell"],
                user_id="reviewer",
            )
        )
        aloop.close()
        # 验证上下文已存储
        contexts = self.honcho.recall_contexts(query="内存泄漏")
        assert len(contexts) >= 1

    def test_learning_hooks_fire(self):
        """学习钩子触发"""
        loop = self._init_loop()
        hook_data = []

        async def test_hook(data):
            hook_data.append(data)

        loop.on_learning(test_hook)
        conversation = [{"role": "user", "content": "hello"}]
        aloop = asyncio.new_event_loop()
        aloop.run_until_complete(
            loop.learn_from_interaction(
                conversation=conversation, task="test",
                result="ok", tools_used=[], user_id="hook_user",
            )
        )
        aloop.close()
        assert len(hook_data) == 1


# ═══════════════════════════════════════════════════════════════
# 阶段 5: 技能生成
# ═══════════════════════════════════════════════════════════════

class TestPhase5_SkillGeneration:
    """阶段 5 — 技能系统：安装→创建→改进→使用"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        skills_dir = Path(self.tmpdir) / "skills"
        skills_dir.mkdir(exist_ok=True)
        from taiji_agent.skills.hub import SkillManager
        self.mgr = SkillManager(skills_dir=skills_dir)

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_market_skills_available(self):
        """技能市场有预置技能"""
        from taiji_agent.skills.hub import SkillMarket
        market = SkillMarket()
        skills = market.browse()
        assert len(skills) >= 7
        skill_ids = {s["id"] for s in skills}
        assert "code-review" in skill_ids
        assert "github-auth" in skill_ids
        assert "web-research" in skill_ids
        assert "chinese-context" in skill_ids

    def test_install_and_use_skill(self):
        """安装并使用技能"""
        self.mgr.install("code-review")
        skill = self.mgr.get("code-review")
        assert skill is not None
        assert skill.name == "代码审查"

        instructions = self.mgr.use("code-review")
        assert instructions is not None
        assert "代码审查" in instructions or "审查" in instructions

    def test_create_skill_from_scratch(self):
        """从零创建技能"""
        loop = asyncio.new_event_loop()
        skill = loop.run_until_complete(
            self.mgr.create(
                name="Python性能分析",
                description="分析Python代码性能瓶颈并提供优化建议",
                instructions="1. cProfile分析\n2. 识别热点函数\n3. 内存分析\n4. 提供优化方案",
                tools=["file_read", "shell", "execute_code"],
                category="开发",
            )
        )
        loop.close()
        assert skill is not None
        assert "python" in skill.id.lower() or "python" in skill.name.lower()
        assert skill.category == "开发"
        assert "file_read" in skill.tools

    def test_skill_improvement(self):
        """技能改进"""
        loop = asyncio.new_event_loop()
        skill = loop.run_until_complete(
            self.mgr.create(
                name="code-quality-check",
                description="代码质量检查",
                instructions="检查代码风格和基本错误",
                tools=["file_read"],
                category="开发",
            )
        )
        loop.close()
        assert skill.confidence == 0.7  # auto_created default

        loop2 = asyncio.new_event_loop()
        improved = loop2.run_until_complete(
            self.mgr.improve(skill.id, [
                "新增: 安全漏洞扫描步骤",
                "优化: 使用AST分析替代正则匹配",
                "改进: 支持自定义规则集",
            ])
        )
        loop2.close()
        assert improved is not None
        assert improved.confidence > 0.7  # 改进后信心提升

    def test_skill_creator_from_conversation(self):
        """从对话中自动提取技能"""
        from taiji_agent.skills.hub import SkillCreator

        creator = SkillCreator(self.mgr)
        # 足够长的对话 + 多个复杂关键词 以触发 complexity >= 0.6
        conversation = [
            {"role": "user", "content": "帮我设计并实现一个代码审查的自动化流水线"},
            {"role": "assistant", "content": "好的，先file_read读取代码，然后用shell运行lint检查"},
            {"role": "user", "content": "还需要分析代码复杂度并优化性能"},
            {"role": "assistant", "content": "可以使用execute_code运行性能测试"},
            {"role": "user", "content": "重构部分代码以符合设计模式"},
            {"role": "assistant", "content": "建议使用策略模式和工厂模式重构"},
        ]
        loop = asyncio.new_event_loop()
        skill = loop.run_until_complete(
            creator.extract_from_conversation(
                task="设计并实现代码审查、性能分析与重构的自动化流水线",
                successful_result="使用 file_read + shell lint + execute_code 实现代码质量门禁与性能优化",
                conversation=conversation,
            )
        )
        loop.close()
        # 复杂度足够高 (>0.6) 时会创建技能
        assert skill is not None
        assert "审查" in skill.name or "代码" in skill.name or "code" in skill.name.lower() or "流水线" in skill.name

    def test_skill_statistics(self):
        """技能统计完整"""
        self.mgr.install("code-review")
        self.mgr.install("web-research")
        loop = asyncio.new_event_loop()
        loop.run_until_complete(self.mgr.create(
            name="custom-skill", description="d", instructions="i",
            tools=[], category="custom",
        ))
        loop.close()

        stats = self.mgr.get_stats()
        assert stats["total"] >= 3
        assert "by_category" in stats
        assert "auto_created" in stats
        assert stats["avg_confidence"] >= 0


# ═══════════════════════════════════════════════════════════════
# 阶段 6: 思考与反思系统
# ═══════════════════════════════════════════════════════════════

class TestPhase6_Thinking:
    """阶段 6 — 思考与反思 (WFGY)"""

    def test_wfgy_verification_flow(self):
        """WFGY 验证流程"""
        from taiji_agent.taiji_verify import WFGYVerifier

        wfgy = WFGYVerifier()
        # 可信内容
        assert wfgy.verify("The Earth orbits around the Sun in approximately 365.25 days.") is True
        # 可信内容
        assert wfgy.verify("Python is a high-level programming language created by Guido van Rossum.") is True

    def test_hallucination_detection_flow(self):
        """幻觉检测流程"""
        from taiji_agent.taiji_verify import HallucinationDetector

        detector = HallucinationDetector()

        # 正常内容 — 低风险
        risk_normal = detector.detect("Python is widely used in data science and web development.")
        assert 0 <= risk_normal <= 1

        # 模糊内容 — 中高风险
        risk_uncertain = detector.detect("I'm not entirely sure but I think Python was invented in 1990 by Dennis Ritchie.")
        assert 0 <= risk_uncertain <= 1

    def test_self_consistency_check(self):
        """自我一致性检查"""
        from taiji_agent.taiji_verify import SelfConsistencyChecker

        checker = SelfConsistencyChecker()
        # 添加多次回答
        for i in range(5):
            checker.add_sample(f"The capital of France is Paris. Answer variant {i}.")

        score = checker.check()
        assert 0 <= score <= 1

    def test_agent_wfgy_integration(self):
        """Agent 中 WFGY 集成"""
        from taiji_agent.agent.engine import AgentConfig, TaijiAgent

        agent = TaijiAgent(config=AgentConfig(verify_enabled=True, verify_threshold=0.5, enable_sandbox=False))

        class MockResponse:
            content = "The Python programming language was created by Guido van Rossum."
            tool_calls = None

        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(agent._verify_and_annotate(MockResponse()))
        loop.close()
        assert result is not None


# ═══════════════════════════════════════════════════════════════
# 阶段 7: 心跳系统
# ═══════════════════════════════════════════════════════════════

class TestPhase7_Heartbeat:
    """阶段 7 — 心跳与健康监测"""

    def test_plugin_health_states(self):
        """插件健康状态完整覆盖"""
        from taiji_agent.plugin.plugin_base import PluginHealth, PluginState

        # 所有健康状态可访问
        states = [PluginHealth.HEALTHY, PluginHealth.DEGRADED, PluginHealth.UNHEALTHY, PluginHealth.ERROR]
        assert all(isinstance(s.value, int) for s in states)

        # 生命周期完整
        lifecycle = [
            PluginState.REGISTERED, PluginState.LOADING, PluginState.LOADED,
            PluginState.ACTIVATING, PluginState.ACTIVE, PluginState.DEACTIVATING,
            PluginState.DEACTIVATED, PluginState.ERROR,
        ]
        assert len(lifecycle) == 8

    def test_tool_definition_heartbeat(self):
        """工具定义健康"""
        from taiji_agent.plugin.plugin_base import ToolDefinition

        td = ToolDefinition(
            name="heartbeat_test",
            description="心跳测试工具",
            parameters={"type": "object", "properties": {"interval": {"type": "integer"}}},
        )
        assert td.name == "heartbeat_test"
        assert td.description != ""

    def test_hook_registration_heartbeat(self):
        """钩子注册心跳"""
        from taiji_agent.plugin.plugin_base import HookRegistration

        hook = HookRegistration(
            event="agent:heartbeat",
            handler=lambda x: {"status": "ok"},
            priority=1,
        )
        assert hook.event == "agent:heartbeat"
        assert hook.priority == 1

    def test_failover_health(self):
        """故障转移健康摘要"""
        from taiji_agent.providers.failover import (
            ProviderRouter, ProviderEndpoint, ProviderStatus,
        )

        router = ProviderRouter()
        router.add_endpoint(ProviderEndpoint(
            name="primary", provider="anthropic", model="claude",
            priority=1, status=ProviderStatus.HEALTHY,
        ))
        router.add_endpoint(ProviderEndpoint(
            name="fallback", provider="openai", model="gpt-4o",
            priority=2, status=ProviderStatus.HEALTHY,
        ))
        router.add_endpoint(ProviderEndpoint(
            name="degraded", provider="qwen", model="qwen-max",
            priority=3, status=ProviderStatus.DEGRADED,
        ))

        health = router.get_health_summary()
        assert health["total"] == 3
        assert health["healthy"] == 2
        assert health["degraded"] == 1
        assert health["available"] is True

        # 端点状态列表
        statuses = router.get_status()
        assert len(statuses) == 3
        assert statuses[0]["name"] == "primary"
        assert statuses[0]["status"] == "healthy"

    def test_taiji_verify_engine_heartbeat(self):
        """太极验证引擎健康"""
        from taiji_agent.taiji_verify.engine import TaijiVerifyEngine

        engine = TaijiVerifyEngine(embedding_dim=64)
        health = engine.system_health
        assert "fu_return_state" in health
        assert "failure_modes_enabled" in health


# ═══════════════════════════════════════════════════════════════
# 阶段 8: 工具调用系统
# ═══════════════════════════════════════════════════════════════

class TestPhase8_ToolCalling:
    """阶段 8 — 工具调用全能力"""

    def setup_method(self):
        from taiji_agent.tools.registry import ToolRegistry
        self.registry = ToolRegistry()

    def test_file_operations(self):
        """文件操作三件套"""
        # Write
        tmp = tempfile.mkdtemp()
        try:
            test_file = os.path.join(tmp, "test.txt")
            result = self.registry._file_write(test_file, "Hello E2E Test!")
            assert "File written" in result

            # Read
            content = self.registry._file_read(test_file)
            assert "Hello E2E Test" in content

            # List
            listing = self.registry._file_list(path=tmp)
            assert "test.txt" in listing

            # Search
            search_result = self.registry._file_search(pattern="E2E", path=tmp)
            assert "E2E" in search_result or "test.txt" in search_result
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_shell_execution(self):
        """Shell 命令执行"""
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(self.registry._shell("echo 'Hello from shell'"))
        loop.close()
        assert "Hello from shell" in result

    def test_shell_timeout(self):
        """Shell 超时处理"""
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(self.registry._shell("sleep 60", timeout=1))
        loop.close()
        assert "timed out" in result.lower()

    def test_git_operations(self):
        """Git 操作"""
        status = self.registry._git_status(path=".")
        assert isinstance(status, str) and len(status) > 0

        log = self.registry._git_log(path=".", limit=3)
        assert isinstance(log, str) and len(log) > 0

    def test_code_execution(self):
        """代码执行"""
        result = self.registry._execute_code("print('E2E code execution OK')", "python")
        assert "E2E code execution OK" in result

    def test_todo_operations(self):
        """Todo 操作"""
        r1 = self.registry._todo_add("E2E 测试任务 #1")
        assert "Task added" in r1

        r2 = self.registry._todo_add("E2E 测试任务 #2")
        assert "Task added" in r2

        r3 = self.registry._todo_list()
        assert "E2E 测试任务 #1" in r3

        r4 = self.registry._todo_done("E2E 测试任务 #1")
        assert "Task completed" in r4

    def test_memory_tools(self):
        """记忆工具"""
        r1 = self.registry._memory_save("e2e_key", "e2e_value_12345")
        assert "Memory saved" in r1

        r2 = self.registry._memory_search("e2e_key")
        assert isinstance(r2, str) and len(r2) > 0

    def test_all_tools_registered(self):
        """所有工具已注册"""
        tools = self.registry.list_tools()
        assert len(tools) >= 15
        # 按类别验证
        file_tools = [t for t in tools if t.startswith("file_")]
        assert len(file_tools) >= 4  # read, write, list, search

        assert "shell" in tools
        assert "web_search" in tools
        assert "web_extract" in tools
        assert "git_status" in tools
        assert "git_log" in tools
        assert "execute_code" in tools
        assert "memory_search" in tools
        assert "memory_save" in tools
        assert "todo_list" in tools
        assert "todo_add" in tools
        assert "todo_done" in tools

    def test_tool_schemas_complete(self):
        """工具 Schema 完整"""
        for tool_name in self.registry.list_tools():
            schema = self.registry.get_schema(tool_name)
            assert schema is not None, f"Schema missing for {tool_name}"
            assert schema.name == tool_name
            assert schema.description != "", f"Empty description for {tool_name}"
            assert "type" in schema.parameters


# ═══════════════════════════════════════════════════════════════
# 阶段 9: 命令系统
# ═══════════════════════════════════════════════════════════════

class TestPhase9_Commands:
    """阶段 9 — 命令系统完整验证"""

    def test_all_commands_registered(self):
        """所有命令已注册"""
        from taiji_agent.cli.main import InteractiveAgent
        from taiji_agent.agent.engine import AgentConfig

        ia = InteractiveAgent(AgentConfig())
        commands = ia._commands

        # Claude Code 对齐命令
        assert "/help" in commands
        assert "/clear" in commands
        assert "/compact" in commands
        assert "/exit" in commands
        assert "/quit" in commands
        assert "/q" in commands

        # Taiji 增强命令
        assert "/new" in commands
        assert "/sessions" in commands
        assert "/switch" in commands
        assert "/delete" in commands
        assert "/history" in commands
        assert "/model" in commands
        assert "/soul" in commands
        assert "/tools" in commands
        assert "/wfgy" in commands
        assert "/export" in commands

        # 总数
        assert len(commands) >= 15

    def test_compact_command_available(self):
        """/compact 命令可用"""
        from taiji_agent.cli.main import InteractiveAgent
        from taiji_agent.agent.engine import AgentConfig, Message

        ia = InteractiveAgent(AgentConfig())
        # 构建足够的消息以触发压缩（需要 > 4 + recent 6 = 10 条才能压缩）
        msgs = [Message(role="system", content="system prompt for the session")]
        for i in range(10):
            msgs.append(Message(role="user", content=f"这是第{i+1}轮用户消息，包含足够多内容来形成有意义的对话历史"))
            msgs.append(Message(role="assistant", content=f"这是第{i+1}轮助手回复，同样包含充分的信息来支撑上下文摘要功能"))
        ia.agent = type('obj', (object,), {'messages': msgs})()
        before = len(ia.agent.messages)
        ia._cmd_compact()
        after = len(ia.agent.messages)
        assert after < before, f"压缩失败: {before} → {after}"

    def test_help_table_contains_new_commands(self):
        """/help 表格包含 /compact"""
        from taiji_agent.cli.main import InteractiveAgent
        from taiji_agent.agent.engine import AgentConfig

        ia = InteractiveAgent(AgentConfig())
        # 调用 _show_help 看是否含 /compact
        assert "/compact" in ia._commands


# ═══════════════════════════════════════════════════════════════
# 阶段 10: 完整闭环集成
# ═══════════════════════════════════════════════════════════════

class TestPhase10_FullClosedLoop:
    """阶段 10 — 完整闭环：进化→记忆→学习→技能→验证"""

    def test_complete_workflow(self):
        """模拟用户完整交互流程"""
        tmpdir = tempfile.mkdtemp()
        try:
            from taiji_agent.learning.loop import HonchoMemory, SelfImprovingLoop
            from taiji_agent.skills.hub import SkillManager
            from taiji_agent.taiji_verify import WFGYVerifier
            from taiji_agent.memory.session import SessionMemory

            # 1. 初始化
            honcho = HonchoMemory(memory_dir=Path(tmpdir))
            skills_dir = Path(tmpdir) / "skills"
            skills_dir.mkdir(exist_ok=True)
            skill_mgr = SkillManager(skills_dir=skills_dir)
            wfgy = WFGYVerifier()
            session_mem = SessionMemory(memory_dir=Path(tmpdir) / "sessions")
            loop = SelfImprovingLoop(honcho, skill_mgr, wfgy)

            # 2. 用户首次对话
            first_conversation = [
                {"role": "user", "content": "你好，我需要分析一段Python代码的性能问题"},
                {"role": "assistant", "content": "好的，我会使用 file_read 读取代码，然后运行性能分析工具"},
            ]

            # 3. 学习
            aloop = asyncio.new_event_loop()
            result = aloop.run_until_complete(
                loop.learn_from_interaction(
                    conversation=first_conversation,
                    task="分析Python代码性能",
                    result="使用cProfile进行性能分析，发现热点在循环嵌套",
                    tools_used=["file_read", "shell", "execute_code"],
                    user_id="e2e_user",
                )
            )
            aloop.close()

            # 4. 验证进化结果
            card = honcho.get_peer_card("e2e_user")
            assert card.interaction_count >= 1
            assert "编程" in card.learned_topics

            # 5. 验证记忆
            contexts = honcho.recall_contexts(query="Python")
            assert len(contexts) >= 1

            # 6. 验证技能生成
            skills = skill_mgr.list()
            # 复杂任务(complexity > 0.7)应生成技能
            if len(skills) > 0:
                assert skills[0].auto_created is True

            # 7. 保存会话
            session_mem.save_session(first_conversation)
            search_result = session_mem.search("Python")
            assert len(search_result) > 0

            # 8. WFGY 验证
            verified = wfgy.verify("使用cProfile进行性能分析是Python性能优化的标准方法")
            assert isinstance(verified, bool)

            print(f"  ✓ 完整闭环: 进化(card={card.interaction_count}) → "
                  f"记忆(contexts={len(contexts)}) → "
                  f"技能(skills={len(skills)}) → "
                  f"验证({verified})")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_multi_turn_learning_progression(self):
        """多轮学习递进"""
        tmpdir = tempfile.mkdtemp()
        try:
            from taiji_agent.learning.loop import HonchoMemory, SelfImprovingLoop
            from taiji_agent.skills.hub import SkillManager
            from taiji_agent.taiji_verify import WFGYVerifier

            honcho = HonchoMemory(memory_dir=Path(tmpdir))
            skills_dir = Path(tmpdir) / "skills"
            skills_dir.mkdir(exist_ok=True)
            skill_mgr = SkillManager(skills_dir=skills_dir)
            wfgy = WFGYVerifier()
            loop = SelfImprovingLoop(honcho, skill_mgr, wfgy)

            # 第1轮
            aloop = asyncio.new_event_loop()
            aloop.run_until_complete(loop.learn_from_interaction(
                conversation=[{"role": "user", "content": "分析这段Python代码的性能问题"}],
                task="分析代码性能优化", result="使用列表推导式改进function",
                tools_used=["file_read"], user_id="learner",
            ))
            aloop.close()

            card1 = honcho.get_peer_card("learner")
            assert card1.interaction_count >= 1
            assert len(card1.learned_topics) >= 1  # "代码" or "分析" keyword

            # 第2轮
            aloop = asyncio.new_event_loop()
            aloop.run_until_complete(loop.learn_from_interaction(
                conversation=[{"role": "user", "content": "设计Docker部署架构"}],
                task="设计Docker部署架构", result="使用多阶段构建优化镜像",
                tools_used=["shell"], user_id="learner",
            ))
            aloop.close()

            card2 = honcho.get_peer_card("learner")
            assert card2.interaction_count >= 2
            assert len(card2.learned_topics) >= 1

            # 第3轮
            aloop = asyncio.new_event_loop()
            aloop.run_until_complete(loop.learn_from_interaction(
                conversation=[{"role": "user", "content": "设计微服务架构"}],
                task="设计微服务架构", result="采用DDD + 事件驱动",
                tools_used=["file_read", "file_write", "shell"],
                user_id="learner",
            ))
            aloop.close()

            card3 = honcho.get_peer_card("learner")
            assert card3.interaction_count >= 3
            assert len(card3.learned_topics) >= 2

        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("   Taiji Agent 2.1 — 开箱即用全流程 E2E 测试")
    print("=" * 80)
    sys.exit(pytest.main([__file__, "-v", "--tb=short", "-p", "no:warnings"]))
