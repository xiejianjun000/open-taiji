"""吉祥物模块"""
from .widget import MascotWidget
from .states import MascotState, MASCOT_COLORS, MASCOT_EMOJIS
from .lottie_player import LottiePlayer
from .lip_sync import LipSync

__all__ = [
    "MascotWidget",
    "MascotState",
    "MASCOT_COLORS",
    "MASCOT_EMOJIS",
    "LottiePlayer",
    "LipSync",
]
