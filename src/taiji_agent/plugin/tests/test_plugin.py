# -*- coding: utf-8 -*-
"""
插件系统测试模块。

测试插件的：
- 生命周期管理（加载/激活/停用/卸载）
- 钩子系统（订阅/发布/中断）
- 预置插件功能
- 依赖解析
"""

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


class TestPluginBase:
    """测试插件基类"""
    
    def test_plugin_metadata_creation(self):
        """测试插件元数据创建"""
        from taiji_agent.plugin import PluginMetadata, PluginDependency
        
        meta = PluginMetadata(
            id="test-plugin",
            name="测试插件",
            version="1.0.0",
            description="一个测试插件",
            author="Test Author",
            dependencies=[
                PluginDependency("dep-plugin-1", ">=1.0.0"),
                PluginDependency("dep-plugin-2", "^2.0.0", optional=True),
            ],
            tags=["test", "demo"],
        )
        
        assert meta.id == "test-plugin"
        assert meta.name == "测试插件"
        assert meta.version == "1.0.0"
        assert len(meta.dependencies) == 2
        assert meta.dependencies[0].plugin_id == "dep-plugin-1"
        assert meta.dependencies[0].optional is False
        assert meta.dependencies[1].optional is True
    
    def test_plugin_state_enum(self):
        """测试插件状态枚举"""
        from taiji_agent.plugin import PluginState
        
        assert PluginState.REGISTERED.value == "registered"
        assert PluginState.LOADING.value == "loading"
        assert PluginState.LOADED.value == "loaded"
        assert PluginState.ACTIVE.value == "active"
        assert PluginState.DEACTIVATED.value == "deactivated"
    
    def test_plugin_health_enum(self):
        """测试插件健康状态枚举"""
        from taiji_agent.plugin import PluginHealth
        
        assert PluginHealth.HEALTHY.value == 1
        assert PluginHealth.DEGRADED.value == 2
        assert PluginHealth.UNHEALTHY.value == 3
        assert PluginHealth.ERROR.value == 4
    
    def test_plugin_logger(self):
        """测试插件日志记录器"""
        from taiji_agent.plugin import PluginLogger
        import logging
        
        # 配置日志
        logging.basicConfig(level=logging.DEBUG)
        
        logger = PluginLogger("test-plugin")
        
        # 测试日志方法存在
        assert hasattr(logger, "debug")
        assert hasattr(logger, "info")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")
        
        # 测试日志前缀
        assert logger._prefix == "[test-plugin]"
    
    def test_configurable_plugin_validate_config(self):
        """测试配置验证"""
        from taiji_agent.plugin import ConfigurablePlugin, PluginMetadata, PluginContext, PluginState
        
        class TestPlugin(ConfigurablePlugin):
            async def activate(self, ctx):
                pass
            
            async def deactivate(self):
                pass
        
        meta = PluginMetadata(
            id="test-plugin",
            name="Test Plugin",
            version="1.0.0",
            config_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "count": {"type": "integer", "minimum": 0}
                },
                "required": ["name"]
            }
        )
        
        plugin = TestPlugin(meta)
        
        # 有效配置
        errors = plugin.validate_config({"name": "test", "count": 5})
        assert len(errors) == 0
        
        # 无效配置（缺少必填字段）
        errors = plugin.validate_config({"count": 5})
        assert len(errors) > 0


