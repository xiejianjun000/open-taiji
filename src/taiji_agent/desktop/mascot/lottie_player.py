"""Lottie 动画播放器"""
import json
from pathlib import Path
from typing import Optional


class LottiePlayer:
    """Lottie 动画播放器"""

    def __init__(self):
        self.animations: dict[str, dict] = {}
        self.current_animation: Optional[str] = None
        self.current_frame = 0

    def load_animation(self, name: str, path: Path):
        """加载动画"""
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.animations[name] = json.load(f)
            except Exception:
                pass

    def play(self, name: str):
        """播放动画"""
        if name in self.animations:
            self.current_animation = name
            self.current_frame = 0

    def get_frame(self, frame_number: int) -> Optional[dict]:
        """获取指定帧"""
        if not self.current_animation:
            return None

        animation = self.animations[self.current_animation]
        frames = animation.get("layers", [])

        if frames:
            return frames[frame_number % len(frames)]
        return None

    def set_viseme(self, viseme: str):
        """设置唇形"""
        pass

    def stop(self):
        """停止动画"""
        self.current_animation = None
        self.current_frame = 0
