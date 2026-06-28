"""
飞书（Feishu/Lark）消息平台适配器。

基于 lark-oapi SDK v1.6.5，支持：
- WebSocket 长连接事件订阅（接收消息）
- REST API 消息发送（文本/卡片/富文本/Markdown）
- 自动重连与 Token 刷新
- 与 TaijiAgent 引擎 Pipeline 集成
"""

import asyncio
import json
import logging
import threading
import time
from collections.abc import Awaitable, Callable
from typing import Any, Optional

# lark_oapi is an optional dependency — lazy import
try:
    from lark_oapi.event.dispatcher_handler import (
        EventDispatcherHandler,
        EventDispatcherHandlerBuilder,
    )
    from lark_oapi.ws.client import Client as WSClient
    from lark_oapi.core.enum import LogLevel as LarkLogLevel
    _LARK_AVAILABLE = True
except ImportError:
    EventDispatcherHandler = None  # type: ignore
    EventDispatcherHandlerBuilder = None  # type: ignore
    WSClient = None  # type: ignore
    LarkLogLevel = None  # type: ignore
    _LARK_AVAILABLE = False

from taiji_agent.gateway.core import Message, OutgoingMessage, PlatformAdapter

logger = logging.getLogger(__name__)


def _build_lark_message_handler(
    dispatch_fn: Callable[[Message], Awaitable[None]],
) -> Callable[[Any], None]:
    """
    构建飞书消息接收处理器（用于 lark_oapi 事件系统）。
    
    将飞书 IM 的 p2.im.message.receive_v1 事件转换为网关 Message 并分发。
    """

    def handler(event: Any) -> None:
        try:
            event_data = event.event if hasattr(event, "event") else {}
            if not event_data:
                return

            message_data = event_data.get("message", {})
            if not message_data:
                return

            msg_type = message_data.get("message_type", "text")
            content_str = message_data.get("content", "{}")

            try:
                content_obj = json.loads(content_str)
            except (json.JSONDecodeError, TypeError):
                content_obj = {}

            # 按消息类型提取文本
            if msg_type == "text":
                text = content_obj.get("text", "")
            elif msg_type == "post":
                post = content_obj.get("content", [[]])
                text_parts = []
                for paragraph in post:
                    if isinstance(paragraph, list):
                        for segment in paragraph:
                            if isinstance(segment, dict):
                                text_parts.append(segment.get("text", ""))
                            elif isinstance(segment, list):
                                for s in segment:
                                    if isinstance(s, dict):
                                        text_parts.append(s.get("text", ""))
                text = "".join(text_parts)
            elif msg_type == "image":
                text = "[图片消息]"
            elif msg_type == "file":
                text = f"[文件: {message_data.get('file_name', 'unknown')}]"
            elif msg_type == "audio":
                text = "[语音消息]"
            elif msg_type == "media":
                text = f"[媒体消息: {message_data.get('file_name', 'unknown')}]"
            elif msg_type == "sticker":
                text = "[表情]"
            else:
                text = f"[{msg_type} 消息]"

            chat_id = message_data.get("chat_id", "")
            sender = event_data.get("sender", {})
            sender_id = sender.get("sender_id", {})
            user_id = (
                sender_id.get("open_id")
                or sender_id.get("user_id")
                or sender_id.get("union_id")
                or ""
            )
            message_id = message_data.get("message_id", "")

            if not chat_id or not text.strip():
                return

            msg = Message(
                platform="feishu",
                chat_id=chat_id,
                user_id=user_id,
                content=text,
                message_id=message_id,
                metadata={
                    "msg_type": msg_type,
                    "raw_event": event_data,
                    "sender": sender,
                },
            )

            # 跨线程安全分发
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            asyncio.run_coroutine_threadsafe(dispatch_fn(msg), loop)

        except Exception as e:
            logger.error(f"飞书消息处理器异常: {e}", exc_info=True)

    return handler


