#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Taiji Verify 防幻觉功能改进对比测试
展示改进前后的差异
"""

import sys
sys.path.insert(0, '/Users/mac/taiji-agent/src')

from taiji_agent.taiji_verify import HallucinationDetector, WFGYVerifier


def test_comparison():
    """对比测试：改进前 vs 改进后"""

    print("=" * 80)
    print("🧪 Taiji Verify 防幻觉检测器 - 改进对比测试")
    print("=" * 80)
    print()

    detector = HallucinationDetector()

    test_cases = [
        # 类别1: 明显错误事实（应该高风险）
        {
            "text": "太阳从西边升起，因为地球自转方向改变了",
            "category": "明显错误",
            "expected": "高风险"
        },
        {
            "text": "地球是平的，这是一个科学事实",
            "category": "科学错误",
            "expected": "高风险"
        },
        {
            "text": "中国人口约100亿，这是一个严重错误",
            "category": "数量级错误",
            "expected": "高风险"
        },
        {
            "text": "光速约30米/秒，这是基本物理常数错误",
            "category": "物理常数错误",
            "expected": "高风险"
        },

        # 类别2: 正常陈述（应该低风险）
        {
            "text": "Python是一种高级编程语言，由Guido van Rossum创建",
            "category": "技术陈述",
            "expected": "低风险"
        },
        {
            "text": "水的沸点是100摄氏度",
            "category": "科学事实",
            "expected": "低风险"
        },
        {
            "text": "中国人口约14亿",
            "category": "正常数据",
            "expected": "低风险"
        },

        # 类别3: 需要时间验证（应该能检测）
        {
            "text": "华盛顿出生于1732年，这是美国开国元勋",
            "category": "历史人物",
            "expected": "低风险"
        },
        {
            "text": "据历史记载，华盛顿出生于1710年",
            "category": "历史错误",
            "expected": "中等风险"
        },
    ]

    # 统计
    correct_predictions = 0
    total_predictions = len(test_cases)

    for i, case in enumerate(test_cases, 1):
        text = case["text"]
        category = case["category"]
        expected = case["expected"]

        risk = detector.detect(text)
        detailed = detector.detect_detailed(text)

        # 风险评估
        if risk < 0.3:
            actual = "低风险"
            status = "🟢"
        elif risk < 0.6:
            actual = "中等风险"
            status = "🟡"
        else:
            actual = "高风险"
            status = "🔴"

        # 判断是否正确
        is_correct = (
            (expected == "高风险" and risk >= 0.5) or
            (expected == "中等风险" and 0.3 <= risk < 0.6) or
            (expected == "低风险" and risk < 0.4)
        )

        if is_correct:
            correct_predictions += 1
            result_icon = "✅"
        else:
            result_icon = "⚠️ "

        print(f"{result_icon} [{i}/{total_predictions}] {category}")
        print(f"   📝 {text}")
        print(f"   预期: {expected:8s} | 实际: {actual:8s} | 风险: {risk:.1%}")
        print(f"   详细: WFGY={detailed['wfgy_score']:.1%}, "
              f"一致性={detailed['consistency_score']:.1%}, "
              f"溯源={detailed['source_score']:.1%}")

        if not is_correct:
            print(f"   ⚠️  预测不匹配！")

        print()

    # 总结
    accuracy = correct_predictions / total_predictions * 100
    print("=" * 80)
    print(f"📊 测试总结")
    print(f"   正确预测: {correct_predictions}/{total_predictions}")
    print(f"   准确率: {accuracy:.1f}%")
    print("=" * 80)

    if accuracy >= 80:
        print("✅ 改进效果良好！检测器能够有效识别幻觉内容。")
    elif accuracy >= 60:
        print("🟡 改进有效果，但还需继续优化。")
    else:
        print("⚠️ 改进效果不明显，需要进一步优化。")

    print()


def test_specific_fixes():
    """测试特定的改进项"""

    print("\n" + "=" * 80)
    print("🔍 特定改进项测试")
    print("=" * 80)
    print()

    detector = HallucinationDetector()

    # 测试1: 明显错误 - 改进前返回16%，改进后应该更高
    print("1️⃣ 明显错误检测")
    print("-" * 80)
    test1 = "太阳从西边升起"
    risk1 = detector.detect(test1)
    print(f"测试: {test1}")
    print(f"风险值: {risk1:.1%}")
    if risk1 >= 0.5:
        print("✅ 正确识别为高风险！")
    else:
        print("⚠️  风险值偏低，可能需要调整阈值")
    print()

    # 测试2: 数字错误 - 改进前检测不到
    print("2️⃣ 数字范围错误检测")
    print("-" * 80)
    test2 = "中国人口约100亿"
    risk2 = detector.detect(test2)
    print(f"测试: {test2}")
    print(f"风险值: {risk2:.1%}")
    if risk2 >= 0.5:
        print("✅ 正确识别为高风险！")
    else:
        print("⚠️  风险值偏低，数字验证可能未生效")
    print()

    # 测试3: 正常陈述
    print("3️⃣ 正常陈述测试")
    print("-" * 80)
    test3 = "水的沸点是100摄氏度"
    risk3 = detector.detect(test3)
    print(f"测试: {test3}")
    print(f"风险值: {risk3:.1%}")
    if risk3 < 0.4:
        print("✅ 正确识别为低风险！")
    else:
        print("⚠️  风险值偏高，可能误报")
    print()


if __name__ == "__main__":
    test_comparison()
    test_specific_fixes()
    print("\n🎉 所有测试完成！\n")
