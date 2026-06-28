"""
消息网关模块
"""

from taiji_agent.gateway.core import (
    DingTalkAdapter,
    DiscordAdapter,
    FeishuAdapter,
    Message,
    MessageGateway,
    MessagePlatform,
    OutgoingMessage,
    PlatformAdapter,
    TelegramAdapter,
    WeChatWorkAdapter,
    create_gateway,
)
from taiji_agent.gateway.feishu import FeishuAdapter as FeishuClient

__all__ = [
    "MessageGateway",
    "PlatformAdapter",
    "Message",
    "OutgoingMessage",
    "MessagePlatform",
    "create_gateway",
    "TelegramAdapter",
    "DiscordAdapter",
    "WeChatWorkAdapter",
    "DingTalkAdapter",
    "FeishuAdapter",
    "FeishuClient",
]
