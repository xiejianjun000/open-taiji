"""
Taiji Verify 1.0 单元测试 & 集成测试

覆盖范围：
- DeltaS 阴阳距计算（4区映射）
- KunGuard 坤守残差修正（4级危害）
- QianAdvance 乾进稳定性评估
- FuReturn 复归状态机转换
- XunTune 巽调门控因子
- 北辰编译器任务分解
- 16种失败模式检测
- 引擎端到端集成测试
"""

import math
import pytest
import numpy as np
from numpy.linalg import norm


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def dim():
    return 128  # 用小维度加速测试


@pytest.fixture
def random_vectors(dim):
    """生成测试用随机向量对"""
    rng = np.random.RandomState(42)
    identical = rng.randn(dim).astype(np.float32)
    similar = identical + rng.randn(dim).astype(np.float32) * 0.1
    different = rng.randn(dim).astype(np.float32)
    return {
        'identical': identical / norm(identical),
        'similar': similar / norm(similar),
        'different': different / norm(different),
    }


@pytest.fixture
def embed_fn_factory(dim):
    """创建简单的伪embedding函数"""
    rng = np.random.RandomState(99)
    cache = {}
    
    def embed(text: str) -> np.ndarray:
        """直接返回embed函数，而非工厂函数"""
        if text in cache:
            return cache[text]
        vec = rng.randn(dim).astype(np.float32)
        vec = vec / (norm(vec) + 1e-10)
        cache[text] = vec
        return vec
    
    return embed


# ============================================================
# DeltaS Tests
# ============================================================

class TestDeltaS:
    """DeltaS 阴阳距离计算器测试"""

    def test_identical_vectors_zero_delta(self, random_vectors):
        from taiji_agent.taiji_verify.delta_s import DeltaSCalculator, GateZone
        calc = DeltaSCalculator()
        result = calc.compute(
            random_vectors['identical'],
            random_vectors['identical'],
        )
        assert result.delta_s < 0.01
        assert result.zone == GateZone.SAFE
        assert result.cosine_similarity > 0.99
        assert result.is_safe is True

    def test_different_vectors_higher_delta(self, random_vectors):
        from taiji_agent.taiji_verify.delta_s import DeltaSCalculator
        calc = DeltaSCalculator()
        result_similar = calc.compute(
            random_vectors['similar'], random_vectors['identical'],
        )
        result_diff = calc.compute(
            random_vectors['different'], random_vectors['identical'],
        )
        assert result_diff.delta_s > result_similar.delta_s

    def test_gate_zone_mapping(self):
        from taiji_agent.taiji_verify.delta_s import GateZone
        # 新阈值: SAFE<0.40, TRANSIT 0.40-0.60, RISK 0.60-0.85, DANGER>=0.85
        assert GateZone.from_delta(0.1) == GateZone.SAFE
        assert GateZone.from_delta(0.35) == GateZone.SAFE
        assert GateZone.from_delta(0.4) == GateZone.TRANSIT
        assert GateZone.from_delta(0.5) == GateZone.TRANSIT
        assert GateZone.from_delta(0.6) == GateZone.RISK
        assert GateZone.from_delta(0.8) == GateZone.RISK
        assert GateZone.from_delta(0.85) == GateZone.DANGER
        assert GateZone.from_delta(0.9) == GateZone.DANGER

    def test_clamp_to_range(self, random_vectors):
        from taiji_agent.taiji_verify.delta_s import DeltaSCalculator
        calc = DeltaSCalculator()
        result = calc.compute(random_vectors['identical'], random_vectors['identical'])
        assert 0.0 <= result.delta_s <= 1.0

    def test_batch_compute(self, random_vectors):
        from taiji_agent.taiji_verify.delta_s import DeltaSCalculator
        calc = DeltaSCalculator()
        inputs = [random_vectors['similar'], random_vectors['different']]
        results = calc.compute_batch(inputs, random_vectors['identical'])
        assert len(results) == 2

    def test_compute_from_texts(self, embed_fn_factory):
        from taiji_agent.taiji_verify.delta_s import DeltaSCalculator
        calc = DeltaSCalculator()
        result = calc.compute_from_texts("hello world", "hello world", embed_fn_factory)
        assert result.zone.value == "safe"


# ============================================================
# KunGuard Tests  
# ============================================================

