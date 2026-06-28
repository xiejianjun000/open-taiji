"""
Data Desensitization (数据脱敏)
敏感数据识别与脱敏规则引擎模块

基于个人信息保护法和数据安全法实现：
- 敏感数据识别（身份证/手机号/地址等）
- 数据脱敏规则引擎
- 脱敏策略配置（全遮盖/部分遮盖/替换/哈希）

映射生态环境部技术保障体系：敏感行为拦截+安全围栏
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any, Callable


class SensitiveType(str, Enum):
    """敏感数据类型"""
    # 身份标识
    ID_CARD = "id_card"                     # 身份证号
    PASSPORT = "passport"                    # 护照号
    MILITARY_ID = "military_id"             # 军官证
    
    # 联系方式
    PHONE = "phone"                         # 手机号
    EMAIL = "email"                         # 电子邮箱
    ADDRESS = "address"                    # 家庭住址
    
    # 金融信息
    BANK_CARD = "bank_card"                 # 银行卡号
    CREDIT_CARD = "credit_card"             # 信用卡号
    
    # 个人属性
    NAME = "name"                          # 姓名
    GENDER = "gender"                      # 性别
    BIRTHDATE = "birthdate"                # 出生日期
    AGE = "age"                            # 年龄
    
    # 生态环境敏感
    GPS_LOCATION = "gps_location"           # GPS定位
    FACILITY_NAME = "facility_name"         # 污染源设施名称
    POLLUTION_DATA = "pollution_data"      # 污染数据
    COMPANY_NAME = "company_name"          # 企业名称
    TRADE_SECRET = "trade_secret"          # 商业机密
    
    # 通用
    PASSWORD = "password"                  # 密码
    API_KEY = "api_key"                    # API密钥
    TOKEN = "token"                        # Token
    IP_ADDRESS = "ip_address"              # IP地址


class DesensitizationMethod(str, Enum):
    """脱敏方法"""
    FULL_MASK = "full_mask"                # 全遮盖: 138****5678
    PARTIAL_MASK = "partial_mask"          # 部分遮盖: 张*
    REPLACE = "replace"                    # 替换: [已脱敏]
    HASH = "hash"                          # 哈希: sm3(text)
    REDACT = "redact"                       # 删除: (空)
    RANDOM = "random"                       # 随机: 随机生成


@dataclass
class DesensitizationRule:
    """脱敏规则"""
    type: SensitiveType                      # 敏感数据类型
    method: DesensitizationMethod           # 脱敏方法
    
    # 方法参数
    mask_char: str = "*"                   # 遮盖字符
    mask_ratio: float = 0.5                 # 遮盖比例
    hash_salt: str = ""                     # 哈希盐值
    replacement: str = "[已脱敏]"           # 替换文本
    preserve_length: bool = True            # 是否保留长度
    
    # 条件
    min_length: Optional[int] = None        # 最小长度（用于正则匹配）
    max_length: Optional[int] = None        # 最大长度
    
    # 优先级
    priority: int = 100                     # 优先级（数字越小优先级越高）


@dataclass
class DetectionPattern:
    """检测模式"""
    type: SensitiveType
    pattern: str                            # 正则表达式
    sample: str = ""                        # 示例
    description: str = ""


@dataclass
class DetectionResult:
    """检测结果"""
    type: SensitiveType
    value: str                              # 原始值
    start: int                              # 起始位置
    end: int                                # 结束位置
    confidence: float                        # 置信度 0-1
    context: str = ""                        # 上下文


@dataclass
class DesensitizationResult:
    """脱敏结果"""
    original: str                           # 原始值
    desensitized: str                      # 脱敏后值
    type: SensitiveType                      # 类型
    method: DesensitizationMethod           # 使用的方法
    success: bool
    error: str = ""


class SensitiveDataDetector:
    """
    敏感数据检测器
    
    使用正则表达式和规则匹配敏感数据。
    
    Usage::
        detector = SensitiveDataDetector()
        results = detector.detect("身份证号: 110101199001011234")
        for r in results:
            print(f"检测到 {r.type.value}: {r.value}")
    """
    
    # 内置检测模式
    BUILTIN_PATTERNS: list[DetectionPattern] = [
        # 身份证（18位）
        DetectionPattern(
            type=SensitiveType.ID_CARD,
            pattern=r'\b[1-9]\d{5}(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b',
            sample="110101199001011234",
            description="中国居民身份证18位"
        ),
        # 手机号
        DetectionPattern(
            type=SensitiveType.PHONE,
            pattern=r'\b1[3-9]\d{9}\b',
            sample="13812345678",
            description="中国大陆手机号"
        ),
        # 电子邮箱
        DetectionPattern(
            type=SensitiveType.EMAIL,
            pattern=r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            sample="user@example.com",
            description="电子邮箱"
        ),
        # 银行卡（16-19位）
        DetectionPattern(
            type=SensitiveType.BANK_CARD,
            pattern=r'\b([1-9]\d{15,18})\b',
            sample="6222021234567890123",
            description="银行卡号"
        ),
        # IP地址
        DetectionPattern(
            type=SensitiveType.IP_ADDRESS,
            pattern=r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b',
            sample="192.168.1.1",
            description="IPv4地址"
        ),
        # GPS坐标
        DetectionPattern(
            type=SensitiveType.GPS_LOCATION,
            pattern=r'[NS]\d+\.\d+[EW]\d+\.\d+|[+-]?\d+\.\d+[,\s]+[+-]?\d+\.\d+',
            sample="39.9042, 116.4074",
            description="GPS坐标"
        ),
        # 日期（年月日）
        DetectionPattern(
            type=SensitiveType.BIRTHDATE,
            pattern=r'\b(19|20)\d{2}[年\-/]?(0[1-9]|1[0-2])[月\-/]?(0[1-9]|[12]\d|3[01])[日]?\b',
            sample="1990-01-01",
            description="出生日期"
        ),
    ]
    
    def __init__(self):
        self._patterns: list[DetectionPattern] = self.BUILTIN_PATTERNS.copy()
        self._compiled_patterns: dict[str, re.Pattern] = {}
        self._custom_keywords: dict[SensitiveType, list[str]] = {}
    
    def add_pattern(
        self,
        sensitive_type: SensitiveType,
        pattern: str,
        sample: str = "",
        description: str = ""
    ) -> None:
        """添加检测模式"""
        detection = DetectionPattern(
            type=sensitive_type,
            pattern=pattern,
            sample=sample,
            description=description
        )
        self._patterns.append(detection)
        # 清除编译缓存
        self._compiled_patterns.clear()
    
    def add_keyword(
        self,
        sensitive_type: SensitiveType,
        keywords: list[str]
    ) -> None:
        """添加关键词（用于上下文辅助检测）"""
        if sensitive_type not in self._custom_keywords:
            self._custom_keywords[sensitive_type] = []
        self._custom_keywords[sensitive_type].extend(keywords)
    
    def detect(self, text: str) -> list[DetectionResult]:
        """
        检测文本中的敏感数据
        
        Args:
            text: 待检测文本
            
        Returns:
            检测结果列表
        """
        results = []
        
        # 编译并缓存正则表达式
        for detection in self._patterns:
            if detection.type.value not in self._compiled_patterns:
                try:
                    self._compiled_patterns[detection.type.value] = re.compile(
                        detection.pattern,
                        re.UNICODE
                    )
                except re.error:
                    continue
            
            pattern = self._compiled_patterns[detection.type.value]
            
            for match in pattern.finditer(text):
                # 计算上下文
                start = max(0, match.start() - 20)
                end = min(len(text), match.end() + 20)
                context = text[start:end]
                
                # 计算置信度
                confidence = self._calculate_confidence(detection, match.group(), context)
                
                results.append(DetectionResult(
                    type=detection.type,
                    value=match.group(),
                    start=match.start(),
                    end=match.end(),
                    confidence=confidence,
                    context=context
                ))
        
        # 按位置排序
        results.sort(key=lambda x: x.start)
        
        return results
    
    def detect_dict(self, data: dict) -> list[tuple[str, DetectionResult]]:
        """
        检测字典中的敏感数据
        
        Args:
            data: 待检测字典
            
        Returns:
            (字段路径, 检测结果) 列表
        """
        results = []
        
        def traverse(obj: Any, path: str = ""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    new_path = f"{path}.{key}" if path else key
                    traverse(value, new_path)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    traverse(item, f"{path}[{i}]")
            elif isinstance(obj, str):
                for detection in self.detect(obj):
                    results.append((path, detection))
        
        traverse(data)
        return results
    
    def _calculate_confidence(
        self,
        detection: DetectionPattern,
        value: str,
        context: str
    ) -> float:
        """计算检测置信度"""
        base_confidence = 0.8
        
        # 关键词增强
        for keyword in self._custom_keywords.get(detection.type, []):
            if keyword.lower() in context.lower():
                base_confidence += 0.1
                break
        
        # 格式验证增强
        if self._validate_format(detection.type, value):
            base_confidence += 0.1
        
        return min(1.0, base_confidence)
    
    def _validate_format(self, sensitive_type: SensitiveType, value: str) -> bool:
        """验证格式有效性"""
        if sensitive_type == SensitiveType.ID_CARD:
            # 校验身份证最后一位
            if len(value) == 18:
                try:
                    coeffs = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
                    check_codes = ['1', '0', 'X', '9', '8', '7', '6', '5', '4', '3', '2']
                    total = sum(int(value[i]) * coeffs[i] for i in range(17))
                    expected = check_codes[total % 11]
                    return value[-1].upper() == expected
                except:
                    return False
        elif sensitive_type == SensitiveType.PHONE:
            # 校验手机号
            return len(value) == 11 and value[0] == '1'
        
        return True


class DesensitizationEngine:
    """
    数据脱敏引擎
    
    根据配置的规则对敏感数据进行脱敏处理。
    
    Usage::
        engine = DesensitizationEngine()
        engine.add_rule(SensitiveType.PHONE, DesensitizationMethod.PARTIAL_MASK)
        
        result = engine.desensitize("13812345678", SensitiveType.PHONE)
        print(result.desensitized)  # 138****5678
    """
    
    def __init__(self):
        self._rules: dict[SensitiveType, DesensitizationRule] = {}
        self._detector = SensitiveDataDetector()
    
    def add_rule(
        self,
        sensitive_type: SensitiveType,
        method: DesensitizationMethod,
        **kwargs
    ) -> None:
        """
        添加脱敏规则
        
        Args:
            sensitive_type: 敏感数据类型
            method: 脱敏方法
            **kwargs: 方法参数
        """
        rule = DesensitizationRule(
            type=sensitive_type,
            method=method,
            **kwargs
        )
        self._rules[sensitive_type] = rule
    
    def add_rules(self, rules: list[DesensitizationRule]) -> None:
        """批量添加规则"""
        for rule in rules:
            self._rules[rule.type] = rule
    
    def remove_rule(self, sensitive_type: SensitiveType) -> bool:
        """移除规则"""
        if sensitive_type in self._rules:
            del self._rules[sensitive_type]
            return True
        return False
    
    def get_rule(self, sensitive_type: SensitiveType) -> Optional[DesensitizationRule]:
        """获取规则"""
        return self._rules.get(sensitive_type)
    
    def desensitize(
        self,
        value: str,
        sensitive_type: SensitiveType
    ) -> DesensitizationResult:
        """
        脱敏单个值
        
        Args:
            value: 原始值
            sensitive_type: 敏感数据类型
            
        Returns:
            脱敏结果
        """
        rule = self._rules.get(sensitive_type)
        
        if not rule:
            return DesensitizationResult(
                original=value,
                desensitized=value,
                type=sensitive_type,
                method=DesensitizationMethod.FULL_MASK,
                success=False,
                error="No rule configured"
            )
        
        try:
            desensitized = self._apply_rule(value, rule)
            return DesensitizationResult(
                original=value,
                desensitized=desensitized,
                type=sensitive_type,
                method=rule.method,
                success=True
            )
        except Exception as e:
            return DesensitizationResult(
                original=value,
                desensitized=value,
                type=sensitive_type,
                method=rule.method,
                success=False,
                error=str(e)
            )
    
    def desensitize_auto(self, text: str) -> tuple[str, list[DetectionResult]]:
        """
        自动检测并脱敏
        
        Args:
            text: 待处理文本
            
        Returns:
            (脱敏后文本, 检测结果列表)
        """
        detections = self._detector.detect(text)
        
        if not detections:
            return text, []
        
        # 从后往前替换，避免位置偏移
        result = text
        for detection in reversed(detections):
            if detection.type in self._rules:
                rule = self._rules[detection.type]
                desensitized = self._apply_rule(detection.value, rule)
                result = result[:detection.start] + desensitized + result[detection.end:]
        
        return result, detections
    
    def desensitize_dict(
        self,
        data: dict,
        field_mappings: Optional[dict[str, SensitiveType]] = None,
        auto_detect: bool = True
    ) -> dict:
        """
        脱敏字典数据
        
        Args:
            data: 待处理字典
            field_mappings: 字段到敏感类型的映射
            auto_detect: 是否自动检测
            
        Returns:
            脱敏后的字典
        """
        result = {}
        
        for key, value in data.items():
            if isinstance(value, dict):
                result[key] = self.desensitize_dict(value, field_mappings, auto_detect)
            elif isinstance(value, list):
                result[key] = [
                    self.desensitize_dict(item, field_mappings, auto_detect) if isinstance(item, dict)
                    else self._desensitize_value(item, key, field_mappings, auto_detect)
                    for item in value
                ]
            elif isinstance(value, str):
                result[key] = self._desensitize_value(value, key, field_mappings, auto_detect)
            else:
                result[key] = value
        
        return result
    
    def _desensitize_value(
        self,
        value: str,
        field_name: str,
        field_mappings: Optional[dict[str, SensitiveType]],
        auto_detect: bool
    ) -> str:
        """脱敏单个字段值"""
        # 先检查字段映射
        if field_mappings and field_name in field_mappings:
            result = self.desensitize(value, field_mappings[field_name])
            return result.desensitized
        
        # 自动检测并脱敏
        if auto_detect:
            desensitized, _ = self.desensitize_auto(value)
            return desensitized
        
        return value
    
    def _apply_rule(self, value: str, rule: DesensitizationRule) -> str:
        """应用脱敏规则"""
        method = rule.method
        
        if method == DesensitizationMethod.FULL_MASK:
            return self._full_mask(value, rule.mask_char)
        
        elif method == DesensitizationMethod.PARTIAL_MASK:
            return self._partial_mask(value, rule.mask_char, rule.mask_ratio)
        
        elif method == DesensitizationMethod.REPLACE:
            return rule.replacement
        
        elif method == DesensitizationMethod.HASH:
            return self._hash_value(value, rule.hash_salt)
        
        elif method == DesensitizationMethod.REDACT:
            return ""
        
        elif method == DesensitizationMethod.RANDOM:
            return self._random_value(value, rule.type)
        
        return value
    
    def _full_mask(self, value: str, mask_char: str = "*") -> str:
        """全遮盖"""
        if not value:
            return value
        
        # 保留首位和末位
        if len(value) <= 2:
            return mask_char * len(value)
        
        return value[0] + mask_char * (len(value) - 2) + value[-1]
    
    def _partial_mask(self, value: str, mask_char: str = "*", ratio: float = 0.5) -> str:
        """部分遮盖"""
        if not value:
            return value
        
        length = len(value)
        mask_count = max(1, int(length * ratio))
        
        if length <= mask_count:
            return mask_char * length
        
        # 中文姓名特殊处理
        if self._is_chinese_name(value):
            return self._mask_chinese_name(value)
        
        start_keep = max(1, (length - mask_count) // 2)
        end_keep = length - start_keep - mask_count
        
        return value[:start_keep] + mask_char * mask_count + value[end_keep:]
    
    def _is_chinese_name(self, value: str) -> bool:
        """判断是否为中国姓名"""
        chinese_char_count = sum(1 for c in value if '\u4e00' <= c <= '\u9fff')
        return chinese_char_count >= 2 and len(value) <= 4
    
    def _mask_chinese_name(self, value: str) -> str:
        """遮盖中文姓名"""
        if len(value) == 2:
            return value[0] + '*'
        elif len(value) == 3:
            return value[0] + '*' + value[2]
        else:
            return value[0] + '*' * (len(value) - 2) + value[-1]
    
    def _hash_value(self, value: str, salt: str = "") -> str:
        """哈希脱敏"""
        # 使用SHA-256（生产环境应使用SM3）
        data = value + salt
        return hashlib.sha256(data.encode('utf-8')).hexdigest()[:16]
    
    def _random_value(self, value: str, sensitive_type: SensitiveType) -> str:
        """生成随机值替代"""
        if sensitive_type == SensitiveType.PHONE:
            return f"1{'{:09d}'.format(hash(value) % 1000000000)}"
        elif sensitive_type == SensitiveType.EMAIL:
            return f"user{hash(value) % 10000}@example.com"
        elif sensitive_type == SensitiveType.ID_CARD:
            return f"110101{hash(value) % 100000:05d}0101X"
        else:
            return f"REDACTED_{hash(value) % 10000}"
    
    def load_preset(self, preset: str) -> None:
        """
        加载预设脱敏规则
        
        Args:
            preset: 预设名称 (default/privacy/compliance)
        """
        if preset == "default":
            # 默认规则
            self.add_rule(SensitiveType.ID_CARD, DesensitizationMethod.PARTIAL_MASK)
            self.add_rule(SensitiveType.PHONE, DesensitizationMethod.PARTIAL_MASK)
            self.add_rule(SensitiveType.EMAIL, DesensitizationMethod.PARTIAL_MASK)
            self.add_rule(SensitiveType.BANK_CARD, DesensitizationMethod.FULL_MASK)
            self.add_rule(SensitiveType.NAME, DesensitizationMethod.PARTIAL_MASK)
            self.add_rule(SensitiveType.ADDRESS, DesensitizationMethod.REPLACE)
            self.add_rule(SensitiveType.PASSWORD, DesensitizationMethod.FULL_MASK)
            self.add_rule(SensitiveType.API_KEY, DesensitizationMethod.FULL_MASK)
            self.add_rule(SensitiveType.TOKEN, DesensitizationMethod.FULL_MASK)
        
        elif preset == "privacy":
            # 隐私保护规则
            self.add_rule(SensitiveType.ID_CARD, DesensitizationMethod.HASH, hash_salt="salt1")
            self.add_rule(SensitiveType.PHONE, DesensitizationMethod.PARTIAL_MASK, mask_ratio=0.6)
            self.add_rule(SensitiveType.EMAIL, DesensitizationMethod.PARTIAL_MASK, mask_ratio=0.5)
            self.add_rule(SensitiveType.BANK_CARD, DesensitizationMethod.FULL_MASK)
            self.add_rule(SensitiveType.NAME, DesensitizationMethod.PARTIAL_MASK)
            self.add_rule(SensitiveType.ADDRESS, DesensitizationMethod.REPLACE, replacement="[详细地址已隐藏]")
            self.add_rule(SensitiveType.GPS_LOCATION, DesensitizationMethod.REPLACE, replacement="[位置已脱敏]")
            self.add_rule(SensitiveType.BIRTHDATE, DesensitizationMethod.REPLACE, replacement="[出生日期已隐藏]")
        
        elif preset == "compliance":
            # 合规审计规则
            self.add_rule(SensitiveType.ID_CARD, DesensitizationMethod.PARTIAL_MASK, preserve_length=True)
            self.add_rule(SensitiveType.PHONE, DesensitizationMethod.FULL_MASK)
            self.add_rule(SensitiveType.EMAIL, DesensitizationMethod.REPLACE, replacement="[邮箱已脱敏]")
            self.add_rule(SensitiveType.BANK_CARD, DesensitizationMethod.FULL_MASK)
            self.add_rule(SensitiveType.NAME, DesensitizationMethod.PARTIAL_MASK)
            self.add_rule(SensitiveType.COMPANY_NAME, DesensitizationMethod.PARTIAL_MASK)
            self.add_rule(SensitiveType.TRADE_SECRET, DesensitizationMethod.REDACT)
            self.add_rule(SensitiveType.POLLUTION_DATA, DesensitizationMethod.REPLACE, replacement="[数据已脱敏]")
        
        elif preset == "eco_environment":
            # 生态环境专用规则
            self.add_rule(SensitiveType.FACILITY_NAME, DesensitizationMethod.PARTIAL_MASK)
            self.add_rule(SensitiveType.POLLUTION_DATA, DesensitizationMethod.HASH)
            self.add_rule(SensitiveType.COMPANY_NAME, DesensitizationMethod.PARTIAL_MASK, mask_ratio=0.3)
            self.add_rule(SensitiveType.GPS_LOCATION, DesensitizationMethod.REPLACE, replacement="[环保监测点]")
            self.add_rule(SensitiveType.TRADE_SECRET, DesensitizationMethod.REDACT)


class DesensitizationPolicy:
    """
    脱敏策略管理器
    
    管理不同场景的脱敏策略配置。
    
    Usage::
        policy = DesensitizationPolicy()
        policy.set_policy("log", ["default"])
        policy.set_policy("report", ["privacy"])
        policy.set_policy("audit", ["compliance"])
        
        engine = policy.get_engine("log")
        result = engine.desensitize_auto("手机号: 13812345678")
    """
    
    def __init__(self):
        self._scenarios: dict[str, list[str]] = {}  # 场景 -> 预设列表
        self._engines: dict[str, DesensitizationEngine] = {}
    
    def set_policy(self, scenario: str, presets: list[str]) -> None:
        """
        设置场景策略
        
        Args:
            scenario: 场景名称
            presets: 预设列表
        """
        self._scenarios[scenario] = presets
        self._engines[scenario] = self._create_engine(presets)
    
    def _create_engine(self, presets: list[str]) -> DesensitizationEngine:
        """创建引擎"""
        engine = DesensitizationEngine()
        for preset in presets:
            engine.load_preset(preset)
        return engine
    
    def get_engine(self, scenario: str) -> Optional[DesensitizationEngine]:
        """获取场景引擎"""
        return self._engines.get(scenario)
    
    def desensitize(
        self,
        data: Any,
        scenario: str,
        auto_detect: bool = True
    ) -> Any:
        """
        根据场景脱敏数据
        
        Args:
            data: 待脱敏数据
            scenario: 场景名称
            auto_detect: 是否自动检测
            
        Returns:
            脱敏后数据
        """
        engine = self._engines.get(scenario)
        if not engine:
            return data
        
        if isinstance(data, str):
            desensitized, _ = engine.desensitize_auto(data)
            return desensitized
        elif isinstance(data, dict):
            return engine.desensitize_dict(data, auto_detect=auto_detect)
        else:
            return data
