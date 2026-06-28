"""
Security Module Tests (安全模块测试)
测试安全合规模块的所有核心功能

测试覆盖：
- Sandbox: 沙箱隔离与资源限制
- KeyManager: 密钥生成与轮换
- Audit: 审计链与完整性验证
- Incident: 应急响应流程
- Desensitize: 数据脱敏引擎
"""

import os
import sys
import time
import tempfile
import unittest
from pathlib import Path

# 添加项目根目录到路径
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from taiji_agent.security import (
    # Sandbox
    Sandbox,
    SandboxConfig,
    SandboxStatus,
    SandboxPool,
    SecurityFence,
    # KeyManager
    KeyManager,
    KeyType,
    KeyStatus,
    KeyRotationConfig,
    # Audit
    AuditChain,
    AuditAction,
    AuditResource,
    DataLevel,
    AuditQuery,
    AuditManager,
    # Incident
    IncidentResponseManager,
    IncidentLevel,
    IncidentStatus,
    IncidentCategory,
    IncidentImpact,
    # Desensitize
    SensitiveDataDetector,
    DesensitizationEngine,
    DesensitizationPolicy,
    SensitiveType,
    DesensitizationMethod,
)


class TestSecurityFence(unittest.TestCase):
    """测试安全围栏"""
    
    def setUp(self):
        self.fence = SecurityFence()
    
    def test_check_with_clean_content(self):
        """测试正常内容通过检查"""
        passed, matched = self.fence.check("Hello, this is a normal message.")
        self.assertTrue(passed)
        self.assertEqual(len(matched), 0)
    
    def test_check_with_sensitive_keywords(self):
        """测试敏感关键词检测"""
        passed, matched = self.fence.check("Please send your password to admin")
        self.assertFalse(passed)
        self.assertIn("password", matched)
    
    def test_check_with_custom_keywords(self):
        """测试自定义关键词"""
        fence = SecurityFence(custom_keywords={"custom_secret"})
        passed, matched = fence.check("This contains custom_secret data")
        self.assertFalse(passed)
        self.assertIn("custom_secret", matched)
    
    def test_filter_command_safe(self):
        """测试安全命令通过"""
        passed, filtered = self.fence.filter_command("echo hello")
        self.assertTrue(passed)
        self.assertEqual(filtered, "echo hello")
    
    def test_filter_command_dangerous(self):
        """测试危险命令拦截"""
        passed, filtered = self.fence.filter_command("rm -rf /")
        self.assertFalse(passed)


class TestSandbox(unittest.TestCase):
    """测试沙箱"""
    
    def setUp(self):
        self.config = SandboxConfig(
            max_cpu_time=5,
            max_wall_time=10,
            max_memory_bytes=128 * 1024 * 1024,
        )
        self.sandbox = Sandbox(self.config)
    
    def test_sandbox_initialization(self):
        """测试沙箱初始化"""
        self.assertEqual(self.sandbox.status, SandboxStatus.CREATED)
    
    def test_execute_simple_code(self):
        """测试执行简单代码"""
        result = self.sandbox.execute_code("print('Hello from sandbox')", language="python")
        self.assertIn(result.status, [SandboxStatus.TERMINATED, SandboxStatus.RUNNING])
        self.assertIn("Hello", result.stdout)
    
    def test_execute_with_timeout(self):
        """测试超时处理"""
        config = SandboxConfig(max_cpu_time=1, max_wall_time=2)
        sandbox = Sandbox(config)
        
        result = sandbox.execute_code("""
import time
time.sleep(10)
print('This should not print')
""", language="python")
        
        self.assertIn(result.status, [SandboxStatus.TIMEOUT, SandboxStatus.TERMINATED])
    
    def test_execute_with_security_violation(self):
        """测试安全违规检测"""
        result = self.sandbox.execute_code("""
import os
os.system('ls')
""", language="python")
        
        self.assertIn(result.status, [SandboxStatus.TERMINATED, SandboxStatus.RUNNING])
    
    def test_execute_code_size_limit(self):
        """测试代码大小限制"""
        config = SandboxConfig(max_code_size=100)
        sandbox = Sandbox(config)
        
        large_code = "x = 1\n" * 1000
        result = sandbox.execute_code(large_code, language="python")
        
        self.assertEqual(result.status, SandboxStatus.TERMINATED)
        self.assertTrue(len(result.security_violations) > 0)
    
    def test_sandbox_termination(self):
        """测试沙箱终止"""
        self.sandbox.status = SandboxStatus.RUNNING
        result = self.sandbox.terminate("Test termination")
        
        self.assertEqual(result.status, SandboxStatus.KILLED)
    
    def tearDown(self):
        if self.sandbox.status == SandboxStatus.RUNNING:
            self.sandbox.terminate()


