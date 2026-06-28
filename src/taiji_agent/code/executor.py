"""
Code Executor - 代码执行器
参考SmolAgents安全代码执行设计
"""

from __future__ import annotations

import asyncio
import io
import logging
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
class StrEnum(str, Enum):
    pass
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ExecutionStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    SANDBOX_VIOLATION = "sandbox_violation"


@dataclass
class ExecutionResult:
    execution_id: str
    status: ExecutionStatus
    output: str
    error: Optional[str] = None
    execution_time_ms: float = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_success(self) -> bool:
        return self.status == ExecutionStatus.SUCCESS


@dataclass
class SandboxConfig:
    timeout_seconds: int = 30
    max_memory_mb: int = 256
    allowed_modules: list[str] = field(default_factory=list)
    blocked_modules: list[str] = field(
        default_factory=lambda: [
            "os",
            "subprocess",
            "socket",
            "requests",
            "urllib",
            "ctypes",
            "sys",
            "builtins",
        ]
    )
    allow_network: bool = False
    allow_file_write: bool = False
    max_output_length: int = 10000


class CodeExecutor:
    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or SandboxConfig()
        self._execution_count = 0
        self._history: list[ExecutionResult] = []

    async def execute(
        self,
        code: str,
        language: str = "python",
        context: Optional[dict[str, Any]] = None,
    ) -> ExecutionResult:
        execution_id = str(uuid.uuid4())[:12]
        self._execution_count += 1
        start_time = datetime.now()
        context = context or {}
        context["_execution_id"] = execution_id
        try:
            if language.lower() == "python":
                result = await self._execute_python(code, context)
            elif language.lower() == "javascript":
                result = await self._execute_javascript(code, context)
            else:
                result = ExecutionResult(
                    execution_id=execution_id,
                    status=ExecutionStatus.ERROR,
                    output="",
                    error=f"Unsupported language: {language}",
                )
        except TimeoutError:
            result = ExecutionResult(
                execution_id=execution_id,
                status=ExecutionStatus.TIMEOUT,
                output="",
                error=f"Execution timeout after {self.config.timeout_seconds}s",
            )
        except Exception as e:
            result = ExecutionResult(
                execution_id=execution_id,
                status=ExecutionStatus.ERROR,
                output="",
                error=str(e),
            )
        end_time = datetime.now()
        result.execution_time_ms = (end_time - start_time).total_seconds() * 1000
        self._history.append(result)
        logger.info(f"Code executed: {execution_id} - {result.status.value}")
        return result

    async def _execute_python(
        self,
        code: str,
        context: dict[str, Any],
    ) -> ExecutionResult:
        forbidden_patterns = [
            "import os",
            "import sys",
            "import subprocess",
            "import ctypes",
            "import socket",
            "__import__",
            "exec(",
            "eval(",
            "compile(",
        ]
        for pattern in forbidden_patterns:
            if pattern in code:
                return ExecutionResult(
                    execution_id=context.get("_execution_id", ""),
                    status=ExecutionStatus.SANDBOX_VIOLATION,
                    output="",
                    error=f"Blocked: {pattern}",
                )
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        local_vars: dict[str, Any] = {}
        try:
            loop = asyncio.get_event_loop()
            async_function = loop.run_in_executor(
                None,
                self._run_python_code,
                code,
                local_vars,
                stdout_capture,
                stderr_capture,
            )
            result = await asyncio.wait_for(
                async_function,
                timeout=self.config.timeout_seconds,
            )
        except TimeoutError:
            return ExecutionResult(
                execution_id=context.get("_execution_id", ""),
                status=ExecutionStatus.TIMEOUT,
                output=stdout_capture.getvalue(),
                error=f"Timeout after {self.config.timeout_seconds}s",
            )
        output = stdout_capture.getvalue()
        error_output = stderr_capture.getvalue()
        if error_output:
            return ExecutionResult(
                execution_id=context.get("_execution_id", ""),
                status=ExecutionStatus.ERROR,
                output=output,
                error=error_output,
            )
        return ExecutionResult(
            execution_id=context.get("_execution_id", ""),
            status=ExecutionStatus.SUCCESS,
            output=output[: self.config.max_output_length],
            metadata={"return_value": result},
        )

    def _run_python_code(
        self,
        code: str,
        local_vars: dict[str, Any],
        stdout: io.StringIO,
        stderr: io.StringIO,
    ) -> Any:
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = stdout
        sys.stderr = stderr
        try:
            compiled = compile(code, "<code>", "exec")
            exec(compiled, {}, local_vars)
            if "final_answer" in local_vars:
                return local_vars["final_answer"]
            return None
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

    async def _execute_javascript(
        self,
        code: str,
        context: dict[str, Any],
    ) -> ExecutionResult:
        return ExecutionResult(
            execution_id=context.get("_execution_id", ""),
            status=ExecutionStatus.ERROR,
            output="",
            error="JavaScript execution requires Node.js sandbox",
        )

    def get_history(self, limit: int = 100) -> list[ExecutionResult]:
        return self._history[-limit:]

    def get_statistics(self) -> dict[str, Any]:
        total = len(self._history)
        success_count = sum(1 for r in self._history if r.is_success())
        avg_time = sum(r.execution_time_ms for r in self._history) / total if total > 0 else 0
        return {
            "total_executions": total,
            "successful": success_count,
            "failed": total - success_count,
            "success_rate": success_count / total if total > 0 else 0,
            "avg_execution_time_ms": avg_time,
        }


class SandboxManager:
    def __init__(self):
        self._sandboxes: dict[str, SandboxConfig] = {}
        self._active_sessions: dict[str, bool] = {}

    def create_sandbox(
        self,
        name: str,
        config: Optional[SandboxConfig] = None,
    ) -> str:
        sandbox_id = str(uuid.uuid4())[:8]
        self._sandboxes[sandbox_id] = config or SandboxConfig()
        logger.info(f"Sandbox created: {sandbox_id} ({name})")
        return sandbox_id

    def get_sandbox(self, sandbox_id: str) -> Optional[SandboxConfig]:
        return self._sandboxes.get(sandbox_id)

    def destroy_sandbox(self, sandbox_id: str) -> bool:
        if sandbox_id in self._sandboxes:
            del self._sandboxes[sandbox_id]
            self._active_sessions.pop(sandbox_id, None)
            logger.info(f"Sandbox destroyed: {sandbox_id}")
            return True
        return False

    def create_executor(self, sandbox_id: Optional[str] = None) -> CodeExecutor:
        config = self._sandboxes.get(sandbox_id) if sandbox_id else None
        return CodeExecutor(config)
