"""STT 语音识别"""
import asyncio
from typing import Optional
import numpy as np


class TaijiSTT:
    """太极主题 STT"""

    def __init__(self, model_size: str = "base"):
        """
        初始化 STT

        Args:
            model_size: 模型大小 (tiny, base, small, medium, large)
        """
        self.model_size = model_size
        self.model = None
        self.language = "zh"

    async def initialize(self):
        """初始化模型"""
        try:
            from faster_whisper import WhisperModel

            self.model = WhisperModel(
                self.model_size,
                device="cpu",
                compute_type="int8"
            )
        except ImportError:
            pass

    async def listen(self) -> str:
        """
        监听麦克风并识别语音

        Returns:
            str: 识别的文本
        """
        if self.model is None:
            await self.initialize()

        try:
            import sounddevice as sd

            duration = 5.0
            sample_rate = 16000

            audio = await self._record_audio(duration, sample_rate)

            if audio is None or len(audio) == 0:
                return ""

            segments, _ = self.model.transcribe(
                audio,
                language=self.language
            )

            text = "".join([segment.text for segment in segments])
            return text.strip()

        except Exception:
            return ""

    async def _record_audio(
        self, duration: float, sample_rate: int
    ) -> np.ndarray:
        """录制音频"""
        try:
            import sounddevice as sd

            audio = sd.rec(
                int(duration * sample_rate),
                samplerate=sample_rate,
                channels=1,
                dtype="float32"
            )

            sd.wait()

            return audio.flatten()

        except Exception:
            return np.array([])

    async def transcribe_file(self, file_path: str) -> str:
        """转写音频文件"""
        if self.model is None:
            await self.initialize()

        try:
            segments, _ = self.model.transcribe(
                file_path,
                language=self.language
            )

            return "".join([segment.text for segment in segments])

        except Exception:
            return ""
