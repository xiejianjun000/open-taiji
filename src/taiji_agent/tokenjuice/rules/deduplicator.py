"""内容去重规则"""
from typing import Set


def deduplicate(text: str, similarity_threshold: float = 0.85) -> str:
    """
    去除重复内容

    Args:
        text: 原始文本
        similarity_threshold: 相似度阈值 (0-1)

    Returns:
        str: 去重后的文本
    """
    if not text:
        return ""

    lines = text.split("\n")
    seen: Set[str] = set()
    result_lines: list[str] = []

    for line in lines:
        normalized = normalize_line(line)
        if not normalized:
            continue

        is_duplicate = False
        for seen_line in seen:
            if similarity(normalized, seen_line) >= similarity_threshold:
                is_duplicate = True
                break

        if not is_duplicate:
            seen.add(normalized)
            result_lines.append(line)

    return "\n".join(result_lines)


def normalize_line(line: str) -> str:
    """标准化行文本"""
    return " ".join(line.lower().split())


def similarity(s1: str, s2: str) -> float:
    """计算两个字符串的相似度"""
    if not s1 or not s2:
        return 0.0

    s1_set = set(s1)
    s2_set = set(s2)

    intersection = len(s1_set & s2_set)
    union = len(s1_set | s2_set)

    if union == 0:
        return 0.0

    return intersection / union