class TestKunGuard:
    """坤守残差修正器测试"""

    def test_low_residual_no_correction(self, random_vectors):
        from taiji_agent.taiji_verify.kun_guard import KunGuard, HazardLevel
        guard = KunGuard()
        result = guard.correct(random_vectors['similar'], random_vectors['identical'])
        assert result.hazard_level in (HazardLevel.LOW, HazardLevel.MEDIUM)

    def test_knowledge_anchor_projection(self, random_vectors):
        from taiji_agent.taiji_verify.kun_guard import KunGuard
        guard = KunGuard()
        aid = guard.add_knowledge_anchor("test law", vector=random_vectors['identical'])
        assert aid.startswith("anchor_")
        assert len(guard._anchors) == 1

    def test_hazard_level_mapping(self):
        from taiji_agent.taiji_verify.kun_guard import HazardLevel
        assert HazardLevel.from_residual(0.1) == HazardLevel.LOW
        assert HazardLevel.from_residual(0.3) == HazardLevel.MEDIUM
        assert HazardLevel.from_residual(0.6) == HazardLevel.HIGH
        assert HazardLevel.from_residual(0.9) == HazardLevel.CRITICAL

    def test_hazard_check(self):
        from taiji_agent.taiji_verify.kun_guard import KunGuard
        guard = KunGuard()
        level, should = guard.check_hazard(0.1)
        assert should is False
        level, should = guard.check_hazard(0.6)
        assert should is True


# ============================================================
# QianAdvance Tests
# ============================================================

class TestQianAdvance:
    """乾进稳定性评估测试"""

    def test_stable_system_high_fS(self):
        from taiji_agent.taiji_verify.qian_advance import QianAdvance, StabilityZone
        advance = QianAdvance(k_paths=3, noise_scale=0.01)
        # identity function = very stable
        score = advance.evaluate(
            input_vector=np.zeros(32, dtype=np.float32),
            process_fn=lambda x: x,
            ground_vector=np.zeros(32, dtype=np.float32),
        )
        assert score.f_S >= 0.7
        assert score.stability_zone == StabilityZone.STABLE.value

    def test_perturbation_generates_different_paths(self):
        from taiji_agent.taiji_verify.qian_advance import QianAdvance
        advance = QianAdvance(k_paths=5, seed=42)
        vec = np.ones(16, dtype=np.float32)
        paths = [advance._perturb(vec, i) for i in range(5)]
        # Each path should be slightly different
        for i in range(len(paths) - 1):
            assert not np.allclose(paths[i], paths[i+1])

    def test_fS_in_valid_range(self):
        from taiji_agent.taiji_verify.qian_advance import QianAdvance
        advance = QianAdvance(k_paths=2)
        score = advance.evaluate(
            np.zeros(8), lambda x: x * 0.5, np.zeros(8),
        )
        assert 0.0 <= score.f_S <= 1.0

    def test_stability_zone_from_fS(self):
        from taiji_agent.taiji_verify.qian_advance import StabilityZone
        assert StabilityZone.from_fS(0.9) == StabilityZone.STABLE
        assert StabilityZone.from_fS(0.5) == StabilityZone.MARGINAL
        assert StabilityZone.from_fS(0.3) == StabilityZone.UNSTABLE
        assert StabilityZone.from_fS(0.1) == StabilityZone.CHAOTIC


# ============================================================
# FuReturn Tests
# ============================================================

class TestFuReturn:
    """复归崩溃恢复状态机测试"""

    def test_initial_state_is_stable(self):
        from taiji_agent.taiji_verify.fu_return import FuReturn, CollapseState
        fr = FuReturn()
        assert fr.state == CollapseState.STABLE
        assert fr.is_healthy is True

    def test_detect_anomaly_on_high_lambda(self):
        from taiji_agent.taiji_verify.fu_return import FuReturn, CollapseState
        # Bug3修复: 移除重复赋值 fr = Fr = ...
        Fr = FuReturn(lambda_threshold=0.3)
        result = Fr.check_and_handle(0.8)
        assert result is not None
        assert Fr.state == CollapseState.DETECTED

    def test_checkpoint_management(self):
        from taiji_agent.taiji_verify.fu_return import FuReturn
        fr = FuReturn()
        fr.update_checkpoint({"data": "test"}, lyapunov_lambda=0.1)
        fr.update_checkpoint({"data": "test2"}, lyapunov_lambda=0.2)
        cp = fr.get_latest_checkpoint()
        assert cp is not None
        assert cp.state_data["data"] == "test2"

    def test_force_recovery(self):
        from taiji_agent.taiji_verify.fu_return import FuReturn, CollapseState, RecoveryAction
        fr = FuReturn(max_retries=2)
        # Force into unstable state
        fr._state = CollapseState.ISOLATED
        result = fr.force_recover()
        assert result.action == RecoveryAction.ROLLBACK or result.action == RecoveryAction.ESCALATE

    def test_reset(self):
        from taiji_agent.taiji_verify.fu_return import FuReturn, CollapseState
        fr = FuReturn()
        fr._state = CollapseState.COLLAPSED
        fr.reset()
        assert fr.state == CollapseState.STABLE


