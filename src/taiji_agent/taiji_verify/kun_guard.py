"""
Kun Guard (坤守 / BBMC - Bias-Bound Minimization Correction)
语义残差修正模块

数学模型: B = I - G + m*c^2
其中 B = 残差向量(需要修正的偏差)
      I = 输入向量
      G = 知识向量  
      m = 残差质量因子
      c = 上下文约束系数

残差阈值:
- low (<0.2): 轻微偏差，可接受
- medium (0.2-0.5): 中等偏差，建议修正
- high (>0.5): 严重偏差，必须拦截

数据来源：基于阶段一小规模实验数据的专家预估值
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable

import numpy as np
from numpy.linalg import norm


class HazardLevel(str, Enum):
    """残差危害等级"""
    LOW = "low"           # < 0.2
    MEDIUM = "medium"     # 0.2 - 0.5
    HIGH = "high"         # > 0.5
    CRITICAL = "critical" # > 0.8

    @classmethod
    def from_residual(cls, magnitude: float) -> HazardLevel:
        if magnitude < 0.2:
            return cls.LOW
        elif magnitude < 0.5:
            return cls.MEDIUM
        elif magnitude < 0.8:
            return cls.HIGH
        else:
            return cls.CRITICAL


@dataclass
class ResidualCorrection:
    """残差修正结果"""
    original_vector: np.ndarray
    corrected_vector: np.ndarray
    residual_magnitude: float
    hazard_level: HazardLevel
    correction_applied: bool
    corrections: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class KnowledgeAnchor:
    """知识锚点"""
    id: str
    content: str
    vector: Optional[np.ndarray] = None
    source: str = ""
    confidence: float = 1.0


class KunGuard:
    """
    坤守 - 语义残差修正器

    检测LLM输出与知识基准之间的语义偏差，并投影到最小化残差的超平面上。

    Usage::
        guard = KunGuard(embedding_dim=768)
        guard.add_knowledge_anchor("法规条款", vector=law_vec)
        result = guard.correct(input_vector, ground_vector)
        if result.hazard_level != HazardLevel.LOW:
            print(result.corrected_vector)  # 使用修正后的向量
    """

    def __init__(
        self,
        embedding_dim: int = 768,
        residual_threshold_low: float = 0.2,
        residual_threshold_high: float = 0.5,
        max_correction_iterations: int = 3,
    ):
        self.embedding_dim = embedding_dim
        self.residual_threshold_low = residual_threshold_low
        self.residual_threshold_high = residual_threshold_high
        self.max_iterations = max_correction_iterations
        self._anchors: list[KnowledgeAnchor] = []
        self._vector_db: list[tuple[np.ndarray, KnowledgeAnchor]] = []

    def add_knowledge_anchor(
        self,
        content: str,
        vector: Optional[np.ndarray] = None,
        source: str = "",
        confidence: float = 1.0,
    ) -> str:
        """添加知识锚点（用于残差投影）"""
        anchor_id = f"anchor_{len(self._anchors)}"
        anchor = KnowledgeAnchor(
            id=anchor_id,
            content=content,
            vector=vector,
            source=source,
            confidence=confidence,
        )
        self._anchors.append(anchor)
        if vector is not None:
            self._vector_db.append((vector, anchor))
        return anchor_id

    def correct(
        self,
        input_vector: np.ndarray,
        ground_vector: np.ndarray,
        context_factor: float = 1.0,
    ) -> ResidualCorrection:
        """
        执行残差修正 B = I - G + m*c^2

        Args:
            input_vector: LLM输出的embedding向量
            ground_vector: 知识基准的embedding向量
            context_factor: 上下文约束系数c，默认1.0

        Returns:
            ResidualCorrection 包含修正后向量和危害等级
        """
        # 计算原始残差
        residual = input_vector - ground_vector
        residual_mag = norm(residual)

        # 质量因子 m: 基于残差方向的异常程度
        m = self._compute_quality_factor(residual)

        # 上下文约束修正项: m * c^2
        constraint_term = m * (context_factor ** 2)

        # 投影到知识超平面上的最近点
        corrected = ground_vector + residual * min(1.0, constraint_term)

        # 如果有向量数据库锚点，做二次投影
        if self._vector_db:
            corrected = self._project_to_anchors(corrected, residual)

        hazard = HazardLevel.from_residual(residual_mag)
        needs_correction = hazard in (HazardLevel.MEDIUM, HazardLevel.HIGH, HazardLevel.CRITICAL)

        corrections = [{
            'type': 'residual_projection',
            'original_magnitude': float(residual_mag),
            'quality_factor': float(m),
            'context_factor': context_factor,
            'hazard': hazard.value,
        }]

        return ResidualCorrection(
            original_vector=input_vector.copy(),
            corrected_vector=corrected,
            residual_magnitude=float(residual_mag),
            hazard_level=hazard,
            correction_applied=needs_correction,
            corrections=corrections,
        )

    def _compute_quality_factor(self, residual: np.ndarray) -> float:
        """
        计算残差质量因子 m
        
        基于残差向量的方向与标准正交基的偏离程度。
        方向越异常（与所有主成分都接近垂直），m值越小，
        表示这个偏差越可能是真正的错误而非正常变化。
        """
        res_norm = norm(residual)
        if res_norm < 1e-10:
            return 0.0

        # 简化模型：基于残差范数的非线性衰减
        # 当残差很小时，m接近1（保留大部分信息）
        # 当残差很大时，m趋近0（强烈压制偏差）
        m = math.exp(-res_norm)
        return float(m)

    def _project_to_anchors(
        self, 
        vector: np.ndarray, 
        residual: np.ndarray,
    ) -> np.ndarray:
        """将向量投影到最近的k个知识锚点的凸包上"""
        k = min(3, len(self._vector_db))

        # 计算与所有锚点的距离
        distances = []
        for anchor_vec, anchor in self._vector_db:
            dist = norm(vector - anchor_vec)
            distances.append((dist, anchor_vec, anchor.confidence))

        # 取最近的k个
        distances.sort(key=lambda x: x[0])
        nearest = distances[:k]

        # 加权平均作为投影目标
        total_weight = sum(conf for _, _, conf in nearest) + 1e-10
        target = sum(conf * vec for _, vec, conf in nearest) / total_weight

        # 线性插值：根据残差大小决定投影强度
        res_norm = norm(residual)
        alpha = min(0.5, res_norm * 0.3)

        return vector * (1 - alpha) + target * alpha

    def check_hazard(self, delta_s: float) -> tuple[HazardLevel, bool]:
        """快速检查ΔS对应的危害等级和是否需要拦截"""
        level = HazardLevel.from_residual(delta_s)
        should_block = level in (HazardLevel.HIGH, HazardLevel.CRITICAL)
        return level, should_block
