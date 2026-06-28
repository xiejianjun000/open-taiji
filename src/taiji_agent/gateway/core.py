"""
消息网关 - 支持多种消息平台
来自 Hermes Agent
"""

import asyncio
import json
import logging
import os
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class MessagePlatform(Enum):
    TELEGRAM = "telegram"
    DISCORD = "discord"
    SLACK = "slack"
    WECHAT_WORK = "wechat_work"
    DINGTALK = "dingtalk"
    FEISHU = "feishu"
    WHATSAPP = "whatsapp"
    LINE = "line"


@dataclass
class Message:
    """消息结构"""

    platform: str
    chat_id: str
    user_id: str
    content: str
    message_id: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


@dataclass
class OutgoingMessage:
    """发送消息结构"""

    content: str
    chat_id: str
    metadata: Optional[dict[str, Any]] = None


class PlatformAdapter(ABC):
    """平台适配器基类"""

    def __init__(self, config: dict):
        self.config = config
        self._handlers: list[Callable] = []

    @abstractmethod
    async def start(self):
        """启动平台连接"""
        pass

    @abstractmethod
    async def stop(self):
        """停止平台连接"""
        pass

    @abstractmethod
    async def send_message(self, message: OutgoingMessage) -> bool:
        """发送消息"""
        pass

    def on_message(self, handler: Callable[[Message], Awaitable[None]]):
        """注册消息处理器"""
        self._handlers.append(handler)

    async def _dispatch(self, message: Message):
        """分发消息到处理器"""
        for handler in self._handlers:
            try:
                await handler(message)
            except Exception as e:
                logger.error(f"Handler error: {e}")


class TelegramAdapter(PlatformAdapter):
    """Telegram 适配器"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.bot_token = config.get("bot_token")
        self.api_base = f"https://api.telegram.org/bot{self.bot_token}"
        self.offset = 0
        self._running = False

    async def start(self):
        """启动 Telegram Bot"""
        self._running = True
        asyncio.create_task(self._poll())
        logger.info("Telegram bot started")

    async def stop(self):
        """停止 Telegram Bot"""
        self._running = False
        logger.info("Telegram bot stopped")

    async def _poll(self):
        """轮询获取更新"""
        import httpx

        async with httpx.AsyncClient() as client:
            while self._running:
                try:
                    response = await client.get(
                        f"{self.api_base}/getUpdates",
                        params={
                            "offset": self.offset,
                            "timeout": 30,
                        },
                        timeout=35,
                    )

                    data = response.json()

                    if data.get("ok"):
                        for update in data.get("result", []):
                            if "message" in update:
                                msg = update["message"]
                                message = Message(
                                    platform="telegram",
                                    chat_id=str(msg["chat"]["id"]),
                                    user_id=str(msg["from"]["id"]),
                                    content=msg.get("text", ""),
                                    message_id=str(update["update_id"]),
                                )
                                await self._dispatch(message)
                                self.offset = update["update_id"] + 1

                except Exception as e:
                    logger.error(f"Telegram poll error: {e}")
                    await asyncio.sleep(5)

    async def send_message(self, message: OutgoingMessage) -> bool:
        """发送消息"""
        import httpx

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.api_base}/sendMessage",
                    json={
                        "chat_id": message.chat_id,
                        "text": message.content,
                    },
                )
                return bool(response.json().get("ok", False))
            except Exception as e:
                logger.error(f"Telegram send error: {e}")
                return False


class DiscordAdapter(PlatformAdapter):
    """Discord 适配器"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.bot_token = config.get("bot_token")
        self.application_id = config.get("application_id")
        self._running = False

    async def start(self):
        """启动 Discord Bot"""
        self._running = True
        asyncio.create_task(self._websocket_loop())
        logger.info("Discord bot started")

    async def stop(self):
        """停止 Discord Bot"""
        self._running = False
        logger.info("Discord bot stopped")

    async def _websocket_loop(self):
        """WebSocket 循环"""
        import httpx
        import websockets

        gateway_url = "wss://gateway.discord.gg/?v=10&encoding=json"

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://discord.com/api/v10/gateway",
                headers={"Authorization": f"Bot {self.bot_token}"},
            )
            gateway_url = resp.json()["url"]

        while self._running:
            try:
                async with websockets.connect(gateway_url) as ws:
                    await ws.send(json.dumps({"op": 2, "d": {"token": self.bot_token, "intents": 1}}))

                    async for msg in ws:
                        data = json.loads(msg)
                        if data["t"] == "MESSAGE_CREATE":
                            msg_data = data["d"]
                            if not msg_data["author"]["bot"]:
                                message = Message(
                                    platform="discord",
                                    chat_id=msg_data["channel_id"],
                                    user_id=msg_data["author"]["id"],
                                    content=msg_data["content"],
                                    message_id=msg_data["id"],
                                )
                                await self._dispatch(message)

            except Exception as e:
                logger.error(f"Discord error: {e}")
                await asyncio.sleep(5)

    async def send_message(self, message: OutgoingMessage) -> bool:
        """发送消息"""
        import httpx

        async with httpx.AsyncClient() as client:
            try:
                channel_id = message.chat_id
                response = await client.post(
                    f"https://discord.com/api/v10/channels/{channel_id}/messages",
                    headers={
                        "Authorization": f"Bot {self.bot_token}",
                        "Content-Type": "application/json",
                    },
                    json={"content": message.content},
                )
                return response.status_code == 200
            except Exception as e:
                logger.error(f"Discord send error: {e}")
                return False


