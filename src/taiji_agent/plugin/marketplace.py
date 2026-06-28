# -*- coding: utf-8 -*-
"""
插件市场模块。

提供插件市场的客户端功能，包括：
- 插件浏览和搜索
- 插件安装、更新、卸载
- 插件评分与审核
"""

import asyncio
import hashlib
import json
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from .plugin_base import PluginMetadata


@dataclass
class MarketplacePlugin:
    """
    市场中的插件信息。
    
    Attributes:
        metadata: 插件元数据
        download_url: 下载地址
        checksum: 文件校验和
        rating: 平均评分
        review_count: 评价数量
        downloads: 下载次数
        verified: 是否已验证
        created_at: 上架时间
        updated_at: 更新时间
    """
    metadata: PluginMetadata
    download_url: str
    checksum: str
    rating: float = 0.0
    review_count: int = 0
    downloads: int = 0
    verified: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class PluginReview:
    """
    插件评价。
    
    Attributes:
        id: 评价 ID
        plugin_id: 插件 ID
        user_id: 用户 ID
        rating: 评分 (1-5)
        title: 评价标题
        content: 评价内容
        created_at: 创建时间
    """
    id: str
    plugin_id: str
    user_id: str
    rating: int
    title: str
    content: str
    created_at: str


@dataclass
class InstallationResult:
    """
    安装结果。
    
    Attributes:
        success: 是否成功
        plugin_id: 插件 ID
        install_path: 安装路径
        error: 错误信息（如果有）
    """
    success: bool
    plugin_id: str
    install_path: Optional[Path] = None
    error: Optional[str] = None