class TestEventBus:
    """测试事件总线"""
    
    @pytest.fixture
    def event_bus(self):
        """创建事件总线"""
        from taiji_agent.plugin import EventBus
        return EventBus()
    
    @pytest.mark.asyncio
    async def test_subscribe_and_emit(self, event_bus):
        """测试订阅和发布"""
        received = []
        
        async def handler(data):
            received.append(data)
            return data
        
        hook_id = await event_bus.subscribe("test:event", handler)
        assert hook_id is not None
        
        await event_bus.emit("test:event", {"value": 123})
        
        assert len(received) == 1
        assert received[0]["value"] == 123
    
    @pytest.mark.asyncio
    async def test_unsubscribe(self, event_bus):
        """测试取消订阅"""
        call_count = 0
        
        async def handler(data):
            nonlocal call_count
            call_count += 1
            return data
        
        hook_id = await event_bus.subscribe("test:event", handler)
        await event_bus.emit("test:event", {})
        await event_bus.unsubscribe(hook_id)
        await event_bus.emit("test:event", {})
        
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_priority_order(self, event_bus):
        """测试优先级顺序"""
        results = []
        
        async def handler1(data):
            results.append("first")
            return data
        
        async def handler2(data):
            results.append("second")
            return data
        
        async def handler3(data):
            results.append("third")
            return data
        
        # 按优先级订阅
        await event_bus.subscribe("test:event", handler2, priority=100)
        await event_bus.subscribe("test:event", handler1, priority=50)
        await event_bus.subscribe("test:event", handler3, priority=150)
        
        await event_bus.emit("test:event", {})
        
        assert results == ["first", "second", "third"]
    
    @pytest.mark.asyncio
    async def test_abort_mechanism(self, event_bus):
        """测试中断机制"""
        call_order = []
        
        async def handler1(data):
            call_order.append("handler1")
            return data
        
        async def handler2(data):
            call_order.append("handler2")
            return {"abort": True, "data": {"aborted": True}}
        
        async def handler3(data):
            call_order.append("handler3")
            return data
        
        await event_bus.subscribe("test:event", handler1, priority=50)
        await event_bus.subscribe("test:event", handler2, priority=100)
        await event_bus.subscribe("test:event", handler3, priority=150)
        
        result = await event_bus.emit("test:event", {"original": True})
        
        assert "handler1" in call_order
        assert "handler2" in call_order
        assert "handler3" not in call_order
        assert result.get("aborted") is True
    
    @pytest.mark.asyncio
    async def test_stats(self, event_bus):
        """测试统计功能"""
        async def handler(data):
            return data

        await event_bus.subscribe("test:event", handler)
        await event_bus.emit("test:event", {})
        await event_bus.emit("test:event", {})

        stats = event_bus.get_stats("test:event")

        assert stats["total"] == 2


class TestPluginRegistry:
    """测试插件注册中心"""
    
    @pytest.fixture
    def registry(self):
        """创建注册中心"""
        from taiji_agent.plugin import PluginRegistry
        return PluginRegistry()
    
    @pytest.fixture
    def mock_plugin(self):
        """创建模拟插件"""
        from taiji_agent.plugin import Plugin, PluginMetadata, PluginState
        
        class MockPlugin(Plugin):
            async def activate(self, ctx):
                pass
            
            async def deactivate(self):
                pass
        
        meta = PluginMetadata(
            id="mock-plugin",
            name="Mock Plugin",
            version="1.0.0",
            tags=["test", "mock"]
        )
        
        return MockPlugin(meta)
    
    def test_register(self, registry, mock_plugin):
        """测试插件注册"""
        registry.register(mock_plugin)
        
        assert "mock-plugin" in registry
        assert registry.get("mock-plugin") == mock_plugin
        assert len(registry) == 1
    
    def test_unregister(self, registry, mock_plugin):
        """测试插件注销"""
        registry.register(mock_plugin)
        assert registry.unregister("mock-plugin") is True
        assert "mock-plugin" not in registry
        
        # 重复注销应返回 False
        assert registry.unregister("mock-plugin") is False
    
    def test_update_state(self, registry, mock_plugin):
        """测试状态更新"""
        from taiji_agent.plugin import PluginState
        
        registry.register(mock_plugin)
        
        assert registry.update_state("mock-plugin", PluginState.ACTIVE) is True
        assert registry.get_info("mock-plugin").state == PluginState.ACTIVE
        
        # 更新不存在插件应返回 False
        assert registry.update_state("non-existent", PluginState.ACTIVE) is False
    
    def test_list_by_state(self, registry, mock_plugin):
        """测试按状态筛选"""
        from taiji_agent.plugin import PluginState
        
        registry.register(mock_plugin)
        
        # 初始状态为 REGISTERED
        assert len(registry.list_by_state(PluginState.REGISTERED)) == 1
        assert len(registry.list_by_state(PluginState.ACTIVE)) == 0
        
        # 更新为 ACTIVE
        registry.update_state("mock-plugin", PluginState.ACTIVE)
        assert len(registry.list_by_state(PluginState.ACTIVE)) == 1
        assert len(registry.list_by_state(PluginState.REGISTERED)) == 0
    
    def test_list_by_tag(self, registry, mock_plugin):
        """测试按标签筛选"""
        registry.register(mock_plugin)
        
        plugins = registry.list_by_tag("test")
        assert len(plugins) == 1
        assert plugins[0].metadata.id == "mock-plugin"
        
        plugins = registry.list_by_tag("nonexistent")
        assert len(plugins) == 0
    
    def test_enable_disable(self, registry, mock_plugin):
        """测试启用/禁用"""
        registry.register(mock_plugin)
        
        assert registry.is_enabled("mock-plugin") is True
        
        registry.disable("mock-plugin")
        assert registry.is_enabled("mock-plugin") is False
        
        registry.enable("mock-plugin")
        assert registry.is_enabled("mock-plugin") is True
    
    def test_get_stats(self, registry, mock_plugin):
        """测试统计信息"""
        registry.register(mock_plugin)
        
        stats = registry.get_stats()
        
        assert stats["total"] == 1
        assert stats["enabled"] == 1


