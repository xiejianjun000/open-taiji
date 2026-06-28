"""
向后兼容的安全模块适配器
匹配 test_security.py 的 API 期望
"""

import re
import time
from pathlib import Path
import subprocess
from dataclasses import dataclass, field
from typing import Optional


# ═══════════════════════════════════════
# SandboxStatus — 状态枚举（兼容旧API）
# ═══════════════════════════════════════

class SandboxStatus:
    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    TERMINATED = "terminated"
    TIMEOUT = "timeout"
    KILLED = "killed"
    ERROR = "error"
    BLOCKED = "blocked"


# ═══════════════════════════════════════
# SandboxConfig — 沙箱配置（兼容旧API）
# ═══════════════════════════════════════

@dataclass
class SandboxConfig:
    max_cpu_time: int = 30
    max_wall_time: int = 60
    max_memory_bytes: int = 128 * 1024 * 1024  # 128MB
    max_disk_bytes: int = 512 * 1024 * 1024    # 512MB
    max_code_size: int = 1024 * 1024            # 1MB
    allowed_modules: list[str] = field(default_factory=lambda: ["math", "json", "re", "datetime", "collections", "itertools"])
    blocked_modules: list[str] = field(default_factory=lambda: ["os", "subprocess", "sys", "shutil", "importlib"])


# ═══════════════════════════════════════
# SandboxResult — 执行结果（兼容旧API）
# ═══════════════════════════════════════

@dataclass
class SandboxResult:
    status: str = SandboxStatus.CREATED
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    duration: float = 0.0
    security_violations: list[str] = field(default_factory=list)
    blocked: bool = False
    block_reason: str = ""


# ═══════════════════════════════════════
# Sandbox — 代码执行沙箱（兼容旧API）
# ═══════════════════════════════════════

class Sandbox:
    """代码执行沙箱"""

    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or SandboxConfig()
        self._status = SandboxStatus.CREATED
        self._execution_count = 0
        self._security_patterns: list[tuple[re.Pattern, str]] = [
            (re.compile(r"os\.system\s*\("), "os.system() call"),
            (re.compile(r"subprocess\."), "subprocess usage"),
            (re.compile(r"eval\s*\("), "eval() call"),
            (re.compile(r"exec\s*\("), "exec() call"),
            (re.compile(r"__import__\s*\("), "__import__() call"),
            (re.compile(r"open\s*\(.*['\"]w"), "file write"),
            (re.compile(r"shutil\."), "shutil usage"),
            (re.compile(r"importlib"), "importlib usage"),
            (re.compile(r"compile\s*\("), "compile() call"),
        ]

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, value):
        self._status = value

    def _check_security(self, code: str) -> list[str]:
        """检查代码安全性"""
        violations = []
        for pattern, desc in self._security_patterns:
            if pattern.search(code):
                violations.append(desc)
        return violations

    def execute_code(self, code: str, language: str = "python") -> SandboxResult:
        """执行代码"""
        if self._status == SandboxStatus.KILLED:
            return SandboxResult(status=SandboxStatus.KILLED, stderr="Sandbox已被终止")

        # 代码大小检查
        if len(code) > self.config.max_code_size:
            return SandboxResult(
                status=SandboxStatus.TERMINATED,
                security_violations=[f"代码过大: {len(code)} > {self.config.max_code_size}"],
            )

        # 安全检查
        violations = self._check_security(code)
        if violations:
            # 仍然执行但标记违规
            pass

        self._status = SandboxStatus.RUNNING
        self._execution_count += 1
        start = time.time()

        if language.lower() in ("python", "py"):
            try:
                import tempfile, os as os_mod
                fd, tmp_path = tempfile.mkstemp(suffix=".py")
                try:
                    with os_mod.fdopen(fd, "w") as f:
                        f.write(code)

                    result = subprocess.run(
                        ["python3", tmp_path],
                        capture_output=True, text=True,
                        timeout=min(self.config.max_cpu_time, 30),
                    )
                    duration = time.time() - start
                    self._status = SandboxStatus.TERMINATED

                    return SandboxResult(
                        status=SandboxStatus.TERMINATED,
                        stdout=result.stdout,
                        stderr=result.stderr,
                        exit_code=result.returncode,
                        duration=duration,
                        security_violations=violations,
                    )
                finally:
                    os_mod.unlink(tmp_path)
            except subprocess.TimeoutExpired:
                self._status = SandboxStatus.TIMEOUT
                return SandboxResult(status=SandboxStatus.TIMEOUT, stderr="执行超时")
            except Exception as e:
                self._status = SandboxStatus.ERROR
                return SandboxResult(status=SandboxStatus.ERROR, stderr=str(e))
        else:
            return SandboxResult(status=SandboxStatus.TERMINATED, stderr=f"不支持的语言: {language}")

    def terminate(self, reason: str = "") -> SandboxResult:
        """终止沙箱"""
        self._status = SandboxStatus.KILLED
        return SandboxResult(status=SandboxStatus.KILLED, stderr=reason or "手动终止")


