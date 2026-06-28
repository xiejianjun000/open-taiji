# -*- coding: utf-8 -*-
"""
排放数据查询插件。

提供企业排放数据、污染物排放清单的查询功能。
支持按时间、地域、行业等维度统计。
"""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..plugin_base import (
    Plugin, PluginMetadata, PluginContext, PluginHealth,
    ToolDefinition, HookRegistration
)
from ..hooks import SystemEvents


class EmissionPlugin(Plugin):
    """
    排放数据查询插件。
    
    提供以下功能：
    - 企业排放数据查询
    - 污染物排放清单统计
    - 排放趋势分析
    - 超标预警
    """
    
    # 插件元数据
    METADATA = PluginMetadata(
        id="emission-data",
        name="排放数据查询",
        version="1.0.0",
        description="污染物排放数据查询与分析插件",
        author="Taiji Team",
        homepage="https://taiji-agent.example.com/plugins/emission",
        license="MIT",
        tags=["排放", "污染物", "监测", "环保"],
        min_agent_version="1.0.0",
        dependencies=[],
        config_schema={
            "type": "object",
            "properties": {
                "data_source": {
                    "type": "string",
                    "description": "数据来源配置"
                },
                "threshold_warning": {
                    "type": "number",
                    "default": 0.8,
                    "description": "预警阈值比例"
                },
                "cache_ttl": {
                    "type": "integer",
                    "default": 300,
                    "description": "缓存有效期（秒）"
                }
            }
        }
    )
    
    def __init__(self, metadata: Optional[PluginMetadata] = None):
        """初始化插件"""
        super().__init__(metadata or self.METADATA)
        self._emission_data: Dict[str, Any] = {}
        self._companies: Dict[str, Any] = {}
        self._initialized = False
    
    async def activate(self, ctx: PluginContext) -> None:
        """
        激活插件。
        
        初始化排放数据库，注册工具和钩子。
        """
        self.context = ctx
        
        ctx.logger.info("Activating EmissionPlugin...")
        
        # 注册工具
        self.tools = [
            ToolDefinition(
                name="query_emission",
                description="查询企业排放数据",
                parameters={
                    "type": "object",
                    "properties": {
                        "company_id": {
                            "type": "string",
                            "description": "企业ID"
                        },
                        "pollutant": {
                            "type": "string",
                            "description": "污染物类型 (SO2/NOx/颗粒物/VOCs等)"
                        },
                        "start_date": {
                            "type": "string",
                            "description": "开始日期 YYYY-MM-DD"
                        },
                        "end_date": {
                            "type": "string",
                            "description": "结束日期 YYYY-MM-DD"
                        }
                    },
                    "required": ["company_id"]
                }
            ),
            ToolDefinition(
                name="get_emission_stats",
                description="获取排放统计数据",
                parameters={
                    "type": "object",
                    "properties": {
                        "region": {
                            "type": "string",
                            "description": "区域"
                        },
                        "industry": {
                            "type": "string",
                            "description": "行业"
                        },
                        "year": {
                            "type": "integer",
                            "description": "年份"
                        }
                    }
                }
            ),
            ToolDefinition(
                name="check_emission_alerts",
                description="检查排放超标预警",
                parameters={
                    "type": "object",
                    "properties": {
                        "company_id": {
                            "type": "string",
                            "description": "企业ID"
                        }
                    },
                    "required": ["company_id"]
                }
            ),
            ToolDefinition(
                name="list_pollutants",
                description="列出污染物类型",
                parameters={
                    "type": "object",
                    "properties": {}
                }
            ),
        ]
        
        # 注册钩子
        self.hooks = [
            HookRegistration(
                event=SystemEvents.EMISSION_DATA_QUERY,
                handler=self._handle_emission_query,
                priority=50,
            )
        ]
        
        # 初始化数据
        await self._load_sample_data()
        
        ctx.logger.info("EmissionPlugin activated successfully")
    
    async def deactivate(self) -> None:
        """停用插件"""
        if self.context:
            self.context.logger.info("Deactivating EmissionPlugin...")
        
        self._emission_data.clear()
        self._companies.clear()
        self._initialized = False
        
        if self.context:
            self.context.logger.info("EmissionPlugin deactivated")
    
    async def health_check(self) -> PluginHealth:
        """健康检查"""
        if not self._initialized:
            return PluginHealth.DEGRADED
        return PluginHealth.HEALTHY
    
    async def get_metrics(self) -> Dict[str, Any]:
        """获取插件指标"""
        return {
            "emission.total_companies": len(self._companies),
            "emission.total_records": len(self._emission_data),
            "emission.alerts": sum(
                1 for d in self._emission_data.values()
                if d.get("exceeded", False)
            )
        }
    
    async def _load_sample_data(self) -> None:
        """加载示例数据"""
        # 示例企业数据
        self._companies = {
            "comp-001": {
                "id": "comp-001",
                "name": "某某发电有限公司",
                "region": "华东地区",
                "province": "江苏省",
                "city": "南京市",
                "industry": "电力行业",
                "capacity": "2x600MW",
                "installed_date": "2010-06-15"
            },
            "comp-002": {
                "id": "comp-002",
                "name": "某某钢铁集团有限公司",
                "region": "华北地区",
                "province": "河北省",
                "city": "唐山市",
                "industry": "钢铁行业",
                "capacity": "年产钢800万吨",
                "installed_date": "2008-03-20"
            },
            "comp-003": {
                "id": "comp-003",
                "name": "某某化工股份有限公司",
                "region": "华东地区",
                "province": "浙江省",
                "city": "宁波市",
                "industry": "化工行业",
                "capacity": "年产乙烯50万吨",
                "installed_date": "2015-09-01"
            }
        }
        
        # 示例排放数据
        self._emission_data = {
            "record-001": {
                "id": "record-001",
                "company_id": "comp-001",
                "date": "2024-01-15",
                "pollutant": "SO2",
                "emission_amount": 12.5,
                "standard_limit": 50.0,
                "exceeded": False,
                "compliance_rate": 100.0
            },
            "record-002": {
                "id": "record-002",
                "company_id": "comp-001",
                "date": "2024-01-15",
                "pollutant": "NOx",
                "emission_amount": 45.0,
                "standard_limit": 100.0,
                "exceeded": False,
                "compliance_rate": 100.0
            },
            "record-003": {
                "id": "record-003",
                "company_id": "comp-002",
                "date": "2024-01-15",
                "pollutant": "颗粒物",
                "emission_amount": 35.0,
                "standard_limit": 30.0,
                "exceeded": True,
                "compliance_rate": 85.0
            },
            "record-004": {
                "id": "record-004",
                "company_id": "comp-003",
                "date": "2024-01-15",
                "pollutant": "VOCs",
                "emission_amount": 8.2,
                "standard_limit": 20.0,
                "exceeded": False,
                "compliance_rate": 100.0
            }
        }
        
        self._initialized = True
    
    async def _handle_emission_query(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """处理排放数据查询事件"""
        query_type = data.get("type")
        
        if query_type == "query":
            company_id = data.get("company_id")
            result = await self._query_emission(company_id, data.get("pollutant"))
            return {"data": result}
        
        return data
    
    async def _query_emission(
        self,
        company_id: str,
        pollutant: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        查询排放数据。
        
        Args:
            company_id: 企业ID
            pollutant: 污染物类型
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            排放数据列表
        """
        results = []
        
        for record in self._emission_data.values():
            if record.get("company_id") != company_id:
                continue
            
            if pollutant and record.get("pollutant") != pollutant:
                continue
            
            if start_date and record.get("date", "") < start_date:
                continue
            
            if end_date and record.get("date", "") > end_date:
                continue
            
            results.append(record)
        
        return results
    
    def _get_company(self, company_id: str) -> Optional[Dict[str, Any]]:
        """获取企业信息"""
        return self._companies.get(company_id)
    
    def _get_pollutants(self) -> List[str]:
        """获取污染物类型列表"""
        pollutants = set()
        for record in self._emission_data.values():
            if record.get("pollutant"):
                pollutants.add(record["pollutant"])
        return sorted(pollutants)
    
    def _check_alerts(self, company_id: str) -> List[Dict[str, Any]]:
        """检查企业是否有超标预警"""
        alerts = []
        threshold = self.get_config("threshold_warning", 0.8)
        
        for record in self._emission_data.values():
            if record.get("company_id") != company_id:
                continue
            
            if record.get("exceeded", False):
                alerts.append({
                    "severity": "high",
                    "pollutant": record.get("pollutant"),
                    "message": f"{record.get('pollutant')}排放超标",
                    "emission": record.get("emission_amount"),
                    "limit": record.get("standard_limit")
                })
            else:
                # 检查是否接近限值
                ratio = record.get("emission_amount", 0) / record.get("standard_limit", 1)
                if ratio >= threshold:
                    alerts.append({
                        "severity": "warning",
                        "pollutant": record.get("pollutant"),
                        "message": f"{record.get('pollutant')}排放接近限值",
                        "emission": record.get("emission_amount"),
                        "limit": record.get("standard_limit"),
                        "ratio": round(ratio, 2)
                    })
        
        return alerts
    
    # 公开的工具方法
    async def query_emission(
        self,
        company_id: str,
        pollutant: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        查询企业排放数据。
        
        Args:
            company_id: 企业ID
            pollutant: 污染物类型
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            查询结果
        """
        # 获取企业信息
        company = self._get_company(company_id)
        if not company:
            return {
                "success": False,
                "error": f"Company not found: {company_id}"
            }
        
        records = await self._query_emission(company_id, pollutant, start_date, end_date)
        
        return {
            "success": True,
            "company": company,
            "count": len(records),
            "records": records
        }
    
    async def get_emission_stats(
        self,
        region: Optional[str] = None,
        industry: Optional[str] = None,
        year: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        获取排放统计数据。
        
        Args:
            region: 区域
            industry: 行业
            year: 年份
            
        Returns:
            统计结果
        """
        # 筛选企业
        companies = list(self._companies.values())
        if region:
            companies = [c for c in companies if c.get("region") == region]
        if industry:
            companies = [c for c in companies if c.get("industry") == industry]
        
        company_ids = {c["id"] for c in companies}
        
        # 统计排放数据
        total_emission = {}
        exceeded_count = 0
        
        for record in self._emission_data.values():
            if record.get("company_id") not in company_ids:
                continue
            
            pollutant = record.get("pollutant", "unknown")
            if pollutant not in total_emission:
                total_emission[pollutant] = 0.0
            total_emission[pollutant] += record.get("emission_amount", 0)
            
            if record.get("exceeded", False):
                exceeded_count += 1
        
        return {
            "success": True,
            "filters": {
                "region": region,
                "industry": industry,
                "year": year
            },
            "total_companies": len(companies),
            "total_emission": total_emission,
            "exceeded_count": exceeded_count
        }
    
    async def check_emission_alerts(self, company_id: str) -> Dict[str, Any]:
        """
        检查排放超标预警。
        
        Args:
            company_id: 企业ID
            
        Returns:
            预警信息
        """
        alerts = self._check_alerts(company_id)
        
        return {
            "success": True,
            "company_id": company_id,
            "alert_count": len(alerts),
            "alerts": alerts
        }
    
    async def list_pollutants(self) -> Dict[str, Any]:
        """
        列出污染物类型。
        
        Returns:
            污染物列表
        """
        pollutants = self._get_pollutants()
        
        # 标准污染物分类
        standard_pollutants = {
            "SO2": "二氧化硫",
            "NOx": "氮氧化物",
            "颗粒物": "颗粒物/粉尘",
            "VOCs": "挥发性有机物",
            "CO": "一氧化碳",
            "O3": "臭氧"
        }
        
        return {
            "success": True,
            "pollutants": [
                {
                    "code": p,
                    "name": standard_pollutants.get(p, p)
                }
                for p in pollutants
            ]
        }
