"""
日志基础设施 — 文件 + 控制台双通道，用于调试 Agent 行为

用法:
    from taiji_agent.logging import setup_logging
    setup_logging(level="DEBUG")  # 或 INFO, WARNING, ERROR
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

TAIJI_HOME = Path.home() / ".taiji"
LOG_DIR = TAIJI_HOME / "logs"
LOG_FILE = LOG_DIR / "taiji-agent.log"

_logging_initialized = False


def setup_logging(
    level: str = "INFO",
    log_file: Optional[Path] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
    console: bool = True,
):
    """
    初始化日志系统

    - 文件日志: ~/.taiji/logs/taiji-agent.log (自动轮转, 10MB x 5个备份)
    - 控制台日志: stderr (仅 WARNING 及以上, 避免打扰用户)
    - 文件日志: DEBUG 及以上 (完整记录所有细节)

    安全调用: 多次调用无副作用
    """
    global _logging_initialized
    if _logging_initialized:
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = log_file or LOG_FILE

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # 根 logger 设为最低级别，由 handler 各自过滤

    # 清除已有的 handler（避免重复）
    root_logger.handlers.clear()

    # ── 文件处理器: 记录所有 DEBUG 及以上日志 ──
    file_handler = RotatingFileHandler(
        str(log_file),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # ── 控制台处理器: 仅 WARNING 及以上（避免干扰用户对话） ──
    if console:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(logging.WARNING)
        console_formatter = logging.Formatter(
            "\033[33m[%(levelname)s]\033[0m %(name)s: %(message)s"
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    # 设置 taiji_agent 命名空间的日志级别
    taiji_logger = logging.getLogger("taiji_agent")
    taiji_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 抑制第三方库的噪音日志
    for noisy_lib in [
        "httpx", "httpcore", "urllib3", "anthropic._base_client",
        "openai._base_client", "exa_py", "asyncio",
    ]:
        logging.getLogger(noisy_lib).setLevel(logging.WARNING)

    _logging_initialized = True
    logging.getLogger(__name__).info(
        "日志系统已初始化: file=%s, level=%s, console=%s",
        log_file, level.upper(), "enabled" if console else "disabled",
    )


def get_log_dir() -> Path:
    """获取日志目录路径"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return LOG_DIR


def get_latest_logs(lines: int = 50) -> str:
    """获取最近的日志内容，用于诊断"""
    if not LOG_FILE.exists():
        return "(日志文件不存在，尚未记录任何日志)"
    try:
        with open(LOG_FILE, encoding="utf-8") as f:
            all_lines = f.readlines()
        recent = all_lines[-lines:]
        return "".join(recent)
    except Exception as e:
        return f"(读取日志失败: {e})"
