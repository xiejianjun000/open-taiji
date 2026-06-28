#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Taiji Verify 防幻觉功能测试脚本
测试各种类型的幻觉内容
"""

from taiji_agent.taiji_verify import HallucinationDetector, WFGYVerifier


def test_hallucination_detection():
    """测试幻觉检测功能"""

    detector = HallucinationDetector()
    verifier = WFGYVerifier()

    test_cases = [
        # 正常陈述（低风险）
        ("Python 是一种编程语言", "正常技术陈述"),
        ("水的沸点是100摄氏度", "正常科学事实"),

        # 明显错误（高风险）
        ("太阳从西边升起", "明显错误事实"),
        ("地球是平的", "科学错误"),
        ("人类不需要呼吸氧气", "基本常识错误"),

        # 模糊/不确定内容（中等风险）
        ("我觉得明天会下雨", "主观预测"),
        ("根据某些科学家的说法...", "未指明来源"),

        # 数字错误
        ("中国人口是100亿", "数量级错误"),
        ("光速是30米/秒", "数量级错误"),

        # 历史错误
        ("华盛顿是1812年出生的", "历史日期错误"),
    ]

    print("=" * 80)
    print("🧪 Taiji Verify 防幻觉功能测试")
    print("=" * 80)
    print()

    for text, description in test_cases:
        risk = detector.detect(text)
        passed = verifier.verify(text)

        # 风险等级
        if risk < 0.3:
            risk_level = "🟢 低风险"
            risk_color = "green"
        elif risk < 0.6:
            risk_level = "🟡 中等风险"
            risk_color = "yellow"
        else:
            risk_level = "🔴 高风险"
            risk_color = "red"

        status = "✅ 通过" if passed else "❌ 违规"

        print(f"{risk_color}")
        print(f"📝 内容: {text}")
        print(f"   类型: {description}")
        print(f"   风险: {risk_level} ({risk:.1%})")
        print(f"   验证: {status}")
        print(f"{risk_color}" if risk_color != "green" else "")
        print("-" * 80)


def test_real_time_detection():
    """模拟实时对话中的幻觉检测"""

    print("\n" + "=" * 80)
    print("🔄 实时对话模拟")
    print("=" * 80)
    print()

    detector = HallucinationDetector()

    user_inputs = [
        "你好，请介绍一下北京",
        "请写一首关于月亮的诗",
        "北京有多少人口？准确数字",
        "Python 是什么？",
        "给我讲个笑话",
    ]

    for user_input in user_inputs:
        print(f"👤 用户: {user_input}")

        # 模拟 LLM 回复（实际是随机生成）
        import random
        responses = [
            "北京是中国的首都，人口约2200万。",
            "月亮是中国古代诗词中常见的意象，象征着思乡和团圆。",
            "根据最新统计，北京常住人口约为2189万人。",
            "Python是一种高级编程语言，由Guido van Rossum创建。",
            "为什么程序员总是分不清万圣节和圣诞节？因为Oct 31 = Dec 25。",
        ]

        response = random.choice(responses)
        risk = detector.detect(response)

        print(f"🤖 回复: {response}")

        if risk > 0.3:
            print(f"   ⚠️  幻觉风险: {risk:.1%}")
        else:
            print(f"   ✅ 风险可控: {risk:.1%}")

        print()


if __name__ == "__main__":
    print("\n🔧 启动 Taiji Verify 测试...\n")
    test_hallucination_detection()
    test_real_time_detection()
    print("\n✅ 测试完成！\n")