class FeishuAdapter(PlatformAdapter):
    """
    飞书平台适配器。

    配置项:
        app_id: str             - 飞书应用 App ID
        app_secret: str         - 飞书应用 App Secret
        verification_token: str - 事件验证 Token（可选）
        encrypt_key: str        - 事件加密 Key（可选）
        lark_domain: str        - 飞书域名（默认 https://open.feishu.cn）
        auto_reconnect: bool    - 自动重连（默认 True）
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self.app_id: str = config.get("app_id", "")
        self.app_secret: str = config.get("app_secret", "")
        self.verification_token: str = config.get("verification_token", "")
        self.encrypt_key: str = config.get("encrypt_key", "")
        self.lark_domain: str = config.get("lark_domain", "https://open.feishu.cn")
        self.auto_reconnect: bool = config.get("auto_reconnect", True)

        self._tenant_access_token: Optional[str] = None
        self._token_expires_at: float = 0.0

        self._ws_client: Optional[WSClient] = None
        self._ws_thread: Optional[threading.Thread] = None
        self._running: bool = False
        self._dispatch_loop: Optional[asyncio.AbstractEventLoop] = None

    # ============ 生命周期 ============

    async def start(self):
        """启动飞书适配器"""
        if not self.app_id or not self.app_secret:
            logger.warning(
                "飞书适配器: app_id/app_secret 未配置，仅发送功能可用。"
                "设置 FEISHU_APP_ID / FEISHU_APP_SECRET 环境变量以启用消息接收。"
            )
            await self._get_token()
            self._running = True
            return

        self._running = True
        self._dispatch_loop = asyncio.get_event_loop()

        await self._get_token()

        event_handler = self._build_event_handler()

        domain = self.lark_domain.replace("https://", "").replace("http://", "")
        self._ws_client = WSClient(
            app_id=self.app_id,
            app_secret=self.app_secret,
            log_level=LarkLogLevel.WARNING,
            event_handler=event_handler,
            domain=domain,
            auto_reconnect=self.auto_reconnect,
        )
        self._ws_client.on_reconnecting = lambda: logger.warning("飞书 WS 连接中断，重连中...")
        self._ws_client.on_reconnected = lambda: logger.info("飞书 WS 重连成功")

        self._ws_thread = threading.Thread(
            target=self._run_ws_client,
            daemon=True,
            name="feishu-ws-client",
        )
        self._ws_thread.start()

        logger.info(f"飞书适配器已启动 (app_id={self.app_id[:8]}...)")

    async def stop(self):
        """停止飞书适配器"""
        self._running = False
        if self._ws_client and self._ws_client._conn:
            await self._ws_client._disconnect()
        logger.info("飞书适配器已停止")

    def _run_ws_client(self):
        """后台线程运行 WS 客户端（阻塞方法）"""
        try:
            self._ws_client.start()
        except Exception as e:
            if self._running:
                logger.error(f"飞书 WS 客户端异常退出: {e}")

    # ============ 事件处理 ============

    def _build_event_handler(self) -> EventDispatcherHandler:
        """构建事件分发处理器"""
        builder = EventDispatcherHandlerBuilder(
            encrypt_key=self.encrypt_key,
            verification_token=self.verification_token,
        )
        handler_fn = _build_lark_message_handler(self._dispatch)
        builder.register_p2_im_message_receive_v1(handler_fn)
        return builder.build()

    # ============ Token 管理 ============

    async def _get_token(self) -> str:
        """获取 tenant_access_token（自动过期检测和刷新）"""
        import httpx

        if self._tenant_access_token and time.time() < self._token_expires_at - 60:
            return self._tenant_access_token

        if not self.app_id or not self.app_secret:
            logger.error("无法获取飞书 Token: 缺少 app_id 或 app_secret")
            return ""

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.lark_domain}/open-apis/auth/v3/tenant_access_token/internal",
                    json={"app_id": self.app_id, "app_secret": self.app_secret},
                    timeout=10,
                )
                data = response.json()
                code = data.get("code", -1)
                if code != 0:
                    logger.error(f"获取飞书 Token 失败: code={code}, msg={data.get('msg')}")
                    return ""

                self._tenant_access_token = data["tenant_access_token"]
                expire = data.get("expire", 7200)
                self._token_expires_at = time.time() + expire
                logger.debug(f"飞书 Token 已刷新，有效期 {expire}s")
                return self._tenant_access_token
            except Exception as e:
                logger.error(f"获取飞书 Token 异常: {e}")
                return ""

    # ============ 消息发送 ============

    async def send_message(self, message: OutgoingMessage) -> bool:
        """发送消息（默认交互式卡片格式，长文本友好）"""
        import httpx

        token = await self._get_token()
        if not token:
            return False

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.lark_domain}/open-apis/im/v1/messages",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    params={"receive_id_type": "chat_id"},
                    json={
                        "receive_id": message.chat_id,
                        "msg_type": "interactive",
                        "content": json.dumps({
                            "config": {"wide_screen_mode": True},
                            "elements": [{"tag": "markdown", "content": message.content}],
                        }),
                    },
                    timeout=15,
                )
                data = response.json()
                ok = data.get("code") == 0
                if not ok:
                    logger.error(f"飞书发送失败: code={data.get('code')}, msg={data.get('msg')}")
                return ok
            except Exception as e:
                logger.error(f"飞书发送异常: {e}")
                return False

    async def send_text(self, chat_id: str, text: str) -> bool:
        """发送纯文本消息"""
        import httpx

        token = await self._get_token()
        if not token:
            return False

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.lark_domain}/open-apis/im/v1/messages",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    params={"receive_id_type": "chat_id"},
                    json={
                        "receive_id": chat_id,
                        "msg_type": "text",
                        "content": json.dumps({"text": text}),
                    },
                    timeout=15,
                )
                return response.json().get("code") == 0
            except Exception as e:
                logger.error(f"飞书发送文本异常: {e}")
                return False

    async def send_card(self, chat_id: str, card: dict) -> bool:
        """发送卡片消息"""
        import httpx

        token = await self._get_token()
        if not token:
            return False

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.lark_domain}/open-apis/im/v1/messages",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    params={"receive_id_type": "chat_id"},
                    json={
                        "receive_id": chat_id,
                        "msg_type": "interactive",
                        "content": json.dumps(card, ensure_ascii=False),
                    },
                    timeout=15,
                )
                return response.json().get("code") == 0
            except Exception as e:
                logger.error(f"飞书发送卡片异常: {e}")
                return False

    async def reply_message(
        self, message_id: str, content: str, msg_type: str = "text"
    ) -> bool:
        """回复指定消息（支持 text/interactive）"""
        import httpx

        token = await self._get_token()
        if not token:
            return False

        if msg_type == "text":
            content_json = json.dumps({"text": content})
        elif msg_type == "interactive":
            content_json = (
                json.dumps(content, ensure_ascii=False)
                if isinstance(content, dict)
                else content
            )
        else:
            content_json = json.dumps({"text": content})

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.lark_domain}/open-apis/im/v1/messages/{message_id}/reply",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    json={"msg_type": msg_type, "content": content_json},
                    timeout=15,
                )
                return response.json().get("code") == 0
            except Exception as e:
                logger.error(f"飞书回复异常: {e}")
                return False

    async def upload_image(self, image_data: bytes) -> Optional[str]:
        """上传图片，返回 image_key"""
        import httpx

        token = await self._get_token()
        if not token:
            return None

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.lark_domain}/open-apis/im/v1/images",
                    headers={"Authorization": f"Bearer {token}"},
                    files={"image": ("image.png", image_data, "image/png")},
                    data={"image_type": "message"},
                    timeout=30,
                )
                data = response.json()
                if data.get("code") == 0:
                    return data["data"]["image_key"]
                return None
            except Exception as e:
                logger.error(f"飞书上传图片异常: {e}")
                return None

    async def send_image(self, chat_id: str, image_key: str) -> bool:
        """发送图片消息"""
        import httpx

        token = await self._get_token()
        if not token:
            return False

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.lark_domain}/open-apis/im/v1/messages",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    params={"receive_id_type": "chat_id"},
                    json={
                        "receive_id": chat_id,
                        "msg_type": "image",
                        "content": json.dumps({"image_key": image_key}),
                    },
                    timeout=15,
                )
                return response.json().get("code") == 0
            except Exception as e:
                logger.error(f"飞书发送图片异常: {e}")
                return False

    # ============ 查询接口 ============

    async def get_chat_info(self, chat_id: str) -> Optional[dict]:
        """获取群组信息"""
        import httpx

        token = await self._get_token()
        if not token:
            return None

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.lark_domain}/open-apis/im/v1/chats/{chat_id}",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10,
                )
                data = response.json()
                return data["data"] if data.get("code") == 0 else None
            except Exception as e:
                logger.error(f"获取飞书群信息异常: {e}")
                return None

    async def get_user_info(self, user_id: str) -> Optional[dict]:
        """获取用户信息"""
        import httpx

        token = await self._get_token()
        if not token:
            return None

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.lark_domain}/open-apis/contact/v3/users/{user_id}",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10,
                )
                data = response.json()
                return data["data"]["user"] if data.get("code") == 0 else None
            except Exception as e:
                logger.error(f"获取飞书用户信息异常: {e}")
                return None

    # ============ 诊断 ============

    async def test_connection(self) -> dict:
        """测试飞书连接状态"""
        token = await self._get_token()
        if not token:
            return {"success": False, "error": "无法获取 Token，请检查 app_id/app_secret"}

        import httpx

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.lark_domain}/open-apis/bot/v3/info",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10,
                )
                data = response.json()
                if data.get("code") == 0:
                    bot = data.get("bot", {})
                    return {
                        "success": True,
                        "bot_name": bot.get("app_name", "unknown"),
                        "bot_description": bot.get("description", ""),
                        "ws_alive": self._ws_thread is not None and self._ws_thread.is_alive(),
                        "token_valid": True,
                    }
                return {
                    "success": False,
                    "error": f"API 错误: code={data.get('code')}, msg={data.get('msg')}",
                }
            except Exception as e:
                return {"success": False, "error": str(e)}
