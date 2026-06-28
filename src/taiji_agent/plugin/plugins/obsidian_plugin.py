"""
Obsidian 知识库同步插件。

通过 Obsidian Local REST API 实现：
- 读取 Obsidian 笔记
- 写入/更新笔记
- 搜索笔记内容
- 与 WPS 知识库双向同步
"""

import json
import logging
import urllib.request
import urllib.error
import ssl
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..plugin_base import (
    Plugin, PluginMetadata, PluginContext, PluginHealth,
    ToolDefinition, HookRegistration,
)

logger = logging.getLogger(__name__)


class ObsidianPlugin(Plugin):
    """Obsidian 知识库同步插件。"""

    METADATA = PluginMetadata(
        id="obsidian-sync",
        name="Obsidian 知识库同步",
        version="1.0.0",
        description="连接 Obsidian 本地知识库，支持笔记读写、搜索、与 WPS 知识库双向同步",
        author="Taiji Team",
        tags=["obsidian", "知识管理", "笔记", "双向同步"],
        config_schema={
            "type": "object",
            "properties": {
                "api_base_url": {
                    "type": "string",
                    "default": "https://127.0.0.1:27124",
                    "description": "Obsidian REST API 地址"
                },
                "api_key": {
                    "type": "string",
                    "description": "API 密钥"
                },
            }
        },
    )

    def __init__(self, metadata: Optional[PluginMetadata] = None):
        super().__init__(metadata or self.METADATA)
        self._base_url: str = "https://127.0.0.1:27124"
        self._api_key: str = ""
        self._ssl_context = ssl.create_default_context()
        self._ssl_context.check_hostname = False
        self._ssl_context.verify_mode = ssl.CERT_NONE

    def _auth_header(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    def _request(self, method: str, path: str, body: Optional[str] = None,
                 content_type: str = "text/markdown") -> Dict[str, Any]:
        """发送请求到 Obsidian REST API"""
        url = f"{self._base_url}{path}"
        headers = self._auth_header()
        if body is not None:
            headers["Content-Type"] = content_type

        data = body.encode("utf-8") if body else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, context=self._ssl_context, timeout=10) as resp:
                content = resp.read().decode("utf-8")
                # Strip HTML wrapper
                if content.startswith("\t\t\t"):
                    content = content.strip("\t\n")
                return {"success": True, "content": content}
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")[:500]
            return {"success": False, "error": f"HTTP {e.code}: {err_body}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def activate(self, ctx: PluginContext) -> None:
        self._api_key = ctx.config.get("api_key", "")
        self._base_url = ctx.config.get("api_base_url", "https://127.0.0.1:27124")

        # Test connection
        result = self._request("GET", "/vault/")
        if result["success"]:
            logger.info(f"Obsidian 连接成功，文件数: {len(result.get('content', '').split(chr(10)))}")
        else:
            logger.warning(f"Obsidian 连接失败: {result.get('error')}")
        self._initialized = True

    async def deactivate(self) -> None:
        self._initialized = False

    async def health_check(self) -> PluginHealth:
        result = self._request("GET", "/vault/")
        return PluginHealth(
            status="healthy" if result["success"] else "unhealthy",
            message="已连接" if result["success"] else result.get("error", "未知错误"),
        )

    # ============================================================
    # 核心操作
    # ============================================================

    async def list_notes(self, directory: str = "") -> Dict[str, Any]:
        """列出笔记文件"""
        path = f"/vault/{directory}/" if directory else "/vault/"
        result = self._request("GET", path)
        if result["success"]:
            content = result["content"]
            # Parse JSON response
            try:
                data = json.loads(content)
                files = data.get("files", [])
                return {"success": True, "files": files, "count": len(files)}
            except json.JSONDecodeError:
                return {"success": True, "files": [content], "count": 1}
        return result

    async def read_note(self, filename: str) -> Dict[str, Any]:
        """读取笔记内容"""
        encoded = urllib.parse.quote(filename, safe="")
        result = self._request("GET", f"/vault/{encoded}")
        return result

    async def write_note(self, filename: str, content: str) -> Dict[str, Any]:
        """创建或覆盖笔记"""
        encoded = urllib.parse.quote(filename, safe="")
        result = self._request("PUT", f"/vault/{encoded}", body=content)
        return result

    async def append_note(self, filename: str, content: str) -> Dict[str, Any]:
        """追加内容到笔记末尾"""
        existing = await self.read_note(filename)
        if existing["success"]:
            new_content = existing["content"].rstrip() + "\n\n" + content
            return await self.write_note(filename, new_content)
        return await self.write_note(filename, content)

    async def delete_note(self, filename: str) -> Dict[str, Any]:
        """删除笔记"""
        encoded = urllib.parse.quote(filename, safe="")
        result = self._request("DELETE", f"/vault/{encoded}")
        return result

    async def search_notes(self, keyword: str) -> Dict[str, Any]:
        """在所有笔记中搜索关键词"""
        list_result = await self.list_notes()
        if not list_result["success"]:
            return list_result

        results = []
        for filename in list_result.get("files", []):
            note = await self.read_note(filename)
            if note["success"] and keyword.lower() in note["content"].lower():
                # Extract context snippet
                content = note["content"]
                idx = content.lower().find(keyword.lower())
                start = max(0, idx - 60)
                end = min(len(content), idx + len(keyword) + 60)
                snippet = content[start:end]
                results.append({
                    "filename": filename,
                    "snippet": f"...{snippet}...",
                })

        return {"success": True, "matched": len(results), "results": results}

    # ============================================================
    # 知识库同步
    # ============================================================

    async def sync_wps_to_obsidian(self, category: str = "") -> Dict[str, Any]:
        """
        将 WPS 生态环境知识库索引同步到 Obsidian。
        在 Obsidian 中创建"生态知识库"文件夹和分类笔记。
        """
        from .eco_law_plugin import EcoLawPlugin
        eco = EcoLawPlugin()
        kb_result = await eco.query_wps_knowledge_base("", category=category)

        if not kb_result.get("success"):
            return {"success": False, "error": "无法获取 WPS 知识库"}

        # Create index note in Obsidian
        lines = [
            "# 生态环境知识库",
            "",
            f"> 来源: WPS KnowledgeBase | 更新: 2026.5",
            f"> 总文档: {kb_result.get('total_files', 0)} 份 | {kb_result['source']}",
            "",
            "---",
            "",
        ]

        category_groups = {}
        for r in kb_result.get("results", []):
            cat = r["category"]
            if cat not in category_groups:
                category_groups[cat] = []
            category_groups[cat].append(r)

        for cat, items in category_groups.items():
            lines.append(f"## {cat}")
            lines.append("")
            for item in items:
                name = item["name"]
                url = item.get("wps_url", "")
                size = item.get("size_mb", 0)
                lines.append(f"- [{name}]({url}) ({size:.0f}MB)")
            lines.append("")

        content = "\n".join(lines)
        result = await self.write_note("生态知识库/索引.md", content)
        return result

    async def sync_obsidian_to_knowledge(self, directory: str = "") -> Dict[str, Any]:
        """
        将 Obsidian 笔记导出为知识库摘要。
        """
        list_result = await self.list_notes(directory)
        if not list_result["success"]:
            return list_result

        summaries = []
        for filename in list_result.get("files", []):
            if filename.startswith(".") or not filename.endswith(".md"):
                continue
            note = await self.read_note(f"{directory}/{filename}" if directory else filename)
            if note["success"]:
                content = note["content"]
                # Extract first heading as title
                first_line = content.strip().split("\n")[0] if content else filename
                summaries.append({
                    "filename": filename,
                    "title": first_line.lstrip("# "),
                    "size_chars": len(content),
                })

        return {"success": True, "notes": summaries, "count": len(summaries)}


# 插件注册入口
def create_plugin() -> ObsidianPlugin:
    return ObsidianPlugin()
