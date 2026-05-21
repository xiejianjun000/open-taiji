"""语音模块"""
from .pipeline import VoicePipeline


def __getattr__(name):
    if name == "TaijiTTS":
        from .tts import TaijiTTS
        globals()["TaijiTTS"] = TaijiTTS
        return TaijiTTS
    if name == "TaijiSTT":
        from .stt import TaijiSTT
        globals()["TaijiSTT"] = TaijiSTT
        return TaijiSTT
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "TaijiTTS",
    "TaijiSTT",
    "VoicePipeline",
]
