#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Taiji Verify 增强版知识溯源模块
添加内置事实数据库、数字验证、时间一致性检查
"""

import re
from typing import Dict, List, Optional, Tuple


class KnowledgeDatabase:
    """内置事实知识库"""

    def __init__(self):
        self.facts: Dict[str, str] = {}
        self._init_common_facts()

    def _init_common_facts(self):
        """初始化常见事实"""
        # 科学事实
        self.facts.update({
            "光速": "299792458 米/秒（约30万公里/秒）",
            "水的沸点": "100摄氏度（标准大气压）",
            "水的冰点": "0摄氏度",
            "地球半径": "约6371公里",
            "地球周长": "约40075公里（赤道）",
            "太阳质量": "约1.989×10³⁰千克",
            "月球质量": "约7.342×10²²千克",
            "光年": "约9.46万亿公里",
            "绝对零度": "-273.15摄氏度",
            "标准大气压": "101.325 kPa",
        })

        # 地理事实
        self.facts.update({
            "中国人口": "约14亿（2023年）",
            "中国面积": "约960万平方公里",
            "北京人口": "约2200万（2023年）",
            "上海人口": "约2500万（2023年）",
            "地球陆地面积": "约1.49亿平方公里",
            "地球海洋面积": "约3.61亿平方公里",
        })

        # 历史事实
        self.facts.update({
            "美国独立": "1776年7月4日",
            "新中国成立": "1949年10月1日",
            "改革开放": "1978年",
            "华盛顿出生": "1732年2月22日",
            "林肯出生": "1809年2月12日",
        })

        # 技术事实
        self.facts.update({
            "Python发布": "1991年",
            "互联网诞生": "1969年（ARPANET）",
            "万维网": "1989年（蒂姆·伯纳斯·李）",
            "Windows发布": "1985年",
            "iPhone发布": "2007年",
        })

    def check_fact(self, statement: str) -> Tuple[bool, float, str]:
        """
        检查陈述是否与已知事实矛盾

        Returns:
            (is_valid, risk_score, explanation)
        """
        statement_lower = statement.lower()

        # 检查数字类事实
        number_checks = [
            (r"光速[是为]*(约)?(\d+)\s*(米|km|公里)", self._check_light_speed, "光速"),
            (r"水[的]*(沸点|冰点)[是为]*(约)?(\d+)\s*度", self._check_water_temp, "水的温度"),
            (r"地球半径[是为]*(约)?(\d+)\s*(km|公里|千米)", self._check_earth_radius, "地球半径"),
            (r"(中国|北京|上海)(人口|有多少人)[是为]*(约)?(\d+)\s*(万|亿)?", self._check_china_population, "人口数量"),
        ]

        for pattern, checker, fact_name in number_checks:
            match = re.search(pattern, statement)
            if match:
                is_valid, risk = checker(match)
                if not is_valid:
                    return False, risk, f"与已知{fact_name}矛盾"

        # 检查明显错误陈述
        obvious_errors = [
            (r"太阳从[东西南北]+边升起", False, "太阳从东方升起"),
            (r"地球是[平立]的", False, "地球是球形的"),
            (r"人类不需要呼吸", False, "人类需要呼吸氧气"),
            (r"水在(\d+)度沸腾", lambda m: 95 <= int(m.group(1)) <= 105, "水在100度沸腾"),
        ]

        for pattern, expected, correct in obvious_errors:
            match = re.search(pattern, statement)
            if match:
                if callable(expected):
                    if not expected(match):
                        return False, 0.9, f"错误：{correct}"
                elif not expected:
                    return False, 0.9, f"错误：{correct}"

        return True, 0.1, "未检测到明显错误"

    def _check_light_speed(self, match) -> Tuple[bool, float]:
        """检查光速"""
        value = float(match.group(2))
        # 合理范围：28万~32万公里/秒
        if "km" in match.group(0) or "公里" in match.group(0):
            value_km = value * 1000 if value < 100 else value
            if not (280000 <= value_km <= 320000):
                return False, 0.8
        else:
            if not (2.8e8 <= value <= 3.2e8):
                return False, 0.8
        return True, 0.1

    def _check_water_temp(self, match) -> Tuple[bool, float]:
        """检查水的温度"""
        value = float(match.group(3))
        if not (95 <= value <= 105):
            return False, 0.85
        return True, 0.1

    def _check_earth_radius(self, match) -> Tuple[bool, float]:
        """检查地球半径"""
        value = float(match.group(2))
        # 合理范围：6000~7000公里
        if not (6000 <= value <= 7000):
            return False, 0.8
        return True, 0.1

    def _check_china_population(self, match) -> Tuple[bool, float]:
        """检查人口数量"""
        value = float(match.group(4))
        unit = match.group(5) if match.group(5) else ""

        if "中国" in match.group(0):
            # 中国人口约14亿
            if unit == "亿":
                if not (12 <= value <= 16):
                    return False, 0.85
            elif unit == "万":
                if not (120000 <= value <= 160000):
                    return False, 0.85
            else:
                if not (1.2e9 <= value <= 1.6e9):
                    return False, 0.85
        elif "北京" in match.group(0):
            if unit == "万":
                if not (1500 <= value <= 3000):
                    return False, 0.8
        elif "上海" in match.group(0):
            if unit == "万":
                if not (2000 <= value <= 3000):
                    return False, 0.8

        return True, 0.1


class NumberValidator:
    """数字范围验证器"""

    def __init__(self):
        self.ranges = {
            "人口": {
                "中国": (13e8, 15e8),
                "北京": (1.5e7, 3e7),
                "上海": (2e7, 3e7),
                "美国": (3e8, 3.5e8),
                "日本": (1.2e8, 1.3e8),
                "全球": (7e9, 9e9),
            },
            "面积": {
                "中国": (9e6, 1e7),  # 900万~1000万平方公里
                "北京": (1.6e4, 1.7e4),  # 1.6万~1.7万平方公里
                "地球陆地": (1.4e8, 1.6e8),
            },
            "距离": {
                "地球半径": (6e6, 7e6),  # 6000~7000公里
                "地球周长": (3.5e7, 4.5e7),
                "月球距离": (3.5e8, 4e8),  # 35万~40万公里
                "太阳距离": (1.4e11, 1.6e11),  # 1.5亿公里
            },
        }

    def validate_number(self, number: float, category: str, location: str = None) -> Tuple[bool, float]:
        """
        验证数字是否在合理范围内

        Returns:
            (is_valid, risk_score)
        """
        if category not in self.ranges:
            return True, 0.3  # 未知类别，中等风险

        if location:
            if location in self.ranges[category]:
                min_val, max_val = self.ranges[category][location]
                if not (min_val <= number <= max_val):
                    return False, 0.85
        else:
            # 检查所有可能的范围
            for min_val, max_val in self.ranges[category].values():
                if min_val <= number <= max_val:
                    return True, 0.1
            return False, 0.8

        return True, 0.1

    def check_numbers_in_text(self, text: str) -> List[Tuple[str, float, float]]:
        """
        检查文本中的所有数字

        Returns:
            List of (context, number, risk_score)
        """
        results = []

        # 提取数字及其上下文
        number_patterns = [
            (r".{10}人口[是为]*(约)?(\d+(?:\.\d+)?)\s*(万|亿)?", "人口", None),
            (r".{10}(?:北京|上海|纽约|东京)[是为]*(约)?(\d+(?:\.\d+)?)\s*(万|亿)?", "人口", None),
            (r".{10}(?:中国|美国|地球)[的]*(?:面积|多大)[是为]*(约)?(\d+(?:\.\d+)?)\s*(万|亿)?平方公里", "面积", None),
            (r".{10}(?:半径|直径|距离)[是为]*(约)?(\d+(?:\.\d+)?)\s*(km|公里|千米|万|亿)?公里", "距离", None),
        ]

        for pattern, category, location in number_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                number = float(match.group(2))
                unit = match.group(3) if match.group(3) else ""

                # 转换单位
                if unit in ["万"]:
                    number *= 1e4
                elif unit in ["亿"]:
                    number *= 1e8

                is_valid, risk = self.validate_number(number, category, location)
                context = match.group(0)[:30]

                if not is_valid:
                    results.append((context, number, risk))

        return results


class TemporalConsistencyChecker:
    """时间一致性检查器"""

    def __init__(self):
        self.historical_events = {
            "美国独立": 1776,
            "新中国成立": 1949,
            "改革开放": 1978,
            "互联网诞生": 1969,
            "万维网发明": 1989,
            "Windows发布": 1985,
            "iPhone发布": 2007,
            "苏联解体": 1991,
            "一战开始": 1914,
            "二战开始": 1939,
            "二战结束": 1945,
        }

        self.person_birth_years = {
            "华盛顿": 1732,
            "林肯": 1809,
            "爱因斯坦": 1879,
            "牛顿": 1643,
            "居里夫人": 1867,
        }

    def check_temporal_consistency(self, text: str) -> List[Tuple[str, float]]:
        """
        检查时间一致性

        Returns:
            List of (issue_description, risk_score)
        """
        issues = []

        # 检查历史事件日期
        for event, year in self.historical_events.items():
            if event in text:
                # 查找文本中的年份
                year_matches = re.findall(r"\b(1[0-9]{3}|20[0-2][0-9])\b", text)
                for match_year in year_matches:
                    match_year = int(match_year)
                    # 检查是否在事件前后10年内
                    if abs(match_year - year) > 10:
                        issues.append(
                            (f"'{event}'发生在{year}年，文本中提到{match_year}年", 0.85)
                        )

        # 检查人物出生年份
        for person, year in self.person_birth_years.items():
            if person in text:
                year_matches = re.findall(r"\b(1[0-9]{3}|20[0-2][0-9])\b", text)
                for match_year in year_matches:
                    match_year = int(match_year)
                    if abs(match_year - year) > 5:
                        issues.append(
                            (f"'{person}'出生于{year}年，文本中提到{match_year}年", 0.9)
                        )

        return issues


def test_enhanced_detector():
    """测试增强版检测器"""
    print("=" * 80)
    print("🧪 Taiji Verify 增强版知识溯源测试")
    print("=" * 80)
    print()

    # 测试知识数据库
    print("1️⃣ 知识数据库测试")
    print("-" * 80)
    kb = KnowledgeDatabase()

    test_statements = [
        "太阳从西边升起，因为地球自转方向改变了",
        "水的沸点是100摄氏度",
        "地球半径约6371公里",
        "中国人口约14亿",
        "光速约30万公里/秒",
        "华盛顿出生于1732年",
    ]

    for stmt in test_statements:
        is_valid, risk, explanation = kb.check_fact(stmt)
        status = "✅" if is_valid else "❌"
        risk_color = "🟢" if risk < 0.3 else ("🟡" if risk < 0.6 else "🔴")

        print(f"{status} {risk_color} {risk:.1%} | {explanation}")
        print(f"   📝 {stmt}")
        print()

    # 测试数字验证器
    print("\n2️⃣ 数字验证器测试")
    print("-" * 80)
    nv = NumberValidator()

    test_numbers = [
        ("中国人口约15亿", True),
        ("中国人口约100亿", False),
        ("地球半径约6371公里", True),
        ("地球半径约100公里", False),
    ]

    for text, expected_valid in test_numbers:
        results = nv.check_numbers_in_text(text)
        if results:
            is_valid = results[0][2] < 0.5
            status = "✅" if is_valid == expected_valid else "❌"
            print(f"{status} {text}")
            if not is_valid:
                print(f"   ⚠️  检测到异常数字: {results[0][0]}")
        else:
            print(f"⚪ 未检测到需要验证的数字: {text}")
        print()

    # 测试时间一致性
    print("\n3️⃣ 时间一致性检查测试")
    print("-" * 80)
    tc = TemporalConsistencyChecker()

    test_temporal = [
        "华盛顿出生于1732年2月22日",
        "据历史记载，华盛顿出生于1710年",
        "新中国成立于1949年10月1日",
        "互联网诞生于1969年",
    ]

    for text in test_temporal:
        issues = tc.check_temporal_consistency(text)
        if issues:
            for issue, risk in issues:
                print(f"❌ 🔴 {risk:.1%} | {issue}")
        else:
            print(f"✅ {text}")
        print()


if __name__ == "__main__":
    test_enhanced_detector()
