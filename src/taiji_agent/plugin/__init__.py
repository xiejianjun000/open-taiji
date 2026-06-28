# -*- coding: utf-8 -*-
"""
Taiji Agent 插件系统模块。

提供完整的插件化架构，支持：
- 插件生命周期管理（加载、激活、停用、卸载）
- 插件注册与发现
- 事件总线与钩子系统
- 插件市场与安装管理
- 生态领域预置插件

平台+模块架构实现：
- 省级统建底座 = Taiji Agent Core
- 市县差异 = 不同插件组合
- 42个场景 = 42个（或更多）垂直插件
"""

# 插件基类与核心接口
from .plugin_base import (
    Plugin,                    # 插件基类
    PluginMetadata,           # 插件元数据
    PluginContext,           # 插件上下文
    PluginLogger,            # 插件日志记录器
    PluginDependency,        # 插件依赖
    PluginHealth,            # 插件健康状态
    PluginState,             # 插件生命周期状态
    ToolDefinition,          # 工具定义
    HookRegistration,        # 钩子注册
    ConfigurablePlugin,      # 支持配置验证的插件基类
    # 异常类
    PluginError,
    PluginLoadError,
    PluginActivationError,
    PluginDeactivationError,
    CircularDependencyError,
    VersionConflictError,
    SandboxError,
    SandboxTimeoutError,
)

# 钩子系统
from .hooks import (
    EventBus,                # 事件总线
    HookManager,            # 钩子管理器
    HookResult,             # 钩子执行结果
    HookInfo,               # 钩子信息
    HookPhase,              # 钩子执行阶段
    SystemEvents,           # 系统事件名称常量
)

# 插件注册中心
from .registry import (
    PluginRegistry,         # 插件注册中心
    PluginInfo,             # 插件信息记录
)

# 插件加载器
from .loader import (
    PluginLoader,           # 插件加载器
    DependencyResolver,     # 依赖解析器
)

# 插件市场
from .marketplace import (
    PluginMarketplaceClient,  # 插件市场客户端
    PluginInstaller,          # 插件安装器
    MarketplacePlugin,        # 市场插件信息
    PluginReview,             # 插件评价
    InstallationResult,       # 安装结果
)

# 预置插件
from .plugins import eco_law_plugin
from .plugins import emission_plugin
from .plugins import assessment_plugin

__all__ = [
    # 插件基类
    "Plugin",
    "PluginMetadata",
    "PluginContext",
    "PluginLogger",
    "PluginDependency",
    "PluginHealth",
    "PluginState",
    "ToolDefinition",
    "HookRegistration",
    "ConfigurablePlugin",
    # 异常
    "PluginError",
    "PluginLoadError",
    "PluginActivationError",
    "PluginDeactivationError",
    "CircularDependencyError",
    "VersionConflictError",
    "SandboxError",
    "SandboxTimeoutError",
    # 钩子系统
    "EventBus",
    "HookManager",
    "HookResult",
    "HookInfo",
    "HookPhase",
    "SystemEvents",
    # 注册中心
    "PluginRegistry",
    "PluginInfo",
    # 加载器
    "PluginLoader",
    "DependencyResolver",
    # 市场
    "PluginMarketplaceClient",
    "PluginInstaller",
    "MarketplacePlugin",
    "PluginReview",
    "InstallationResult",
]

__version__ = "1.0.0"
