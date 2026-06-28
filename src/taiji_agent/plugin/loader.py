# -*- coding: utf-8 -*-
"""
插件加载器模块。

负责插件的发现、解析、加载、激活和生命周期管理。
支持本地目录扫描、动态导入、热加载和依赖注入。
"""

import asyncio
import importlib.util
import os
import sys
import yaml
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .plugin_base import (
    Plugin, PluginMetadata, PluginContext, PluginDependency,
    PluginState, PluginLoadError, CircularDependencyError,
    VersionConflictError, PluginLogger
)
from .registry import PluginRegistry
from .hooks import EventBus, SystemEvents

if TYPE_CHECKING:
    from .hooks import HookManager


class DependencyResolver:
    """
    依赖解析器。
    
    实现 Kahn 拓扑排序、循环依赖检测和版本冲突检测。
    """
    
    def __init__(self, plugins: List[PluginMetadata]):
        """
        初始化依赖解析器。
        
        Args:
            plugins: 插件元数据列表
        """
        self.plugins = {p.id: p for p in plugins}
    
    def resolve(self) -> List[PluginMetadata]:
        """
        解析依赖并返回拓扑排序后的插件列表。
        
        Returns:
            按依赖顺序排列的插件列表（前置依赖在前）
            
        Raises:
            CircularDependencyError: 存在循环依赖
            VersionConflictError: 存在版本冲突
        """
        # Step 1: 构建入度表和邻接表
        in_degree: Dict[str, int] = {p.id: 0 for p in self.plugins.values()}
        adj: Dict[str, List[str]] = {p.id: [] for p in self.plugins.values()}
        
        for plugin in self.plugins.values():
            for dep in plugin.dependencies:
                if dep.plugin_id in self.plugins:
                    # dep.plugin_id 是前置依赖，plugin.id 依赖于它
                    adj.setdefault(dep.plugin_id, []).append(plugin.id)
                    in_degree[plugin.id] = in_degree.get(plugin.id, 0) + 1
        
        # Step 2: Kahn 拓扑排序
        queue = deque([pid for pid, deg in in_degree.items() if deg == 0])
        ordered: List[PluginMetadata] = []
        
        while queue:
            pid = queue.popleft()
            ordered.append(self.plugins[pid])
            
            for neighbor in adj.get(pid, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        # Step 3: 循环依赖检测
        if len(ordered) != len(self.plugins):
            unresolved = set(self.plugins.keys()) - {p.id for p in ordered}
            raise CircularDependencyError(
                f"Circular dependency detected involving plugins: {unresolved}"
            )
        
        # Step 4: 版本冲突检测
        self._check_version_conflicts(ordered)
        
        return ordered
    
    def _check_version_conflicts(self, plugins: List[PluginMetadata]) -> None:
        """检查同一插件的多个版本是否存在冲突"""
        version_map: Dict[str, set] = {}
        for p in plugins:
            version_map.setdefault(p.id, set()).add(p.version)
        
        for pid, versions in version_map.items():
            if len(versions) > 1:
                raise VersionConflictError(
                    f"Plugin {pid} has multiple versions: {versions}"
                )
    
    @staticmethod
    def check_version_compatibility(
        actual_version: str,
        version_spec: str,
    ) -> bool:
        """
        检查实际版本是否满足版本约束。
        
        Args:
            actual_version: 实际版本号
            version_spec: 版本约束，如 ">=1.0.0", ">=1.0.0, <2.0.0"
            
        Returns:
            是否满足约束
        """
        try:
            # 简单的语义版本检查
            actual = actual_version
            
            for constraint in version_spec.split(","):
                constraint = constraint.strip()
                if not constraint or constraint == "*":
                    continue
                
                # 解析实际版本
                actual_parts = actual.lstrip("v").split(".")
                actual_major = int(actual_parts[0]) if len(actual_parts) > 0 else 0
                actual_minor = int(actual_parts[1]) if len(actual_parts) > 1 else 0
                actual_patch = int(actual_parts[2].split("-")[0].split("+")[0]) if len(actual_parts) > 2 else 0
                
                if constraint.startswith(">="):
                    req_version = constraint[2:].strip()
                    req_parts = req_version.lstrip("v").split(".")
                    req_major = int(req_parts[0]) if len(req_parts) > 0 else 0
                    req_minor = int(req_parts[1]) if len(req_parts) > 1 else 0
                    req_patch = int(req_parts[2].split("-")[0].split("+")[0]) if len(req_parts) > 2 else 0
                    
                    actual_ver = (actual_major, actual_minor, actual_patch)
                    req_ver = (req_major, req_minor, req_patch)
                    if actual_ver < req_ver:
                        return False
                        
                elif constraint.startswith("<="):
                    req_version = constraint[2:].strip()
                    req_parts = req_version.lstrip("v").split(".")
                    req_major = int(req_parts[0]) if len(req_parts) > 0 else 0
                    req_minor = int(req_parts[1]) if len(req_parts) > 1 else 0
                    req_patch = int(req_parts[2].split("-")[0].split("+")[0]) if len(req_parts) > 2 else 0
                    
                    actual_ver = (actual_major, actual_minor, actual_patch)
                    req_ver = (req_major, req_minor, req_patch)
                    if actual_ver > req_ver:
                        return False
                        
                elif constraint.startswith(">"):
                    req_version = constraint[1:].strip()
                    req_parts = req_version.lstrip("v").split(".")
                    req_major = int(req_parts[0]) if len(req_parts) > 0 else 0
                    req_minor = int(req_parts[1]) if len(req_parts) > 1 else 0
                    req_patch = int(req_parts[2].split("-")[0].split("+")[0]) if len(req_parts) > 2 else 0
                    
                    actual_ver = (actual_major, actual_minor, actual_patch)
                    req_ver = (req_major, req_minor, req_patch)
                    if actual_ver <= req_ver:
                        return False
                        
                elif constraint.startswith("<"):
                    req_version = constraint[1:].strip()
                    req_parts = req_version.lstrip("v").split(".")
                    req_major = int(req_parts[0]) if len(req_parts) > 0 else 0
                    req_minor = int(req_parts[1]) if len(req_parts) > 1 else 0
                    req_patch = int(req_parts[2].split("-")[0].split("+")[0]) if len(req_parts) > 2 else 0
                    
                    actual_ver = (actual_major, actual_minor, actual_patch)
                    req_ver = (req_major, req_minor, req_patch)
                    if actual_ver >= req_ver:
                        return False
                        
                elif constraint.startswith("=="):
                    req_version = constraint[2:].strip()
                    if actual != req_version:
                        return False
                        
                elif constraint.startswith("^"):
                    # ^1.2.3 → >=1.2.3, <2.0.0
                    base_version = constraint[1:].strip()
                    base_parts = base_version.lstrip("v").split(".")
                    base_major = int(base_parts[0]) if len(base_parts) > 0 else 0
                    
                    lower = (base_major, 0, 0)
                    upper = (base_major + 1, 0, 0)
                    
                    actual_ver = (actual_major, actual_minor, actual_patch)
                    if not (lower <= actual_ver < upper):
                        return False
                        
                elif constraint.startswith("~"):
                    # ~1.2.3 → >=1.2.3, <1.3.0
                    base_version = constraint[1:].strip()
                    base_parts = base_version.lstrip("v").split(".")
                    base_major = int(base_parts[0]) if len(base_parts) > 0 else 0
                    base_minor = int(base_parts[1]) if len(base_parts) > 1 else 0
                    
                    lower = (base_major, base_minor, 0)
                    upper = (base_major, base_minor + 1, 0)
                    
                    actual_ver = (actual_major, actual_minor, actual_patch)
                    if not (lower <= actual_ver < upper):
                        return False
            
            return True
            
        except Exception:
            # 解析失败时保守返回 True
            return True


class PluginLoader:
    """
    插件加载器。
    
    负责发现、解析、验证、加载、激活插件。
    
    Features:
        - 目录扫描和 YAML 解析
        - 动态导入 (importlib)
        - 依赖解析和拓扑排序
        - 热插拔支持（可选）
        - 生命周期管理
    """
    
    def __init__(
        self,
        plugin_dirs: Optional[List[Path]] = None,
        event_bus: Optional[EventBus] = None,
        registry: Optional[PluginRegistry] = None,
        enable_watchdog: bool = False,
        data_root: Optional[Path] = None,
    ):
        """
        初始化插件加载器。
        
        Args:
            plugin_dirs: 插件目录列表
            event_bus: 事件总线
            registry: 插件注册中心
            enable_watchdog: 是否启用文件监听热插拔
            data_root: 数据根目录
        """
        self.plugin_dirs = plugin_dirs or [Path.cwd() / "plugins"]
        self.event_bus = event_bus or EventBus()
        self.registry = registry or PluginRegistry()
        self._enable_watchdog = enable_watchdog
        self._watcher = None
        self._data_root = data_root or Path.cwd() / "data"
        
        # 自动发现祖先目录的 plugins/ 文件夹
        self._discover_ancestor_plugins()
    
    def _discover_ancestor_plugins(self) -> None:
        """向上遍历目录树，发现 plugins/ 文件夹"""
        dir_current = Path.cwd()
        while True:
            parent = dir_current.parent
            if parent == dir_current:
                break
            candidate = parent / "plugins"
            if candidate not in self.plugin_dirs and candidate.is_dir():
                self.plugin_dirs.append(candidate)
            dir_current = parent
    
    async def load_all(
        self,
        enabled_plugins: Optional[List[str]] = None,
    ) -> List[Plugin]:
        """
        扫描所有插件目录，解析依赖，按拓扑序加载和激活。
        
        Args:
            enabled_plugins: 启用的插件 ID 列表，None 表示全部
            
        Returns:
            加载的插件列表
        """
        # Step 1: 扫描并解析所有插件
        discovered = self._scan_all()
        if not discovered:
            return []
        
        # 过滤启用的插件
        if enabled_plugins:
            discovered = [p for p in discovered if p.id in enabled_plugins]
        
        # 如果有已注册的插件，只加载未注册的
        already_loaded = set(self.registry.list_ids())
        discovered = [p for p in discovered if p.id not in already_loaded]
        
        if not discovered:
            return []
        
        # Step 2: 依赖解析 + 拓扑排序
        try:
            ordered = self._resolve_dependencies(discovered)
        except (CircularDependencyError, VersionConflictError) as e:
            import logging; logging.getLogger(__name__).error(f'Dependency resolution failed: {e}')
            return []
        
        # Step 3: 按序加载
        loaded: List[Plugin] = []
        for meta in ordered:
            plugin = await self._load_single(meta)
            if plugin:
                loaded.append(plugin)
        
        # Step 4: 启动热插拔文件监听
        if self._enable_watchdog and not self._watcher:
            self._start_watchdog()
        
        return loaded
    
    def _scan_all(self) -> List[PluginMetadata]:
        """
        扫描所有插件目录，返回元数据列表。
        
        Returns:
            发现的插件元数据列表
        """
        discovered = []
        for plugin_dir in self.plugin_dirs:
            if not plugin_dir.is_dir():
                continue
            for entry in sorted(plugin_dir.iterdir()):
                if not entry.is_dir():
                    continue
                yaml_path = entry / "plugin.yaml"
                if not yaml_path.exists():
                    continue
                meta = self._parse_yaml(yaml_path)
                if meta:
                    meta._plugin_dir = entry
                    discovered.append(meta)
        return discovered
    
    def _parse_yaml(self, yaml_path: Path) -> Optional[PluginMetadata]:
        """
        解析 plugin.yaml 文件。
        
        Args:
            yaml_path: YAML 文件路径
            
        Returns:
            插件元数据或 None
        """
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            
            if not data:
                return None
            
            deps = []
            for dep in data.get("dependencies", []):
                deps.append(PluginDependency(
                    plugin_id=dep["id"],
                    version_spec=dep.get("version", "*"),
                    optional=dep.get("optional", False),
                ))
            
            return PluginMetadata(
                id=data["id"],
                name=data.get("name", data["id"]),
                version=data["version"],
                description=data.get("description", ""),
                author=data.get("author", ""),
                homepage=data.get("homepage", ""),
                license=data.get("license", ""),
                dependencies=deps,
                permissions=data.get("permissions", []),
                config_schema=data.get("config_schema"),
                min_agent_version=data.get("min_agent_version", "1.0.0"),
                tags=data.get("tags", []),
                main=data.get("main", "main.py"),
            )
        except Exception as e:
            import logging; logging.getLogger(__name__).error(f'Failed to parse {yaml_path}: {e}')
            return None
    
    async def _load_single(self, meta: PluginMetadata) -> Optional[Plugin]:
        """
        加载单个插件。
        
        Args:
            meta: 插件元数据
            
        Returns:
            加载的插件实例或 None
        """
        if meta.id in self.registry:
            return self.registry.get(meta.id)
        
        # 发射加载前事件
        await self.event_bus.emit(SystemEvents.PLUGIN_BEFORE_LOAD, {
            "plugin_id": meta.id,
            "plugin_dir": getattr(meta, "_plugin_dir", None),
        })
        
        try:
            # 确定模块入口
            entry = self._resolve_entry(meta)
            if not entry:
                return None
            
            # 动态导入
            spec = importlib.util.spec_from_file_location(meta.id, entry)
            if not spec or not spec.loader:
                raise PluginLoadError(f"Cannot load plugin module: {entry}")
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[meta.id] = module
            spec.loader.exec_module(module)
            
            # 查找插件类
            plugin_cls = self._find_plugin_class(module)
            if not plugin_cls:
                raise PluginLoadError(f"No Plugin subclass found in {entry}")
            
            # 实例化
            plugin = plugin_cls(meta)
            
            # 注册到注册中心
            self.registry.register(plugin, meta)
            
            # 发射加载后事件
            await self.event_bus.emit(SystemEvents.PLUGIN_AFTER_LOAD, {
                "plugin_id": meta.id,
                "success": True,
            })
            
            return plugin
            
        except Exception as e:
            # 发射错误事件
            await self.event_bus.emit(SystemEvents.PLUGIN_ERROR, {
                "plugin_id": meta.id,
                "error": str(e),
            })
            import logging; logging.getLogger(__name__).error(f'Failed to load plugin {meta.id}: {e}')
            return None
    
    def _resolve_entry(self, meta: PluginMetadata) -> Optional[Path]:
        """
        解析插件入口文件。
        
        Args:
            meta: 插件元数据
            
        Returns:
            入口文件路径或 None
        """
        plugin_dir = getattr(meta, "_plugin_dir", None)
        if not plugin_dir:
            return None
        
        # 优先使用 YAML 中定义的 main
        yaml_path = plugin_dir / "plugin.yaml"
        if yaml_path.exists():
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                main = data.get("main", "main.py")
        else:
            main = meta.main
        
        entry = plugin_dir / main
        return entry if entry.exists() else None
    
    def _find_plugin_class(self, module: Any) -> Optional[type]:
        """
        从模块中查找 Plugin 子类。
        
        Args:
            module: Python 模块
            
        Returns:
            Plugin 子类或 None
        """
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, Plugin)
                and attr is not Plugin
            ):
                return attr
        return None
    
    def _resolve_dependencies(
        self,
        plugins: List[PluginMetadata],
    ) -> List[PluginMetadata]:
        """
        依赖解析 + 拓扑排序。
        
        Args:
            plugins: 插件元数据列表
            
        Returns:
            按依赖顺序排列的列表
        """
        resolver = DependencyResolver(plugins)
        return resolver.resolve()
    
    async def activate(self, plugin: Plugin) -> bool:
        """
        激活插件。
        
        Args:
            plugin: 插件实例
            
        Returns:
            是否成功激活
        """
        plugin_id = plugin.metadata.id
        
        # 发射激活前事件
        await self.event_bus.emit(SystemEvents.PLUGIN_BEFORE_ACTIVATE, {
            "plugin_id": plugin_id,
        })
        
        self.registry.update_state(plugin_id, PluginState.ACTIVATING)
        
        try:
            # 创建上下文
            ctx = self._create_context(plugin.metadata)
            plugin.context = ctx
            
            # 激活插件
            await plugin.activate(ctx)
            
            # 更新状态
            self.registry.update_state(plugin_id, PluginState.ACTIVE)
            
            # 发射激活后事件
            await self.event_bus.emit(SystemEvents.PLUGIN_AFTER_ACTIVATE, {
                "plugin_id": plugin_id,
                "success": True,
            })
            
            return True
            
        except Exception as e:
            self.registry.update_state(plugin_id, PluginState.ERROR)
            
            await self.event_bus.emit(SystemEvents.PLUGIN_ERROR, {
                "plugin_id": plugin_id,
                "state": PluginState.ACTIVATING,
                "error": str(e),
            })
            
            import logging; logging.getLogger(__name__).error(f'Failed to activate plugin {plugin_id}: {e}')
            return False
    
    async def deactivate(self, plugin: Plugin) -> bool:
        """
        停用插件。
        
        Args:
            plugin: 插件实例
            
        Returns:
            是否成功停用
        """
        plugin_id = plugin.metadata.id
        
        # 发射停用前事件
        await self.event_bus.emit(SystemEvents.PLUGIN_BEFORE_DEACTIVATE, {
            "plugin_id": plugin_id,
        })
        
        self.registry.update_state(plugin_id, PluginState.DEACTIVATING)
        
        try:
            await plugin.deactivate()
            
            # 更新状态
            self.registry.update_state(plugin_id, PluginState.DEACTIVATED)
            
            # 发射停用后事件
            await self.event_bus.emit(SystemEvents.PLUGIN_AFTER_DEACTIVATE, {
                "plugin_id": plugin_id,
                "success": True,
            })
            
            return True
            
        except Exception as e:
            self.registry.update_state(plugin_id, PluginState.ERROR)
            
            await self.event_bus.emit(SystemEvents.PLUGIN_ERROR, {
                "plugin_id": plugin_id,
                "state": PluginState.DEACTIVATING,
                "error": str(e),
            })
            
            import logging; logging.getLogger(__name__).error(f'Failed to deactivate plugin {plugin_id}: {e}')
            return False
    
    async def reload(self, plugin: Plugin) -> bool:
        """
        热重载插件。
        
        Args:
            plugin: 插件实例
            
        Returns:
            是否成功重载
        """
        plugin_id = plugin.metadata.id
        
        # 停用
        await self.deactivate(plugin)
        
        # 重新加载
        meta = plugin.metadata
        new_plugin = await self._load_single(meta)
        if not new_plugin:
            return False
        
        # 重新激活
        return await self.activate(new_plugin)
    
    def _create_context(self, meta: PluginMetadata) -> PluginContext:
        """
        创建插件上下文。
        
        Args:
            meta: 插件元数据
            
        Returns:
            插件上下文
        """
        plugin_id = meta.id
        
        # 创建插件私有数据目录
        data_dir = self._data_root / "plugins" / plugin_id
        data_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建日志记录器
        logger = PluginLogger(plugin_id)
        
        # 加载配置
        config = self._load_plugin_config(meta)
        
        return PluginContext(
            plugin_id=plugin_id,
            event_bus=self.event_bus,
            config=config,
            data_dir=data_dir,
            logger=logger,
        )
    
    def _load_plugin_config(self, meta: PluginMetadata) -> Dict[str, Any]:
        """
        加载插件配置。
        
        Args:
            meta: 插件元数据
            
        Returns:
            配置字典
        """
        # 默认配置
        config: Dict[str, Any] = {}
        
        # 从 YAML 加载默认配置
        plugin_dir = getattr(meta, "_plugin_dir", None)
        if plugin_dir:
            yaml_path = plugin_dir / "plugin.yaml"
            if yaml_path.exists():
                with open(yaml_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    config = data.get("config", {})
        
        return config
    
    def _start_watchdog(self) -> None:
        """启动文件监听，支持热插拔"""
        try:
            from watchdog.observers import Observer
            from .watchdog_integration import PluginFileHandler
            
            self._watcher = Observer()
            handler = PluginFileHandler(self)
            
            for plugin_dir in self.plugin_dirs:
                if plugin_dir.is_dir():
                    self._watcher.schedule(handler, str(plugin_dir), recursive=True)
            
            self._watcher.start()
        except ImportError:
            import logging; logging.getLogger(__name__).warning('watchdog not installed, hot reload disabled')
    
    def stop_watchdog(self) -> None:
        """停止文件监听"""
        if self._watcher:
            self._watcher.stop()
            self._watcher = None
