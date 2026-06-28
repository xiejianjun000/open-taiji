# -*- coding: utf-8 -*-
"""
插件注册中心模块。

负责插件的注册、注销、查询和状态管理。
提供插件发现、版本索引和依赖追踪功能。
"""

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .plugin_base import Plugin, PluginMetadata, PluginState


@dataclass
class PluginInfo:
    """
    插件信息记录。
    
    存储插件实例及其相关元数据。
    """
    plugin: Plugin
    metadata: PluginMetadata
    state: PluginState = PluginState.REGISTERED
    enabled: bool = True
    load_order: int = 0  # 加载顺序（基于依赖关系）


class PluginRegistry:
    """
    插件注册中心。
    
    负责管理所有已注册的插件，提供：
    - 插件注册/注销
    - 插件查询（按 ID、标签、状态）
    - 版本索引
    - 依赖追踪
    
    使用示例:
        registry = PluginRegistry()
        registry.register(my_plugin)
        
        plugin = registry.get("my-plugin-id")
        all_plugins = registry.list_all()
        active_plugins = registry.list_by_state(PluginState.ACTIVE)
    """
    
    def __init__(self):
        """初始化插件注册中心"""
        # plugin_id -> PluginInfo
        self._plugins: Dict[str, PluginInfo] = {}
        # 插件索引
        self._tag_index: Dict[str, Set[str]] = defaultdict(set)  # tag -> plugin_ids
        self._name_index: Dict[str, str] = {}  # name -> plugin_id
        self._version_index: Dict[str, str] = {}  # plugin_id -> version
    
    def register(
        self,
        plugin: Plugin,
        metadata: Optional[PluginMetadata] = None,
        load_order: int = 0,
    ) -> None:
        """
        注册插件。
        
        Args:
            plugin: 插件实例
            metadata: 插件元数据（如果插件已有则使用插件的元数据）
            load_order: 加载顺序
            
        Raises:
            ValueError: 如果插件已注册
        """
        plugin_id = plugin.metadata.id
        
        if plugin_id in self._plugins:
            raise ValueError(f"Plugin already registered: {plugin_id}")
        
        meta = metadata or plugin.metadata
        
        plugin_info = PluginInfo(
            plugin=plugin,
            metadata=meta,
            state=plugin.state,
            load_order=load_order,
        )
        
        self._plugins[plugin_id] = plugin_info
        self._version_index[plugin_id] = meta.version
        self._name_index[meta.name] = plugin_id
        
        # 索引标签
        for tag in meta.tags:
            self._tag_index[tag].add(plugin_id)
    
    def unregister(self, plugin_id: str) -> bool:
        """
        注销插件。
        
        Args:
            plugin_id: 插件 ID
            
        Returns:
            是否成功注销
        """
        if plugin_id not in self._plugins:
            return False
        
        plugin_info = self._plugins[plugin_id]
        
        # 清理索引
        self._version_index.pop(plugin_id, None)
        self._name_index.pop(plugin_info.metadata.name, None)
        
        for tag in plugin_info.metadata.tags:
            self._tag_index[tag].discard(plugin_id)
        
        del self._plugins[plugin_id]
        return True
    
    def get(self, plugin_id: str) -> Optional[Plugin]:
        """
        获取插件实例。
        
        Args:
            plugin_id: 插件 ID
            
        Returns:
            插件实例或 None
        """
        plugin_info = self._plugins.get(plugin_id)
        return plugin_info.plugin if plugin_info else None
    
    def get_info(self, plugin_id: str) -> Optional[PluginInfo]:
        """
        获取插件信息。
        
        Args:
            plugin_id: 插件 ID
            
        Returns:
            插件信息或 None
        """
        return self._plugins.get(plugin_id)
    
    def get_metadata(self, plugin_id: str) -> Optional[PluginMetadata]:
        """
        获取插件元数据。
        
        Args:
            plugin_id: 插件 ID
            
        Returns:
            插件元数据或 None
        """
        plugin_info = self._plugins.get(plugin_id)
        return plugin_info.metadata if plugin_info else None
    
    def exists(self, plugin_id: str) -> bool:
        """
        检查插件是否已注册。
        
        Args:
            plugin_id: 插件 ID
            
        Returns:
            是否已注册
        """
        return plugin_id in self._plugins
    
    def list_all(self) -> List[Plugin]:
        """
        列出所有已注册的插件。
        
        Returns:
            插件列表
        """
        return [info.plugin for info in self._plugins.values()]
    
    def list_ids(self) -> List[str]:
        """
        列出所有已注册的插件 ID。
        
        Returns:
            插件 ID 列表
        """
        return list(self._plugins.keys())
    
    def list_by_state(self, state: PluginState) -> List[Plugin]:
        """
        按状态筛选插件。
        
        Args:
            state: 插件状态
            
        Returns:
            符合条件的插件列表
        """
        return [
            info.plugin for info in self._plugins.values()
            if info.state == state
        ]
    
    def list_by_tag(self, tag: str) -> List[Plugin]:
        """
        按标签筛选插件。
        
        Args:
            tag: 标签
            
        Returns:
            符合条件的插件列表
        """
        plugin_ids = self._tag_index.get(tag, set())
        return [
            self._plugins[pid].plugin for pid in plugin_ids
            if pid in self._plugins
        ]
    
    def list_enabled(self) -> List[Plugin]:
        """
        列出所有已启用的插件。
        
        Returns:
            启用的插件列表
        """
        return [
            info.plugin for info in self._plugins.values()
            if info.enabled
        ]
    
    def list_active(self) -> List[Plugin]:
        """
        列出所有活跃的插件（状态为 ACTIVE）。
        
        Returns:
            活跃的插件列表
        """
        return self.list_by_state(PluginState.ACTIVE)
    
    def update_state(self, plugin_id: str, state: PluginState) -> bool:
        """
        更新插件状态。
        
        Args:
            plugin_id: 插件 ID
            state: 新状态
            
        Returns:
            是否成功更新
        """
        plugin_info = self._plugins.get(plugin_id)
        if not plugin_info:
            return False
        
        plugin_info.state = state
        plugin_info.plugin.state = state
        return True
    
    def enable(self, plugin_id: str) -> bool:
        """
        启用插件。
        
        Args:
            plugin_id: 插件 ID
            
        Returns:
            是否成功启用
        """
        plugin_info = self._plugins.get(plugin_id)
        if not plugin_info:
            return False
        
        plugin_info.enabled = True
        return True
    
    def disable(self, plugin_id: str) -> bool:
        """
        禁用插件。
        
        Args:
            plugin_id: 插件 ID
            
        Returns:
            是否成功禁用
        """
        plugin_info = self._plugins.get(plugin_id)
        if not plugin_info:
            return False
        
        plugin_info.enabled = False
        return True
    
    def is_enabled(self, plugin_id: str) -> bool:
        """
        检查插件是否已启用。
        
        Args:
            plugin_id: 插件 ID
            
        Returns:
            是否已启用
        """
        plugin_info = self._plugins.get(plugin_id)
        return plugin_info.enabled if plugin_info else False
    
    def get_version(self, plugin_id: str) -> Optional[str]:
        """
        获取插件版本。
        
        Args:
            plugin_id: 插件 ID
            
        Returns:
            版本字符串或 None
        """
        return self._version_index.get(plugin_id)
    
    def get_dependencies(self, plugin_id: str) -> List[str]:
        """
        获取插件的依赖列表。
        
        Args:
            plugin_id: 插件 ID
            
        Returns:
            依赖的插件 ID 列表
        """
        plugin_info = self._plugins.get(plugin_id)
        if not plugin_info:
            return []
        
        return [dep.plugin_id for dep in plugin_info.metadata.dependencies]
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取注册中心统计信息。
        
        Returns:
            统计信息字典
        """
        state_counts = defaultdict(int)
        for info in self._plugins.values():
            state_counts[info.state.value] += 1
        
        return {
            "total": len(self._plugins),
            "enabled": sum(1 for info in self._plugins.values() if info.enabled),
            "active": len(self.list_active()),
            "by_state": dict(state_counts),
            "tags": len(self._tag_index),
        }
    
    def clear(self) -> None:
        """清空注册中心"""
        self._plugins.clear()
        self._tag_index.clear()
        self._name_index.clear()
        self._version_index.clear()
    
    def __contains__(self, plugin_id: str) -> bool:
        """支持 in 操作符"""
        return plugin_id in self._plugins
    
    def __len__(self) -> int:
        """支持 len() 函数"""
        return len(self._plugins)
    
    def __iter__(self):
        """支持迭代"""
        return iter(self._plugins.values())
