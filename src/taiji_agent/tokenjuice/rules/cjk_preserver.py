"""CJK 字符保留规则"""
import re


CJK_RANGES = [
    (0x4E00, 0x9FFF),   # 中文
    (0x3040, 0x309F),   # 日文平假名
    (0x30A0, 0x30FF),   # 日文片假名
    (0xAC00, 0xD7AF),   # 韩文
]


def is_cjk(char: str) -> bool:
    """检查字符是否为 CJK"""
    if not char:
        return False
    code = ord(char)
    return any(start <= code <= end for start, end in CJK_RANGES)


def preserve_cjk(text: str) -> str:
    """
    保留 CJK 字符，逐字保留

    Args:
        text: 原始文本

    Returns:
        str: CJK 字符被保留的文本
    """
    if not text:
        return ""

    result = []
    for char in text:
        if is_cjk(char):
            result.append(char)
        else:
            result.append(char)
    return "".join(result)