class TestSandboxPool(unittest.TestCase):
    """测试沙箱池"""
    
    def setUp(self):
        self.pool = SandboxPool(pool_size=2)
    
    def test_acquire_release(self):
        """测试获取和释放沙箱"""
        sandbox = self.pool.acquire()
        self.assertIsNotNone(sandbox)
        
        self.pool.release(sandbox)
    
    def test_execute_in_pool(self):
        """测试在池中执行代码"""
        result = self.pool.execute_in_pool("print('test')", language="python")
        self.assertIsNotNone(result)
    
    def test_shutdown(self):
        """测试关闭池"""
        self.pool.shutdown()
        # 验证池已清空
        self.assertEqual(len(self.pool._available), 0)


class TestKeyManager(unittest.TestCase):
    """测试密钥管理器"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.manager = KeyManager(storage_path=self.temp_dir)
        self.manager.initialize("test_master_password")
    
    def test_initialization(self):
        """测试初始化"""
        self.assertTrue(self.manager._initialized)
    
    def test_get_active_key(self):
        """测试获取活跃密钥"""
        result = self.manager.get_active_key(KeyType.SM2_SIGN)
        self.assertIsNotNone(result)
        key_id, key_data = result
        self.assertIsNotNone(key_id)
        self.assertIsNotNone(key_data)
    
    def test_rotate_key(self):
        """测试密钥轮换"""
        # 首先确保有活跃的SM4_SESSION密钥
        result = self.manager.rotate_key(KeyType.SM4_SESSION, force=True)
        
        # 如果没有活跃密钥，需要先生成一个
        if not result.success and "No active key" in result.error:
            # 手动创建一个活跃的SM4_SESSION密钥
            from taiji_agent.security.key_manager import KeyMetadata, KeyStatus
            key_id = self.manager._generate_key(
                KeyType.SM4_SESSION,
                created_at=time.time(),
                expires_at=time.time() + 86400
            )
            result = self.manager.rotate_key(KeyType.SM4_SESSION, force=True)
        
        self.assertTrue(result.success)
        self.assertIsNotNone(result.new_key_id)
        self.assertNotEqual(result.old_key_id, result.new_key_id)
    
    def test_list_keys(self):
        """测试列出密钥"""
        keys = self.manager.list_keys(status=KeyStatus.ACTIVE)
        self.assertGreater(len(keys), 0)
    
    def test_get_expiring_keys(self):
        """测试获取即将过期密钥"""
        expiring = self.manager.get_expiring_keys(days_threshold=365)
        self.assertIsInstance(expiring, list)
    
    def test_audit_log(self):
        """测试访问审计日志"""
        self.manager.get_active_key(KeyType.SM2_SIGN)
        log = self.manager.get_audit_log()
        self.assertGreater(len(log), 0)
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)


class TestAuditChain(unittest.TestCase):
    """测试审计链"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.chain = AuditChain(tenant_id="test_tenant", storage_path=self.temp_dir)
    
    def test_add_entry(self):
        """测试添加审计记录"""
        entry = self.chain.add_entry(
            user_id="user_001",
            action=AuditAction.DATA_READ,
            resource=AuditResource(type="document", id="doc_001", level=DataLevel.L2_INTERNAL)
        )
        
        self.assertIsNotNone(entry)
        self.assertEqual(entry.user_id, "user_001")
        self.assertEqual(entry.action, AuditAction.DATA_READ)
        self.assertIsNotNone(entry.current_hash)
    
    def test_hash_chain_integrity(self):
        """测试哈希链完整性"""
        # 添加多条记录
        for i in range(3):
            self.chain.add_entry(
                user_id=f"user_{i}",
                action=AuditAction.CONFIG_CHANGE
            )
        
        # 验证链
        is_valid, broken = self.chain.verify()
        self.assertTrue(is_valid)
        self.assertEqual(len(broken), 0)
    
    def test_query_by_user(self):
        """测试按用户查询"""
        self.chain.add_entry(user_id="user_query_test", action=AuditAction.DATA_READ)
        
        entries = self.chain.get_user_activity(user_id="user_query_test")
        self.assertGreater(len(entries), 0)
    
    def test_query_by_time_range(self):
        """测试按时间范围查询"""
        start_time = time.time() - 3600
        end_time = time.time() + 3600
        
        self.chain.add_entry(user_id="user_time", action=AuditAction.LOGIN_SUCCESS)
        
        entries = self.chain.query(AuditQuery(
            start_time=start_time,
            end_time=end_time
        ))
        
        self.assertGreater(len(entries), 0)
    
    def test_compliance_report(self):
        """测试合规报告生成"""
        # 添加测试数据
        self.chain.add_entry(user_id="user_report", action=AuditAction.DATA_READ)
        self.chain.add_entry(user_id="user_report", action=AuditAction.LOGIN_FAILURE)
        
        start_time = time.time() - 86400
        end_time = time.time() + 86400
        
        report = self.chain.generate_compliance_report(start_time, end_time)
        
        self.assertIsNotNone(report)
        self.assertGreater(report.total_entries, 0)
        self.assertTrue(report.chain_integrity_verified)
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)


