"""吉祥物模块"""
from .states import MascotState, MASCOT_COLORS, MASCOT_EMOJIS
from .lottie_player import LottiePlayer
from .lip_sync import LipSync


def __getattr__(name):
    if name == "MascotWidget":
        from .widget import MascotWidget
        globals()["MascotWidget"] = MascotWidget
        return MascotWidget
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "MascotWidget",
    "MascotState",
    "MASCOT_COLORS",
    "MASCOT_EMOJIS",
    "LottiePlayer",
    "LipSync",
]
