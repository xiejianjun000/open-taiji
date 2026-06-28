#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试 Taiji Verify 增强模块
"""

import sys
sys.path.insert(0, '/Users/mac/taiji-agent/src')

print("=" * 80)
print("🔍 调试增强模块")
print("=" * 80)
print()

# 测试1: 导入增强模块
print("1️⃣ 测试导入增强模块")
print("-" * 80)
try:
    from taiji_agent.taiji_verify.verifier_enhanced import (
        KnowledgeDatabase,
        NumberValidator,
        TemporalConsistencyChecker
    )
    print("✅ 导入成功！")
    print(f"   KnowledgeDatabase: {KnowledgeDatabase}")
    print(f"   NumberValidator: {NumberValidator}")
    print(f"   TemporalConsistencyChecker: {TemporalConsistencyChecker}")
except Exception as e:
    print(f"❌ 导入失败: {e}")
    import traceback
    traceback.print_exc()
print()

# 测试2: 实例化
print("2️⃣ 测试实例化")
print("-" * 80)
try:
    kb = KnowledgeDatabase()
    nv = NumberValidator()
    tc = TemporalConsistencyChecker()
    print("✅ 实例化成功！")
    print(f"   kb.facts 数量: {len(kb.facts)}")
    print(f"   nv.ranges 类别: {list(nv.ranges.keys())}")
    print(f"   tc.historical_events 数量: {len(tc.historical_events)}")
except Exception as e:
    print(f"❌ 实例化失败: {e}")
    import traceback
    traceback.print_exc()
print()

# 测试3: 调用知识库
print("3️⃣ 测试知识库 check_fact")
print("-" * 80)
try:
    kb = KnowledgeDatabase()

    test1 = "太阳从西边升起"
    result1 = kb.check_fact(test1)
    print(f"测试: {test1}")
    print(f"结果: is_valid={result1[0]}, risk={result1[1]:.1%}, explanation={result1[2]}")

    test2 = "水的沸点是100摄氏度"
    result2 = kb.check_fact(test2)
    print(f"\n测试: {test2}")
    print(f"结果: is_valid={result2[0]}, risk={result2[1]:.1%}, explanation={result2[2]}")
except Exception as e:
    print(f"❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()
print()

# 测试4: 调用数字验证器
print("4️⃣ 测试数字验证器")
print("-" * 80)
try:
    nv = NumberValidator()

    test_numbers = [
        ("中国人口约100亿", "中国", 100e8),
        ("北京人口约2000万", "北京", 2000e4),
        ("地球半径约6371公里", "地球半径", 6371e3),
    ]

    for text, category, number in test_numbers:
        is_valid, risk = nv.validate_number(number, category)
        print(f"测试: {text}")
        print(f"结果: is_valid={is_valid}, risk={risk:.1%}")
        print()
except Exception as e:
    print(f"❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()
print()

# 测试5: 调用时间一致性检查
print("5️⃣ 测试时间一致性检查")
print("-" * 80)
try:
    tc = TemporalConsistencyChecker()

    test_temporal = [
        "华盛顿出生于1732年",
        "华盛顿出生于1710年",
        "新中国成立于1949年",
    ]

    for text in test_temporal:
        issues = tc.check_temporal_consistency(text)
        print(f"测试: {text}")
        print(f"问题数量: {len(issues)}")
        if issues:
            for issue, risk in issues:
                print(f"  ⚠️ {issue}, risk={risk:.1%}")
        else:
            print("  ✅ 无问题")
        print()
except Exception as e:
    print(f"❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()
print()

# 测试6: 测试 HallucinationDetector
print("6️⃣ 测试 HallucinationDetector")
print("-" * 80)
try:
    from taiji_agent.taiji_verify import HallucinationDetector

    detector = HallucinationDetector()

    print("检查属性是否存在:")
    print(f"   hasattr(detector, '_knowledge_db'): {hasattr(detector, '_knowledge_db')}")
    print(f"   hasattr(detector, '_number_validator'): {hasattr(detector, '_number_validator')}")
    print(f"   hasattr(detector, '_temporal_checker'): {hasattr(detector, '_temporal_checker')}")

    if hasattr(detector, '_knowledge_db'):
        print(f"   _knowledge_db 类型: {type(detector._knowledge_db)}")
        print(f"   _knowledge_db 是否为 None: {detector._knowledge_db is None}")

    # 测试检测
    test_text = "太阳从西边升起"
    risk = detector.detect(test_text)
    print(f"\n测试文本: {test_text}")
    print(f"检测风险: {risk:.1%}")

    detailed = detector.detect_detailed(test_text)
    print(f"详细结果: {detailed}")
except Exception as e:
    print(f"❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()
print()

print("=" * 80)
print("🔍 调试完成！")
print("=" * 80)
