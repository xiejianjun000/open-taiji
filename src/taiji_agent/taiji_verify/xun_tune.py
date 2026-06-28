"""
Xun Tune (巽调 / BBAM - Bearing Balance Attention Modulation)
方差门控注意力调节模块

核心公式: factor = exp(-gamma * sigma^2)
其中 sigma = 输出分布的标准差
      gamma = 敏感度系数（默认0.618 - 太极黄金比例）
      factor ∈ (0, 1] 为注意力调制因子

当输出方差大时（模型不确定），factor趋近0，降低该输出的注意力权重。
当输出方差小时（模型确定），factor接近1，保持原有注意力。

数据来源：基于同规模政务系统的性能基线
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class AttentionModulation:
    """单次注意力调节结果"""
    original_weights: np.ndarray
    modulated_weights: np.ndarray
    gate_factor: float
    variance: float
    metadata: dict = field(default_factory=dict)


@dataclass
class TunedOutput:
    """巽调后的完整输出"""
    content_vector: np.ndarray
    attention_weights: np.ndarray
    modulation_factor: float
    confidence_adjusted: bool
    metadata: dict = field(default_factory=dict)


class XunTune:
    """
    巽调 - 方差门控注意力调节器

    Usage::
        tuner = XunTune(gamma=0.618)
        result = tuner.modulate(
            output_vectors=layer_outputs,
            attention_weights=original_attn,
        )
        print(result.modulation_factor, result.confidence_adjusted)
    """

    def __init__(self, gamma: float = 0.618, min_factor: float = 0.05):
        """
        Args:
            gamma: 敏感度系数（默认0.618太极黄金比例），越大对方差越敏感
            min_factor: 最小门控因子下限，防止完全抑制
        """
        self.gamma = gamma
        self.min_factor = min_factor

    def compute_gate(self, variance: float) -> float:
        """
        计算方差门控 factor = exp(-gamma * sigma^2)

        Args:
            variance: 输出的方差值 σ²

        Returns:
            门控因子 ∈ [min_factor, 1.0]
        """
        factor = math.exp(-self.gamma * variance)
        return max(self.min_factor, min(1.0, factor))

    def modulate(
        self,
        output_vectors: list[np.ndarray],
        attention_weights: Optional[np.ndarray] = None,
    ) -> TunedOutput:
        """
        对多个输出向量进行方差门控注意力调节

        Args:
            output_vectors: 多个输出层的向量列表（如LLM各层输出）
            attention_weights: 原始注意力权重矩阵

        Returns:
            TunedOutput 调节后的结果
        """
        if not output_vectors:
            raise ValueError("output_vectors cannot be empty")

        # 计算每个向量的方差
        variances = []
        for vec in output_vectors:
            v = float(np.var(vec))
            variances.append(v)

        avg_var = sum(variances) / len(variances)

        # 门控因子
        gate = self.compute_gate(avg_var)

        # 如果有注意力权重，应用门控调制
        if attention_weights is not None:
            modulated = attention_weights * gate
        else:
            modulated = np.ones(len(output_vectors)) * gate

        # 加权融合所有输出向量
        if len(output_vectors) == 1:
            fused = output_vectors[0] * gate
        else:
            weights = modulated if len(modulated) == len(output_vectors) else np.ones(len(output_vectors))
            weights = weights / (weights.sum() + 1e-10)
            fused = sum(w * v for w, v in zip(weights, output_vectors))

        return TunedOutput(
            content_vector=fused,
            attention_weights=modulated,
            modulation_factor=gate,
            confidence_adjusted=gate < 0.7,
            metadata={
                'variance_per_output': variances,
                'average_variance': avg_var,
                'gamma': self.gamma,
            },
        )

    def modulate_single(self, vector: np.ndarray) -> AttentionModulation:
        """对单个向量计算门控并返回原始/调节后对比"""
        var = float(np.var(vector))
        gate = self.compute_gate(var)

        return AttentionModulation(
            original_weights=np.ones_like(vector),
            modulated_weights=np.ones_like(vector) * gate,
            gate_factor=gate,
            variance=var,
        )
