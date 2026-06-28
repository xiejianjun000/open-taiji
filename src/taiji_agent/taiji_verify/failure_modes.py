"""Failure Mode Detector - 16种失败模式检测器"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class FailureSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class FailureMode:
    id: str
    name: str
    name_cn: str
    severity: FailureSeverity
    category: str
    detection_fn_name: str
    remediation: str

# 16种失败模式定义
FAILURE_MODES: list[FailureMode] = [
    FailureMode("FM01", "Hallucination", "幻觉生成", FailureSeverity.CRITICAL, "factuality",
        "detect_hallucination", "触发坤守残差修正，若ΔS>0.7则拦截并重写"),
    FailureMode("FM02", "FactConflicting", "事实冲突", FailureSeverity.ERROR, "consistency",
        "detect_fact_conflict", "标记冲突点，要求模型重新检索知识库后回答"),
    FailureMode("FM03", "ContextDrift", "上下文漂移", FailureSeverity.WARNING, "coherence",
        "detect_context_drift", "插入上下文锚定提示词，重新聚焦"),
    FailureMode("FM04", "OverConfidence", "过度自信", FailureSeverity.WARNING, "calibration",
        "detect_overconfidence", "添加不确定性声明要求"),
    FailureMode("FM05", "KnowledgeGap", "知识缺口", FailureSeverity.ERROR, "completeness",
        "detect_knowledge_gap", "补充相关知识库条目后重试"),
    FailureMode("FM06", "InstructionIgnored", "指令忽略", FailureSeverity.ERROR, "obedience",
        "detect_instruction_ignored", "强化系统提示词，增加格式约束"),
    FailureMode("FM07", "FormatViolation", "格式违规", FailureSeverity.WARNING, "format",
        "detect_format_violation", "提供输出模板示例"),
    FailureMode("FM08", "ToxicContent", "有害内容", FailureSeverity.CRITICAL, "safety",
        "detect_toxic_content", "立即拦截，返回安全替代回复"),
    FailureMode("FM09", "PIILeakage", "隐私泄露", FailureSeverity.CRITICAL, "privacy",
        "detect_pii_leakage", "脱敏处理后重新生成"),
    FailureMode("FM10", "CircularReasoning", "循环推理", FailureSeverity.ERROR, "logic",
        "detect_circular_reasoning", "打断循环链，提供外部事实基准"),
    FailureMode("FM11", "LengthAnomaly", "长度异常", FailureSeverity.INFO, "quality",
        "detect_length_anomaly", "调整生成长度约束"),
    FailureMode("FM12", "RepetitionExcess", "重复过多", FailureSeverity.WARNING, "quality",
        "detect_repetition_excess", "启用去重过滤"),
    FailureMode("FM13", "LanguageInconsistency", "语言不一致", FailureSeverity.INFO, "format",
        "detect_language_inconsistency", "锁定输出语言设置"),
    FailureMode("FM14", "TemporalConfusion", "时序混乱", FailureSeverity.ERROR, "temporal",
        "detect_temporal_confusion", "注入时间线上下文"),
    FailureMode("FM15", "NumericalError", "数值错误", FailureSeverity.ERROR, "accuracy",
        "detect_numerical_error", "触发计算器工具验证"),
    FailureMode("FM16", "CitationMissing", "引用缺失", FailureSeverity.WARNING, "grounding",
        "detect_citation_missing", "强制要求引用来源"),
]

@dataclass
class FailureDetection:
    mode: FailureMode
    detected: bool
    confidence: float
    details: str = ""
    location: str = ""

class FailureModeDetector:
    """16模式失败检测器"""
    
    def __init__(self):
        self._modes = {m.id: m for m in FAILURE_MODES}
    
    def detect_all(self, content: str, delta_s: float = 0.0) -> list[FailureDetection]:
        results = []
        detectors = {
            "FM01": lambda: self.detect_hallucination(content, delta_s),
            "FM02": lambda: self.detect_fact_conflict(content),
            "FM03": lambda: self.detect_context_drift(content),
            "FM04": lambda: self.detect_overconfidence(content),
            "FM05": lambda: self.detect_knowledge_gap(content),
            "FM06": lambda: self.detect_instruction_ignored(content),
            "FM07": lambda: self.detect_format_violation(content),
            "FM08": lambda: self.detect_toxic_content(content),
            "FM09": lambda: self.detect_pii_leakage(content),
            "FM10": lambda: self.detect_circular_reasoning(content),
            "FM11": lambda: self.detect_length_anomaly(content),
            "FM12": lambda: self.detect_repetition_excess(content),
            "FM13": lambda: self.detect_language_inconsistency(content),
            "FM14": lambda: self.detect_temporal_confusion(content),
            "FM15": lambda: self.detect_numerical_error(content),
            "FM16": lambda: self.detect_citation_missing(content),
        }
        for fm_id, detector in detectors.items():
            try:
                det = detector()
                results.append(det)
            except Exception:
                pass
        return [r for r in results if r.detected]

    # --- 各检测方法的简化实现 ---
    def detect_hallucination(self, content: str, delta_s: float) -> FailureDetection:
        return FailureDetection(self._modes["FM01"], delta_s > 0.7, min(delta_s / 1.0, 1.0), f"delta_s={delta_s:.3f}")
    def detect_fact_conflict(self, content: str) -> FailureDetection:
        has_contradiction = bool(len(content) > 200 and ("但是" in content or "然而" in content))
        return FailureDetection(self._modes["FM02"], has_contradiction, 0.5 if has_contradiction else 0.0)
    def detect_context_drift(self, content: str) -> FailureDetection:
        return FailureDetection(self._modes["FM03"], False, 0.0)
    def detect_overconfidence(self, content: str) -> FailureDetection:
        keywords = ["肯定", "绝对", "一定", "毫无疑问", "必须"]
        count = sum(1 for k in keywords if k in content)
        return FailureDetection(self._modes["FM04"], count >= 3, min(count * 0.2, 1.0))
    def detect_knowledge_gap(self, content: str) -> FailureDetection:
        uncertain = ["不确定", "不清楚", "可能", "大概", "也许", "不太了解"]
        count = sum(1 for k in uncertain if k in content)
        return FailureDetection(self._modes["FM05"], count >= 2, min(count * 0.25, 1.0))
    def detect_instruction_ignored(self, content: str) -> FailureDetection:
        return FailureDetection(self._modes["FM06"], False, 0.0)
    def detect_format_violation(self, content: str) -> FailureDetection:
        lines = content.strip().split("\n")
        has_structure = any(l.strip().startswith(("- ", "* ", "# ", "1.", "|")) for l in lines)
        return FailureDetection(self._modes["FM07"], not has_structure and len(lines) < 3, 0.3)
    def detect_toxic_content(self, content: str) -> FailureDetection:
        toxic = []  # 实际部署时应使用完整敏感词库
        return FailureDetection(self._modes["FM08"], False, 0.0)
    def detect_pii_leakage(self, content: str) -> FailureDetection:
        import re
        phone = re.findall(r'1[3-9]\d{9}', content)
        email = re.findall(r'[\w.-]+@[\w.-]+\.\w+', content)
        has_pii = len(phone) + len(email) > 0
        return FailureDetection(self._modes["FM09"], has_pii, 1.0 if has_pii else 0.0)
    def detect_circular_reasoning(self, content: str) -> FailureDetection:
        sentences = content.replace("。", ".").split(".")
        repeated = len(sentences) != len(set(s.strip() for s in sentences if len(s.strip()) > 5))
        return FailureDetection(self._modes["FM10"], repeated and len(sentences) >= 4, 0.4 if repeated else 0.0)
    def detect_length_anomaly(self, content: str) -> FailureDetection:
        length = len(content)
        anomalous = length < 20 or length > 10000
        return FailureDetection(self._modes["FM11"], anomalous, 0.7 if anomalous else 0.0, f"length={length}")
    def detect_repetition_excess(self, content: str) -> FailureDetection:
        # 支持中文和英文重复检测
        import re
        # 句子级别重复检测（按句号/逗号/换行分割）
        sentences = re.split(r'[。！？\n]+', content)
        sentences = [s.strip() for s in sentences if s.strip()]
        if len(sentences) >= 4:
            unique_sentences = set(sentences)
            sentence_ratio = len(unique_sentences) / len(sentences)
            if sentence_ratio < 0.5:  # 超过一半的句子重复
                return FailureDetection(self._modes["FM12"], True, 1.0 - sentence_ratio, f"repeated_sentences={len(sentences) - len(unique_sentences)}")
        
        # 词语级别重复检测（支持中英文分词）
        if ' ' in content:
            words = content.split()
        else:
            # 中文字符级别重复检测（每2-4个字符作为词组）
            words = [content[i:i+3] for i in range(0, min(len(content)-2, 30), 3)]
        
        if len(words) < 10:
            return FailureDetection(self._modes["FM12"], False, 0.0)
        
        ratio = len(set(words)) / len(words)
        return FailureDetection(self._modes["FM12"], ratio < 0.5, 1.0 - ratio, f"unique_ratio={ratio:.2f}")
    def detect_language_inconsistency(self, content: str) -> FailureDetection:
        import re
        has_cn = bool(re.search(r'[\u4e00-\u9fff]', content))
        has_en = bool(re.search(r'[a-zA-Z]{3,}', content))
        return FailureDetection(self._modes["FM13"], has_cn and has_en, 0.4)
    def detect_temporal_confusion(self, content: str) -> FailureDetection:
        return FailureDetection(self._modes["FM14"], False, 0.0)
    def detect_numerical_error(self, content: str) -> FailureDetection:
        import re
        numbers = re.findall(r'\d+(?:\.\d+)?(?:%?)', content)
        suspicious = any(float(n) > 10000 or float(n) < 0 for n in numbers if n.replace("%",""))
        return FailureDetection(self._modes["FM15"], suspicious, 0.5 if suspicious else 0.0)
    def detect_citation_missing(self, content: str) -> FailureDetection:
        import re
        has_citation = bool(re.search(r'\[.*?\]|（[^）]+）|\([^)]+\)', content))
        return FailureDetection(self._modes["FM16"], not has_citation and len(content) > 200, 0.3)