class TestDependencyResolver:
    """测试依赖解析器"""
    
    def test_simple_dependency_order(self):
        """测试简单依赖顺序"""
        from taiji_agent.plugin import PluginMetadata, PluginDependency
        from taiji_agent.plugin.loader import DependencyResolver
        
        plugins = [
            PluginMetadata(
                id="plugin-c",
                name="Plugin C",
                version="1.0.0",
                dependencies=[
                    PluginDependency("plugin-b", ">=1.0.0")
                ]
            ),
            PluginMetadata(
                id="plugin-b",
                name="Plugin B",
                version="1.0.0",
                dependencies=[
                    PluginDependency("plugin-a", ">=1.0.0")
                ]
            ),
            PluginMetadata(
                id="plugin-a",
                name="Plugin A",
                version="1.0.0",
                dependencies=[]
            ),
        ]
        
        resolver = DependencyResolver(plugins)
        ordered = resolver.resolve()
        
        # plugin-a 应该在最前面
        assert ordered[0].id == "plugin-a"
        # plugin-c 应该在最后面
        assert ordered[-1].id == "plugin-c"
    
    def test_circular_dependency_detection(self):
        """测试循环依赖检测"""
        from taiji_agent.plugin import PluginMetadata, PluginDependency
        from taiji_agent.plugin.loader import DependencyResolver, CircularDependencyError
        
        plugins = [
            PluginMetadata(
                id="plugin-a",
                name="Plugin A",
                version="1.0.0",
                dependencies=[
                    PluginDependency("plugin-b", ">=1.0.0")
                ]
            ),
            PluginMetadata(
                id="plugin-b",
                name="Plugin B",
                version="1.0.0",
                dependencies=[
                    PluginDependency("plugin-a", ">=1.0.0")
                ]
            ),
        ]
        
        resolver = DependencyResolver(plugins)
        
        with pytest.raises(CircularDependencyError):
            resolver.resolve()
    
    def test_version_compatibility(self):
        """测试版本兼容性检查"""
        from taiji_agent.plugin.loader import DependencyResolver
        
        # 完全匹配
        assert DependencyResolver.check_version_compatibility("1.0.0", "1.0.0") is True
        
        # 大于等于
        assert DependencyResolver.check_version_compatibility("1.1.0", ">=1.0.0") is True
        assert DependencyResolver.check_version_compatibility("0.9.0", ">=1.0.0") is False
        
        # caret 版本
        assert DependencyResolver.check_version_compatibility("1.2.3", "^1.0.0") is True
        assert DependencyResolver.check_version_compatibility("2.0.0", "^1.0.0") is False
        
        # tilde 版本
        assert DependencyResolver.check_version_compatibility("1.2.0", "~1.2.0") is True
        assert DependencyResolver.check_version_compatibility("1.3.0", "~1.2.0") is False
        
        # 通配符
        assert DependencyResolver.check_version_compatibility("1.2.3", "*") is True


