"""语音管道"""
import asyncio
from typing import Optional, Callable

from .tts import TaijiTTS
from .stt import TaijiSTT


class VoicePipeline:
    """语音管道 - TTS/STT 集成"""

    def __init__(self):
        self.tts = TaijiTTS()
        self.stt = TaijiSTT()
        self.is_listening = False
        self.is_speaking = False
        self.on_speaking_start: Optional[Callable] = None
        self.on_speaking_end: Optional[Callable] = None
        self.on_text_recognized: Optional[Callable] = None

    async def speak(self, text: str):
        """说话"""
        self.is_speaking = True
        if self.on_speaking_start:
            self.on_speaking_start()

        try:
            audio_data = await self.tts.speak(text)
            return audio_data
        finally:
            self.is_speaking = False
            if self.on_speaking_end:
                self.on_speaking_end()

    async def listen(self) -> str:
        """监听并返回识别文本"""
        self.is_listening = True
        try:
            text = await self.stt.listen()
            if text and self.on_text_recognized:
                self.on_text_recognized(text)
            return text
        finally:
            self.is_listening = False

    def stop(self):
        """停止语音"""
        self.is_listening = False
        self.is_speaking = False
