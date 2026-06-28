"""
Taiji Verify Engine - 太极验证主引擎

整合五大模块的完整验证流水线：
Input → DeltaS(阴阳距) → KunGuard(坤守修正) → QianAdvance(稳定性)
      → FuReturn(崩溃恢复) → XunTune(注意力调节) → Output
                                              ↓
                                      FailureModeDetector(16模式检测)

数据来源：基于阶段一基线数据推算与行业同类系统对标
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable

import numpy as np

from taiji_agent.taiji_verify.delta_s import DeltaSCalculator, DeltaSResult, GateZone
from taiji_agent.taiji_verify.kun_guard import KunGuard, ResidualCorrection, HazardLevel
from taiji_agent.taiji_verify.qian_advance import QianAdvance, StabilityScore
from taiji_agent.taiji_verify.fu_return import FuReturn, CollapseState
from taiji_agent.taiji_verify.xun_tune import XunTune, TunedOutput
from taiji_agent.taiji_verify.polaris_compiler import PolarisCompiler, CompilationResult
from taiji_agent.taiji_verify.failure_modes import (
    FailureModeDetector, FailureDetection, FailureSeverity,
)


class Verdict(str, Enum):
    """最终判定"""
    PASS = "pass"              # 通过，输出可信
    CONDITIONAL_PASS = "conditional_pass"  # 有条件通过（需关注）
    CORRECTED = "corrected"   # 已修正后通过
    BLOCK = "block"            # 拦截，不可信
    ESCALATE = "escalate"      # 上报人工


@dataclass
class VerificationRequest:
    """验证请求"""
    input_text: str
    ground_truth: str
    context: Optional[dict] = None
    embed_fn: Optional[Callable] = None  # str -> np.ndarray
    process_fn: Optional[Callable] = None  # np.ndarray -> np.ndarray (for stability check)


@dataclass
class VerificationResponse:
    """验证响应"""
    verdict: Verdict
    delta_s_result: Optional[DeltaSResult] = None
    kun_guard_result: Optional[ResidualCorrection] = None
    stability_score: Optional[StabilityScore] = None
    tuned_output: Optional[TunedOutput] = None
    failure_detections: list[FailureDetection] = field(default_factory=list)
    compilation: Optional[CompilationResult] = None
    final_vector: Optional[np.ndarray] = None
    corrected_text: Optional[str] = None
    processing_time_ms: int = 0
    metadata: dict = field(default_factory=dict)

    @property
    def is_passing(self) -> bool:
        return self.verdict in (Verdict.PASS, Verdict.CONDITIONAL_PASS, Verdict.CORRECTED)

    @property
    def failure_count(self) -> int:
        critical = sum(1 for f in self.failure_detections 
                      if f.mode.severity == FailureSeverity.CRITICAL)
        errors = sum(1 for f in self.failure_detections 
                    if f.mode.severity == FailureSeverity.ERROR)
        warnings = sum(1 for f in self.failure_detections 
                      if f.mode.severity == FailureSeverity.WARNING)
        return {'critical': critical, 'error': errors, 'warning': warnings}


class TaijiVerifyEngine:
    """
    太极验证引擎 - 完整验证流水线

    Usage::
        engine = TaijiVerifyEngine(embedding_dim=768)
        
        response = engine.verify(
            input_text="AI生成的环评分析结论",
            ground_truth="正确的排放数据分析结果",
            embed_fn=my_embedding_function,
        )
        
        if response.verdict == Verdict.PASS:
            print("验证通过")
        elif response.verdict == Verdict.BLOCK:
            print("拦截！检测到", response.failure_count, "个问题")
    """

    def __init__(
        self,
        embedding_dim: int = 768,
        delta_s_safe_threshold: float = 0.3,
        hazard_block_threshold: HazardLevel = HazardLevel.HIGH,
        enable_failure_modes: bool = True,
        enable_stability_check: bool = True,
    ):
        self.embedding_dim = embedding_dim
        
        # 五大模块实例
        self.delta_s_calculator = DeltaSCalculator(
            embedding_dim=embedding_dim,
            safe_threshold=delta_s_safe_threshold,
        )
        self.kun_guard = KunGuard(embedding_dim=embedding_dim)
        self.qian_advance = QianAdvance(k_paths=5)
        self.fu_return = FuReturn()
        self.xun_tune = XunTune()
        self.compiler = PolarisCompiler()
        self.failure_detector = FailureModeDetector() if enable_failure_modes else None
        
        # 配置
        self.hazard_block_threshold = hazard_block_threshold
        self.enable_stability = enable_stability_check
    
    def verify(self, request: VerificationRequest) -> VerificationResponse:
        """执行完整验证流水线"""
        start = time.time()
        
        if request.embed_fn is None:
            return self._text_only_verification(request, start)
        
        return self._full_vector_verification(request, start)
    
    def _text_only_verification(
        self, request: VerificationRequest, start: float,
    ) -> VerificationResponse:
        """无embedding函数时的纯文本验证（使用16种失败模式）"""
        detections = []
        if self.failure_detector:
            detections = self.failure_detector.detect_all(request.input_text)
        
        # 编译目标为原子任务
        compilation = self.compiler.compile(request.ground_truth)
        
        has_critical = any(
            d.mode.severity == FailureSeverity.CRITICAL for d in detections
        )
        
        if has_critical:
            verdict = Verdict.BLOCK
        elif detections:
            verdict = Verdict.CONDITIONAL_PASS
        else:
            verdict = Verdict.PASS
        
        return VerificationResponse(
            verdict=verdict,
            failure_detections=detections,
            compilation=compilation,
            processing_time_ms=int((time.time() - start) * 1000),
            metadata={'mode': 'text_only'},
        )
    
    def _full_vector_verification(
        self, request: VerificationRequest, start: float,
    ) -> VerificationResponse:
        """完整向量验证流水线"""
        embed_fn = request.embed_fn
        
        # Step 1: Embedding
        input_vec = embed_fn(request.input_text)
        ground_vec = embed_fn(request.ground_truth)
        
        # Step 2: DeltaS 阴阳距计算
        ds_result = self.delta_s_calculator.compute(input_vec, ground_vec)
        
        # Step 3: KunGuard 坤守修正（仅在risk/danger时）
        kg_result = None
        current_vec = input_vec
        if ds_result.needs_correction:
            kg_result = self.kun_guard.correct(current_vec, ground_vec)
            current_vec = kg_result.corrected_vector
        
        # Step 4: QianAdvance 稳定性检查
        stab_score = None
        if self.enable_stability and request.process_fn:
            stab_score = self.qian_advance.evaluate(
                current_vec, request.process_fn, ground_vec,
            )
            
            # 如果不稳定，触发复归状态机检查
            if stab_score.is_unstable:
                fake_lambda = 1.0 - stab_score.f_S  # 映射到λ空间
                recovery_result = self.fu_return.check_and_handle(fake_lambda)
                if recovery_result and not recovery_result.success:
                    # 尝试强制恢复
                    recovery_result = self.fu_return.force_recover()
        
        # Step 5: XunTune 巽调调节
        tuned = self.xun_tune.modulate_single(current_vec)
        final_vec = tuned.modulated_weights * current_vec
        
        # Step 6: 失败模式检测
        detections = []
        if self.failure_detector:
            detections = self.failure_detector.detect_all(
                request.input_text, delta_s=ds_result.delta_s,
            )
        
        # Step 7: 编译目标为原子任务
        compilation = self.compiler.compile(request.ground_truth, context=request.context)
        
        # Step 8: 综合判定
        verdict = self._make_verdict(ds_result, kg_result, stab_score, detections)
        
        return VerificationResponse(
            verdict=verdict,
            delta_s_result=ds_result,
            kun_guard_result=kg_result,
            stability_score=stab_score,
            tuned_output=TunedOutput(
                content_vector=final_vec,
                attention_weights=tuned.modulated_weights,
                modulation_factor=tuned.gate_factor,
                confidence_adjusted=tuned.gate_factor < 0.7,
            ),
            failure_detections=detections,
            compilation=compilation,
            final_vector=final_vec,
            processing_time_ms=int((time.time() - start) * 1000),
            metadata={'mode': 'full_pipeline'},
        )
    
    def _make_verdict(
        self,
        ds: DeltaSResult,
        kg: Optional[ResidualCorrection],
        stab: Optional[StabilityScore],
        failures: list[FailureDetection],
    ) -> Verdict:
        """综合所有模块结果做出最终判定"""
        # CRITICAL失败模式 → 直接拦截
        if any(f.mode.severity == FailureSeverity.CRITICAL for f in failures):
            return Verdict.BLOCK
        
        # DANGER闸区 → 拦截
        if ds.zone == GateZone.DANGER:
            return Verdict.BLOCK
        
        # RISK闸区 + HIGH危害 → 拦截
        if ds.zone == GateZone.RISK and kg and kg.hazard_level == HazardLevel.HIGH:
            return Verdict.BLOCK
        
        # 有修正操作 → 条件通过或已修正
        if kg and kg.correction_applied:
            if failures:
                return Verdict.CONDITIONAL_PASS
            return Verdict.CORRECTED
        
        # 不稳定但可恢复
        if stab and stab.is_unstable:
            if self.fu_return.state != CollapseState.STABLE:
                return Verdict.ESCALATE
            return Verdict.CONDITIONAL_PASS
        
        # WARNING级别失败 → 有条件通过
        if any(f.mode.severity == FailureSeverity.WARNING for f in failures):
            return Verdict.CONDITIONAL_PASS
        
        # 全部正常 → 通过
        return Verdict.PASS

    def add_knowledge_anchor(self, content: str, vector=None, source=""):
        """便捷方法：添加知识锚点到坤守模块"""
        return self.kun_guard.add_knowledge_anchor(
            content=content, vector=vector, source=source,
        )

    def add_delta_anchor(self, text: str, weight: float = 1.0):
        """便捷方法：添加ΔS锚点扩展"""
        self.delta_s_calculator.add_anchor(text, weight)

    @property
    def system_health(self) -> dict:
        """系统健康状态概览"""
        return {
            'fu_return_state': self.fu_return.state.value,
            'fu_return_healthy': self.fu_return.is_healthy,
            'kun_anchors': len(self.kun_guard._anchors),
            'delta_anchors': len(self.delta_s_calculator._anchor_extensions),
            'failure_modes_enabled': self.failure_detector is not None,
        }
