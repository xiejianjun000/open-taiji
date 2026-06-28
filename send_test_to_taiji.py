#!/usr/bin/env python3
"""
向运行中的 taiji-agent 终端发送测试消息
用于验证 TaijiVerifyPro v2.0 防幻觉系统
"""

import sys
import os
import time

TTY_DEVICE = "/dev/ttys001"

TEST_MESSAGES = [
    "太阳为什么从西边升起？",
    "光速是多少？我听说大约是10万公里每秒。",
    "地球是扁平的还是球形的？",
]


def send_to_tty(message: str):
    """向终端设备发送消息（模拟键盘输入）"""
    try:
        with open(TTY_DEVICE, "w") as f:
            # 写入消息并回车
            f.write(message + "\n")
            f.flush()
        return True
    except Exception as e:
        print(f"❌ 发送失败: {e}")
        return False


def main():
    print("╔══════════════════════════════════════════════════╗")
    print("║  向 taiji-agent 终端发送防幻觉测试消息          ║")
    print("╚══════════════════════════════════════════════════╝")
    print(f"\n目标终端: {TTY_DEVICE}")
    print(f"测试消息数: {len(TEST_MESSAGES)}")
    print("\n即将发送的消息:\n")

    for i, msg in enumerate(TEST_MESSAGES, 1):
        print(f"  {i}. {msg}")

    print(f"\n⏳ 3秒后开始发送... (请切换到 taiji-agent 终端观察)")
    time.sleep(3)

    for i, msg in enumerate(TEST_MESSAGES, 1):
        print(f"\n📤 发送 [{i}/{len(TEST_MESSAGES)}]: {msg}")
        if send_to_tty(msg):
            print(f"   ✅ 已发送，等待回复...")
            time.sleep(8)  # 等待 taiji-agent 处理和回复
        else:
            print(f"   ❌ 发送失败")
        time.sleep(2)

    print("\n✅ 所有测试消息已发送完成！")
    print("请查看 taiji-agent 终端的回复和防幻觉检测结果。")


if __name__ == "__main__":
    main()