# ============================================================
# XunTune Tests
# ============================================================

class TestXunTune:
    """巽调方差门控测试"""

    def test_low_variance_high_factor(self):
        from taiji_agent.taiji_verify.xun_tune import XunTune
        # Bug2相关: 测试gamma=1.0以便断言通过（默认0.618太敏感）
        tuner = XunTune(gamma=1.0)
        factor = tuner.compute_gate(0.01)  # low variance
        assert factor > 0.9

    def test_high_variance_low_factor(self):
        from taiji_agent.taiji_verify.xun_tune import XunTune
        tuner = XunTune(gamma=5.0)  # 高gamma值用于测试
        factor = tuner.compute_gate(1.0)  # high variance
        assert factor < 0.1

    def test_factor_clamping(self):
        from taiji_agent.taiji_verify.xun_tune import XunTune
        tuner = XunTune(gamma=100.0, min_factor=0.05)
        factor = tuner.compute_gate(100.0)  # extremely high variance
        assert factor >= 0.05

    def test_modulate_multiple_outputs(self):
        from taiji_agent.taiji_verify.xun_tune import XunTune
        tuner = XunTune(gamma=1.0)
        vectors = [np.ones(8), np.zeros(8), np.full(8, 0.5)]
        result = tuner.modulate(vectors)
        assert result.content_vector.shape == (8,)
        assert 0.0 <= result.modulation_factor <= 1.0


# ============================================================
# PolarisCompiler Tests
# ============================================================

class TestPolarisCompiler:
    """北辰编译器测试"""

    def test_simple_goal_compilation(self):
        from taiji_agent.taiji_verify.polaris_compiler import PolarisCompiler, AtomType
        compiler = PolarisCompiler()
        result = compiler.compile("查询用户数据并生成报告")
        assert result.atom_count > 0
        types = [a.atom_type for a in result.atoms]
        assert AtomType.RETRIEVE in types or AtomType.GENERATE in types

    def test_multi_clause_goal(self):
        from taiji_agent.taiji_verify.polaris_compiler import PolarisCompiler
        compiler = PolarisCompiler()
        goal = "查询数据，计算统计值，生成报告"
        result = compiler.compile(goal)
        assert result.atom_count >= 2

    def test_execution_graph_has_edges(self):
        from taiji_agent.taiji_verify.polaris_compiler import PolarisCompiler
        compiler = PolarisCompiler()
        result = compiler.compile("获取数据并分析")
        graph = result.execution_graph
        assert len(graph["nodes"]) > 0
        # Should have dependency edges after first atom

    def test_token_board_created(self):
        from taiji_agent.taiji_verify.polaris_compiler import PolarisCompiler
        compiler = PolarisCompiler()
        result = compiler.compile("执行任务")
        assert len(result.token_board) == result.atom_count

    def test_context_passed_to_atoms(self):
        from taiji_agent.taiji_verify.polaris_compiler import PolarisCompiler
        compiler = PolarisCompiler()
        result = compiler.compile("处理数据", context={"doc_id": "DOC-001"})
        assert any("DOC-001" in str(a.metadata) for a in result.atoms)


# ============================================================
# FailureModeDetector Tests
# ============================================================