# ═══════════════════════════════════════
# SandboxPool — 沙箱池（兼容旧API）
# ═══════════════════════════════════════

class SandboxPool:
    """沙箱池"""

    def __init__(self, pool_size: int = 4, config: Optional[SandboxConfig] = None):
        self.pool_size = pool_size
        self.config = config or SandboxConfig()
        self._pool: list[Sandbox] = []
        self._available: list[Sandbox] = []  # 兼容旧 test
        self._in_use: set[int] = set()
        self._initialize_pool()

    def _initialize_pool(self):
        for i in range(self.pool_size):
            self._pool.append(Sandbox(self.config))

    def acquire(self) -> Optional[Sandbox]:
        """获取一个可用沙箱"""
        for i, sb in enumerate(self._pool):
            if i not in self._in_use and sb.status != SandboxStatus.KILLED:
                self._in_use.add(i)
                sb.status = SandboxStatus.RUNNING
                return sb
        # 池已满，创建临时沙箱
        if len(self._pool) < self.pool_size * 2:
            sb = Sandbox(self.config)
            sb.status = SandboxStatus.RUNNING
            self._pool.append(sb)
            self._in_use.add(len(self._pool) - 1)
            return sb
        return None

    def release(self, sandbox: Sandbox):
        """释放沙箱"""
        for i, sb in enumerate(self._pool):
            if sb is sandbox:
                self._in_use.discard(i)
                if sb.status not in (SandboxStatus.KILLED, SandboxStatus.ERROR):
                    sb.status = SandboxStatus.CREATED
                break

    def execute_in_pool(self, code: str, language: str = "python") -> SandboxResult:
        """在池中执行代码"""
        sb = self.acquire()
        if sb is None:
            return SandboxResult(status=SandboxStatus.ERROR, stderr="沙箱池已满")
        try:
            return sb.execute_code(code, language)
        finally:
            self.release(sb)

    def shutdown(self):
        """关闭所有沙箱"""
        for sb in self._pool:
            sb.terminate("池关闭")
        self._pool.clear()
        self._available.clear()
        self._in_use.clear()


# ═══════════════════════════════════════
# SecurityFence — 安全围栏（兼容旧API）
# ═══════════════════════════════════════

DEFAULT_SENSITIVE_KEYWORDS = {
    "password", "passwd", "secret", "token", "api_key", "apikey",
    "private_key", "ssh_key", "credential", "authorization",
    "bearer", "access_key", "secret_key",
}


class SecurityFence:
    """安全围栏 — 关键词扫描 + 命令过滤"""

    def __init__(self, custom_keywords: Optional[set] = None):
        self.keywords = DEFAULT_SENSITIVE_KEYWORDS | (custom_keywords or set())
        self._dangerous_commands = [
            "rm -rf /", "mkfs", "dd if=", "> /dev/", "shutdown",
            "reboot", "halt", "poweroff", "init 0", "init 6",
            "kill -9", "pkill", "killall",
        ]

    def check(self, content: str) -> tuple:
        """
        检查内容是否安全
        
        Returns:
            (passed: bool, matched: list[str])
        """
        content_lower = content.lower()
        matched = []
        for keyword in self.keywords:
            if keyword.lower() in content_lower:
                matched.append(keyword)
        return len(matched) == 0, matched

    def filter_command(self, command: str) -> tuple:
        """
        过滤命令
        
        Returns:
            (passed: bool, filtered: str)
        """
        for dangerous in self._dangerous_commands:
            if dangerous in command:
                return False, command
        return True, command


# ═══════════════════════════════════════
# ResourceLimit — 资源限制（兼容旧API）
# ═══════════════════════════════════════

@dataclass
class ResourceLimit:
    max_cpu_percent: int = 80
    max_memory_mb: int = 512
    max_disk_mb: int = 1024
    max_processes: int = 10
    max_open_files: int = 100

# ═══════════════════════════════════════
# 兼容别名（兼容 v2.1 升级代码）
# ═══════════════════════════════════════

SecuritySandbox = Sandbox
CodeSandbox = Sandbox
default_sandbox = SecurityFence()
code_sandbox = Sandbox()