class TestPluginLifecycle:
    """测试插件生命周期"""
    
    @pytest.fixture
    def event_bus(self):
        from taiji_agent.plugin import EventBus
        return EventBus()
    
    @pytest.fixture
    def registry(self):
        from taiji_agent.plugin import PluginRegistry
        return PluginRegistry()
    
    @pytest.fixture
    def loader(self, event_bus, registry):
        from taiji_agent.plugin import PluginLoader
        return PluginLoader(
            event_bus=event_bus,
            registry=registry,
        )
    
    @pytest.fixture
    def mock_plugin(self):
        from taiji_agent.plugin import Plugin, PluginMetadata, PluginContext, PluginState
        
        class MockPlugin(Plugin):
            def __init__(self, metadata):
                super().__init__(metadata)
                self.activate_called = False
                self.deactivate_called = False
            
            async def activate(self, ctx):
                self.activate_called = True
                self.context = ctx
                self.state = PluginState.ACTIVE
            
            async def deactivate(self):
                self.deactivate_called = True
                self.state = PluginState.DEACTIVATED
        
        meta = PluginMetadata(
            id="lifecycle-test-plugin",
            name="Lifecycle Test Plugin",
            version="1.0.0",
        )
        
        return MockPlugin(meta)
    
    @pytest.mark.asyncio
    async def test_plugin_activation(self, loader, mock_plugin, registry):
        """测试插件激活"""
        from taiji_agent.plugin import PluginState
        
        registry.register(mock_plugin)

        success = await loader.activate(mock_plugin)

        assert success is True
        assert mock_plugin.activate_called is True
        assert mock_plugin.state == PluginState.ACTIVE

    @pytest.mark.asyncio
    async def test_plugin_deactivation(self, loader, mock_plugin, registry):
        """测试插件停用"""
        from taiji_agent.plugin import PluginState
        
        registry.register(mock_plugin)
        await loader.activate(mock_plugin)

        success = await loader.deactivate(mock_plugin)

        assert success is True
        assert mock_plugin.deactivate_called is True
        assert mock_plugin.state == PluginState.DEACTIVATED
    
    @pytest.mark.asyncio
    async def test_lifecycle_events_emitted(self, loader, mock_plugin, event_bus):
        """测试生命周期事件发射"""
        from taiji_agent.plugin import SystemEvents
        
        events_received = []
        
        async def event_handler(data):
            events_received.append(data)
            return data
        
        # 订阅所有生命周期事件
        for event_name in [
            SystemEvents.PLUGIN_BEFORE_ACTIVATE,
            SystemEvents.PLUGIN_AFTER_ACTIVATE,
            SystemEvents.PLUGIN_BEFORE_DEACTIVATE,
            SystemEvents.PLUGIN_AFTER_DEACTIVATE,
        ]:
            await event_bus.subscribe(event_name, event_handler)
        
        loader.registry.register(mock_plugin)
        
        await loader.activate(mock_plugin)
        await loader.deactivate(mock_plugin)
        
        # 验证事件发射
        event_names = [e for e in events_received]
        assert SystemEvents.PLUGIN_BEFORE_ACTIVATE in str(event_names) or events_received