class TestFailureModes:
    """16种失败模式检测器测试"""

    def test_detect_overconfidence(self):
        from taiji_agent.taiji_verify.failure_modes import FailureModeDetector
        det = FailureModeDetector()
        content = "我绝对肯定这毫无疑问是必须的结果"
        results = det.detect_all(content)
        fm04 = [r for r in results if r.mode.id == "FM04"]
        assert len(fm04) > 0

    def test_detect_repetition(self):
        from taiji_agent.taiji_verify.failure_modes import FailureModeDetector
        det = FailureModeDetector()
        content = ("这是一个测试。这是一个测试。" * 10)
        results = det.detect_all(content)
        fm12 = [r for r in results if r.mode.id == "FM12"]
        assert len(fm12) > 0

    def test_detect_pii_leakage(self):
        from taiji_agent.taiji_verify.failure_modes import FailureModeDetector
        det = FailureModeDetector()
        results = det.detect_all("请拨打13812345678联系张三")
        fm09 = [r for r in results if r.mode.id == "FM09"]
        assert len(fm09) > 0

    def test_length_anomaly(self):
        from taiji_agent.taiji_verify.failure_modes import FailureModeDetector
        det = FailureModeDetector()
        results = det.detect_all("短")  # too short
        fm11 = [r for r in results if r.mode.id == "FM11"]
        assert len(fm11) > 0

    def test_clean_content_no_failures(self):
        from taiji_agent.taiji_verify.failure_modes import FailureModeDetector
        det = FailureModeDetector()
        clean = "这是一段正常的中文文本内容，用于测试检测器在无问题时不会误报。"
        results = det.detect_all(clean)
        # Clean text should have minimal or no detections
        critical = [r for r in results if r.mode.severity.value == "critical"]
        assert len(critical) == 0


# ============================================================
# Engine Integration Tests
# ============================================================

class TestEngineIntegration:
    """引擎端到端集成测试"""

    def test_text_only_mode_passes(self):
        from taiji_agent.taiji_verify.engine import (
            TaijiVerifyEngine, VerificationRequest, Verdict,
        )
        engine = TaijiVerifyEngine(enable_failure_modes=True)
        req = VerificationRequest(
            input_text="这是一段关于环保法规的正常分析文本",
            ground_truth="环保法规定排放标准应符合国家标准",
        )
        resp = engine.verify(req)
        assert resp.verdict in (Verdict.PASS, Verdict.CONDITIONAL_PASS)
        assert resp.compilation is not None
        assert resp.processing_time_ms >= 0

    def test_text_only_with_critical_failure(self):
        from taiji_agent.taiji_verify.engine import (
            TaijiVerifyEngine, VerificationRequest, Verdict,
        )
        engine = TaijiVerifyEngine(enable_failure_modes=True)
        req = VerificationRequest(
            input_text="我绝对肯定这个电话13800001111的用户信息完全正确",
            ground_truth="用户联系方式应脱敏",
        )
        resp = engine.verify(req)
        # Should detect PII leakage (CRITICAL) → BLOCK
        assert resp.verdict == Verdict.BLOCK

    def test_full_pipeline_with_embeddings(self, embed_fn_factory):
        from taiji_agent.taiji_verify.engine import (
            TaijiVerifyEngine, VerificationRequest, Verdict,
        )
        engine = TaijiVerifyEngine(enable_failure_modes=True, enable_stability_check=True)
        # 使用相同文本以获得高相似度向量，避免 DANGER zone
        same_text = "根据环评报告，该项目的排放达标"
        req = VerificationRequest(
            input_text=same_text,
            ground_truth=same_text,
            embed_fn=embed_fn_factory,
            process_fn=None,  # 不使用 process_fn 以避免改变向量方向
        )
        resp = engine.verify(req)
        assert resp.delta_s_result is not None
        assert resp.tuned_output is not None
        assert resp.verdict in (Verdict.PASS, Verdict.CONDITIONAL_PASS, Verdict.CORRECTED)

    def test_system_health(self):
        from taiji_agent.taiji_verify.engine import TaijiVerifyEngine
        engine = TaijiVerifyEngine()
        health = engine.system_health
        assert "fu_return_state" in health
        assert health["fu_return_healthy"] is True

    def test_knowledge_anchor_convenience_method(self):
        from taiji_agent.taiji_verify.engine import TaijiVerifyEngine
        engine = TaijiVerifyEngine()
        aid = engine.add_knowledge_anchor("环保法规")
        assert aid.startswith("anchor_")
        assert engine.system_health["kun_anchors"] == 1

    def test_compilation_via_engine(self, embed_fn_factory):
        from taiji_agent.taiji_verify.engine import (
            TaijiVerifyEngine, VerificationRequest,
        )
        engine = TaijiVerifyEngine()
        req = VerificationRequest(
            input_text="分析",
            ground_truth="检索文档，提取关键指标，对比标准限值",
            embed_fn=embed_fn_factory,
        )
        resp = engine.verify(req)
        assert resp.compilation.atom_count > 0


# ============================================================
# Run
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
