"""
DeltaS (阴阳距) - Taiji Verify 核心计算模块

数学定义: ΔS = 1 - cos(I, G)
其中 I = 输入向量(Embedding of input text)
      G = 知识向量(Embedding of ground truth / knowledge base)

闸区体系:
- safe (<0.4): 安全区，输出可信
- transit (0.4-0.6): 过渡区，需要关注
- risk (0.6-0.85): 风险区，建议修正
- danger (>=0.85): 危险区，必须拦截

数据来源：基于阶段一基线数据推算与行业同类系统对标
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np
from numpy.linalg import norm


class GateZone(str, Enum):
    """阴阳距闸区"""
    SAFE = "safe"           # < 0.40
    TRANSIT = "transit"     # 0.40 - 0.60
    RISK = "risk"           # 0.60 - 0.85
    DANGER = "danger"       # >= 0.85

    @classmethod
    def from_delta(cls, delta_s: float) -> GateZone:
        """根据ΔS值返回对应闸区"""
        if delta_s < 0.40:
            return cls.SAFE
        elif delta_s < 0.60:
            return cls.TRANSIT
        elif delta_s < 0.85:
            return cls.RISK
        else:
            return cls.DANGER


@dataclass
class DeltaSResult:
    """ΔS计算结果"""
    delta_s: float
    zone: GateZone
    cosine_similarity: float
    input_vector: Optional[np.ndarray] = None
    ground_vector: Optional[np.ndarray] = None
    anchor_extensions: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def is_safe(self) -> bool:
        return self.zone in (GateZone.SAFE, GateZone.TRANSIT)

    @property
    def needs_correction(self) -> bool:
        return self.zone in (GateZone.RISK, GateZone.DANGER)


@dataclass
class AnchorExtension:
    """锚点扩展配置"""
    source_text: str
    weight: float = 1.0
    vector: Optional[np.ndarray] = None


class DeltaSCalculator:
    """
    阴阳距离计算器

    Usage::
        calc = DeltaSCalculator(embedding_dim=768)
        result = calc.compute(
            input_text="LLM生成的回答",
            ground_truth="基于事实的正确答案",
            embedding_fn=my_embedder,
        )
        print(result.delta_s, result.zone)  # 0.15 safe
    """

    def __init__(
        self,
        embedding_dim: int = 768,
        safe_threshold: float = 0.40,
        transit_threshold: float = 0.60,
        risk_threshold: float = 0.85,
    ):
        self.embedding_dim = embedding_dim
        self._thresholds = {
            'safe': safe_threshold,
            'transit': transit_threshold,
            'risk': risk_threshold,
        }
        self._anchor_extensions: list[AnchorExtension] = []

    def add_anchor(self, source_text: str, weight: float = 1.0):
        """添加锚点扩展（补充知识源）"""
        ext = AnchorExtension(source_text=source_text, weight=weight)
        self._anchor_extensions.append(ext)

    def clear_anchors(self):
        """清除所有锚点扩展"""
        self._anchor_extensions.clear()

    def compute(
        self,
        input_vector: np.ndarray,
        ground_vector: np.ndarray,
        anchor_vectors: Optional[list[np.ndarray]] = None,
    ) -> DeltaSResult:
        """
        计算阴阳距离 ΔS = 1 - cos(I, G')

        其中 G' 是 G 与所有锚点向量的加权融合:
          G' = normalize(G + sum(w_i * A_i))
        """
        # 基础余弦相似度
        cos_sim = self._cosine_similarity(input_vector, ground_vector)

        # 锚点扩展融合
        effective_ground = ground_vector.copy()
        if anchor_vectors:
            for i, av in enumerate(anchor_vectors):
                w = self._anchor_extensions[i].weight if i < len(self._anchor_extensions) else 1.0
                effective_ground = effective_ground + w * av
        elif self._anchor_extensions:
            for ext in self._anchor_extensions:
                if ext.vector is not None:
                    effective_ground = effective_ground + ext.weight * ext.vector

        # 归一化后的有效知识向量
        norm_eff = norm(effective_ground)
        if norm_eff > 1e-10:
            effective_ground = effective_ground / norm_eff

        # 最终余弦相似度和阴阳距
        final_cos_sim = self._cosine_similarity(input_vector, effective_ground)
        delta_s = 1.0 - final_cos_sim
        delta_s = max(0.0, min(1.0, delta_s))  # clamp to [0, 1]

        zone = GateZone.from_delta(delta_s)

        return DeltaSResult(
            delta_s=delta_s,
            zone=zone,
            cosine_similarity=final_cos_sim,
            input_vector=input_vector,
            ground_vector=effective_ground,
            anchor_extensions=[
                {'source': a.source_text, 'weight': a.weight}
                for a in self._anchor_extensions
            ],
        )

    def compute_batch(
        self,
        input_vectors: list[np.ndarray],
        ground_vector: np.ndarray,
    ) -> list[DeltaSResult]:
        """批量计算多个输入的ΔS"""
        return [self.compute(iv, ground_vector) for iv in input_vectors]

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """计算两个向量的余弦相似度"""
        norm_a, norm_b = norm(a), norm(b)
        if norm_a < 1e-10 or norm_b < 1e-10:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def compute_from_texts(
        self,
        input_text: str,
        ground_truth: str,
        embed_fn,  # callable: str -> np.ndarray
    ) -> DeltaSResult:
        """从文本直接计算（需要提供embedding函数）"""
        input_vec = embed_fn(input_text)
        ground_vec = embed_fn(ground_truth)
        
        # 处理锚点
        anchor_vecs = []
        for ext in self._anchor_extensions:
            ext.vector = embed_fn(ext.source_text)
            anchor_vecs.append(ext.vector)

        return self.compute(input_vec, ground_vec, anchor_vecs)
