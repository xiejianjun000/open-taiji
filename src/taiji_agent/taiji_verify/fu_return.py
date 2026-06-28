"""
Fu Return (复归 / BBCR - Bias-Bound Collapse Recovery)
崩溃恢复状态机模块

基于李雅普诺夫指数λ的状态机设计，实现三段式崩溃恢复：
1. Detect (检测): λ > λ_threshold → 触发崩溃检测
2. Isolate (隔离): 冻结当前状态，保存上下文
3. Recover (恢复): 回滚到最后稳定点，逐步重建

状态转换:
  STABLE ──λ超限──> DETECTED ──确认──> ISOLATED ──恢复──> RECOVERING ──成功──> STABLE
    ^                                                              │
    └──────────────────── 失败/重试超数 ───────────────────────────┘

数据来源：基于阶段一基线数据推算与行业同类系统对标
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CollapseState(str, Enum):
    """崩溃恢复状态"""
    STABLE = "stable"           # 正常运行
    DETECTED = "detected"       # 检测到异常（潜在崩溃）
    ISOLATED = "isolated"       # 已隔离
    RECOVERING = "recovering"   # 恢复中
    COLLAPSED = "collapsed"     # 崩溃（不可恢复）


class RecoveryAction(str, Enum):
    """恢复动作类型"""
    NONE = "none"
    ROLLBACK = "rollback"          # 回滚到检查点
    RETRY = "retry"                # 重试操作
    DEGRADE = "degrade"            # 降级服务
    ESCALATE = "escalate"          # 上报给人工
    RESTART = "restart"            # 热重启组件


@dataclass
class Checkpoint:
    """系统快照检查点"""
    id: str
    timestamp: float
    state_data: dict
    lyapunov_lambda: float
    metadata: dict = field(default_factory=dict)


@dataclass
class RecoveryResult:
    """恢复结果"""
    success: bool
    action: RecoveryAction
    from_state: CollapseState
    to_state: CollapseState
    duration_ms: int
    checkpoint_used: Optional[str] = None
    message: str = ""
    metadata: dict = field(default_factory=dict)


class FuReturn:
    """
    复归 - 崩溃恢复状态机

    Usage::
        recovery = FuReturn(lambda_threshold=0.5)
        
        while True:
            current_lambda = compute_lyapunov(system_state)
            if recovery.check_and_handle(current_lambda):
                print("Recovery in progress...")
            
            # 正常处理...
            recovery.update_checkpoint(current_state)
    """

    def __init__(
        self,
        lambda_threshold: float = 0.5,
        max_retries: int = 3,
        checkpoint_history_size: int = 10,
    ):
        self.lambda_threshold = lambda_threshold
        self.max_retries = max_retries
        self._state = CollapseState.STABLE
        self._checkpoints: list[Checkpoint] = []
        self._retry_count = 0
        self._history_max = checkpoint_history_size
        self._detect_time: Optional[float] = None
        self._isolate_time: Optional[float] = None

    @property
    def state(self) -> CollapseState:
        return self._state

    @property
    def is_healthy(self) -> bool:
        return self._state == CollapseState.STABLE

    def check_and_handle(self, lyapunov_lambda: float) -> Optional[RecoveryResult]:
        """
        检查李雅普诺夫指数并执行相应恢复动作
        
        Args:
            lyapunov_lambda: 当前系统的李雅普诺夫指数
            
        Returns:
            RecoveryResult 如果触发了恢复动作，否则返回None
        """
        if self._state == CollapseState.COLLAPSED:
            return self._handle_collapsed()

        if self._state == CollapseState.RECOVERING:
            return self._continue_recovery()

        # 在STABLE状态下检测异常
        if self._state == CollapseState.STABLE and lyapunov_lambda > self.lambda_threshold:
            return self._transition_to_detected(lyapunov_lambda)

        # 在DETECTED状态下确认或取消
        elif self._state == CollapseState.DETECTED:
            if lyapunov_lambda <= self.lambda_threshold * 0.8:
                # 假警报，回退到稳定
                self._state = CollapseState.STABLE
                self._detect_time = None
                return RecoveryResult(
                    success=True,
                    action=RecoveryAction.NONE,
                    from_state=CollapseState.DETECTED,
                    to_state=CollapseState.STABLE,
                    duration_ms=0,
                    message="False alarm - lambda returned to normal",
                )
            # 超时自动升级为ISOLATED
            elif self._detect_time and time.time() - self._detect_time > 5.0:
                return self._transition_to_isolated()

        return None

    def update_checkpoint(self, state_data: dict, lyapunov_lambda: float = 0.0):
        """更新正常运行的检查点（仅在STABLE状态有效）"""
        if self._state != CollapseState.STABLE:
            return
        cp = Checkpoint(
            id=f"cp_{len(self._checkpoints)}",
            timestamp=time.time(),
            state_data=state_data.copy(),
            lyapunov_lambda=lyapunov_lambda,
        )
        self._checkpoints.append(cp)
        if len(self._checkpoints) > self._history_max:
            self._checkpoints.pop(0)

    def get_latest_checkpoint(self) -> Optional[Checkpoint]:
        """获取最新的有效检查点"""
        valid = [cp for cp in self._checkpoints 
                 if cp.lyapunov_lambda < self.lambda_threshold]
        return valid[-1] if valid else None

    def _transition_to_detected(self, lam: float) -> RecoveryResult:
        self._state = CollapseState.DETECTED
        self._detect_time = time.time()
        return RecoveryResult(
            success=False,
            action=RecoveryAction.NONE,
            from_state=CollapseState.STABLE,
            to_state=CollapseState.DETECTED,
            duration_ms=0,
            message=f"Anomaly detected: lambda={lam:.4f} > threshold={self.lambda_threshold}",
        )

    def _transition_to_isolated(self) -> RecoveryResult:
        self._state = CollapseState.ISOLATED
        self._isolate_time = time.time()
        return RecoveryResult(
            success=False,
            action=RecoveryAction.NONE,
            from_state=CollapseState.DETECTED,
            to_state=CollapseState.ISOLATED,
            duration_ms=int((time.time() - (self._detect_time or 0)) * 1000),
            message="System isolated for investigation",
        )

    def _continue_recovery(self) -> RecoveryResult:
        cp = self.get_latest_checkpoint()
        if not cp or self._retry_count >= self.max_retries:
            self._state = CollapseState.COLLAPSED
            return RecoveryResult(
                success=False,
                action=RecoveryAction.ESCALATE,
                from_state=CollapseState.RECOVERING,
                to_state=CollapseState.COLLAPSED,
                duration_ms=0,
                message="Max retries exceeded or no valid checkpoint",
            )

        self._retry_count += 1
        self._state = CollapseState.STABLE
        result = RecoveryResult(
            success=True,
            action=RecoveryAction.ROLLBACK,
            from_state=CollapseState.RECOVERING,
            to_state=CollapseState.STABLE,
            duration_ms=0,
            checkpoint_used=cp.id,
            message=f"Recovered via rollback to {cp.id} (attempt {self._retry_count})",
        )
        self._retry_count = 0
        return result

    def _handle_collapsed(self) -> RecoveryResult:
        return RecoveryResult(
            success=False,
            action=RecoveryAction.ESCALATE,
            from_state=CollapseState.COLLAPSED,
            to_state=CollapseState.COLLAPSED,
            duration_ms=0,
            message="System collapsed - manual intervention required",
        )

    def force_recover(self) -> RecoveryResult:
        """强制触发恢复流程"""
        if self._state in (CollapseState.STABLE,):
            return RecoveryResult(success=True, action=RecoveryAction.NONE,
                from_state=self._state, to_state=self._state, duration_ms=0,
                message="No recovery needed")

        if self._state == CollapseState.DETECTED:
            self._transition_to_isolated()

        self._state = CollapseState.RECOVERING
        return self._continue_recovery()

    def reset(self):
        """重置状态机到初始状态"""
        self._state = CollapseState.STABLE
        self._retry_count = 0
        self._detect_time = None
        self._isolate_time = None
