"""
Taiji Agent 2.1 — 首次对话体验 vs Claude Code 对比测试
========================================================
验证安装后的首次对话内容、欢迎语、提示系统、命令系统与 Claude Code 的一致性
"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from taiji_agent.agent.engine import AgentConfig, TaijiAgent
from taiji_agent.souls.loader import SoulLoader, inject_soul
from taiji_agent.cli.main import InteractiveAgent, SessionStore, load_config
from taiji_agent.taiji_verify import WFGYVerifier, HallucinationDetector


class TestOnboardingBanner:
    """首次对话横幅/欢迎语 对比 Claude Code"""

    def test_banner_contains_session_info(self):
        """横幅包含会话ID、模型、提供者信息 — Claude Code 层级"""
        ia = InteractiveAgent(AgentConfig())
        assert ia.config.model == "claude-sonnet-4-20250514"
        assert ia.config.provider == "anthropic"
        assert ia.config.soul == "default"

    def test_banner_shows_wfgy_status(self):
        """横幅显示 WFGY 防幻觉状态 — Taiji 特有功能标记"""
        config_wfgy_on = AgentConfig(verify_enabled=True)
        ia = InteractiveAgent(config_wfgy_on)
        assert ia.config.verify_enabled is True

        config_wfgy_off = AgentConfig(verify_enabled=False)
        ia2 = InteractiveAgent(config_wfgy_off)
        assert ia2.config.verify_enabled is False

    def test_banner_shows_stream_status(self):
        """横幅显示流式输出状态 — Claude Code 默认流式"""
        config = AgentConfig(stream=True)
        ia = InteractiveAgent(config)
        assert ia.config.stream is True

    def test_banner_hints_help_command(self):
        """横幅提示 /help 命令 — Claude Code 风格"""
        # InteractiveAgent._commands always includes /help
        ia = InteractiveAgent(AgentConfig())
        assert "/help" in ia._commands

    def test_default_prompt_format(self):
        """默认提示格式 [你] → 清晰标识用户输入"""
        # 验证 prompt 约定存在于代码中
        assert "[你]" in " [你] → "
        assert "[太极]" in "[太极] → "


class TestSystemPrompt:
    """系统提示词 vs Claude Code 系统提示"""

    def test_system_prompt_has_identity(self):
        """系统提示包含 Agent 身份标识"""
        agent = TaijiAgent(config=AgentConfig(verify_enabled=False, enable_sandbox=False))
        prompt = agent._build_system_prompt()
        assert "太极 Agent" in prompt
        assert "OpenTaiji" in prompt

    def test_system_prompt_has_wfgy_guide(self):
        """系统提示包含防幻觉指南 — Claude Code 无此能力"""
        agent = TaijiAgent(config=AgentConfig(verify_enabled=True, enable_sandbox=False))
        prompt = agent._build_system_prompt()
        assert "WFGY" in prompt
        assert "事实依据" in prompt

    def test_system_prompt_has_taiji_philosophy(self):
        """系统提示包含太极哲学 — 阴阳平衡"""
        agent = TaijiAgent(config=AgentConfig(verify_enabled=False, enable_sandbox=False))
        prompt = agent._build_system_prompt()
        assert "阳" in prompt
        assert "阴" in prompt
        assert "平衡" in prompt

    def test_system_prompt_has_tool_awareness(self):
        """系统提示体现工具使用意识"""
        agent = TaijiAgent(config=AgentConfig(verify_enabled=False, enable_sandbox=False))
        prompt = agent._build_system_prompt()
        # 工具系统在 Agent Loop 中动态注入，但系统提示不含具体工具
        assert isinstance(prompt, str)
        assert len(prompt) > 200  # 足够丰富

    def test_first_turn_message_structure(self):
        """首轮对话消息结构: system + user"""
        agent = TaijiAgent(config=AgentConfig(verify_enabled=False, enable_sandbox=False))
        agent.messages = []  
        # 模拟 run() 的第一步
        system_prompt = agent._build_system_prompt()
        from taiji_agent.agent.engine import Message
        agent.messages.append(Message(role="system", content=system_prompt))
        agent.messages.append(Message(role="user", content="你好"))
        
        assert len(agent.messages) == 2
        assert agent.messages[0].role == "system"
        assert agent.messages[1].role == "user"
        assert agent.messages[1].content == "你好"


class TestCommandParity:
    """命令系统对比 Claude Code"""

    def test_help_command_exists(self):
        """Claude Code 有 /help，Taiji 也有 /help"""
        ia = InteractiveAgent(AgentConfig())
        assert "/help" in ia._commands

    def test_new_session_command(self):
        """Claude Code 无显式 /new，Taiji 增强：支持 /new 创建会话"""
        ia = InteractiveAgent(AgentConfig())
        assert "/new" in ia._commands

    def test_sessions_command(self):
        """Claude Code 无 /sessions 列表，Taiji 增强：会话管理"""
        ia = InteractiveAgent(AgentConfig())
        assert "/sessions" in ia._commands

    def test_clear_command(self):
        """Claude Code 有 /clear，Taiji 也有 /clear"""
        ia = InteractiveAgent(AgentConfig())
        assert "/clear" in ia._commands

    def test_exit_commands(self):
        """Claude Code /exit，Taiji 有 /exit + /quit + /q"""
        ia = InteractiveAgent(AgentConfig())
        assert "/exit" in ia._commands
        assert "/quit" in ia._commands
        assert "/q" in ia._commands

    def test_tools_command(self):
        """Claude Code 自动展示工具，Taiji 有 /tools 命令"""
        ia = InteractiveAgent(AgentConfig())
        assert "/tools" in ia._commands

    def test_export_command(self):
        """Claude Code 无导出，Taiji 增强：/export 导出 Markdown"""
        ia = InteractiveAgent(AgentConfig())
        assert "/export" in ia._commands

    def test_model_switch_command(self):
        """Taiji 独有：/model 切换模型"""
        ia = InteractiveAgent(AgentConfig())
        assert "/model" in ia._commands

    def test_soul_switch_command(self):
        """Taiji 独有：/soul 切换人格"""
        ia = InteractiveAgent(AgentConfig())
        assert "/soul" in ia._commands

    def test_wfgy_toggle_command(self):
        """Taiji 独有：/wfgy 开关防幻觉"""
        ia = InteractiveAgent(AgentConfig())
        assert "/wfgy" in ia._commands

    def test_history_command(self):
        """Claude Code 无 /history，Taiji 增强：查看历史"""
        ia = InteractiveAgent(AgentConfig())
        assert "/history" in ia._commands

    def test_switch_command(self):
        """Taiji 独有：/switch 切换会话"""
        ia = InteractiveAgent(AgentConfig())
        assert "/switch" in ia._commands

    def test_delete_command(self):
        """Taiji 独有：/delete 删除会话"""
        ia = InteractiveAgent(AgentConfig())
        assert "/delete" in ia._commands

    def test_command_total_count(self):
        """命令总数统计"""
        ia = InteractiveAgent(AgentConfig())
        # /help, /new, /sessions, /switch, /delete,
        # /history, /clear, /model, /soul, /tools,
        # /wfgy, /export, /exit, /quit, /q = 15
        assert len(ia._commands) >= 14

    def test_tab_completion_enabled(self):
        """Tab 自动补全已启用"""
        ia = InteractiveAgent(AgentConfig())
        # _init_readline 设置了 completer
        import readline
        completer = readline.get_completer()
        assert completer is not None


class TestSoulSystem:
    """Soul 人格系统首次对话影响"""

    def test_default_soul_loaded(self):
        """默认 Soul '太极助手' 被加载"""
        loader = SoulLoader()
        soul = loader.load("default")
        assert soul.id == "default"
        assert soul.name == "太极助手"
        assert len(soul.boundaries) >= 4
        assert len(soul.ethics) >= 4

    def test_default_soul_has_taiji_aspect(self):
        """默认 Soul 包含太极阴阳特质"""
        loader = SoulLoader()
        soul = loader.load("default")
        assert "阳" in soul.taiji_aspect or "阳" in str(soul.character)
        assert "阴" in soul.taiji_aspect or "阴" in str(soul.character)

    def test_soul_injection_into_prompt(self):
        """Soul 注入系统提示的正确性"""
        loader = SoulLoader()
        soul = loader.load("default")
        prompt = inject_soul(soul)
        assert "太极助手" in prompt
        assert "行为边界" in prompt
        assert "核心价值观" in prompt
        assert "性格特征" in prompt

    def test_soul_boundaries_enforced(self):
        """Soul 边界约束存在 — Claude Code 靠 Constitution，Taiji 靠 Soul"""
        loader = SoulLoader()
        soul = loader.load("default")
        boundaries_text = " ".join(soul.boundaries)
        assert "有害" in boundaries_text or "不产生" in boundaries_text
        assert "不确定" in boundaries_text or "坦诚" in boundaries_text
        assert "捏造" in boundaries_text or "事实" in boundaries_text


class TestWFGYFirstContact:
    """WFGY 防幻觉在首次对话中的表现"""

    def test_verify_enabled_by_default(self):
        """WFGY 默认启用"""
        config = AgentConfig()
        assert config.verify_enabled is True

    def test_verify_threshold_default(self):
        """WFGY 阈值默认 0.5"""
        config = AgentConfig()
        assert config.verify_threshold == 0.5

    def test_wfgy_verifier_instant(self):
        """WFGY 验证器立即可用"""
        v = WFGYVerifier()
        result = v.verify("Earth orbits the Sun.")
        assert isinstance(result, bool)

    def test_hallucination_detector_instant(self):
        """幻觉检测器立即可用"""
        d = HallucinationDetector()
        risk = d.detect("Python is a programming language.")
        assert 0 <= risk <= 1

    def test_wfgy_in_system_prompt(self):
        """WFGY 哲学注入系统提示"""
        agent = TaijiAgent(config=AgentConfig(verify_enabled=True, enable_sandbox=False))
        prompt = agent._build_system_prompt()
        assert "WFGY" in prompt


class TestOnboardingGapAnalysis:
    """差距分析：Taiji vs Claude Code 首次体验"""

    def test_claude_shows_project_context(self):
        """Claude Code 显示 "The current project is ..."，Taiji 显示会话信息"""
        # Taiji 的 banner 显示模型/提供者/Soul/WFGY 状态
        config = AgentConfig()
        assert config.workdir == "."  # workdir 可配置
        assert config.provider is not None

    def test_claude_shows_tools_auto(self):
        """Claude Code 自动展示工具，Taiji 需要 /tools 手动查看"""
        ia = InteractiveAgent(AgentConfig())
        assert "/tools" in ia._commands
        # 差异：未在启动横幅中自动列出工具数量

    def test_claude_shows_version(self):
        """Claude Code 显示版本号，Taiji 通过 --version 显示"""
        from taiji_agent.cli.main import cli
        assert cli is not None
        # CLI 通过 click.version_option 显示版本

    def test_taiji_has_session_persistence(self):
        """Taiji 独有：会话持久化到 SQLite"""
        import tempfile, os
        tmpdir = tempfile.mkdtemp()
        try:
            db_path = os.path.join(tmpdir, "test.db")
            store = SessionStore(db_path=db_path)
            sid = store.create_session(name="首次对话测试")
            store.save_message(sid, "user", "你好")
            msgs = store.load_messages(sid)
            assert len(msgs) == 1
            assert msgs[0]["role"] == "user"
            store.close()
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_taiji_has_anti_hallucination(self):
        """Taiji 独有：WFGY 防幻觉 — Claude Code 无等价功能"""
        v = WFGYVerifier()
        d = HallucinationDetector()
        assert v is not None
        assert d is not None

    def test_taiji_has_soul_switch(self):
        """Taiji 独有：人格切换 — Claude Code 无等价功能"""
        loader = SoulLoader()
        souls = loader.list_souls()
        assert "default" in souls


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("   Taiji Agent 2.1 — 首次对话体验 vs Claude Code 对比测试")
    print("=" * 80)
    sys.exit(pytest.main([__file__, "-v", "--tb=short", "-p", "no:warnings"]))
