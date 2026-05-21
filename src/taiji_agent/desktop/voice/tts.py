"""TTS 语音合成"""
import asyncio
from typing import Optional


class TaijiTTS:
    """太极主题 TTS"""

    VOICE_MAP = {
        "zh-CN": "zh-CN-XiaoxiaoNeural",
        "en-US": "en-US-JennyNeural",
        "zh-CN-Male": "zh-CN-YunxiNeural",
    }

    def __init__(self):
        self.voice = self.VOICE_MAP["zh-CN"]
        self.pitch = "+5%"
        self.rate = "+10%"
        self._edge_tts = None

    async def speak(self, text: str) -> bytes:
        """
        将文本转为语音

        Args:
            text: 要说话的文本

        Returns:
            bytes: 音频数据
        """
        try:
            from edge_tts import Communicate

            communicate = Communicate(
                text,
                self.voice,
                pitch=self.pitch,
                rate=self.rate
            )

            audio_data = await communicate.get_audio()

            return audio_data

        except ImportError:
            return b""

    async def speak_to_file(self, text: str, file_path: str):
        """说话并保存到文件"""
        try:
            from edge_tts import Communicate

            communicate = Communicate(
                text,
                self.voice,
                pitch=self.pitch,
                rate=self.rate
            )

            await communicate.save(file_path)

        except ImportError:
            pass

    def set_voice(self, voice: str):
        """设置语音"""
        if voice in self.VOICE_MAP:
            self.voice = self.VOICE_MAP[voice]
        else:
            self.voice = voice
