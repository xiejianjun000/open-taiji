"""
小佳 · Hermes 终端对话窗口 — 完整版 v2.1
融合：Hermes Banner + 会话管理(SQLite) + 20+命令 + readline补全 + 梦境系统
"""

import asyncio
import atexit
import json
import os
import readline
import shlex
import signal
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from taiji_agent.agent.engine import AgentConfig, TaijiAgent, TaskStatus
from taiji_agent.memory import SessionMemory

console = Console()

# ══════════════════════════════════════════════════════════════
# 会话持久化层 (SQLite)
# ══════════════════════════════════════════════════════════════

class SessionStore:
    """会话持久化存储 — 基于 SQLite"""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = Path.home() / ".taiji_agent" / "sessions.db"
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = str(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self._init_tables()

    def _init_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                model TEXT DEFAULT 'deepseek-v4-pro',
                provider TEXT DEFAULT 'anthropic',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                message_count INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                tool_calls TEXT,
                tool_call_id TEXT,
                token_estimate INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS session_meta (
                session_id TEXT PRIMARY KEY,
                verify_blocked INTEGER DEFAULT 0,
                verify_warnings INTEGER DEFAULT 0,
                tools_used TEXT DEFAULT '[]',
                summary TEXT DEFAULT '',
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at DESC);
        """)
        self.conn.commit()
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")

    def create_session(self, name: str = "", model: str = "deepseek-v4-pro", provider: str = "anthropic") -> str:
        sid = datetime.now().strftime("%Y%m%d-%H%M%S-") + os.urandom(4).hex()
        name = name or f"会话 {sid[:15]}"
        self.conn.execute(
            "INSERT INTO sessions (id, name, model, provider) VALUES (?, ?, ?, ?)",
            (sid, name, model, provider),
        )
        self.conn.commit()
        return sid

    def list_sessions(self, limit: int = 20) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id, name, model, provider, created_at, updated_at, message_count, total_tokens "
            "FROM sessions ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        cols = ["id", "name", "model", "provider", "created_at", "updated_at", "message_count", "total_tokens"]
        return [dict(zip(cols, r)) for r in rows]

    def save_message(self, session_id: str, role: str, content: str, tool_calls=None, tool_call_id=None):
        token_est = len(content) // 4 if content else 0
        self.conn.execute(
            "INSERT INTO messages (session_id, role, content, tool_calls, tool_call_id, token_estimate) "
            "VALUES (?,?,?,?,?,?)",
            (session_id, role, content, json.dumps(tool_calls) if tool_calls else None, tool_call_id, token_est),
        )
        self.conn.execute(
            "UPDATE sessions SET updated_at=CURRENT_TIMESTAMP, message_count = message_count + 1, "
            "total_tokens = total_tokens + ? WHERE id=?",
            (token_est, session_id),
        )
        self.conn.commit()

    def load_messages(self, session_id: str, limit: int = 200) -> list[dict]:
        rows = self.conn.execute(
            "SELECT role, content, tool_calls, tool_call_id FROM messages "
            "WHERE session_id=? ORDER BY id ASC LIMIT ?",
            (session_id, limit),
        ).fetchall()
        msgs = []
        for r in rows:
            msg = {"role": r[0], "content": r[1]}
            if r[2]:
                msg["tool_calls"] = json.loads(r[2])
            if r[3]:
                msg["tool_call_id"] = r[3]
            msgs.append(msg)
        return msgs

    def update_meta(self, session_id: str, **kwargs):
        existing = self.conn.execute(
            "SELECT 1 FROM session_meta WHERE session_id=?", (session_id,)
        ).fetchone()
        if existing:
            sets = ", ".join(f"{k}=?" for k in kwargs)
            vals = list(kwargs.values()) + [session_id]
            self.conn.execute(f"UPDATE session_meta SET {sets} WHERE session_id=?", vals)
        else:
            keys = ", ".join(kwargs.keys())
            placeholders = ", ".join("?" for _ in kwargs)
            self.conn.execute(
                f"INSERT INTO session_meta (session_id, {keys}) VALUES (?, {placeholders})",
                [session_id] + list(kwargs.values()),
            )
        self.conn.commit()

    def get_meta(self, session_id: str) -> dict:
        row = self.conn.execute(
            "SELECT * FROM session_meta WHERE session_id=?", (session_id,)
        ).fetchone()
        if row:
            return dict(zip(["session_id", "verify_blocked", "verify_warnings", "tools_used", "summary"], row))
        return {}

    def delete_session(self, session_id: str):
        self.conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
        self.conn.commit()

    def close(self):
        self.conn.close()


_session_store: Optional[SessionStore] = None

def get_session_store() -> SessionStore:
    global _session_store
    if _session_store is None:
        _session_store = SessionStore()
        atexit.register(_session_store.close)
    return _session_store


# ══════════════════════════════════════════════════════════════
# 工具图标 & 辅助函数
# ══════════════════════════════════════════════════════════════

TOOL_ICONS = {
    "shell": "💻", "file_read": "📄", "file_write": "✏️",
    "file_list": "📂", "file_search": "🔍", "web_search": "🌐",
    "web_extract": "📰", "memory_save": "🧠", "memory_search": "🔎",
    "execute_code": "🐍", "todo_list": "📋", "todo_add": "➕",
    "todo_done": "✅", "skills_list": "🎯", "skill_view": "📖",
    "skill_manage": "⚙️", "cronjob": "⏰", "git_status": "📊",
    "git_log": "📜",
}

def fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.0f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


# ══════════════════════════════════════════════════════════════
# Banner 扫描函数
# ══════════════════════════════════════════════════════════════

def _scan_skills() -> dict:
    """扫描 ~/.taiji/skills/ 目录，返回技能统计（自动合并同系列分类）"""
    skills_dir = Path.home() / ".taiji" / "skills"
    raw_categories = {}
    total = 0

    if skills_dir.exists():
        for cat_dir in sorted(skills_dir.iterdir()):
            if not cat_dir.is_dir():
                continue
            skill_files = list(cat_dir.rglob("SKILL.md"))
            if skill_files:
                cat_name = cat_dir.name
                skill_names = []
                for sf in skill_files:
                    try:
                        content = sf.read_text(encoding="utf-8")
                        for line in content.split("\n")[:10]:
                            if line.startswith("name:"):
                                skill_names.append(line.split("name:")[1].strip())
                                break
                        else:
                            skill_names.append(sf.parent.name)
                    except Exception:
                        skill_names.append(sf.parent.name)
                raw_categories[cat_name] = skill_names
                total += len(skill_files)

    # 合并同系列分类
    merged = {}
    merge_groups = [
        ("coldsteel", [k for k in raw_categories if k.startswith("coldsteel")]),
        ("lark", [k for k in raw_categories if k.startswith("lark-")]),
    ]
    for group_name, keys in merge_groups:
        if len(keys) > 1:
            all_skills = []
            for k in keys:
                all_skills.extend(raw_categories.pop(k))
            merged[group_name] = all_skills
    merged.update(raw_categories)

    return {"categories": merged, "total": total}


def _scan_tools() -> dict:
    """扫描工具注册表，返回工具统计"""
    try:
        from taiji_agent.tools.registry import ToolRegistry
        registry = ToolRegistry()
        tool_names = sorted(registry._schemas.keys())
        return {"names": tool_names, "total": len(tool_names)}
    except Exception:
        return {"names": list(TOOL_ICONS.keys()), "total": len(TOOL_ICONS)}


def _build_banner(model_name: str) -> str:
    """构建 Hermes 风格的启动 banner"""
    tools = _scan_tools()
    skills = _scan_skills()
    width = min(console.width, 100)

    header = f" 小佳 v2.1.0 · {model_name} · anthropic "
    border_top = "╭" + "─" * (width - 2) + "╮"
    border_bot = "╰" + "─" * (width - 2) + "╯"

    lines = [border_top]

    # 标题
    pad = (width - 2 - len(header)) // 2
    lines.append("│" + " " * pad + header + " " * (width - 2 - pad - len(header)) + "│")

    # Tools
    lines.append("│" + " Available Tools ".center(width - 2) + "│")
    lines.append("│" + " " * (width - 2) + "│")
    tool_names = tools["names"]
    tool_line = ""
    for name in tool_names:
        candidate = tool_line + (" · " if tool_line else "") + name
        if len(candidate) > width - 6:
            lines.append("│  " + tool_line.ljust(width - 4) + "│")
            tool_line = name
        else:
            tool_line = candidate
    if tool_line:
        lines.append("│  " + tool_line.ljust(width - 4) + "│")
    lines.append("│" + " " * (width - 2) + "│")

    # MCP
    lines.append("│" + " MCP Servers ".center(width - 2) + "│")
    lines.append("│" + " " * (width - 2) + "│")
    lines.append("│  xhs (stdio) — 10 tool(s)".ljust(width - 2) + " │")
    lines.append("│" + " " * (width - 2) + "│")

    # Skills
    lines.append("│" + " Available Skills ".center(width - 2) + "│")
    lines.append("│" + " " * (width - 2) + "│")
    skill_cats = skills["categories"]
    MAX_LINES = 20
    cat_items = sorted(skill_cats.items(), key=lambda x: len(x[1]), reverse=True)
    for cat_name, skill_names in cat_items[:MAX_LINES]:
        count = len(skill_names)
        if count <= 2:
            names_str = ", ".join(skill_names)
        elif count <= 5:
            names_str = ", ".join(skill_names[:3]) + f", … ({count})"
        else:
            names_str = ", ".join(skill_names[:2]) + f", … ({count})"
        lines.append(f"│   {cat_name}: {names_str}".ljust(width - 2) + " │")
    if len(cat_items) > MAX_LINES:
        remaining = len(cat_items) - MAX_LINES
        lines.append(f"│   … and {remaining} more categories".ljust(width - 2) + " │")
    lines.append("│" + " " * (width - 2) + "│")

    # 底部摘要
    summary = f" {tools['total']} tools · {skills['total']} skills · 1 MCP server · /help 查看命令 "
    pad = (width - 2 - len(summary)) // 2
    lines.append("│" + " " * pad + summary + " " * (width - 2 - pad - len(summary)) + "│")
    lines.append(border_bot)

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
# HermesTUI — 完整交互式终端界面
# ══════════════════════════════════════════════════════════════

class HermesTUI:
    """完整版终端对话界面 — 会话管理 + 命令系统 + readline补全"""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.agent: Optional[TaijiAgent] = None
        self.store = get_session_store()
        self.session_id: Optional[str] = None
        self._stop_flag = False
        self._dream_engine = None
        self.bot_name = "小佳"
        self.user_name = "你"
        self._user_introduced = False
        self._init_readline()

    # ── readline ──

    def _init_readline(self):
        hist_file = Path.home() / ".taiji_agent" / ".history"
        hist_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            readline.read_history_file(str(hist_file))
        except (FileNotFoundError, PermissionError, OSError):
            pass
        readline.set_history_length(1000)
        atexit.register(lambda: readline.write_history_file(str(hist_file)))

        self._commands = [
            "/help", "/new", "/sessions", "/switch", "/delete",
            "/history", "/clear", "/compact", "/model", "/soul",
            "/tools", "/verify", "/export", "/exit", "/quit", "/q",
            "/skills", "/cron", "/dream", "/providers", "/logs",
        ]

        def completer(text, state):
            options = [c for c in self._commands if c.startswith(text)]
            if state < len(options):
                return options[state]
            return None

        readline.set_completer(completer)
        readline.parse_and_bind("tab: complete")

    # ── 初始化 & 启动 ──

    async def _init_agent(self):
        self.agent = TaijiAgent(config=self.config)

    async def start(self, session_id: Optional[str] = None):
        await self._init_agent()

        if session_id:
            sessions = self.store.list_sessions(limit=100)
            matched = [s for s in sessions if s["id"].startswith(session_id)]
            if matched:
                self.session_id = matched[0]["id"]
                self._restore_context()
            else:
                self.session_id = self.store.create_session(model=self.config.model)
        else:
            self.session_id = self.store.create_session(model=self.config.model)

        # 加载持久化名字
        try:
            from taiji_agent.memory.session import SessionMemory
            mem = SessionMemory()
            saved_bot = mem.get("bot_name")
            saved_user = mem.get("user_name")
            if saved_bot:
                self.bot_name = saved_bot
            if saved_user:
                self.user_name = saved_user
                self._user_introduced = True
        except Exception:
            pass

        # Banner
        banner = _build_banner(self.config.model)
        console.print(banner, style="dim")
        console.print()

        # 问候
        console.print(f"[bold cyan][{self.bot_name}][/bold cyan] 就绪。直接说需求。")
        console.print()

        signal.signal(signal.SIGINT, self._handle_sigint)

        # 梦境系统
        try:
            from taiji_agent.dream.engine import DreamEngine, DreamConfig
            dream_config = DreamConfig(
                enabled=os.getenv("TAIJI_DREAM_ENABLED", "true").lower() == "true",
                interval_hours=int(os.getenv("TAIJI_DREAM_INTERVAL_HOURS", "4")),
                deep_enabled=os.getenv("TAIJI_DREAM_DEEP_ENABLED", "true").lower() == "true",
            )
            if dream_config.enabled:
                self._dream_engine = DreamEngine(config=dream_config)
                self._dream_engine.start()
        except Exception:
            pass

        await self._chat_loop()

    def _handle_sigint(self, signum, frame):
        console.print("\n[yellow]👋 Ctrl+C 退出[/yellow]")
        self._stop_flag = True
        sys.exit(0)

    def _restore_context(self):
        msgs = self.store.load_messages(self.session_id)
        if self.agent and msgs:
            from taiji_agent.agent.engine import Message
            restored = []
            for m in msgs:
                restored.append(Message(
                    role=m["role"],
                    content=m["content"],
                    tool_calls=m.get("tool_calls"),
                    tool_call_id=m.get("tool_call_id"),
                ))
            self.agent.messages = restored
            console.print(f"[dim]已恢复 {len(restored)} 条历史消息[/dim]")

    # ── 主循环 ──

    async def _chat_loop(self):
        while not self._stop_flag:
            try:
                if self._user_introduced:
                    user_label = self.user_name
                else:
                    user_label = "你"
                user_input = input(f"\n[{user_label}] → ").strip()
            except EOFError:
                console.print("\n[yellow]👋 再见！[/yellow]")
                break

            if not user_input:
                continue

            if user_input.startswith("/"):
                self._stop_flag = await self._handle_command(user_input)
                if self._stop_flag:
                    break
                continue

            await self._process_message(user_input)

    # ── 名字检测 ──

    def _detect_bot_name(self, text: str) -> Optional[str]:
        import re
        patterns = [
            r'以后(?:你)?就?叫\s*["\']?(\S+?)["\']?\s*(?:吧|好了|$|，|。)',
            r'以后我叫你\s*["\']?(\S+?)["\']?\s*(?:吧|好了|$|，|。)',
            r'给你起(?:个)?名(?:字)?叫\s*["\']?(\S+?)["\']?\s*(?:吧|好了|$|，|。)',
            r'叫你\s*["\']?(\S+?)["\']?\s*(?:吧|好了|$)',
            r'你(?:的)?名字(?:就)?(?:叫|是)\s*["\']?(\S+?)["\']?\s*(?:吧|好了|$|，|。)',
            r'就叫\s*["\']?(\S+?)["\']?\s*(?:吧|好了|$)',
        ]
        for pat in patterns:
            m = re.search(pat, text)
            if m:
                name = m.group(1).strip().rstrip('，。！？、')
                if 2 <= len(name) <= 10:
                    return name
        return None

    def _detect_user_name(self, text: str) -> Optional[str]:
        import re
        patterns = [
            r'(?:我的名字(?:是|叫)|我叫|我是)\s*(\S+)',
            r'叫我\s*(\S+)',
            r'你可以叫我\s*(\S+)',
            r'就叫我\s*(\S+)',
        ]
        for pat in patterns:
            m = re.search(pat, text)
            if m:
                raw = m.group(1)
                name = re.sub(r'[,，。！!\.\s].*$', '', raw)
                name = re.sub(r'(吧|好了|就可以|就行|即可|吧啦)$', '', name)
                name = name.strip().rstrip('，。！？、的也啦')
                if 2 <= len(name) <= 10 and name not in ('什么', '谁', '哪个', '怎么', '你叫什么'):
                    return name
        return None

    # ── 消息处理 ──

    async def _process_message(self, user_input: str):
        self.store.save_message(self.session_id, "user", user_input)

        if self.agent is None:
            await self._init_agent()

        # 检测 bot 起名
        detected_bot = self._detect_bot_name(user_input)
        if detected_bot and detected_bot != self.bot_name:
            self.bot_name = detected_bot
            console.print(f"[dim]  ✓ 记住了，以后我就叫 {detected_bot}[/dim]")
            try:
                from taiji_agent.memory.session import SessionMemory
                mem = SessionMemory()
                mem.save("bot_name", detected_bot)
            except Exception:
                pass

        # 检测用户自我介绍
        if not self._user_introduced:
            detected_user = self._detect_user_name(user_input)
            if detected_user:
                self.user_name = detected_user
                self._user_introduced = True
                console.print(f"[dim]  ✓ 很高兴认识你，{detected_user}！[/dim]")
                try:
                    from taiji_agent.memory.session import SessionMemory
                    mem = SessionMemory()
                    mem.save("user_name", detected_user)
                except Exception:
                    pass

        full_response = ""
        tool_count = 0
        try:
            async for chunk in self.agent.stream_run(user_input):
                if not chunk:
                    continue

                s = str(chunk)

                if s.startswith("__TOOL_CALL__:"):
                    tool_count += 1
                    self._render_tool_call(s)
                    continue

                if s.startswith("__TOOL_RESULT__:"):
                    self._render_tool_result(s)
                    continue

                if s.startswith("[") and ("已自动停止" in s or "⚠" in s or "连续" in s):
                    console.print(f"[yellow]{s}[/yellow]")
                    continue

                # 过滤 TaijiVerifyPro 信号
                if "TaijiVerifyPro" in s or "拦截" in s:
                    continue

                # 流式输出文本（使用 Rich console.print 保证一致性）
                console.print(s, end="")
                full_response += s

            console.print()
            if tool_count > 0:
                console.print(f"[dim]  ── {tool_count} tool(s) used ──[/dim]")
        except Exception as e:
            console.print(f"\n[red]错误: {e}[/red]")
            return

        # Taiji Verify
        if self.config.verify_enabled and self.agent:
            risk = self.agent.hallucination_detector.detect(full_response)
            if risk > 0.3:
                color = "red" if risk > 0.5 else "yellow"
                console.print(f"[{color}][Taiji Verify 幻觉风险: {risk:.1%}][/{color}]")
                self.store.update_meta(self.session_id, verify_warnings=1)

        self.store.save_message(self.session_id, "assistant", full_response)
        self.store.update_meta(
            self.session_id,
            tools_used=json.dumps(self.agent.tools.get_used_tools() if self.agent else []),
        )

        # 后台审查
        if self.agent and full_response:
            self._trigger_background_review(user_input, full_response)

    def _trigger_background_review(self, user_input: str, response: str):
        try:
            from taiji_agent.review.engine import BackgroundReviewEngine
            engine = BackgroundReviewEngine()
            review_mem, review_skills = engine.should_review(
                getattr(self.agent, 'messages', [])
            )
            if review_mem or review_skills:
                messages = getattr(self.agent, 'messages', [])
                engine.spawn_review(messages, review_mem, review_skills)
        except ImportError:
            pass

    # ── 命令分发 ──

    async def _handle_command(self, cmd_line: str) -> bool:
        parts = shlex.split(cmd_line)
        cmd = parts[0].lower()
        args = parts[1:]

        handlers = {
            "/exit": lambda: True,
            "/quit": lambda: True,
            "/q": lambda: True,
            "/help": lambda: self._show_help(),
            "/new": lambda: asyncio.create_task(self._cmd_new(args)),
            "/sessions": lambda: self._cmd_list_sessions(),
            "/switch": lambda: asyncio.create_task(self._cmd_switch(args)),
            "/delete": lambda: self._cmd_delete(args),
            "/history": lambda: self._cmd_history(),
            "/clear": lambda: self._cmd_clear(),
            "/compact": lambda: self._cmd_compact(),
            "/model": lambda: self._cmd_model(args),
            "/soul": lambda: self._cmd_soul(args),
            "/tools": lambda: self._cmd_tools(),
            "/verify": lambda: self._cmd_verify(args),
            "/export": lambda: self._cmd_export(),
            "/skills": lambda: self._cmd_skills(args),
            "/cron": lambda: self._cmd_cron(),
            "/dream": lambda: self._cmd_dream(args),
            "/providers": lambda: self._cmd_providers(),
            "/logs": lambda: self._cmd_logs(args),
        }

        if cmd in handlers:
            result = handlers[cmd]()
            # exit/quit/q return True (stop flag), others return None/False
            if isinstance(result, bool) and result:
                console.print("[yellow]👋 再见！[/yellow]")
                return True
            return False
        else:
            console.print(f"[red]未知命令: {cmd}。输入 /help 查看帮助[/red]")
            return False

    # ── /help ──

    def _show_help(self):
        table = Table(title="小佳 交互命令", show_header=True, header_style="bold cyan")
        table.add_column("命令", style="cyan", width=18)
        table.add_column("说明", style="green", width=30)
        table.add_column("示例", style="dim", width=25)

        for cmd, desc, ex in [
            ("/help", "显示帮助信息", "/help"),
            ("/new [名称]", "创建新会话", "/new 环评项目分析"),
            ("/sessions", "列出所有保存的会话", "/sessions"),
            ("/switch <ID>", "切换到指定会话", "/switch 20260517"),
            ("/delete <ID>", "删除指定会话", "/delete 20260517-001"),
            ("/history", "查看当前会话对话历史", "/history"),
            ("/clear", "清除当前会话上下文", "/clear"),
            ("/compact", "压缩上下文（保留摘要）", "/compact"),
            ("/model <name>", "切换模型", "/model deepseek-v4-pro"),
            ("/soul <name>", "切换人格", "/soul default"),
            ("/tools", "列出所有可用工具", "/tools"),
            ("/verify [on|off]", "开关 Taiji Verify", "/verify off"),
            ("/export", "导出当前会话为 Markdown", "/export"),
            ("/skills [list|create]", "管理技能市场", "/skills list"),
            ("/cron", "查看定时任务状态", "/cron"),
            ("/dream", "手动触发梦境消化", "/dream"),
            ("/providers", "列出可用模型提供商", "/providers"),
            ("/logs [行数]", "查看最近日志（默认50行）", "/logs 100"),
            ("/exit, /quit, /q", "退出程序", "/exit"),
        ]:
            table.add_row(cmd, desc, ex)
        console.print(table)

    # ── /new ──

    async def _cmd_new(self, args):
        name = args[0] if args else ""
        self.session_id = self.store.create_session(name=name, model=self.config.model)
        if self.agent:
            self.agent.messages = []
        console.print(f"[green]✓ 新会话已创建: {self.session_id}[/green]")

    # ── /sessions ──

    def _cmd_list_sessions(self):
        sessions = self.store.list_sessions()
        if not sessions:
            console.print("[dim]暂无保存的会话[/dim]")
            return
        table = Table(title=f"会话列表 ({len(sessions)})", show_header=True)
        table.add_column("ID", style="cyan", width=18)
        table.add_column("名称", style="green", width=25)
        table.add_column("模型", style="blue", width=28)
        table.add_column("消息", justify="right", width=6)
        table.add_column("更新时间", width=20)
        for s in sessions:
            marker = " ←" if s["id"] == self.session_id else ""
            table.add_row(
                s["id"][:16] + marker,
                s["name"],
                s["model"],
                str(s["message_count"]),
                (s["updated_at"] or s["created_at"] or "")[:19],
            )
        console.print(table)

    # ── /switch ──

    async def _cmd_switch(self, args):
        if not args:
            console.print("[red]用法: /switch <会话ID前缀>[/red]")
            return
        prefix = args[0]
        sessions = self.store.list_sessions(limit=100)
        matched = [s for s in sessions if s["id"].startswith(prefix)]
        if matched:
            self.session_id = matched[0]["id"]
            self._restore_context()
            console.print(f"[green]✓ 已切换到: {self.session_id} ({matched[0]['name']})[/green]")
        else:
            console.print(f"[red]未找到匹配的会话: {prefix}[/red]")

    # ── /delete ──

    def _cmd_delete(self, args):
        if not args:
            console.print("[red]用法: /delete <会话ID前缀>[/red]")
            return
        prefix = args[0]
        sessions = self.store.list_sessions(limit=100)
        matched = [s for s in sessions if s["id"].startswith(prefix)]
        if matched:
            self.store.delete_session(matched[0]["id"])
            if self.session_id == matched[0]["id"]:
                self.session_id = None
            console.print(f"[green]✓ 已删除会话: {matched[0]['id']}[/green]")
        else:
            console.print(f"[red]未找到匹配的会话: {prefix}[/red]")

    # ── /history ──

    def _cmd_history(self):
        if not self.session_id:
            console.print("[red]无活跃会话[/red]")
            return
        msgs = self.store.load_messages(self.session_id, limit=30)
        if not msgs:
            console.print("[dim]暂无对话历史[/dim]")
            return
        for i, msg in enumerate(msgs, 1):
            role_color = "cyan" if msg["role"] == "user" else "green"
            role_icon = "👤" if msg["role"] == "user" else "🤖"
            content_preview = msg["content"][:150].replace("\n", " ")
            console.print(f"[{role_color}]{i}. {role_icon} {content_preview}...[/{role_color}]")

    # ── /clear ──

    def _cmd_clear(self):
        if self.agent:
            self.agent.messages = []
        console.print("[yellow]✓ 上下文已清除（会话消息仍保留在数据库中）[/yellow]")

    # ── /compact ──

    def _cmd_compact(self):
        """压缩上下文 — 优先 ContextCompressor，回退手动压缩"""
        if not self.agent or not self.agent.messages:
            console.print("[yellow]无活跃上下文可压缩[/yellow]")
            return

        msgs = self.agent.messages

        # 优先 ContextCompressor
        try:
            from taiji_agent.context.compressor import ContextCompressor
            compressor = ContextCompressor()
            old_len = len(msgs)
            self.agent.messages = compressor.compress(msgs)
            new_len = len(self.agent.messages)
            console.print(f"[dim]上下文已压缩: {old_len} → {new_len} 条 ({compressor.compression_count}次压缩)[/dim]")
            return
        except ImportError:
            pass

        # 手动压缩
        if len(msgs) <= 4:
            console.print(f"[dim]上下文仅 {len(msgs)} 条，无需压缩[/dim]")
            return

        system_msgs = [m for m in msgs if hasattr(m, 'role') and m.role == "system"]
        recent = msgs[-6:]

        old_msgs = [m for m in msgs if m not in recent and m not in system_msgs]
        summary_parts = []
        for m in old_msgs:
            content = getattr(m, 'content', '') or ''
            if content and len(content) > 10:
                summary_parts.append(f"[{getattr(m, 'role', '?')}] {content[:80]}...")

        if summary_parts:
            from taiji_agent.agent.engine import Message
            summary = "## 历史对话摘要\n" + "\n".join(summary_parts[-20:])
            self.agent.messages = system_msgs + [
                Message(role="user", content="(前文摘要)"),
                Message(role="assistant", content=summary),
            ] + [m for m in recent if getattr(m, 'role', '') != 'system']

        before = len(msgs)
        after = len(self.agent.messages)
        console.print(f"[green]✓ 上下文已压缩: {before} 条 → {after} 条[/green]")

    # ── /model ──

    def _cmd_model(self, args):
        if not args:
            console.print(f"当前模型: [cyan]{self.config.model}[/cyan]")
            return
        self.config.model = args[0]
        console.print(f"[green]✓ 已切换模型: {self.config.model}[/green]")

    # ── /soul ──

    def _cmd_soul(self, args):
        if not args:
            console.print(f"当前 Soul: [cyan]{self.config.soul}[/cyan]")
            return
        self.config.soul = args[0]
        console.print(f"[green]✓ 已切换 Soul: {self.config.soul}[/green]")

    # ── /tools ──

    def _cmd_tools(self):
        from taiji_agent.tools import registry
        tools_list = registry.list_tools()
        table = Table(title=f"可用工具 ({len(tools_list)})", show_header=True)
        table.add_column("工具名", style="cyan", width=18)
        table.add_column("描述", style="green", width=55)
        for t in sorted(tools_list):
            schema = registry.get_schema(t)
            desc = schema.description[:70] if schema else "N/A"
            table.add_row(t, desc)
        console.print(table)

    # ── /verify ──

    def _cmd_verify(self, args):
        if not args:
            status = "✅ 启用" if self.config.verify_enabled else "❌ 禁用"
            console.print(f"Taiji Verify: {status}")
            return
        self.config.verify_enabled = args[0].lower() in ("on", "true", "1", "enable")
        status = "✅ 启用" if self.config.verify_enabled else "❌ 禁用"
        console.print(f"[green]✓ Taiji Verify: {status}[/green]")

    # ── /export ──

    def _cmd_export(self):
        if not self.session_id:
            console.print("[red]无活跃会话[/red]")
            return
        msgs = self.store.load_messages(self.session_id)
        export_dir = Path.home() / ".taiji_agent" / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        export_path = export_dir / f"taiji-{self.session_id}.md"

        with open(export_path, "w", encoding="utf-8") as f:
            f.write(f"# 小佳 会话导出\n\n")
            f.write(f"- 会话ID: {self.session_id}\n")
            f.write(f"- 模型: {self.config.model}\n")
            f.write(f"- 提供者: {self.config.provider}\n")
            f.write(f"- 导出时间: {datetime.now().isoformat()}\n")
            f.write(f"- 消息数: {len(msgs)}\n\n---\n\n")
            for msg in msgs:
                role = "👤 用户" if msg["role"] == "user" else "🤖 小佳"
                f.write(f"### {role}\n\n{msg['content']}\n\n---\n\n")

        console.print(f"[green]✓ 已导出 {len(msgs)} 条消息到: {export_path}[/green]")

    # ── /skills ──

    def _cmd_skills(self, args):
        try:
            from taiji_agent.skills import skills_list, SkillRegistry
            reg = SkillRegistry()
            if args and args[0] == "list":
                result = skills_list()
                data = json.loads(result)
                if data.get("success"):
                    console.print(f"[bold]技能市场 ({data.get('count', 0)} 个):[/bold]")
                    for s in data.get("skills", []):
                        cat = f"[{s.get('category', 'general')}]" if s.get("category") else ""
                        console.print(f"  • {cat} [cyan]{s['name']}[/cyan]: {s.get('description', '')[:80]}")
                else:
                    console.print(f"[yellow]{data.get('error', '')}[/yellow]")
            else:
                all_skills = reg.find_all_skills()
                console.print(f"[bold]已加载技能 ({len(all_skills)} 个):[/bold]")
                console.print("[dim]使用 /skills list 查看详情[/dim]")
                for s in sorted(all_skills, key=lambda x: x.get('name', '') or ''):
                    console.print(f"  • [cyan]{s.get('name', '?')}[/cyan]")
        except ImportError:
            console.print("[yellow]技能系统未启用[/yellow]")

    # ── /cron ──

    def _cmd_cron(self):
        try:
            from taiji_agent.cron.jobs import list_jobs
            jobs = list_jobs()
            if not jobs:
                console.print("[dim]无定时任务[/dim]")
            else:
                console.print(f"[bold]定时任务 ({len(jobs)}):[/bold]")
                for j in jobs:
                    status = "⏰" if j.get("enabled") else "⏸"
                    console.print(f"  {status} [{j['id'][:8]}] {j.get('name', '?')} | {j.get('schedule_display', '?')} | {j.get('state', '?')}")
        except ImportError:
            console.print("[yellow]定时任务系统未启用[/yellow]")

    # ── /dream ──

    def _cmd_dream(self, args=None):
        if args is None:
            args = []
        sub = args[0] if args else "status"

        try:
            from taiji_agent.dream.engine import DreamEngine, DreamType

            engine = self._dream_engine
            if engine is None:
                engine = DreamEngine()

            if sub == "trigger" or sub in ("deep", "light", "rem"):
                dtype = DreamType.DEEP
                if len(args) >= 2:
                    arg_type = args[1] if sub == "trigger" else sub
                    try:
                        dtype = DreamType(arg_type)
                    except ValueError:
                        console.print(f"[yellow]未知梦境类型: {arg_type}，使用 deep[/yellow]")
                engine.trigger_dream(dtype)
                console.print(f"[green]✓ 已触发 {dtype.value} 梦境...[/green]")
                console.print("[dim]梦境在后台运行，结果将自动保存[/dim]")
                console.print("[dim]使用 /dream results 查看产出[/dim]")

            elif sub == "results":
                self._show_dream_results()

            elif sub == "status":
                self._show_dream_status(engine)

            else:
                console.print(f"[red]未知子命令: {sub}。用法: /dream [status|trigger|results][/red]")

        except ImportError:
            console.print("[yellow]梦境系统未启用[/yellow]")

    def _show_dream_status(self, engine):
        from rich.table import Table as RTable

        running = "✅ 运行中" if (self._dream_engine and self._dream_engine._running) else "⏸ 未运行"

        table = RTable(title="🌙 梦境系统状态", show_header=True)
        table.add_column("项目", style="cyan", width=15)
        table.add_column("状态", style="green", width=40)

        table.add_row("运行状态", running)
        table.add_row("间隔", f"{engine.config.interval_hours} 小时")
        table.add_row("深度梦境", "✅ 启用" if engine.config.deep_enabled else "❌ 禁用")
        table.add_row("轻度梦境", "✅ 启用" if engine.config.light_enabled else "❌ 禁用")
        table.add_row("REM 梦境", "✅ 启用" if engine.config.rem_enabled else "❌ 禁用")

        last = engine._last_dream
        for dtype_key, label in [("deep", "深度"), ("light", "轻度"), ("rem", "REM")]:
            ts = last.get(dtype_key, 0)
            if ts > 0:
                dt_str = datetime.fromtimestamp(ts).strftime("%m-%d %H:%M")
                table.add_row(f"最近{label}梦境", dt_str)
            else:
                table.add_row(f"最近{label}梦境", "从未运行")

        console.print(table)

        jsonl = Path.home() / ".taiji" / "conversations.jsonl"
        sqlite_db = Path.home() / ".taiji_agent" / "sessions.db"
        mem_file = Path.home() / ".taiji" / "memory" / "dream_memories.jsonl"

        console.print()
        console.print("[dim]数据源:[/dim]")
        src = "JSONL" if jsonl.exists() else ("SQLite" if sqlite_db.exists() else "无")
        console.print(f"  [dim]会话来源: {src}[/dim]")
        if mem_file.exists():
            with open(mem_file) as f:
                lines = f.readlines()
            console.print(f"  [dim]梦境记忆: {len(lines)} 条[/dim]")
        else:
            console.print("  [dim]梦境记忆: 暂无[/dim]")

    def _show_dream_results(self):
        mem_file = Path.home() / ".taiji" / "memory" / "dream_memories.jsonl"
        profile_file = Path.home() / ".taiji" / "user_profile.json"

        if mem_file.exists():
            with open(mem_file) as f:
                lines = f.readlines()
            if lines:
                console.print(f"[bold]🌙 梦境记忆 ({len(lines)} 条):[/bold]")
                try:
                    import json as _json
                    for line in lines[-10:]:
                        mem = _json.loads(line)
                        ts = mem.get("timestamp", 0)
                        summary = mem.get("summary", "")[:100]
                        tags = mem.get("tags", [])
                        tag_str = " ".join(f"[#{t}]" for t in tags) if tags else ""
                        dt_str = ""
                        if ts:
                            dt_str = datetime.fromtimestamp(ts).strftime("%m-%d %H:%M")
                        console.print(f"  [dim]{dt_str}[/dim] {summary}{' ' + tag_str if tag_str else ''}")
                except Exception:
                    console.print(f"  [dim]{len(lines)} 条记录[/dim]")
            else:
                console.print("[dim]暂无梦境记忆[/dim]")
        else:
            console.print("[dim]暂无梦境记忆[/dim]")

        if profile_file.exists():
            try:
                import json as _json
                with open(profile_file) as f:
                    profile = _json.load(f)
                console.print()
                console.print("[bold]👤 用户画像:[/bold]")
                for k, v in profile.items():
                    console.print(f"  [dim]{k}:[/dim] {v}")
            except Exception:
                pass

    # ── /providers ──

    def _cmd_providers(self):
        try:
            from taiji_agent.providers.unified import get_available_chinese_models
            providers = get_available_chinese_models()
            console.print("[bold]可用模型提供商:[/bold]")
            for p in providers:
                console.print(f"  • [cyan]{p['name']}[/cyan] ({p['key']}) — {', '.join(p['models'][:3])}")
        except ImportError:
            console.print("[yellow]暂无可用提供商[/yellow]")

    # ── /logs ──

    def _cmd_logs(self, args):
        lines = 50
        if args:
            try:
                lines = int(args[0])
            except ValueError:
                pass
        try:
            from taiji_agent.logging import get_latest_logs
            log_content = get_latest_logs(lines)
            if log_content.strip():
                console.print(Syntax(log_content, "log", theme="monokai", line_numbers=True))
            else:
                console.print("[dim]日志为空[/dim]")
        except ImportError:
            console.print("[yellow]日志系统未启用[/yellow]")

    # ── 工具调用渲染 ──

    def _render_tool_call(self, raw: str):
        content = raw[len("__TOOL_CALL__:"):]
        if ";" in content:
            name, args_str = content.split(";", 1)
        else:
            name, args_str = content, "{}"

        icon = TOOL_ICONS.get(name, "🔧")

        detail = ""
        try:
            args = json.loads(args_str)
            for key in ("command", "path", "query", "pattern", "content", "text"):
                if key in args:
                    val = str(args[key])
                    detail = val[:70].replace("\n", " ")
                    if len(val) > 70:
                        detail += "..."
                    break
            if not detail:
                detail = str(args)[:70]
        except Exception:
            detail = args_str[:70]

        console.print(f"  {icon} [cyan]{name}[/cyan] → [dim]{detail}[/dim]")

    def _render_tool_result(self, raw: str):
        text = raw[len("__TOOL_RESULT__:"):]
        if not text.strip():
            return

        lines = text.strip().split("\n")
        preview_lines = []
        for line in lines[:2]:
            if len(line) > 100:
                line = line[:100] + "..."
            preview_lines.append(line)

        preview = " │ ".join(preview_lines)
        if len(lines) > 2:
            preview += f" ... ({len(lines)} lines)"

        console.print(f"  │ [dim]{preview}[/dim]")


def run_tui(config=None):
    """入口"""
    if config is None:
        from taiji_agent.agent.engine import AgentConfig
        config = AgentConfig(
            provider=os.getenv("TAIJI_AGENT_PROVIDER", "anthropic"),
            model=os.getenv("TAIJI_AGENT_MODEL", "deepseek-v4-pro"),
            api_key=os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("ANTHROPIC_BASE_URL") or os.getenv("TAIJI_AGENT_BASE_URL"),
            stream=True,
        )
    app = HermesTUI(config)
    asyncio.run(app.start())


if __name__ == "__main__":
    run_tui()
