#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
终端富文本渲染器 - 为 taiji-agent 提供类似 IDE 内置 AI Agent 的动态交互输出风格。
支持：
- 动态准备状态（带转圈或原地刷新）
- 工具调用计时和分层缩进
- 带边框的助手消息框
- 完全无额外依赖，仅使用标准库
"""

import sys
import time
import textwrap
from typing import Optional, Dict, Any, ContextManager
from contextlib import contextmanager


class TerminalRenderer:
    """终端渲染器，负责美化 agent 的交互输出"""

    def __init__(
        self,
        max_width: int = 100,
        indent_char: str = "  ┊ ",
        action_prefix: str = "  │ ",
        prepare_icon: str = "🔍",
        execute_icon_map: Optional[Dict[str, str]] = None,
        default_icon: str = "⚙️",
    ):
        """
        Args:
            max_width: 消息框的最大宽度（字符数）
            indent_char: 顶层缩进前缀（如准备阶段前）
            action_prefix: 子动作/工具调用前缀
            prepare_icon: 准备阶段显示的图标（可动态变化）
            execute_icon_map: 工具名 → 执行时图标的映射字典
            default_icon: 未映射工具时使用的默认图标
        """
        self.max_width = max_width
        self.indent = indent_char
        self.action_prefix = action_prefix
        self.prepare_icon = prepare_icon
        self.default_icon = default_icon

        # 图标映射（可扩展）
        if execute_icon_map is None:
            self.icon_map = {
                "search_files": "🔎",
                "recall": "🔍",
                "read_file": "📖",
                "terminal": "💻",
                "execute_code": "🐍",
                "run_tests": "🧪",
                "analyze": "📊",
                "write_file": "✏️",
                "list_dir": "📂",
                "find": "🔍",
                "git_status": "📌",
                "git_commit": "✅",
            }
        else:
            self.icon_map = execute_icon_map

        # 状态变量
        self._last_prepare_line = ""
        self._prepare_start_time: Optional[float] = None
        self._current_indent_level = 0   # 支持未来多级缩进

    def start_preparation(self, action_name: str, icon: Optional[str] = None) -> None:
        """
        开始一个动作的准备阶段，显示动态的 'preparing xxx…' 行。
        使用 '\r' 原地刷新，不会换行。
        """
        used_icon = icon or self.prepare_icon
        line = f"{self.indent}{used_icon} preparing {action_name}…"
        # 清空上一行残留
        if self._last_prepare_line:
            sys.stdout.write("\r" + " " * len(self._last_prepare_line) + "\r")
        sys.stdout.write(line)
        sys.stdout.flush()
        self._last_prepare_line = line
        self._prepare_start_time = time.perf_counter()

    def finish_action(
        self,
        action_name: str,
        detail: str = "",
        duration: Optional[float] = None,
        icon: Optional[str] = None,
    ) -> None:
        """
        结束当前动作，输出最终结果（带图标和耗时）。

        Args:
            action_name: 动作名称（如工具名）
            detail: 额外细节信息（如查询内容）
            duration: 耗时（秒），若为 None 则使用内部计时
            icon: 动作图标，若不提供则从 icon_map 中查找或使用默认图标
        """
        # 计算耗时
        if duration is None and self._prepare_start_time is not None:
            duration = time.perf_counter() - self._prepare_start_time
        time_str = f"{duration:.1f}s" if duration is not None else ""

        # 确定图标
        if icon is None:
            icon = self.icon_map.get(action_name, self.default_icon)

        # 构建最终行
        detail_part = f" {detail}" if detail else ""
        line = f"{self.action_prefix}{icon} {action_name}{detail_part} {time_str}".strip()
        # 覆盖之前的 preparing 行
        if self._last_prepare_line:
            sys.stdout.write("\r" + " " * len(self._last_prepare_line) + "\r")
        print(line)
        sys.stdout.flush()
        # 重置状态
        self._last_prepare_line = ""
        self._prepare_start_time = None

    def print_boxed_message(self, agent_name: str, content: str) -> None:
        """
        打印带边框的消息框，用于显示 AI 助手的完整回答。

        Args:
            agent_name: 智能体名称（如 "Taiji Agent"）
            content: 要显示的多行文本
        """
        # 确保宽度足够容纳名字
        header_len = len(agent_name) + 5  # "╭─ ⚕ " + name + " ─"
        if header_len > self.max_width:
            effective_width = header_len + 10
        else:
            effective_width = self.max_width

        # 顶部边框
        top = f"╭─ ⚙ {agent_name} ─" + "─" * (effective_width - len(agent_name) - 5) + "╮"
        bottom = "╰" + "─" * (effective_width - 2) + "╯"
        print(top)

        # 自动换行并加上左边框
        wrapper = textwrap.TextWrapper(width=effective_width - 4, replace_whitespace=False)
        lines = []
        for para in content.splitlines():
            if para.strip() == "":
                lines.append("")   # 保留空行
            else:
                lines.extend(wrapper.wrap(para))

        for line in lines:
            if line == "":
                print(f"│{' ' * (effective_width - 2)}│")
            else:
                print(f"│ {line:<{effective_width-4}} │")

        print(bottom)
        sys.stdout.flush()

    def clear_current_line(self) -> None:
        """清除当前行（用于异常恢复）"""
        if self._last_prepare_line:
            sys.stdout.write("\r" + " " * len(self._last_prepare_line) + "\r")
            self._last_prepare_line = ""

    @contextmanager
    def action_context(self, action_name: str, detail: str = "", icon: Optional[str] = None) -> ContextManager[None]:
        """
        上下文管理器，自动处理准备和完成。用法：
        with renderer.action_context("search_files", detail="*.py"):
            # 执行实际工作
            result = do_search()
        """
        self.start_preparation(action_name, icon=icon)
        try:
            yield
        finally:
            self.finish_action(action_name, detail=detail, icon=icon)


# 简单的使用示例（当直接运行此文件时）
if __name__ == "__main__":
    renderer = TerminalRenderer()

    # 模拟工具调用
    renderer.start_preparation("search_files")
    time.sleep(0.5)
    renderer.finish_action("search_files", detail="*.py", duration=0.5)

    renderer.start_preparation("read_file")
    time.sleep(0.2)
    renderer.finish_action("read_file", detail="/path/to/file.txt", duration=0.2)

    # 打印消息框
    renderer.print_boxed_message(
        "Taiji Agent",
        "这是智能体返回的一段回答。\n它可以包含多行文本，并且会自动换行，保持边框整齐。"
    )
