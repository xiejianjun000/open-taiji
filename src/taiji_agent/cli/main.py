"""
小佳 CLI — 命令入口 + 独立命令行工具
会话管理和 TUI 交互已合并到 taiji_agent.cli.tui
"""

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

import click
from dotenv import load_dotenv, find_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

load_dotenv(find_dotenv(usecwd=True))

from taiji_agent.agent.engine import AgentConfig, TaijiAgent
from taiji_agent.memory import SessionMemory
from taiji_agent.souls import SoulLoader
from taiji_agent.tools import registry
from taiji_agent.taiji_verify import HallucinationDetector, WFGYVerifier
from taiji_agent.cli.tui import SessionStore, get_session_store, HermesTUI, run_tui

# 向后兼容别名（旧测试/代码引用 InteractiveAgent）
InteractiveAgent = HermesTUI

console = Console()


# ══════════════════════════════════════════════════════════════
# 配置加载 & 单次执行
# ══════════════════════════════════════════════════════════════

def load_config() -> AgentConfig:
    config = AgentConfig()
    config.api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY")
    config.base_url = os.getenv("ANTHROPIC_BASE_URL") or os.getenv("TAIJI_AGENT_BASE_URL")
    config.provider = os.getenv("TAIJI_AGENT_PROVIDER", "anthropic")
    config.model = os.getenv("TAIJI_AGENT_MODEL", "deepseek-v4-pro")
    config.workdir = os.getenv("TAIJI_AGENT_WORKDIR", ".")
    config.verify_enabled = os.getenv("TAIJI_AGENT_VERIFY", "true").lower() == "true"
    return config


async def run_agent(task: str, config: AgentConfig, stream: bool = False):
    agent = TaijiAgent(config=config)
    if stream:
        console.print(Panel("[bold blue]小佳[/bold blue] 启动中..."))
        full_response = ""
        async for chunk in agent.stream_run(task):
            s = str(chunk)
            # 跳过工具调用信号（单次执行模式简化输出）
            if s.startswith("__TOOL_CALL__:") or s.startswith("__TOOL_RESULT__:"):
                continue
            if s.startswith("[") and ("已自动停止" in s or "⚠" in s):
                continue
            console.print(s, end="")
            full_response += s
        console.print()
        if config.verify_enabled:
            risk = agent.hallucination_detector.detect(full_response)
            if risk > 0.3:
                console.print(f"[yellow][Taiji Verify 幻觉风险: {risk:.1%}][/yellow]")
    else:
        console.print(Panel("[bold blue]小佳[/bold blue] 思考中..."))
        result = await agent.run(task)
        if result.status.value == "completed":
            console.print(Panel(f"[green]✓ 完成 ({result.iterations} 次迭代)[/green]\n\n{result.content}"))
        else:
            console.print(Panel(f"[yellow]⚠ {result.error}[/yellow]"))


# ══════════════════════════════════════════════════════════════
# CLI 命令组
# ══════════════════════════════════════════════════════════════

@click.group()
@click.version_option(version="2.1.0")
def cli():
    """小佳 2.1 — 融合 Hermes Agent + Taiji Verify + 交互式对话"""


@cli.command()
@click.argument("task", required=False)
@click.option("--provider", "-p", default="anthropic", help="LLM Provider")
@click.option("--model", "-m", default="deepseek-v4-pro", help="Model name")
@click.option("--api-key", "-k", default=None, help="API Key")
@click.option("--soul", "-s", default="default", help="Soul to use")
@click.option("--no-verify", is_flag=True, help="Disable Taiji Verify")
@click.option("--stream/--no-stream", default=True, help="Stream response")
@click.option("--session", default=None, help="恢复指定会话ID")
def interactive(task, provider, model, api_key, soul, no_verify, stream, session):
    """
    进入交互式对话模式（完整版 HermesTUI）

    不提供 TASK 参数进入交互模式，提供则单次执行。
    """
    # 初始化日志
    log_level = os.getenv("TAIJI_LOG_LEVEL", "DEBUG")
    try:
        from taiji_agent.logging import setup_logging
        setup_logging(level=log_level)
    except ImportError:
        pass

    config = AgentConfig(
        provider=provider, model=model, api_key=api_key,
        soul=soul, verify_enabled=not no_verify, stream=stream,
    )
    if task:
        asyncio.run(run_agent(task, config, stream))
    else:
        app = HermesTUI(config)
        asyncio.run(app.start(session_id=session))


@cli.command()
@click.option("--provider", "-p", default="anthropic", help="LLM Provider")
@click.option("--model", "-m", default="deepseek-v4-pro", help="Model name")
def tui(provider, model):
    """启动小佳终端对话窗口（精简入口，完整版同 interactive）"""
    config = AgentConfig(
        provider=provider,
        model=model,
        api_key=os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("ANTHROPIC_BASE_URL") or os.getenv("TAIJI_AGENT_BASE_URL"),
        stream=True,
    )
    run_tui(config)


@cli.command()
def init():
    """初始化 Taiji Agent 工作环境"""
    home = Path.home() / ".taiji_agent"
    for d in ["souls", "memory", "skills", "logs", "exports"]:
        (home / d).mkdir(parents=True, exist_ok=True)

    config_file = home / "config.yaml"
    if not config_file.exists():
        config_file.write_text("""# Taiji Agent 配置
provider: anthropic
model: deepseek-v4-pro
soul: default
verify_enabled: true
verify_threshold: 0.5
max_iterations: 25
stream: true
""")
    store = SessionStore()
    store.close()

    console.print("[green]✓ Taiji Agent 初始化完成[/green]")
    console.print(f"配置目录: {home}")
    console.print(f"会话数据库: {home / 'sessions.db'}")
    console.print()
    console.print("[bold]快速开始:[/bold]")
    console.print("  taiji          # 进入交互式对话模式")
    console.print('  taiji "你好"   # 单次对话')


