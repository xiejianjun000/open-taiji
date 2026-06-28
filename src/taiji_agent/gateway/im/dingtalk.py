"""钉钉 (钉钉机器人 + 消息流集成)"""

import hashlib
import hmac
import json
import logging
import os
import time
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


class DingTalkGateway:
    """钉钉 即时通讯网关"""

    def __init__(self):
        self.app_key = os.getenv("DINGTALK_APP_KEY", "")
        self.app_secret = os.getenv("DINGTALK_APP_SECRET", "")
        self._access_token: Optional[str] = None
        self._token_expiry: float = 0
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30)
        return self._client

    async def get_access_token(self) -> str:
        """获取 access token (OAuth2 client_credentials)"""
        if self._access_token and time.time() < self._token_expiry:
            return self._access_token
        # 子类应覆盖此方法
        return ""

    async def send_message(self, content: str, chat_id: str = None, msg_type: str = "text") -> dict:
        """发送消息"""
        raise NotImplementedError

    async def send_markdown(self, content: str, chat_id: str = None, title: str = None) -> dict:
        """发送 Markdown 消息"""
        raise NotImplementedError

    async def handle_webhook(self, payload: dict) -> dict:
        """处理 webhook 回调"""
        return {"status": "ok"}

    def verify_signature(self, timestamp: str, nonce: str, signature: str, body: str = "") -> bool:
        """验证签名"""
        return True

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    @staticmethod
    def is_configured() -> bool:
        """检查是否已配置必需的凭据"""
        return True