class WeChatWorkAdapter(PlatformAdapter):
    """企业微信适配器"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.corp_id = config.get("corp_id")
        self.corp_secret = config.get("corp_secret")
        self.agent_id = config.get("agent_id")
        self._access_token = None

    async def start(self):
        """启动企业微信 Bot"""
        await self._get_access_token()
        logger.info("WeChat Work bot started")

    async def stop(self):
        """停止企业微信 Bot"""
        logger.info("WeChat Work bot stopped")

    async def _get_access_token(self):
        """获取访问令牌"""
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://qyapi.weixin.qq.com/cgi-bin/gettoken",
                params={
                    "corpid": self.corp_id,
                    "corpsecret": self.corp_secret,
                },
            )
            data = response.json()
            if data.get("access_token"):
                self._access_token = data["access_token"]

    async def send_message(self, message: OutgoingMessage) -> bool:
        """发送消息"""
        import httpx

        if not self._access_token:
            await self._get_access_token()

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    "https://qyapi.weixin.qq.com/cgi-bin/message/send",
                    params={"access_token": self._access_token},
                    json={
                        "touser": message.chat_id,
                        "msgtype": "text",
                        "agentid": self.agent_id,
                        "text": {"content": message.content},
                    },
                )
                return bool(response.json().get("errcode") == 0)
            except Exception as e:
                logger.error(f"WeChat Work send error: {e}")
                return False


class DingTalkAdapter(PlatformAdapter):
    """钉钉适配器"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.app_key = config.get("app_key")
        self.app_secret = config.get("app_secret")
        self._access_token = None

    async def start(self):
        """启动钉钉 Bot"""
        await self._get_access_token()
        logger.info("DingTalk bot started")

    async def stop(self):
        """停止钉钉 Bot"""
        logger.info("DingTalk bot stopped")

    async def _get_access_token(self):
        """获取访问令牌"""
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.dingtalk.com/v1.0/oauth2/accessToken",
                json={
                    "appKey": self.app_key,
                    "appSecret": self.app_secret,
                },
            )
            data = response.json()
            if data.get("accessToken"):
                self._access_token = data["accessToken"]

    async def send_message(self, message: OutgoingMessage) -> bool:
        """发送消息"""
        import httpx

        if not self._access_token:
            await self._get_access_token()

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    "https://api.dingtalk.com/v1.0/im/messages",
                    headers={"x-acs-dingtalk-access-token": self._access_token or ""},
                    json={
                        "robotCode": self.app_key,
                        "msgId": str(hash(message.content)),
                        "msgParam": json.dumps({"content": message.content}),
                        "msgType": "text",
                    },
                )
                return bool(response.json().get("success", False))
            except Exception as e:
                logger.error(f"DingTalk send error: {e}")
                return False