class TestEcoLawPlugin:
    """测试环保法规插件"""
    
    @pytest.fixture
    def plugin(self):
        from taiji_agent.plugin.plugins import EcoLawPlugin
        return EcoLawPlugin()
    
    @pytest.fixture
    def mock_context(self, tmp_path):
        from taiji_agent.plugin import PluginContext, EventBus, PluginLogger
        import logging
        
        logging.basicConfig(level=logging.DEBUG)
        
        return PluginContext(
            plugin_id="eco-law",
            event_bus=EventBus(),
            config={"max_results": 10},
            data_dir=tmp_path,
            logger=PluginLogger("eco-law"),
        )
    
    @pytest.mark.asyncio
    async def test_activate(self, plugin, mock_context):
        """测试插件激活"""
        await plugin.activate(mock_context)
        
        assert plugin.context is not None
        assert len(plugin.tools) > 0
        assert len(plugin.hooks) > 0
    
    @pytest.mark.asyncio
    async def test_search_laws(self, plugin, mock_context):
        """测试法规搜索"""
        await plugin.activate(mock_context)
        
        result = await plugin.search_laws("环境保护")
        
        assert result["success"] is True
        assert result["count"] > 0
    
    @pytest.mark.asyncio
    async def test_get_law_detail(self, plugin, mock_context):
        """测试获取法规详情"""
        await plugin.activate(mock_context)
        
        result = await plugin.get_law_detail("law-001")
        
        assert result["success"] is True
        assert result["data"]["id"] == "law-001"
    
    @pytest.mark.asyncio
    async def test_list_categories(self, plugin, mock_context):
        """测试列出分类"""
        await plugin.activate(mock_context)
        
        result = await plugin.list_law_categories()
        
        assert result["success"] is True
        assert len(result["categories"]) > 0
    
    @pytest.mark.asyncio
    async def test_health_check(self, plugin, mock_context):
        """测试健康检查"""
        await plugin.activate(mock_context)
        
        health = await plugin.health_check()
        
        from taiji_agent.plugin import PluginHealth
        assert health == PluginHealth.HEALTHY


class TestEmissionPlugin:
    """测试排放数据插件"""
    
    @pytest.fixture
    def plugin(self):
        from taiji_agent.plugin.plugins import EmissionPlugin
        return EmissionPlugin()
    
    @pytest.fixture
    def mock_context(self, tmp_path):
        from taiji_agent.plugin import PluginContext, EventBus, PluginLogger
        import logging
        
        logging.basicConfig(level=logging.DEBUG)
        
        return PluginContext(
            plugin_id="emission-data",
            event_bus=EventBus(),
            config={},
            data_dir=tmp_path,
            logger=PluginLogger("emission-data"),
        )
    
    @pytest.mark.asyncio
    async def test_activate(self, plugin, mock_context):
        """测试插件激活"""
        await plugin.activate(mock_context)
        
        assert plugin.context is not None
        assert len(plugin.tools) > 0
    
    @pytest.mark.asyncio
    async def test_query_emission(self, plugin, mock_context):
        """测试排放数据查询"""
        await plugin.activate(mock_context)
        
        result = await plugin.query_emission("comp-001")
        
        assert result["success"] is True
        assert result["company"]["id"] == "comp-001"
    
    @pytest.mark.asyncio
    async def test_check_emission_alerts(self, plugin, mock_context):
        """测试排放预警检查"""
        await plugin.activate(mock_context)
        
        result = await plugin.check_emission_alerts("comp-002")
        
        assert result["success"] is True
        # comp-002 有超标记录，应该有警告
        assert result["alert_count"] > 0
    
    @pytest.mark.asyncio
    async def test_list_pollutants(self, plugin, mock_context):
        """测试列出污染物"""
        await plugin.activate(mock_context)
        
        result = await plugin.list_pollutants()
        
        assert result["success"] is True
        assert len(result["pollutants"]) > 0


