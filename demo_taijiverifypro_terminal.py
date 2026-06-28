#!/usr/bin/env python3
"""
TaijiVerifyPro v2.0 终端演示 — 模拟 taiji-agent 对话并展示防幻觉检测

在终端中完整展示：
1. 用户发送消息
2. LLM 生成回复（模拟）
3. TaijiVerifyPro 7层防御检测
4. 判定结果 + 详细报告
"""

import sys
import os
import time
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from taiji_agent.agent.engine import TaijiAgent, AgentConfig


class MockResponse:
    """模拟 LLM 响应"""
    def __init__(self, content: str):
        self.content = content
        self.tool_calls = None


# ════════════════════════════════════════════════════════
# 测试场景定义
# ════════════════════════════════════════════════════════

SCENARIOS = [
    {
        "name": "🔴 明显常识错误",
        "user_msg": "太阳为什么从西边升起？",
        "llm_reply": "根据天文学研究，太阳每天从西边升起，东边落下。这是由于地球自转方向导致的自然现象。",
        "expect_block": True,
    },
    {
        "name": "🟠 事实数据错误",
        "user_msg": "光速的准确值是多少？",
        "llm_reply": "光速约为10万公里每秒，这是物理学的基本常数。爱因斯坦在相对论中首次提出了这个概念。",
        "expect_warning": True,
    },
    {
        "name": "🟡 地球形状错误",
        "user_msg": "地球是圆的还是扁的？",
        "llm_reply": "现代科学已经证实，地球实际上是一个扁平的圆盘，就像一张大饼一样悬浮在宇宙中。",
        "expect_block": True,
    },
    {
        "name": "🟢 正常科普回复",
        "user_msg": "光速的准确值是多少？",
        "llm_reply": "光速在真空中的准确值为299,792,458米/秒，约等于每秒30万公里。这一数值由物理学家通过精确测量得出，已被众多实验所验证。根据爱因斯坦的狭义相对论，光速是宇宙中的速度上限。",
        "expect_pass": True,
    },
    {
        "name": "🟢 带不确定性的诚实回答",
        "user_msg": "暗物质到底是什么？",
        "llm_reply": "关于暗物质的确切本质，目前科学界还没有完全一致的结论。据我所知，它可能是一种不与电磁相互作用的粒子，但具体是什么粒子还需要更多研究来验证。科学家们正在通过多种实验尝试探测它。",
        "expect_pass": True,
    },
]


def print_banner():
    print("\n" + "╔" + "═"*68 + "╗")
    print("║" + "  🛡️  TaijiVerifyPro v2.0 — 防幻觉系统终端演示 ".center(66) + "║")
    print("║" + "  业界领先的多层次防幻觉验证系统 (7层防御) ".center(66) + "║")
    print("╚" + "═"*68 + "╝")


def print_separator(char="─", length=70):
    print(char * length)


async def run_demo():
    print_banner()

    # 初始化引擎
    config = AgentConfig(
        taijiverifypro_enabled=True,
        taijiverifypro_auto_block=True,
        taijiverifypro_show_report=True,
        verbose=True,
    )

    agent = TaijiAgent(config=config)

    if not agent.taijiverifypro:
        print("❌ TaijiVerifyPro 初始化失败！")
        return

    print(f"\n✅ 引擎已初始化 | 版本: {agent.taijiverifypro.system_info['version']}")
    print(f"   运行模式: {agent.taijiverifypro.system_info['mode']}")
    print(f"   知识库条目: {agent.taijiverifypro.system_info['knowledge_facts']} 个事实")
    print(f"   阈值穿透: {'✅ 开启' if config.taijiverifypenetration_enabled else '❌ 关闭'}")

    print("\n" + "="*70)
    print("  开始模拟对话测试...")
    print("="*70)

    for i, scenario in enumerate(SCENARIOS, 1):
        print(f"\n{'━'*70}")
        print(f"  📋 场景 {i}/{len(SCENARIOS)}: {scenario['name']}")
        print(f"{'━'*70}")

        # 显示用户消息
        print(f"\n  👤 用户: {scenario['user_msg']}")

        # 显示 LLM 回复（原始）
        print(f"\n  🤖 AI回复 (原始):")
        print(f"  ┌{'─'*66}┐")
        lines = scenario['llm_reply'].split('\n')
        for line in lines:
            print(f"  │ {line:<66} │")
        print(f"  └{'─'*66}┘")

        # 执行 TaijiVerifyPro 验证
        print(f"\n  ⏳ 正在执行 TaijiVerifyPro 防幻觉检测...")
        start = time.time()

        response = MockResponse(scenario['llm_reply'])
        verified_response = await agent._verify_and_annotate(response)

        elapsed_ms = (time.time() - start) * 1000

        # 显示检测结果
        print(f"\n  🛡️  检测完成 ({elapsed_ms:.0f}ms)")
        print(f"  {'─'*66}")

        output = verified_response.content

        if "🚫 [TaijiVerifyPro 拦截]" in output:
            print(f"\n  🔴 判定: BLOCK (已拦截)")
            print(f"  {'─'*66}")
            # 打印完整拦截报告
            print(output)
        elif "⚠️ [TaijiVerifyPro 警告]" in output:
            print(f"\n  🟠 判定: HIGH_RISK (警告)")
            print(f"  {'─'*66}")
            print(output)
        else:
            print(f"\n  🟢 判定: PASS/LOW_RISK (通过)")
            print(f"  {'─'*66}")
            print(f"  ✅ 回复内容无变化，未触发拦截或警告")

        # 等待用户查看
        if i < len(SCENARIOS):
            print(f"\n  ⏳ 3秒后进入下一个测试场景...")
            await asyncio.sleep(3)

    # 汇总
    print(f"\n\n{'='*70}")
    print(f"  🎉 测试演示完成！")
    print(f"{'='*70}")
    print(f"""
  📊 TaijiVerifyPro v2.0 工作流程总结:

  用户输入 → LLM生成回复 → 7层防御检测 → 判定输出
                              ↓
              ┌─────────────────────────────┐
              │ Layer 1: 快速预检 (0.1ms)   │ ← 过滤明显错误
              │ Layer 2: 符号层验证          │ ← 绝对化/自我引用
              │ Layer 3: 事实核查 (动态权重)  │ ← 知识库+数字+时间
              │ Layer 4: 语义一致性          │ ← 自相矛盾检查
              │ Layer 5: 失败模式 (16种)     │ ← CRITICAL直接拦截
              │ Layer 6: 向量流水线 [可选]   │ ← 完整TaijiVerifyEngine
              │ Layer 7: 综合判定 (阈值穿透) │ ← 加权融合
              └─────────────────────────────┘
                              ↓
              risk < 30%         risk >= 85%
              (PASS/LOW)        (BLOCK)
               ✅ 正常输出       🚫 拦截+详细报告

  💡 你现在可以在 taiji-agent 终端中对话，
     所有回复都会经过同样的防幻觉检测流程！
""")


def main():
    try:
        asyncio.run(run_demo())
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断测试")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