class FeishuAdapter:
    """
    飞书适配器（向后兼容代理）。

    实际实现在 taiji_agent.gateway.feishu 模块中。
    通过此类保留 API 兼容性，同时支持完整的 WS 事件订阅。
    """

    def __new__(cls, config: dict):
        from taiji_agent.gateway.feishu import FeishuAdapter as NewFeishuAdapter

        instance = NewFeishuAdapter.__new__(NewFeishuAdapter)
        PlatformAdapter.__init__(instance, config)
        NewFeishuAdapter.__init__(instance, config)
        return instance


class MessageGateway:
    """
    消息网关

    统一管理多个消息平台
    """

    def __init__(self):
        self._adapters: dict[str, PlatformAdapter] = {}

    def register(self, platform: str, adapter: PlatformAdapter):
        """注册平台适配器"""
        self._adapters[platform] = adapter
        logger.info(f"Registered platform: {platform}")

    async def start_all(self):
        """启动所有平台"""
        for adapter in self._adapters.values():
            try:
                await adapter.start()
            except Exception as e:
                logger.error(f"Start platform error: {e}")

    async def stop_all(self):
        """停止所有平台"""
        for adapter in self._adapters.values():
            try:
                await adapter.stop()
            except Exception as e:
                logger.error(f"Stop platform error: {e}")

    async def send(
        self,
        platform: str,
        chat_id: str,
        content: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        """发送消息"""
        if platform not in self._adapters:
            logger.error(f"Unknown platform: {platform}")
            return False

        adapter = self._adapters[platform]
        message = OutgoingMessage(
            content=content,
            chat_id=chat_id,
            metadata=metadata,
        )
        return await adapter.send_message(message)

    def on_message(
        self,
        platform: str,
        handler: Callable[[Message], Awaitable[None]],
    ):
        """注册消息处理器"""
        if platform in self._adapters:
            self._adapters[platform].on_message(handler)

    def get_platforms(self) -> list[str]:
        """获取已注册的平台"""
        return list(self._adapters.keys())


def create_gateway(config: dict) -> MessageGateway:
    """创建消息网关。支持从环境变量自动读取飞书配置。"""
    gateway = MessageGateway()

    if "telegram" in config:
        gateway.register("telegram", TelegramAdapter(config["telegram"]))

    if "discord" in config:
        gateway.register("discord", DiscordAdapter(config["discord"]))

    if "wechat_work" in config:
        gateway.register("wechat_work", WeChatWorkAdapter(config["wechat_work"]))

    if "dingtalk" in config:
        gateway.register("dingtalk", DingTalkAdapter(config["dingtalk"]))

    # 飞书：优先使用显式配置，其次从环境变量读取
    if "feishu" in config:
        gateway.register("feishu", FeishuAdapter(config["feishu"]))
    else:
        _feishu_app_id = os.environ.get("FEISHU_APP_ID", "")
        _feishu_app_secret = os.environ.get("FEISHU_APP_SECRET", "")
        if _feishu_app_id and _feishu_app_secret:
            from taiji_agent.gateway.feishu import FeishuAdapter as FSAdapter

            fs_config = {
                "app_id": _feishu_app_id,
                "app_secret": _feishu_app_secret,
                "verification_token": os.environ.get("FEISHU_VERIFICATION_TOKEN", ""),
                "encrypt_key": os.environ.get("FEISHU_ENCRYPT_KEY", ""),
            }
            gateway.register("feishu", FSAdapter(fs_config))

    return gateway