class PluginMarketplaceClient:
    """
    插件市场客户端。
    
    提供与远程插件市场的交互能力。
    
    Attributes:
        base_url: 市场服务器地址
        timeout: 请求超时（秒）
    """
    
    def __init__(
        self,
        base_url: str = "https://marketplace.taiji-agent.example.com",
        timeout: int = 30,
    ):
        """
        初始化插件市场客户端。
        
        Args:
            base_url: 市场服务器地址
            timeout: 请求超时（秒）
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 HTTP 客户端"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._client
    
    async def close(self) -> None:
        """关闭客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def list_plugins(
        self,
        category: Optional[str] = None,
        tag: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> List[MarketplacePlugin]:
        """
        列出市场中的插件。
        
        Args:
            category: 分类筛选
            tag: 标签筛选
            page: 页码
            page_size: 每页数量
            
        Returns:
            插件列表
        """
        client = await self._get_client()
        
        params = {
            "page": page,
            "page_size": page_size,
        }
        if category:
            params["category"] = category
        if tag:
            params["tag"] = tag
        
        try:
            response = await client.get("/api/v1/plugins", params=params)
            response.raise_for_status()
            data = response.json()
            
            return [
                self._parse_marketplace_plugin(item)
                for item in data.get("plugins", [])
            ]
        except httpx.HTTPError as e:
            import logging; logging.getLogger(__name__).error(f'Failed to list plugins: {e}')
            return []
    
    async def search_plugins(
        self,
        query: str,
        page: int = 1,
        page_size: int = 20,
    ) -> List[MarketplacePlugin]:
        """
        搜索插件。
        
        Args:
            query: 搜索关键词
            page: 页码
            page_size: 每页数量
            
        Returns:
            搜索结果
        """
        client = await self._get_client()
        
        params = {
            "q": query,
            "page": page,
            "page_size": page_size,
        }
        
        try:
            response = await client.get("/api/v1/plugins/search", params=params)
            response.raise_for_status()
            data = response.json()
            
            return [
                self._parse_marketplace_plugin(item)
                for item in data.get("results", [])
            ]
        except httpx.HTTPError as e:
            import logging; logging.getLogger(__name__).error(f'Failed to search plugins: {e}')
            return []
    
    async def get_plugin(self, plugin_id: str) -> Optional[MarketplacePlugin]:
        """
        获取插件详情。
        
        Args:
            plugin_id: 插件 ID
            
        Returns:
            插件信息或 None
        """
        client = await self._get_client()
        
        try:
            response = await client.get(f"/api/v1/plugins/{plugin_id}")
            response.raise_for_status()
            data = response.json()
            
            return self._parse_marketplace_plugin(data)
        except httpx.HTTPError:
            return None
    
    async def download_plugin(
        self,
        plugin_id: str,
        target_dir: Path,
    ) -> Optional[Path]:
        """
        下载插件到本地。
        
        Args:
            plugin_id: 插件 ID
            target_dir: 目标目录
            
        Returns:
            下载的文件路径或 None
        """
        client = await self._get_client()
        
        # 获取插件信息
        plugin_info = await self.get_plugin(plugin_id)
        if not plugin_info:
            return None
        
        try:
            # 下载文件
            response = await client.get(plugin_info.download_url)
            response.raise_for_status()
            content = response.content
            
            # 验证校验和
            checksum = hashlib.sha256(content).hexdigest()
            if checksum != plugin_info.checksum:
                import logging; logging.getLogger(__name__).warning(f'Checksum mismatch for plugin {plugin_id}')
                return None
            
            # 保存文件
            target_dir.mkdir(parents=True, exist_ok=True)
            target_path = target_dir / f"{plugin_id}.tar.gz"
            
            with open(target_path, "wb") as f:
                f.write(content)
            
            return target_path
            
        except httpx.HTTPError as e:
            import logging; logging.getLogger(__name__).error(f'Failed to download plugin: {e}')
            return None
    
    async def get_reviews(
        self,
        plugin_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> List[PluginReview]:
        """
        获取插件评价。
        
        Args:
            plugin_id: 插件 ID
            page: 页码
            page_size: 每页数量
            
        Returns:
            评价列表
        """
        client = await self._get_client()
        
        params = {
            "plugin_id": plugin_id,
            "page": page,
            "page_size": page_size,
        }
        
        try:
            response = await client.get("/api/v1/reviews", params=params)
            response.raise_for_status()
            data = response.json()
            
            return [
                self._parse_review(item)
                for item in data.get("reviews", [])
            ]
        except httpx.HTTPError:
            return []
    
    async def submit_review(
        self,
        plugin_id: str,
        user_id: str,
        rating: int,
        title: str,
        content: str,
    ) -> bool:
        """
        提交插件评价。
        
        Args:
            plugin_id: 插件 ID
            user_id: 用户 ID
            rating: 评分 (1-5)
            title: 评价标题
            content: 评价内容
            
        Returns:
            是否成功提交
        """
        client = await self._get_client()
        
        payload = {
            "plugin_id": plugin_id,
            "user_id": user_id,
            "rating": rating,
            "title": title,
            "content": content,
        }
        
        try:
            response = await client.post("/api/v1/reviews", json=payload)
            response.raise_for_status()
            return True
        except httpx.HTTPError:
            return False
    
    def _parse_marketplace_plugin(
        self,
        data: Dict[str, Any],
    ) -> MarketplacePlugin:
        """解析市场插件数据"""
        # 解析依赖
        dependencies = []
        for dep in data.get("dependencies", []):
            from .plugin_base import PluginDependency
            dependencies.append(PluginDependency(
                plugin_id=dep["id"],
                version_spec=dep.get("version", "*"),
                optional=dep.get("optional", False),
            ))
        
        metadata = PluginMetadata(
            id=data["id"],
            name=data.get("name", data["id"]),
            version=data["version"],
            description=data.get("description", ""),
            author=data.get("author", ""),
            homepage=data.get("homepage", ""),
            license=data.get("license", ""),
            dependencies=dependencies,
            permissions=data.get("permissions", []),
            config_schema=data.get("config_schema"),
            min_agent_version=data.get("min_agent_version", "1.0.0"),
            tags=data.get("tags", []),
        )
        
        return MarketplacePlugin(
            metadata=metadata,
            download_url=data.get("download_url", ""),
            checksum=data.get("checksum", ""),
            rating=data.get("rating", 0.0),
            review_count=data.get("review_count", 0),
            downloads=data.get("downloads", 0),
            verified=data.get("verified", False),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )
    
    def _parse_review(self, data: Dict[str, Any]) -> PluginReview:
        """解析评价数据"""
        return PluginReview(
            id=data["id"],
            plugin_id=data["plugin_id"],
            user_id=data["user_id"],
            rating=data["rating"],
            title=data["title"],
            content=data["content"],
            created_at=data["created_at"],
        )


class PluginInstaller:
    """
    插件安装器。
    
    负责插件的安装、更新、卸载操作。
    """
    
    def __init__(self, plugins_dir: Path):
        """
        初始化安装器。
        
        Args:
            plugins_dir: 插件安装目录
        """
        self.plugins_dir = plugins_dir
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
    
    async def install(
        self,
        source: Path,
        plugin_id: Optional[str] = None,
    ) -> InstallationResult:
        """
        安装插件。
        
        Args:
            source: 插件包路径（.tar.gz 或包含 plugin.yaml 的目录）
            plugin_id: 指定的插件 ID（用于覆盖）
            
        Returns:
            安装结果
        """
        try:
            # 解压插件包
            import tarfile
            
            if source.is_file() and source.suffix == ".tar.gz":
                # 解压 tar.gz
                with tempfile.TemporaryDirectory() as tmp_dir:
                    tmp_path = Path(tmp_dir)
                    
                    with tarfile.open(source, "r:gz") as tar:
                        tar.extractall(tmp_path)
                    
                    # 查找 plugin.yaml
                    plugin_dir = self._find_plugin_dir(tmp_path)
                    if not plugin_dir:
                        return InstallationResult(
                            success=False,
                            plugin_id=plugin_id or "unknown",
                            error="No plugin.yaml found in archive",
                        )
                    
                    return await self._install_from_dir(plugin_dir, plugin_id)
            
            elif source.is_dir():
                return await self._install_from_dir(source, plugin_id)
            
            else:
                return InstallationResult(
                    success=False,
                    plugin_id=plugin_id or "unknown",
                    error=f"Invalid source: {source}",
                )
                
        except Exception as e:
            return InstallationResult(
                success=False,
                plugin_id=plugin_id or "unknown",
                error=str(e),
            )
    
    async def update(
        self,
        plugin_id: str,
        new_source: Path,
    ) -> InstallationResult:
        """
        更新插件。
        
        Args:
            plugin_id: 插件 ID
            new_source: 新版本插件包路径
            
        Returns:
            更新结果
        """
        # 先卸载旧版本
        uninstall_result = await self.uninstall(plugin_id)
        if not uninstall_result.success:
            return uninstall_result
        
        # 安装新版本
        return await self.install(new_source, plugin_id)
    
    async def uninstall(self, plugin_id: str) -> InstallationResult:
        """
        卸载插件。
        
        Args:
            plugin_id: 插件 ID
            
        Returns:
            卸载结果
        """
        plugin_dir = self.plugins_dir / plugin_id
        
        if not plugin_dir.exists():
            return InstallationResult(
                success=False,
                plugin_id=plugin_id,
                error=f"Plugin not found: {plugin_id}",
            )
        
        try:
            # 递归删除
            import shutil
            shutil.rmtree(plugin_dir)
            
            return InstallationResult(
                success=True,
                plugin_id=plugin_id,
                install_path=plugin_dir,
            )
            
        except Exception as e:
            return InstallationResult(
                success=False,
                plugin_id=plugin_id,
                error=str(e),
            )
    
    def list_installed(self) -> List[str]:
        """
        列出已安装的插件。
        
        Returns:
            插件 ID 列表
        """
        if not self.plugins_dir.exists():
            return []
        
        return [
            d.name for d in self.plugins_dir.iterdir()
            if d.is_dir() and (d / "plugin.yaml").exists()
        ]
    
    async def _install_from_dir(
        self,
        source_dir: Path,
        override_id: Optional[str] = None,
    ) -> InstallationResult:
        """从目录安装插件"""
        yaml_path = source_dir / "plugin.yaml"
        if not yaml_path.exists():
            return InstallationResult(
                success=False,
                plugin_id=override_id or "unknown",
                error="No plugin.yaml found",
            )
        
        # 解析元数据
        import yaml
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        plugin_id = override_id or data.get("id")
        if not plugin_id:
            return InstallationResult(
                success=False,
                plugin_id="unknown",
                error="No plugin ID found",
            )
        
        # 创建目标目录
        target_dir = self.plugins_dir / plugin_id
        target_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # 复制文件
            import shutil
            
            for item in source_dir.iterdir():
                if item.name == "__pycache__":
                    continue
                dest = target_dir / item.name
                if item.is_dir():
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)
            
            return InstallationResult(
                success=True,
                plugin_id=plugin_id,
                install_path=target_dir,
            )
            
        except Exception as e:
            # 清理失败的文件
            import shutil
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)
            
            return InstallationResult(
                success=False,
                plugin_id=plugin_id,
                error=str(e),
            )
    
    def _find_plugin_dir(self, base_dir: Path) -> Optional[Path]:
        """查找包含 plugin.yaml 的目录"""
        for item in base_dir.iterdir():
            if item.is_dir() and (item / "plugin.yaml").exists():
                return item
            # 也有可能在根目录
        if (base_dir / "plugin.yaml").exists():
            return base_dir
        return None
