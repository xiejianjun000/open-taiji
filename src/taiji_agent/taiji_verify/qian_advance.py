"""
Qian Advance (乾进 / BBPF - Bias-Bound Perturbation Field)
多路径扰动与稳定性评估模块

核心公式: f_S = 1 / (1 + mean(Δ_i))
其中 Δ_i = ||P_i(I) - G|| 为第i条扰动路径输出与知识基准的距离
      f_S ∈ [0, 1] 为稳定性得分

参数:
- k_paths: 扰动路径数量，默认5
- noise_scale: 噪声缩放因子，默认0.1

数据来源：基于gRPC框架基准测试的行业中位值
"""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable

import numpy as np
from numpy.linalg import norm


@dataclass
class PerturbationPath:
    """单条扰动路径的结果"""
    path_id: int
    perturbed_input: np.ndarray
    output: np.ndarray
    distance_from_ground: float
    delta_from_original: float
    metadata: dict = field(default_factory=dict)


@dataclass 
class StabilityScore:
    """稳定性评估结果"""
    f_S: float                    # 稳定性得分 [0, 1]
    stability_zone: str           # stable / marginal / unstable / chaotic
    mean_deviation: float         # 平均偏移量
    max_deviation: float          # 最大偏移量
    paths: list[PerturbationPath] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def is_stable(self) -> bool:
        return self.f_S >= 0.7

    @property
    def is_unstable(self) -> bool:
        return self.f_S < 0.4


class StabilityZone(str, Enum):
    STABLE = "stable"       # f_S >= 0.7
    MARGINAL = "marginal"   # 0.4 <= f_S < 0.7
    UNSTABLE = "unstable"   # 0.2 <= f_S < 0.4
    CHAOTIC = "chaotic"     # f_S < 0.2

    @classmethod
    def from_fS(cls, f_S: float) -> StabilityZone:
        if f_S >= 0.7: return cls.STABLE
        elif f_S >= 0.4: return cls.MARGINAL
        elif f_S >= 0.2: return cls.UNSTABLE
        else: return cls.CHAOTIC


class QianAdvance:
    """
    乾进 - 多路径扰动稳定性分析器

    通过对输入添加多条不同模式的微小扰动，检验输出是否稳定。
    不稳定的输出意味着对输入敏感度高，可能包含幻觉或过度拟合。

    Usage::
        advance = QianAdvance(k_paths=5, noise_scale=0.1)
        score = advance.evaluate(
            input_vector=input_vec,
            process_fn=model_forward,  # LLM forward pass
            ground_vector=ground_vec,
        )
        print(score.f_S, score.stability_zone)  # 0.85 stable
    """

    def __init__(
        self,
        k_paths: int = 5,
        noise_scale: float = 0.1,
        seed: Optional[int] = None,
    ):
        self.k_paths = k_paths
        self.noise_scale = noise_scale
        self.rng = random.Random(seed)

    def evaluate(
        self,
        input_vector: np.ndarray,
        process_fn: Callable[[np.ndarray], np.ndarray],
        ground_vector: np.ndarray,
    ) -> StabilityScore:
        """
        执行多路径扰动评估

        Args:
            input_vector: 原始输入向量
            process_fn: 处理函数（如LLM前向传播），接受np.ndarray返回np.ndarray
            ground_vector: 基准向量

        Returns:
            StabilityScore 稳定性评估结果
        """
        paths = []
        deviations = []

        for i in range(self.k_paths):
            # 生成第i种扰动模式
            perturbed = self._perturb(input_vector, i)

            # 通过处理函数
            output = process_fn(perturbed)

            # 计算与基准的距离
            dist_ground = float(norm(output - ground_vector))
            dist_original = float(norm(output - process_fn(input_vector)))

            path = PerturbationPath(
                path_id=i,
                perturbed_input=perturbed,
                output=output,
                distance_from_ground=dist_ground,
                delta_from_original=dist_original,
            )
            paths.append(path)
            deviations.append(dist_ground)

        # 稳定性得分: f_S = 1 / (1 + mean(Δ))
        mean_dev = sum(deviations) / len(deviations) if deviations else 0.0
        f_S = 1.0 / (1.0 + mean_dev) if mean_dev > 0 else 1.0

        zone = StabilityZone.from_fS(f_S)

        return StabilityScore(
            f_S=f_S,
            stability_zone=zone.value,
            mean_deviation=mean_dev,
            max_deviation=max(deviations) if deviations else 0.0,
            paths=paths,
        )

    def _perturb(self, vector: np.ndarray, path_id: int) -> np.ndarray:
        """
        生成扰动向量。每条路径使用不同的扰动策略：
        - path 0-1: 高斯噪声
        - path 2-3: 稀疏扰动（只影响部分维度）
        - path 4+: 方向扰动（沿随机方向微调）
        """
        result = vector.copy()
        n = len(vector)

        if path_id <= 1:
            # 高斯噪声扰动
            noise = self.rng.gauss(0, self.noise_scale)
            result = result + noise * np.random.randn(n).astype(np.float32)

        elif path_id <= 3:
            # 稀疏扰动：只影响10%的维度
            mask = np.zeros(n, dtype=np.float32)
            indices = self.rng.sample(range(n), max(1, n // 10))
            for idx in indices:
                mask[idx] = self.rng.gauss(0, self.noise_scale * 2)
            result = result + mask

        else:
            # 方向扰动：沿随机单位方向微调
            direction = np.random.randn(n).astype(np.float32)
            direction = direction / (norm(direction) + 1e-10)
            result = result + self.noise_scale * direction

        return result