class TestAssessmentPlugin:
    """测试环评报告辅助插件"""
    
    @pytest.fixture
    def plugin(self):
        from taiji_agent.plugin.plugins import AssessmentPlugin
        return AssessmentPlugin()
    
    @pytest.fixture
    def mock_context(self, tmp_path):
        from taiji_agent.plugin import PluginContext, EventBus, PluginLogger
        import logging
        
        logging.basicConfig(level=logging.DEBUG)
        
        return PluginContext(
            plugin_id="assessment-assist",
            event_bus=EventBus(),
            config={},
            data_dir=tmp_path,
            logger=PluginLogger("assessment-assist"),
        )
    
    @pytest.mark.asyncio
    async def test_activate(self, plugin, mock_context):
        """测试插件激活"""
        await plugin.activate(mock_context)
        
        assert plugin.context is not None
        assert len(plugin.tools) > 0
    
    @pytest.mark.asyncio
    async def test_create_report(self, plugin, mock_context):
        """测试创建报告"""
        await plugin.activate(mock_context)
        
        result = await plugin.create_report(
            project_name="测试项目",
            project_type="工业类",
            industry="电力",
            location="江苏省"
        )
        
        assert result["success"] is True
        assert "report_id" in result
    
    @pytest.mark.asyncio
    async def test_generate_section(self, plugin, mock_context):
        """测试生成章节"""
        await plugin.activate(mock_context)
        
        # 先创建报告
        create_result = await plugin.create_report(
            project_name="测试项目",
            project_type="工业类"
        )
        report_id = create_result["report_id"]
        
        # 生成章节
        result = await plugin.generate_section(
            report_id=report_id,
            section_id="overview"
        )
        
        assert result["success"] is True
        assert len(result["content"]) > 0
    
    @pytest.mark.asyncio
    async def test_check_compliance(self, plugin, mock_context):
        """测试合规性检查"""
        await plugin.activate(mock_context)
        
        # 创建报告
        create_result = await plugin.create_report(
            project_name="测试项目",
            project_type="工业类"
        )
        report_id = create_result["report_id"]
        
        # 检查合规
        result = await plugin.check_compliance(report_id)
        
        assert result["success"] is True
        # 未完成的章节应该产生警告
        assert result["warnings_count"] > 0
    
    @pytest.mark.asyncio
    async def test_get_report_outline(self, plugin, mock_context):
        """测试获取报告大纲"""
        await plugin.activate(mock_context)
        
        result = await plugin.get_report_outline("工业类")
        
        assert result["success"] is True
        assert len(result["outline"]) > 0
        assert "focus_areas" in result


class TestHookManager:
    """测试钩子管理器"""
    
    @pytest.mark.asyncio
    async def test_register_lifecycle_hooks(self):
        """测试注册生命周期钩子"""
        from taiji_agent.plugin import EventBus, HookManager
        
        event_bus = EventBus()
        hook_manager = HookManager(event_bus)
        
        pre_called = False
        post_called = False
        
        async def pre_handler(data):
            nonlocal pre_called
            pre_called = True
            return data
        
        async def post_handler(data):
            nonlocal post_called
            post_called = True
            return data
        
        await hook_manager.register_lifecycle_hooks(
            plugin_id="test-plugin",
            pre_process=pre_handler,
            post_process=post_handler,
        )
        
        # 触发事件
        await event_bus.emit(HookManager.PRE_PROCESS, {"test": True})
        await event_bus.emit(HookManager.POST_PROCESS, {"test": True})
        
        assert pre_called is True
        assert post_called is True
    
    @pytest.mark.asyncio
    async def test_unregister_hooks(self):
        """测试取消注册钩子"""
        from taiji_agent.plugin import EventBus, HookManager
        
        event_bus = EventBus()
        hook_manager = HookManager(event_bus)
        
        call_count = 0
        
        async def handler(data):
            nonlocal call_count
            call_count += 1
            return data
        
        await hook_manager.register_lifecycle_hooks(
            plugin_id="test-plugin",
            pre_process=handler,
        )
        
        await event_bus.emit(HookManager.PRE_PROCESS, {})
        await hook_manager.unregister_hooks("test-plugin")
        await event_bus.emit(HookManager.PRE_PROCESS, {})
        
        assert call_count == 1


# 测试运行入口
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
