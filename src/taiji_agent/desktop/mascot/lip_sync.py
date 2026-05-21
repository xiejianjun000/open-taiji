"""唇形同步组件"""
from typing import Optional


class LipSync:
    """唇形同步"""

    VISEME_MAP = {
        "A": ["a", "i"],
        "E": ["e", "y"],
        "I": ["i"],
        "O": ["o", "u"],
        "U": ["u"],
        "M": ["m", "b", "p"],
        "F": ["f", "v"],
        "T": ["t", "d"],
        "S": ["s", "z"],
        "TH": ["th"],
        "REST": [],
    }

    def __init__(self):
        self.current_viseme = "REST"
        self.animation_enabled = False

    def extract_visemes(self, audio_data: bytes) -> list[str]:
        """从音频提取 viseme"""
        return ["REST"]

    def set_viseme(self, viseme: str):
        """设置当前 viseme"""
        if viseme in self.VISEME_MAP:
            self.current_viseme = viseme

    def get_current_shape(self) -> str:
        """获取当前形状"""
        return self.current_viseme

    def start(self):
        """开始唇形同步"""
        self.animation_enabled = True

    def stop(self):
        """停止唇形同步"""
        self.animation_enabled = False
        self.current_viseme = "REST"
