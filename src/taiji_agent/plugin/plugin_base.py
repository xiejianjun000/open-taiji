# -*- coding: utf-8 -*-
"""
插件基类与核心接口定义。

定义 Plugin 抽象基类、插件元数据、上下文等核心接口，
兼容 Harness TypeScript 版的 Plugin 接口设计。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class PluginHealth(Enum):
    """插件健康状态枚举"""
    HEALTHY = auto()      # 健康运行
    DEGRADED = auto()     # 降级运行
    UNHEALTHY = auto()    # 不健康
    ERROR = auto()        # 错误状态


class PluginState(Enum):
    """插件生命周期状态枚举"""
    REGISTERED = "registered"     # 已注册（发现但未加载）
    LOADING = "loading"            # 加载中
    LOADED = "loaded"              # 已加载
    ACTIVATING = "activating"      # 激活中
    ACTIVE = "active"              # 已激活（正常运行）
    DEACTIVATING = "deactivating"  # 停用中
    DEACTIVATED = "deactivated"    # 已停用
    ERROR = "error"                # 错误状态


@dataclass
class ToolDefinition:
    """
    工具定义 - 与 Harness ToolDefinition 兼容。
    
    Attributes:
        name: 工具名称
        description: 工具描述
        parameters: JSON Schema 格式的参数定义
        handler: 工具处理函数
    """
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Optional[Callable[..., Any]] = None


@dataclass
class HookRegistration:
    """
    事件钩子注册 - 与 Harness AnyHookRegistration 兼容。
    
    Attributes:
        event: 事件名称（如 "tool:request"）
        handler: 异步处理函数，接收 data 返回处理后的 data 或 {"abort": True}
        priority: 优先级，越小越优先，默认 100
    """
    event: str
    handler: Callable[..., Any]
    priority: int = 100


@dataclass
class PluginDependency:
    """
    插件依赖声明。
    
    Attributes:
        plugin_id: 依赖插件 ID
        version_spec: 语义版本号约束，如 ">=1.0.0, <2.0.0"
        optional: 是否为可选依赖
    """
    plugin_id: str
    version_spec: str = "*"
    optional: bool = False


@dataclass
class PluginMetadata:
    """
    插件元数据。
    
    包含插件的基本信息、依赖、权限声明和配置 Schema。
    通常从 plugin.yaml 文件解析生成。
    """
    id: str                           # 插件唯一标识
    name: str                         # 插件显示名称
    version: str                      # 语义版本号
    description: str = ""             # 插件描述
    author: str = ""                  # 作者
    homepage: str = ""                # 主页
    license: str = ""                 # 许可证
    dependencies: List[PluginDependency] = field(default_factory=list)  # 依赖列表
    permissions: List[str] = field(default_factory=list)  # 所需权限列表
    config_schema: Optional[Dict[str, Any]] = None  # JSON Schema 格式的配置校验
    min_agent_version: str = "1.0.0"  # 最低兼容 Agent 版本
    tags: List[str] = field(default_factory=list)  # 标签
    main: str = "main.py"             # 入口文件
    _plugin_dir: Optional[Path] = None  # 内部：插件目录路径


class PluginContext:
    """
    插件上下文。
    
    在插件激活时注入，提供插件运行所需的各种服务和资源。
    
    Attributes:
        plugin_id: 插件 ID
        event_bus: 事件总线引用
        config: 插件配置（来自 YAML 或运行时注入）
        data_dir: 插件私有数据目录
        logger: 带插件前缀的日志记录器
        state_manager: Agent 状态管理器（可选）
        store: 持久化存储（可选）
        tool_registry: 工具注册表（可选）
        secret_store: 密钥存储（可选）
    """
    
    def __init__(
        self,
        plugin_id: str,
        event_bus: "EventBus",
        config: Dict[str, Any],
        data_dir: Path,
        logger: "PluginLogger",
        state_manager: Optional[Any] = None,
        store: Optional[Any] = None,
        tool_registry: Optional[Any] = None,
        secret_store: Optional[Any] = None,
    ):
        self.plugin_id = plugin_id
        self.event_bus = event_bus
        self.config = config
        self.data_dir = data_dir
        self.logger = logger
        self.state_manager = state_manager
        self.store = store
        self.tool_registry = tool_registry
        self.secret_store = secret_store
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        return self.config.get(key, default)
    
    def set_config(self, key: str, value: Any) -> None:
        """更新配置值"""
        self.config[key] = value


class PluginLogger:
    """
    带插件前缀的日志记录器。
    
    为每个插件提供独立的日志记录器，日志消息自动添加插件前缀。
    """
    
    def __init__(self, plugin_id: str, logger_name: Optional[str] = None):
        """
        初始化插件日志记录器。
        
        Args:
            plugin_id: 插件 ID，用于日志前缀
            logger_name: 可选的日志记录器名称，默认使用 "plugin.{plugin_id}"
        """
        import logging
        self._logger = logging.getLogger(logger_name or f"plugin.{plugin_id}")
        self._prefix = f"[{plugin_id}]"
    
    def debug(self, message: str, *args, **kwargs) -> None:
        """调试级别日志"""
        self._logger.debug(f"{self._prefix} {message}", *args, **kwargs)
    
    def info(self, message: str, *args, **kwargs) -> None:
        """信息级别日志"""
        self._logger.info(f"{self._prefix} {message}", *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs) -> None:
        """警告级别日志"""
        self._logger.warning(f"{self._prefix} {message}", *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs) -> None:
        """错误级别日志"""
        self._logger.error(f"{self._prefix} {message}", *args, **kwargs)
    
    def critical(self, message: str, *args, **kwargs) -> None:
        """严重级别日志"""
        self._logger.critical(f"{self._prefix} {message}", *args, **kwargs)


class Plugin(ABC):
    """
    插件基类。
    
    所有插件必须继承此类并实现抽象方法。
    兼容 Harness 的 HarnessPlugin 接口设计。
    
    Attributes:
        metadata: 插件元数据
        tools: 插件提供的工具定义列表
        hooks: 插件注册的事件钩子列表
        ui_contributions: UI 贡献（可选）
    """
    
    # 元数据（子类可通过类属性或构造器设置）
    metadata: PluginMetadata
    
    # 能力声明
    tools: List[ToolDefinition] = []
    hooks: List[HookRegistration] = []
    ui_contributions: Optional[Dict[str, Any]] = None
    
    def __init__(self, metadata: PluginMetadata):
        """
        初始化插件。
        
        Args:
            metadata: 插件元数据
        """
        self.metadata = metadata
        self._state = PluginState.REGISTERED
        self._context: Optional[PluginContext] = None
    
    @abstractmethod
    async def activate(self, ctx: PluginContext) -> None:
        """
        激活插件。
        
        在此方法中：
        - 注册工具、钩子
        - 初始化资源（数据库连接、网络客户端、文件句柄）
        
        Note:
            在 activate() 中抛出异常将导致状态回退到 ERROR
        
        Args:
            ctx: 插件上下文
        """
        pass
    
    @abstractmethod
    async def deactivate(self) -> None:
        """
        停用插件。
        
        在此方法中：
        - 释放资源
        - 取消事件监听
        - 关闭网络连接
        """
        pass
    
    async def health_check(self) -> PluginHealth:
        """
        健康检查。
        
        默认返回 HEALTHY，子类可重写以检查依赖服务可用性。
        
        Returns:
            插件健康状态
        """
        return PluginHealth.HEALTHY
    
    async def get_metrics(self) -> Dict[str, Any]:
        """
        获取插件指标。
        
        返回 Prometheus 兼容的键值对。
        
        Returns:
            指标字典
        """
        return {}
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """
        获取配置值。
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            配置值或默认值
        """
        if self._context is None:
            return default
        return self._context.config.get(key, default)
    
    def set_config(self, key: str, value: Any) -> None:
        """
        更新配置值。
        
        Args:
            key: 配置键
            value: 配置值
        """
        if self._context is not None:
            self._context.config[key] = value
    
    @property
    def state(self) -> PluginState:
        """获取插件当前状态"""
        return self._state
    
    @state.setter
    def state(self, value: PluginState) -> None:
        """设置插件状态"""
        self._state = value
        if self._context and self._context.logger:
            self._context.logger.info(f"State changed to: {value.value}")
    
    @property
    def context(self) -> Optional[PluginContext]:
        """获取插件上下文"""
        return self._context
    
    @context.setter
    def context(self, ctx: PluginContext) -> None:
        """设置插件上下文"""
        self._context = ctx


class ConfigurablePlugin(Plugin):
    """
    支持配置 Schema 验证的插件基类。
    
    当插件定义了 config_schema 时，自动启用配置验证。
    """
    
    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        """
        验证配置是否符合 metadata.config_schema。
        
        Args:
            config: 待验证的配置字典
            
        Returns:
            错误列表，空列表表示验证通过
        """
        if self.metadata.config_schema is None:
            return []
        
        errors = []
        try:
            import jsonschema
            jsonschema.validate(instance=config, schema=self.metadata.config_schema)
        except ImportError:
            # jsonschema 未安装，跳过验证
            pass
        except Exception as e:
            errors.append(str(e))
        
        return errors


class PluginError(Exception):
    """插件相关异常基类"""
    pass


class PluginLoadError(PluginError):
    """插件加载失败"""
    pass


class PluginActivationError(PluginError):
    """插件激活失败"""
    pass


class PluginDeactivationError(PluginError):
    """插件停用失败"""
    pass


class CircularDependencyError(PluginError):
    """循环依赖错误"""
    pass


class VersionConflictError(PluginError):
    """版本冲突错误"""
    pass


class SandboxError(PluginError):
    """沙箱相关错误"""
    pass


class SandboxTimeoutError(SandboxError):
    """沙箱执行超时错误"""
    pass