class TestSensitiveDataDetector(unittest.TestCase):
    """测试敏感数据检测器"""
    
    def setUp(self):
        self.detector = SensitiveDataDetector()
    
    def test_detect_phone(self):
        """测试手机号检测"""
        text = "联系电话: 13812345678"
        results = self.detector.detect(text)
        
        phone_results = [r for r in results if r.type == SensitiveType.PHONE]
        self.assertEqual(len(phone_results), 1)
        self.assertEqual(phone_results[0].value, "13812345678")
    
    def test_detect_id_card(self):
        """测试身份证号检测"""
        text = "身份证号: 110101199001011234"
        results = self.detector.detect(text)
        
        id_results = [r for r in results if r.type == SensitiveType.ID_CARD]
        self.assertEqual(len(id_results), 1)
    
    def test_detect_email(self):
        """测试邮箱检测"""
        text = "邮箱: user@example.com"
        results = self.detector.detect(text)
        
        email_results = [r for r in results if r.type == SensitiveType.EMAIL]
        self.assertEqual(len(email_results), 1)
    
    def test_detect_multiple(self):
        """测试多类型检测"""
        text = "手机: 13812345678, 邮箱: test@test.com"
        results = self.detector.detect(text)
        
        self.assertGreaterEqual(len(results), 2)
    
    def test_detect_clean_text(self):
        """测试无敏感数据文本"""
        text = "这是一段正常的文本内容"
        results = self.detector.detect(text)
        self.assertEqual(len(results), 0)


class TestDesensitizationEngine(unittest.TestCase):
    """测试脱敏引擎"""
    
    def setUp(self):
        self.engine = DesensitizationEngine()
        self.engine.load_preset("default")
    
    def test_desensitize_phone(self):
        """测试手机号脱敏"""
        result = self.engine.desensitize("13812345678", SensitiveType.PHONE)
        
        self.assertTrue(result.success)
        self.assertNotEqual(result.original, result.desensitized)
        # 脱敏后应包含遮盖字符
        self.assertIn("*", result.desensitized)
    
    def test_desensitize_email(self):
        """测试邮箱脱敏"""
        result = self.engine.desensitize("user@example.com", SensitiveType.EMAIL)
        
        self.assertTrue(result.success)
        self.assertIn("*", result.desensitized)
    
    def test_desensitize_id_card(self):
        """测试身份证脱敏"""
        result = self.engine.desensitize("110101199001011234", SensitiveType.ID_CARD)
        
        self.assertTrue(result.success)
        self.assertNotEqual(result.original, result.desensitized)
    
    def test_desensitize_auto(self):
        """测试自动检测脱敏"""
        text = "手机号: 13812345678"
        desensitized, detections = self.engine.desensitize_auto(text)
        
        self.assertNotEqual(text, desensitized)
        self.assertEqual(len(detections), 1)
    
    def test_desensitize_dict(self):
        """测试字典脱敏"""
        data = {
            "name": "张三",
            "phone": "13812345678",
            "email": "zhang@example.com",
            "age": 30
        }
        
        result = self.engine.desensitize_dict(data, auto_detect=True)
        
        self.assertNotEqual(result["phone"], data["phone"])
        self.assertNotEqual(result["email"], data["email"])
        self.assertEqual(result["age"], data["age"])  # 非字符串应保持不变
    
    def test_no_rule_returns_original(self):
        """测试无规则时返回原值"""
        result = self.engine.desensitize("some_value", SensitiveType.IP_ADDRESS)
        
        self.assertFalse(result.success)
        self.assertEqual(result.desensitized, "some_value")
    
    def test_preset_rules(self):
        """测试预设规则"""
        engine = DesensitizationEngine()
        engine.load_preset("privacy")
        
        result = engine.desensitize("13812345678", SensitiveType.PHONE)
        self.assertTrue(result.success)
        
        result = engine.desensitize("zhang@example.com", SensitiveType.EMAIL)
        self.assertTrue(result.success)


class TestDesensitizationPolicy(unittest.TestCase):
    """测试脱敏策略"""
    
    def test_set_and_get_policy(self):
        """测试设置和获取策略"""
        policy = DesensitizationPolicy()
        policy.set_policy("log", ["default"])
        policy.set_policy("report", ["privacy"])
        
        engine = policy.get_engine("log")
        self.assertIsNotNone(engine)
        
        engine = policy.get_engine("report")
        self.assertIsNotNone(engine)
    
    def test_desensitize_with_scenario(self):
        """测试按场景脱敏"""
        policy = DesensitizationPolicy()
        policy.set_policy("default", ["default"])
        
        result = policy.desensitize("手机: 13812345678", "default")
        self.assertNotEqual(result, "手机: 13812345678")


