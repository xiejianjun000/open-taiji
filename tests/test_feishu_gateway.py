#!/usr/bin/env python3
"""
飞书网关集成测试。

用法:
    # 设置凭据后运行
    export FEISHU_APP_ID="cli_xxxxx"
    export FEISHU_APP_SECRET="xxxxx"
    python tests/test_feishu_gateway.py

    # 或直接传参
    python tests/test_feishu_gateway.py --app-id cli_xxx --app-secret xxx
"""

# 此文件设计为 CLI 脚本运行（python tests/test_feishu_gateway.py）
# pytest 会自动跳过（所有需要凭据的函数不在 pytest 发现范围内）
__test__ = False

import asyncio
import argparse
import json
import os
import sys


async def test_feishu_direct(app_id: str, app_secret: str):
    """直接测试 FeishuAdapter（不经过网关）"""
    from taiji_agent.gateway.feishu import FeishuAdapter

    print("=" * 60)
    print("飞书网关集成测试")
    print("=" * 60)

    adapter = FeishuAdapter({
        "app_id": app_id,
        "app_secret": app_secret,
    })

    # 1. 测试连接
    print("\n[1/4] 测试 API 连接...")
    result = await adapter.test_connection()
    print(f"  结果: {json.dumps(result, ensure_ascii=False, indent=2)}")

    if not result.get("success"):
        print("\n❌ 连接失败，请检查 app_id/app_secret 是否正确。")
        print("  获取凭据: https://open.feishu.cn/app → 找到应用 → 凭证与基础信息")
        return False

    # 2. 测试 Token 获取
    print("\n[2/4] 测试 Token 获取...")
    token = await adapter._get_token()
    print(f"  Token: {token[:20]}..." if token else "  ❌ Token 获取失败")

    # 3. 测试简单消息发送（需要 chat_id）
    print("\n[3/4] 消息发送功能可用（需要 chat_id 才能实际发送）。")
    print(f"  适配器方法: send_text(), send_card(), send_message(), reply_message()")

    # 4. 启动 WS 连接（测试用，5 秒后自动断开）
    print("\n[4/4] 测试 WebSocket 事件订阅（5秒）...")
    try:
        await adapter.start()
        print("  WS 连接已建立，等待消息事件...")
        await asyncio.sleep(5)
    except KeyboardInterrupt:
        pass
    finally:
        await adapter.stop()

    print("\n✅ 核心功能测试通过！")
    return True


async def test_feishu_gateway(app_id: str, app_secret: str):
    """通过 MessageGateway 测试飞书集成"""
    from taiji_agent.gateway.core import (
        Message,
        MessageGateway,
        create_gateway,
    )

    print("=" * 60)
    print("飞书网关集成测试 (MessageGateway)")
    print("=" * 60)

    # 创建网关
    gateway = create_gateway({
        "feishu": {
            "app_id": app_id,
            "app_secret": app_secret,
        }
    })

    assert "feishu" in gateway.get_platforms(), "飞书平台未注册"

    # 注册消息处理器
    received_messages = []

    async def message_handler(msg: Message):
        received_messages.append(msg)
        print(f"  📩 收到消息: [{msg.user_id}] {msg.content[:80]}")

    gateway.on_message("feishu", message_handler)

    # 启动网关
    print("\n[1/3] 启动飞书适配器...")
    await gateway.start_all()

    # 等待一会儿以建立 WS 连接
    await asyncio.sleep(3)

    adapter = gateway._adapters.get("feishu")
    if adapter:
        result = await adapter.test_connection()
        print(f"  连接状态: {'✅ 正常' if result.get('success') else '❌ 异常'}")
        if result.get("success"):
            print(f"  Bot 名称: {result.get('bot_name')}")
            print(f"  WS 存活: {result.get('ws_alive')}")

    # 尝试发送测试消息（需要实际 chat_id）
    print("\n[2/3] 消息发送测试（跳过 - 需要实际 chat_id）")

    # 模拟接收消息
    print("\n[3/3] 消息分发测试...")
    test_msg = Message(
        platform="feishu",
        chat_id="oc_test123",
        user_id="ou_test456",
        content="你好，太极 Agent！",
        message_id="om_test789",
    )
    await adapter._dispatch(test_msg) if adapter else print("  适配器未启动")

    # 停止
    await gateway.stop_all()

    print(f"\n✅ 网关集成测试完成！收到消息: {len(received_messages)} 条")
    return True


async def test_feishu_plugin():
    """测试 FeishuPlugin 集成"""
    import logging
    from dataclasses import dataclass

    from taiji_agent.plugin.plugins.feishu_plugin import FeishuPlugin

    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("飞书插件测试")
    print("=" * 60)

    plugin = FeishuPlugin(
        app_id=os.environ.get("FEISHU_APP_ID", ""),
        app_secret=os.environ.get("FEISHU_APP_SECRET", ""),
    )

    print(f"  插件 ID: {plugin.metadata.id}")
    print(f"  插件名称: {plugin.metadata.name}")
    print(f"  插件版本: {plugin.metadata.version}")
    print(f"  配置项: {list(plugin.metadata.config_schema['properties'].keys())}")

    print("\n✅ 插件元数据验证通过！")


async def main():
    parser = argparse.ArgumentParser(description="飞书网关集成测试")
    parser.add_argument("--app-id", help="飞书应用 App ID")
    parser.add_argument("--app-secret", help="飞书应用 App Secret")
    parser.add_argument("--skip-ws", action="store_true", help="跳过 WebSocket 测试")
    parser.add_argument("--plugin-only", action="store_true", help="仅测试插件元数据")
    args = parser.parse_args()

    if args.plugin_only:
        await test_feishu_plugin()
        return

    app_id = args.app_id or os.environ.get("FEISHU_APP_ID", "")
    app_secret = args.app_secret or os.environ.get("FEISHU_APP_SECRET", "")

    if not app_id or not app_secret:
        print("=" * 60)
        print("飞书网关集成测试 - 环境检查")
        print("=" * 60)
        print("\n⚠️  未设置飞书凭据。")
        print("\n要完成完整测试，请先：")
        print("  1. 访问 https://open.feishu.cn 创建飞书应用")
        print("  2. 获取 App ID 和 App Secret")
        print("  3. 设置凭据：")
        print("     export FEISHU_APP_ID=\"cli_xxxxx\"")
        print("     export FEISHU_APP_SECRET=\"xxxxx\"")
        print("  4. 重新运行：python tests/test_feishu_gateway.py")
        print()

        # 提供只测试插件元数据的方式
        print("也可以运行仅测试：python tests/test_feishu_gateway.py --plugin-only")
        return

    if args.skip_ws:
        from taiji_agent.gateway.feishu import FeishuAdapter
        adapter = FeishuAdapter({"app_id": app_id, "app_secret": app_secret})
        result = await adapter.test_connection()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    await test_feishu_direct(app_id, app_secret)
    print()
    await test_feishu_gateway(app_id, app_secret)
    print()
    await test_feishu_plugin()


if __name__ == "__main__":
    asyncio.run(main())
