# -*- coding: utf-8 -*-
"""
环保法规检索插件。

提供环保法规、标准的检索和查询功能。
支持按关键词、分类、时间范围等条件检索。
"""

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..plugin_base import (
    Plugin, PluginMetadata, PluginContext, PluginHealth,
    ToolDefinition, HookRegistration
)
from ..hooks import SystemEvents


class EcoLawPlugin(Plugin):
    """
    环保法规检索插件。
    
    提供以下功能：
    - 法规全文检索
    - 法规分类浏览
    - 法规详情查询
    - 相关法规推荐
    """
    
    # 插件元数据
    METADATA = PluginMetadata(
        id="eco-law",
        name="环保法规检索",
        version="1.0.0",
        description="生态环境法规检索插件，支持国家/地方政策法规查询",
        author="Taiji Team",
        homepage="https://taiji-agent.example.com/plugins/eco-law",
        license="MIT",
        tags=["环保", "法规", "合规"],
        min_agent_version="1.0.0",
        dependencies=[],
        config_schema={
            "type": "object",
            "properties": {
                "data_dir": {
                    "type": "string",
                    "description": "法规数据目录"
                },
                "cache_enabled": {
                    "type": "boolean",
                    "default": True,
                    "description": "是否启用缓存"
                },
                "max_results": {
                    "type": "integer",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 100,
                    "description": "最大返回结果数"
                }
            }
        }
    )
    
    def __init__(self, metadata: Optional[PluginMetadata] = None):
        """初始化插件"""
        super().__init__(metadata or self.METADATA)
        self._law_database: Dict[str, Any] = {}
        self._initialized = False
    
    async def activate(self, ctx: PluginContext) -> None:
        """
        激活插件。
        
        初始化法规数据库，注册工具和钩子。
        """
        self.context = ctx
        
        ctx.logger.info("Activating EcoLawPlugin...")
        
        # 注册工具
        self.tools = [
            ToolDefinition(
                name="search_laws",
                description="搜索环保法规",
                parameters={
                    "type": "object",
                    "properties": {
                        "keyword": {
                            "type": "string",
                            "description": "搜索关键词"
                        },
                        "category": {
                            "type": "string",
                            "enum": ["国家法律", "行政法规", "部门规章", "地方性法规", "标准规范"],
                            "description": "法规分类"
                        },
                        "year": {
                            "type": "integer",
                            "description": "发布年份"
                        }
                    },
                    "required": ["keyword"]
                }
            ),
            ToolDefinition(
                name="get_law_detail",
                description="获取法规详细信息",
                parameters={
                    "type": "object",
                    "properties": {
                        "law_id": {
                            "type": "string",
                            "description": "法规 ID"
                        }
                    },
                    "required": ["law_id"]
                }
            ),
            ToolDefinition(
                name="list_law_categories",
                description="列出法规分类",
                parameters={
                    "type": "object",
                    "properties": {}
                }
            ),
        ]
        
        # 注册钩子
        self.hooks = [
            HookRegistration(
                event=SystemEvents.ECO_LAW_QUERY,
                handler=self._handle_law_query,
                priority=50,
            )
        ]
        
        # 初始化数据库
        await self._load_law_database()
        
        ctx.logger.info("EcoLawPlugin activated successfully")
    
    async def deactivate(self) -> None:
        """停用插件"""
        if self.context:
            self.context.logger.info("Deactivating EcoLawPlugin...")
        
        # 清理资源
        self._law_database.clear()
        self._initialized = False
        
        if self.context:
            self.context.logger.info("EcoLawPlugin deactivated")
    
    async def health_check(self) -> PluginHealth:
        """健康检查"""
        if not self._initialized:
            return PluginHealth.DEGRADED
        return PluginHealth.HEALTHY
    
    async def get_metrics(self) -> Dict[str, Any]:
        """获取插件指标"""
        return {
            "eco_law.total_laws": len(self._law_database),
            "eco_law.categories": len(set(
                law.get("category") for law in self._law_database.values()
            )),
        }
    
    async def _load_law_database(self) -> None:
        """加载法规数据库"""
        # 示例：初始化一些环保法规数据
        # 实际应用中会从文件或API加载
        self._law_database = {
            "law-001": {
                "id": "law-001",
                "title": "中华人民共和国环境保护法",
                "category": "国家法律",
                "department": "全国人大常委会",
                "issue_date": "2014-04-24",
                "effective_date": "2015-01-01",
                "summary": "环境保护法是环境保护领域的基本法律，确立了保护优先、预防为主、综合治理、公众参与、损害担责的基本原则。",
                "keywords": ["环境保护", "基本法", "污染防治", "生态保护"],
                "status": "有效"
            },
            "law-002": {
                "id": "law-002",
                "title": "中华人民共和国大气污染防治法",
                "category": "国家法律",
                "department": "全国人大常委会",
                "issue_date": "2015-08-29",
                "effective_date": "2016-01-01",
                "summary": "大气污染防治法规定了大气污染物排放控制、机动车船污染防治、扬尘污染防治等内容。",
                "keywords": ["大气污染", "排放控制", "空气质量"],
                "status": "有效"
            },
            "law-003": {
                "id": "law-003",
                "title": "中华人民共和国水污染防治法",
                "category": "国家法律",
                "department": "全国人大常委会",
                "issue_date": "2017-06-27",
                "effective_date": "2018-01-01",
                "summary": "水污染防治法对水污染防治的监督管理、防治措施、饮用水水源保护等内容作出了规定。",
                "keywords": ["水污染", "水环境", "饮用水保护"],
                "status": "有效"
            },
            "law-004": {
                "id": "law-004",
                "title": "建设项目环境保护管理条例",
                "category": "行政法规",
                "department": "国务院",
                "issue_date": "2017-07-16",
                "effective_date": "2017-10-01",
                "summary": "规范建设项目的环境保护管理，明确环评制度、三同时制度等要求。",
                "keywords": ["建设项目", "环评", "三同时"],
                "status": "有效"
            },
            "law-005": {
                "id": "law-005",
                "title": "排污许可管理条例",
                "category": "行政法规",
                "department": "国务院",
                "issue_date": "2020-12-09",
                "effective_date": "2021-03-01",
                "summary": "对排污许可管理作出全面规定，实行排污许可分类管理。",
                "keywords": ["排污许可", "排污许可分类管理"],
                "status": "有效"
            }
        }
        
        self._initialized = True
    
    async def _handle_law_query(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """处理法规查询事件"""
        query_type = data.get("type")
        
        if query_type == "search":
            keyword = data.get("keyword", "")
            results = self._search_laws(keyword)
            return {"data": results, "count": len(results)}
        
        return data
    
    def _search_laws(
        self,
        keyword: str,
        category: Optional[str] = None,
        year: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        搜索法规。
        
        Args:
            keyword: 搜索关键词
            category: 法规分类
            year: 发布年份
            
        Returns:
            匹配的法规列表
        """
        results = []
        max_results = self.get_config("max_results", 20)
        
        keyword_lower = keyword.lower()
        
        for law in self._law_database.values():
            # 检查关键词匹配
            matched = False
            if keyword_lower in law.get("title", "").lower():
                matched = True
            elif any(keyword_lower in k.lower() for k in law.get("keywords", [])):
                matched = True
            elif keyword_lower in law.get("summary", "").lower():
                matched = True
            
            if not matched:
                continue
            
            # 检查分类
            if category and law.get("category") != category:
                continue
            
            # 检查年份
            if year:
                law_year = int(law.get("issue_date", "0")[:4]) if law.get("issue_date") else 0
                if law_year != year:
                    continue
            
            results.append(law)
            
            if len(results) >= max_results:
                break
        
        return results
    
    def _get_law_detail(self, law_id: str) -> Optional[Dict[str, Any]]:
        """
        获取法规详情。
        
        Args:
            law_id: 法规 ID
            
        Returns:
            法规详情或 None
        """
        return self._law_database.get(law_id)
    
    def _list_categories(self) -> List[str]:
        """
        列出法规分类。
        
        Returns:
            分类列表
        """
        categories = set()
        for law in self._law_database.values():
            if law.get("category"):
                categories.add(law["category"])
        return sorted(categories)
    
    # 公开的工具方法
    async def search_laws(
        self,
        keyword: str,
        category: Optional[str] = None,
        year: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        搜索环保法规。
        
        Args:
            keyword: 搜索关键词
            category: 法规分类
            year: 发布年份
            
        Returns:
            搜索结果
        """
        results = self._search_laws(keyword, category, year)
        return {
            "success": True,
            "count": len(results),
            "results": results
        }
    
    async def get_law_detail(self, law_id: str) -> Dict[str, Any]:
        """
        获取法规详细信息。
        
        Args:
            law_id: 法规 ID
            
        Returns:
            法规详情
        """
        law = self._get_law_detail(law_id)
        if law:
            return {"success": True, "data": law}
        return {
            "success": False,
            "error": f"Law not found: {law_id}"
        }
    
    async def list_law_categories(self) -> Dict[str, Any]:
        """
        列出法规分类。
        
        Returns:
            分类列表
        """
        categories = self._list_categories()
        return {
            "success": True,
            "categories": categories
        }

    async def query_wps_knowledge_base(
        self,
        keyword: str,
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        查询 WPS 生态环境知识库（通过 MCP mcporter）。

        知识库包含 22 份核心文档，涵盖：
        - 生态环境保护法律法规汇编（2026.5）
        - 生态环境法典含新旧对照
        - 国家生态环境标准目录汇编（2026.4）
        - 建设项目环评审批原则汇编（2026.4）
        - 生态环境监测技术规范清单（2026.3）
        - 各类行业排放标准及执法指引

        Args:
            keyword: 搜索关键词
            category: 知识分类（法律法规/标准规范/环评管理/执法监管/监测技术/企业管理）

        Returns:
            匹配的知识库文件列表
        """
        import json
        import subprocess

        index_path = Path(__file__).parent.parent.parent.parent.parent / "data" / "knowledge" / "eco_environment" / "index.json"

        try:
            if index_path.exists():
                with open(index_path, "r", encoding="utf-8") as f:
                    kb_index = json.load(f)
            else:
                # Fallback to embedded index
                kb_index = self._get_embedded_kb_index()

            results = []
            keyword_lower = keyword.lower() if keyword else ""

            for cat_name, files in kb_index.get("categories", {}).items():
                if category and cat_name != category:
                    continue
                for f in files:
                    if keyword_lower and keyword_lower not in f["name"].lower():
                        continue
                    results.append({
                        "name": f["name"],
                        "category": cat_name,
                        "size_mb": f["size_mb"],
                        "format": f["format"],
                        "kuid": f["kuid"],
                        "wps_url": f"https://www.kdocs.cn/wiki/l/{f['kuid']}",
                    })

            return {
                "success": True,
                "source": "WPS 生态环境知识库",
                "total_files": kb_index.get("total_files", 0),
                "matched": len(results),
                "results": results,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def _get_embedded_kb_index(self) -> dict:
        """返回内嵌的知识库索引（离线备用）"""
        return {
            "version": "2026.5",
            "name": "生态环境知识库",
            "total_files": 22,
            "categories": {
                "法律法规": [
                    {"name": "生态环境保护法律法规汇编（2026.5）", "kuid": "0lcilV7Cn4Ovdw", "size_mb": 32.8},
                    {"name": "中华人民共和国生态环境法典含新旧对照", "kuid": "0lcjIgK6W1YJIU", "size_mb": 4.2},
                    {"name": "生态环境部复函汇编（2026.3）", "kuid": "0lcoVqctezlpK4", "size_mb": 37.2},
                    {"name": "生态环境部部长信箱回复汇编（2026.1）", "kuid": "0lcn0h9Q1pbWn0", "size_mb": 11.8},
                    {"name": "生态环境保护标准修改单汇编（2026.3）", "kuid": "0lcsCzWOjy2alo", "size_mb": 23.0},
                ],
                "标准规范": [
                    {"name": "国家生态环境标准目录汇编（2026.4）", "kuid": "0lcaQ7cEfsFDt8", "size_mb": 29.6},
                    {"name": "大气污染物综合排放标准详解", "kuid": "0lcpGObxglL9cp", "size_mb": 12.4},
                    {"name": "各行业排气筒高度及烟气基准含氧量要求（2026.4）", "kuid": "0lcnHKy7T1u6Y0", "size_mb": 11.6},
                    {"name": "各类环境管控物质名录汇编（2026.2）", "kuid": "0lcmS3UGqsWR4v", "size_mb": 25.2},
                    {"name": "生态环境监测技术规范清单（2026.3）", "kuid": "0lcdg2Vzao6w3b", "size_mb": 24.4},
                ],
                "环评管理": [
                    {"name": "建设项目环评文件审批原则汇编（2026.4）", "kuid": "0lcrsZIkLqZzkJ", "size_mb": 26.8},
                    {"name": "建设项目重大变动清单汇编（2025.8）", "kuid": "0lcizhNLBGhvW9", "size_mb": 0.4},
                    {"name": "环保合同管理服务技术手册及案例汇编", "kuid": "0lccSzVrdflrH7", "size_mb": 27.4},
                ],
                "执法监管": [
                    {"name": "湖南省生态环境行政处罚文书范本（2024）", "kuid": "0lcvh3crXpbpoK", "size_mb": 5.6},
                    {"name": "广东省工业污染源达标排放执法指引", "kuid": "0lcku4eUmJv28t", "size_mb": 13.5},
                    {"name": "排污单位自行监测法律法规汇编", "kuid": "0lcge7miiguzRp", "size_mb": 0.7},
                ],
                "监测技术": [
                    {"name": "土壤环境监测分析方法", "kuid": "0lcn3ah3P3FuHB", "size_mb": 254.1},
                    {"name": "环境监测（第六版，奚旦立）", "kuid": "0lcgOawPH5Q1K0", "size_mb": 170.8},
                    {"name": "生态环境监测机构资质认定评审案例解析", "kuid": "0lcnmOb8gxl5lW", "size_mb": 20.3},
                ],
                "企业管理": [
                    {"name": "固定污染源企业环境保护规范化管理手册", "kuid": "0lcoknCXYcmriT", "size_mb": 26.8},
                ],
            },
        }