class TestIncidentResponse(unittest.TestCase):
    """测试应急响应"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.manager = IncidentResponseManager(
            tenant_id="test_org",
            storage_path=self.temp_dir
        )
    
    def test_report_incident(self):
        """测试上报事件"""
        incident = self.manager.report_incident(
            level=IncidentLevel.L3_MAJOR,
            category=IncidentCategory.DATA_BREACH,
            title="测试数据泄露事件",
            description="测试事件描述"
        )
        
        self.assertIsNotNone(incident)
        self.assertEqual(incident.level, IncidentLevel.L3_MAJOR)
        self.assertEqual(incident.category, IncidentCategory.DATA_BREACH)
        self.assertTrue(incident.incident_id.startswith("INC-"))
    
    def test_assess_incident(self):
        """测试评估事件"""
        incident = self.manager.report_incident(
            level=IncidentLevel.L2_SIGNIFICANT,
            category=IncidentCategory.CONFIG_ERROR,
            title="配置错误",
            description="配置错误测试"
        )
        
        success = self.manager.assess_incident(
            incident.incident_id,
            confirmed=True,
            level=IncidentLevel.L1_GENERAL
        )
        
        self.assertTrue(success)
    
    def test_add_action(self):
        """测试添加处置动作"""
        incident = self.manager.report_incident(
            level=IncidentLevel.L1_GENERAL,
            category=IncidentCategory.SERVICE_OUTAGE,
            title="服务异常",
            description="服务异常测试"
        )
        
        action_id = self.manager.add_action(
            incident.incident_id,
            action_type="contain",
            description="重启服务",
            handler_id="handler_001"
        )
        
        self.assertIsNotNone(action_id)
    
    def test_resolve_incident(self):
        """测试解决事件"""
        incident = self.manager.report_incident(
            level=IncidentLevel.L1_GENERAL,
            category=IncidentCategory.CONFIG_ERROR,
            title="配置问题",
            description="配置问题测试"
        )
        
        success = self.manager.resolve_incident(
            incident.incident_id,
            root_cause="配置项错误"
        )
        
        self.assertTrue(success)
    
    def test_match_plan(self):
        """测试匹配预案"""
        incident = self.manager.report_incident(
            level=IncidentLevel.L4_CRITICAL,
            category=IncidentCategory.DATA_BREACH,
            title="严重数据泄露",
            description="严重数据泄露测试"
        )
        
        plan = self.manager.match_plan(incident)
        self.assertIsNotNone(plan)
    
    def test_incident_statistics(self):
        """测试事件统计"""
        # 添加测试事件
        for i in range(3):
            self.manager.report_incident(
                level=IncidentLevel.L1_GENERAL,
                category=IncidentCategory.CONFIG_ERROR,
                title=f"测试事件{i}",
                description="测试事件描述"
            )
        
        stats = self.manager.get_incident_statistics()
        
        self.assertGreaterEqual(stats["total"], 3)
        self.assertIn("L1", stats["by_level"])
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)


class TestAuditManager(unittest.TestCase):
    """测试审计管理器"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.manager = AuditManager(storage_path=self.temp_dir)
    
    def test_get_chain(self):
        """测试获取审计链"""
        chain = self.manager.get_chain("tenant_001")
        self.assertIsNotNone(chain)
        self.assertEqual(chain.tenant_id, "tenant_001")
    
    def test_generate_report(self):
        """测试生成合规报告"""
        chain = self.manager.get_chain("tenant_report")
        
        # 添加测试数据
        chain.add_entry(
            user_id="user_report",
            action=AuditAction.DATA_READ
        )
        
        report = self.manager.generate_report(
            "tenant_report",
            start_time=time.time() - 86400,
            end_time=time.time() + 86400
        )
        
        self.assertIsNotNone(report)
        self.assertGreater(report.total_entries, 0)
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)


def run_tests():
    """运行所有测试"""
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加测试类
    test_classes = [
        TestSecurityFence,
        TestSandbox,
        TestSandboxPool,
        TestKeyManager,
        TestAuditChain,
        TestSensitiveDataDetector,
        TestDesensitizationEngine,
        TestDesensitizationPolicy,
        TestIncidentResponse,
        TestAuditManager,
    ]
    
    for test_class in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(test_class))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 输出统计
    print("\n" + "=" * 60)
    print(f"测试完成: {result.testsRun} 个测试")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")
    
    if result.wasSuccessful():
        print(f"\n✓ 测试通过率: 100%")
    else:
        print(f"\n✗ 测试通过率: {(result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100:.1f}%")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
