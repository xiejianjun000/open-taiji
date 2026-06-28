# -*- coding: utf-8 -*-
"""
飞书消息平台插件。

提供飞书/Lark 消息平台的完整集成：
- 消息接收（WebSocket 长连接事件订阅）
- 消息发送（文本/卡片/Markdown/图片）
- 用户/群组信息查询
- 与 TaijiAgent 引擎的双向绑定

配置方式（三选一，优先级从高到低）：
1. 显式传参：FeishuPlugin(app_id=..., app_secret=...)
2. 环境变量：FEISHU_APP_ID / FEISHU_APP_SECRET
3. gateway 配置：通过 create_gateway() 统一管理
"""

import os
from typing import Any, Dict, Optional

from ..plugin_base import (
    Plugin,
    PluginMetadata,
    PluginContext,
    PluginHealth,
    ToolDefinition,
)


class FeishuPlugin(Plugin):
    """
    飞书消息平台插件。

    功能：
    - 飞书消息收发
    - 知识库查询（通过飞书机器人交互）
    - 群组消息监听与回复
    """

    METADATA = PluginMetadata(
        id="feishu",
        name="飞书消息平台",
        version="1.0.0",
        description="飞书/Lark 消息平台集成插件，支持双向消息收发",
        author="Taiji Team",
        tags=["飞书", "消息", "Lark"],
        min_agent_version="1.0.0",
        dependencies=[],
        config_schema={
            "type": "object",
            "properties": {
                "app_id": {
                    "type": "string",
                    "description": "飞书应用 App ID",
                },
                "app_secret": {
                    "type": "string",
                    "description": "飞书应用 App Secret",
                },
                "verification_token": {
                    "type": "string",
                    "description": "事件验证 Token",
                },
                "encrypt_key": {
                    "type": "string",
                    "description": "事件加密 Key",
                },
                "auto_reconnect": {
                    "type": "boolean",
                    "default": True,
                    "description": "是否自动重连",
                },
            },
        },
    )

    def __init__(
        self,
        metadata: Optional[PluginMetadata] = None,
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None,
    ):
        super().__init__(metadata or self.METADATA)
        self._app_id = app_id
        self._app_secret = app_secret
        self._adapter = None
        self._agent = None  # 绑定的 TaijiAgent 实例

    async def activate(self, ctx: PluginContext) -> None:
        """激活插件"""
        self.context = ctx
        ctx.logger.info("Activating FeishuPlugin...")

        # 读取配置
        app_id = self._app_id or self.get_config("app_id") or os.environ.get("FEISHU_APP_ID", "")
        app_secret = self._app_secret or self.get_config("app_secret") or os.environ.get("FEISHU_APP_SECRET", "")

        if not app_id or not app_secret:
            ctx.logger.warning(
                "FeishuPlugin: 缺少 app_id/app_secret。"
                "请设置环境变量 FEISHU_APP_ID 和 FEISHU_APP_SECRET，"
                "或在飞书开放平台创建应用：https://open.feishu.cn"
            )
            return

        # 创建适配器实例
        from taiji_agent.gateway.feishu import FeishuAdapter

        self._adapter = FeishuAdapter({
            "app_id": app_id,
            "app_secret": app_secret,
            "verification_token": self.get_config("verification_token") or os.environ.get("FEISHU_VERIFICATION_TOKEN", ""),
            "encrypt_key": self.get_config("encrypt_key") or os.environ.get("FEISHU_ENCRYPT_KEY", ""),
            "auto_reconnect": self.get_config("auto_reconnect", True),
        })

        # 注册消息处理器 - 当收到消息时调用 agent
        self._adapter.on_message(self._handle_message)

        # 启动适配器
        await self._adapter.start()

        # 注册工具
        self.tools = [
            ToolDefinition(
                name="feishu_test_connection",
                description="测试飞书连接状态",
                parameters={"type": "object", "properties": {}},
            ),
            ToolDefinition(
                name="feishu_send_message",
                description="通过飞书发送消息",
                parameters={
                    "type": "object",
                    "properties": {
                        "chat_id": {"type": "string", "description": "目标会话 ID"},
                        "content": {"type": "string", "description": "消息内容"},
                        "msg_type": {
                            "type": "string",
                            "enum": ["text", "interactive"],
                            "default": "text",
                            "description": "消息类型",
                        },
                    },
                    "required": ["chat_id", "content"],
                },
            ),
        ]

        ctx.logger.info("FeishuPlugin activated successfully")

    async def deactivate(self) -> None:
        """停用插件"""
        if self.context:
            self.context.logger.info("Deactivating FeishuPlugin...")

        if self._adapter:
            await self._adapter.stop()
            self._adapter = None

        self._agent = None

        if self.context:
            self.context.logger.info("FeishuPlugin deactivated")

    async def health_check(self) -> PluginHealth:
        """健康检查"""
        if self._adapter is None:
            return PluginHealth.UNHEALTHY

        try:
            result = await self._adapter.test_connection()
            if result.get("success"):
                return PluginHealth.HEALTHY
            return PluginHealth.DEGRADED
        except Exception:
            return PluginHealth.DEGRADED

    # ============ 消息处理 ============

    async def _handle_message(self, message) -> None:
        """
        处理收到的飞书消息。

        如果绑定了 agent，则将消息转发给 agent 处理，并回复结果。
        """
        if not self._adapter:
            return

        ctx = self.context
        if ctx:
            ctx.logger.info(
                f"收到飞书消息: chat_id={message.chat_id}, "
                f"user_id={message.user_id}, content={message.content[:100]}"
            )

        # 如果有绑定的 agent，执行智能回复
        if self._agent:
            try:
                result = await self._agent.run(
                    task=message.content,
                    system_message=(
                        "你是一个通过飞书提供服务的太极 Agent。"
                        "请用友好、简洁的方式回复用户。"
                    ),
                )
                reply_text = result.content or "抱歉，我暂时无法处理您的请求。"
                await self._adapter.send_text(message.chat_id, reply_text)
            except Exception as e:
                if ctx:
                    ctx.logger.error(f"Agent 处理消息异常: {e}")
                await self._adapter.send_text(
                    message.chat_id,
                    f"处理您的消息时遇到问题：{e}",
                )

    def bind_agent(self, agent) -> None:
        """
        绑定 TaijiAgent 实例。

        绑定后，所有收到的飞书消息将自动转发给 agent 处理。
        """
        self._agent = agent

    # ============ 工具方法 ============

    async def feishu_test_connection(self) -> Dict[str, Any]:
        """测试飞书连接"""
        if not self._adapter:
            return {
                "success": False,
                "error": "适配器未初始化，请检查 app_id/app_secret 配置",
            }
        return await self._adapter.test_connection()

    async def feishu_send_message(
        self, chat_id: str, content: str, msg_type: str = "text"
    ) -> Dict[str, Any]:
        """通过飞书发送消息"""
        if not self._adapter:
            return {"success": False, "error": "适配器未初始化"}

        try:
            if msg_type == "text":
                ok = await self._adapter.send_text(chat_id, content)
            elif msg_type == "interactive":
                # 构建简单卡片
                card = {
                    "config": {"wide_screen_mode": True},
                    "elements": [{"tag": "markdown", "content": content}],
                }
                ok = await self._adapter.send_card(chat_id, card)
            else:
                ok = await self._adapter.send_text(chat_id, content)

            return {"success": ok, "chat_id": chat_id, "msg_type": msg_type}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_metrics(self) -> Dict[str, Any]:
        """获取插件指标"""
        if not self._adapter:
            return {"feishu.status": "not_configured"}

        conn_info = await self._adapter.test_connection()
        return {
            "feishu.status": "connected" if conn_info.get("success") else "error",
            "feishu.bot_name": conn_info.get("bot_name", "unknown"),
            "feishu.ws_alive": conn_info.get("ws_alive", False),
        }
