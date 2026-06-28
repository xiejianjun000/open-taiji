"""梦境引擎 — 后台自主记忆处理"""

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class DreamType(str, Enum):
    DEEP = "deep"    # 深度处理：记忆提取 + 技能创建
    LIGHT = "light"  # 轻度处理：用户画像更新
    REM = "rem"      # 快速眼动：记忆关联


@dataclass
class DreamConfig:
    """梦境系统配置"""
    enabled: bool = True
    interval_hours: int = 4
    deep_enabled: bool = True
    light_enabled: bool = True
    rem_enabled: bool = False
    max_dream_duration: int = 120  # 秒
    max_memories_per_dream: int = 50
    auto_create_skills: bool = True

    @classmethod
    def from_dict(cls, data: dict) -> "DreamConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class DreamEngine:
    """梦境引擎 — OpenClaw memory-core 兼容"""

    def __init__(self, config: Optional[DreamConfig] = None):
        self.config = config or DreamConfig()
        self._state_file = Path.home() / ".taiji" / "dream_state.json"
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_dream: dict[str, float] = {"deep": 0, "light": 0, "rem": 0}
        self._load_state()

    def _load_state(self):
        try:
            import json
            if self._state_file.exists():
                with open(self._state_file) as f:
                    data = json.load(f)
                    self._last_dream = data.get("last_dream", self._last_dream)
        except Exception:
            pass

    def _save_state(self):
        try:
            import json
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._state_file, "w") as f:
                json.dump({"last_dream": self._last_dream}, f)
        except Exception:
            pass

    def start(self):
        """启动梦境后台线程"""
        if not self.config.enabled:
            logger.info("Dream system disabled")
            return
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._dream_loop, daemon=True)
        self._thread.start()
        logger.info("Dream engine started (interval: %dh)", self.config.interval_hours)

    def stop(self):
        self._running = False

    def _dream_loop(self):
        """梦境循环"""
        while self._running:
            time.sleep(60)  # 每分钟检查一次
            try:
                self._tick()
            except Exception as e:
                logger.warning("Dream tick error: %s", e)

    def _tick(self):
        """检查是否需要梦境"""
        now = time.time()
        interval_seconds = self.config.interval_hours * 3600

        # Deep dream
        if self.config.deep_enabled and (now - self._last_dream["deep"]) > interval_seconds:
            self._run_dream(DreamType.DEEP)
            self._last_dream["deep"] = now

        # Light dream (更频繁)
        elif self.config.light_enabled and (now - self._last_dream["light"]) > interval_seconds / 2:
            self._run_dream(DreamType.LIGHT)
            self._last_dream["light"] = now

    def _run_dream(self, dream_type: DreamType):
        """执行梦境"""
        logger.info("Starting %s dream...", dream_type.value)
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._process_dream(dream_type))
            loop.close()
        except Exception as e:
            logger.error("Dream processing error: %s", e)
        finally:
            self._save_state()

    async def _process_dream(self, dream_type: DreamType):
        """处理梦境"""
        if dream_type == DreamType.DEEP:
            await self._deep_dream()
        elif dream_type == DreamType.LIGHT:
            await self._light_dream()
        elif dream_type == DreamType.REM:
            await self._rem_dream()

    async def _deep_dream(self):
        """深度梦境: 提取记忆、创建技能"""
        try:
            from taiji_agent.dream.digest import MemoryDigester
            digester = MemoryDigester()
            result = await digester.digest_deep()
            if result:
                logger.info("Deep dream complete: %d memories processed, %d skills created",
                           result.get("memories", 0), result.get("skills", 0))
        except Exception as e:
            logger.warning("Deep dream failed: %s", e)

    async def _light_dream(self):
        """轻度梦境: 更新用户画像"""
        try:
            from taiji_agent.dream.digest import MemoryDigester
            digester = MemoryDigester()
            await digester.digest_light()
        except Exception as e:
            logger.warning("Light dream failed: %s", e)

    async def _rem_dream(self):
        """快速眼动: 记忆关联"""
        try:
            from taiji_agent.dream.digest import MemoryDigester
            digester = MemoryDigester()
            await digester.digest_rem()
        except Exception as e:
            logger.warning("REM dream failed: %s", e)

    def trigger_dream(self, dream_type: DreamType = DreamType.DEEP):
        """手动触法梦境"""
        threading.Thread(target=self._run_dream, args=(dream_type,), daemon=True).start()