@cli.command()
def souls():
    """列出可用的 Souls (人格)"""
    loader = SoulLoader()
    available = loader.list_souls()
    console.print("[bold]可用的 Souls:[/bold]")
    for soul_id in available:
        soul = loader.load(soul_id)
        console.print(f"  • {soul_id}: {soul.name}")


@cli.command()
def tools():
    """列出可用工具"""
    tool_list = registry.list_tools()
    table = Table(title=f"可用工具 ({len(tool_list)})")
    table.add_column("工具", style="cyan", width=18)
    table.add_column("描述", style="green", width=60)
    for t in sorted(tool_list):
        schema = registry.get_schema(t)
        desc = schema.description[:80] if schema else "N/A"
        table.add_row(t, desc)
    console.print(table)


@cli.command()
@click.option("--limit", "-n", default=10, help="显示条数")
def sessions(limit):
    """查看保存的会话列表"""
    store = SessionStore()
    sessions_list = store.list_sessions(limit=limit)
    store.close()
    if not sessions_list:
        console.print("[dim]暂无保存的会话[/dim]")
        return
    table = Table(title=f"会话列表 ({len(sessions_list)})")
    table.add_column("ID", style="cyan", width=18)
    table.add_column("名称", style="green", width=25)
    table.add_column("模型", style="blue", width=28)
    table.add_column("消息", justify="right")
    table.add_column("更新时间")
    for s in sessions_list:
        table.add_row(s["id"][:16], s["name"], s["model"], str(s["message_count"]), (s["updated_at"] or "")[:19])
    console.print(table)


@cli.command()
@click.argument("session_id", required=False)
def memory(session_id):
    """查看会话记录或内存记忆"""
    if session_id:
        store = SessionStore()
        msgs = store.load_messages(session_id, limit=50)
        store.close()
        console.print(f"[bold]会话 {session_id} ({len(msgs)} 条):[/bold]")
        for msg in msgs:
            role_icon = "👤" if msg["role"] == "user" else "🤖"
            console.print(f"{role_icon} {msg['content'][:200]}...")
    else:
        mem = SessionMemory()
        console.print("[bold]短期记忆:[/bold]")
        items = list(mem._memory.items())[:10]
        if items:
            for key, entry in items:
                console.print(f"  [{key}] {entry['value'][:100]}...")
        else:
            console.print("  [dim](空)[/dim]")


@cli.command()
@click.option("--text", "-t", required=True, help="要检测的文本")
@click.option("--verbose", "-v", is_flag=True, help="详细输出")
def verify(text, verbose):
    """Taiji Verify 验证文本"""
    verifier = WFGYVerifier()
    detector = HallucinationDetector()
    passed = verifier.verify(text)
    risk = detector.detect(text)

    console.print("[bold]Taiji Verify 验证结果:[/bold]")
    status = "✓" if passed else "✗"
    risk_color = "green" if risk < 0.3 else ("yellow" if risk < 0.5 else "red")
    console.print(f"  通过: {status}")
    console.print(f"  幻觉风险: [{risk_color}]{risk:.1%}[/{risk_color}]")

    if verbose:
        result = verifier.verify_detailed(text)
        if result.violations:
            console.print("[yellow]违规项:[/yellow]")
            for v in result.violations:
                console.print(f"  • {v}")
        levels = [
            (0.3, "green", "安全 — 输出可信度高"),
            (0.5, "yellow", "注意 — 建议人工复核"),
            (0.7, "red", "警告 — 存在明显幻觉风险"),
            (1.0, "bold red", "危险 — 强烈建议拦截"),
        ]
        for threshold, color, msg in levels:
            if risk < threshold:
                console.print(f"[{color}]{msg}[/{color}]")
                break


@cli.command()
@click.argument("session_id", required=False)
def export(session_id):
    """导出会话为 Markdown 文件"""
    store = SessionStore()
    if session_id:
        sessions_list = [{"id": session_id, "name": session_id}]
    else:
        sessions_list = store.list_sessions(limit=1)
    if not sessions_list:
        console.print("[red]无可用会话[/red]")
        store.close()
        return
    s = sessions_list[0]
    msgs = store.load_messages(s["id"])
    export_dir = Path.home() / ".taiji_agent" / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    export_path = export_dir / f"taiji-{s['id']}.md"

    with open(export_path, "w", encoding="utf-8") as f:
        f.write(f"# 小佳 会话导出\n\n")
        f.write(f"- 会话ID: {s['id']}\n")
        f.write(f"- 导出时间: {datetime.now().isoformat()}\n")
        f.write(f"- 消息数: {len(msgs)}\n\n---\n\n")
        for msg in msgs:
            role = "👤 用户" if msg["role"] == "user" else "🤖 小佳"
            f.write(f"### {role}\n\n{msg['content']}\n\n---\n\n")
    console.print(f"[green]✓ 已导出 {len(msgs)} 条消息到: {export_path}[/green]")
    store.close()


def main():
    """CLI 入口 — 默认进入交互模式（完整版 HermesTUI）"""
    if len(sys.argv) == 1:
        cli.main(["interactive"])
    else:
        cli()


if __name__ == "__main__":
    main()
