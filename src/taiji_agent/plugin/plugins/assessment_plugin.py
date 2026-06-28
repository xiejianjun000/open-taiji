# -*- coding: utf-8 -*-
"""
环评报告辅助插件。

提供环境影响评价报告的辅助生成和审查功能。
支持报告模板、章节生成、合规检查等。
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..plugin_base import (
    Plugin, PluginMetadata, PluginContext, PluginHealth,
    ToolDefinition, HookRegistration
)
from ..hooks import SystemEvents


class AssessmentPlugin(Plugin):
    """
    环评报告辅助插件。
    
    提供以下功能：
    - 环评报告模板生成
    - 报告章节辅助编写
    - 法规符合性检查
    - 报告质量审查
    """
    
    # 插件元数据
    METADATA = PluginMetadata(
        id="assessment-assist",
        name="环评报告辅助",
        version="1.0.0",
        description="环境影响评价报告辅助生成与审查插件",
        author="Taiji Team",
        homepage="https://taiji-agent.example.com/plugins/assessment",
        license="MIT",
        tags=["环评", "环境影响评价", "报告", "辅助"],
        min_agent_version="1.0.0",
        dependencies=["eco-law"],
        config_schema={
            "type": "object",
            "properties": {
                "template_dir": {
                    "type": "string",
                    "description": "报告模板目录"
                },
                "auto_save": {
                    "type": "boolean",
                    "default": True,
                    "description": "是否自动保存"
                },
                "strict_mode": {
                    "type": "boolean",
                    "default": False,
                    "description": "严格模式（更严格的合规检查）"
                }
            }
        }
    )
    
    # 报告模板结构
    REPORT_SECTIONS = [
        {
            "id": "overview",
            "title": "项目概述",
            "required": True,
            "subsections": [
                {"id": "project_background", "title": "项目背景"},
                {"id": "construction_content", "title": "建设内容与规模"},
                {"id": "location_analysis", "title": "选址分析"}
            ]
        },
        {
            "id": "environment_status",
            "title": "环境现状调查",
            "required": True,
            "subsections": [
                {"id": "air_quality", "title": "环境空气质量现状"},
                {"id": "water_quality", "title": "地表水环境质量现状"},
                {"id": "acoustic_env", "title": "声环境质量现状"},
                {"id": "ecological", "title": "生态环境现状"}
            ]
        },
        {
            "id": "impact_analysis",
            "title": "环境影响预测分析",
            "required": True,
            "subsections": [
                {"id": "construction_phase", "title": "施工期环境影响"},
                {"id": "operation_phase", "title": "运营期环境影响"},
                {"id": "accident_risk", "title": "事故风险分析"}
            ]
        },
        {
            "id": "mitigation_measures",
            "title": "环境保护措施",
            "required": True,
            "subsections": [
                {"id": "air_pollution", "title": "大气污染防治措施"},
                {"id": "water_pollution", "title": "水污染防治措施"},
                {"id": "noise_control", "title": "噪声控制措施"},
                {"id": "solid_waste", "title": "固体废物处置措施"}
            ]
        },
        {
            "id": "environmental_monitoring",
            "title": "环境监测计划",
            "required": True,
            "subsections": [
                {"id": "monitoring_items", "title": "监测项目"},
                {"id": "monitoring_method", "title": "监测方法与频次"},
                {"id": "monitoring_agency", "title": "监测机构要求"}
            ]
        },
        {
            "id": "conclusion",
            "title": "结论与建议",
            "required": True,
            "subsections": [
                {"id": "main_conclusions", "title": "主要结论"},
                {"id": "improvement_suggestions", "title": "改进建议"}
            ]
        }
    ]
    
    def __init__(self, metadata: Optional[PluginMetadata] = None):
        """初始化插件"""
        super().__init__(metadata or self.METADATA)
        self._reports: Dict[str, Any] = {}
        self._templates: Dict[str, Any] = {}
        self._initialized = False
    
    async def activate(self, ctx: PluginContext) -> None:
        """
        激活插件。
        
        初始化报告模板，注册工具和钩子。
        """
        self.context = ctx
        
        ctx.logger.info("Activating AssessmentPlugin...")
        
        # 注册工具
        self.tools = [
            ToolDefinition(
                name="create_report",
                description="创建环评报告项目",
                parameters={
                    "type": "object",
                    "properties": {
                        "project_name": {
                            "type": "string",
                            "description": "项目名称"
                        },
                        "project_type": {
                            "type": "string",
                            "enum": ["工业类", "基础设施类", "房地产类", "农业类", "其他"],
                            "description": "项目类型"
                        },
                        "industry": {
                            "type": "string",
                            "description": "所属行业"
                        },
                        "location": {
                            "type": "string",
                            "description": "项目地点"
                        }
                    },
                    "required": ["project_name", "project_type"]
                }
            ),
            ToolDefinition(
                name="generate_section",
                description="生成报告章节内容",
                parameters={
                    "type": "object",
                    "properties": {
                        "report_id": {
                            "type": "string",
                            "description": "报告ID"
                        },
                        "section_id": {
                            "type": "string",
                            "description": "章节ID"
                        },
                        "context": {
                            "type": "object",
                            "description": "上下文信息"
                        }
                    },
                    "required": ["report_id", "section_id"]
                }
            ),
            ToolDefinition(
                name="check_compliance",
                description="合规性检查",
                parameters={
                    "type": "object",
                    "properties": {
                        "report_id": {
                            "type": "string",
                            "description": "报告ID"
                        }
                    },
                    "required": ["report_id"]
                }
            ),
            ToolDefinition(
                name="get_report_outline",
                description="获取报告大纲",
                parameters={
                    "type": "object",
                    "properties": {
                        "project_type": {
                            "type": "string",
                            "description": "项目类型"
                        }
                    },
                    "required": ["project_type"]
                }
            ),
            ToolDefinition(
                name="export_report",
                description="导出报告",
                parameters={
                    "type": "object",
                    "properties": {
                        "report_id": {
                            "type": "string",
                            "description": "报告ID"
                        },
                        "format": {
                            "type": "string",
                            "enum": ["markdown", "html", "docx"],
                            "default": "markdown",
                            "description": "导出格式"
                        }
                    },
                    "required": ["report_id"]
                }
            ),
        ]
        
        # 注册钩子
        self.hooks = [
            HookRegistration(
                event=SystemEvents.ASSESSMENT_GENERATE,
                handler=self._handle_assessment_generate,
                priority=50,
            )
        ]
        
        # 初始化模板
        self._load_templates()
        
        ctx.logger.info("AssessmentPlugin activated successfully")
    
    async def deactivate(self) -> None:
        """停用插件"""
        if self.context:
            self.context.logger.info("Deactivating AssessmentPlugin...")
        
        self._reports.clear()
        self._templates.clear()
        self._initialized = False
        
        if self.context:
            self.context.logger.info("AssessmentPlugin deactivated")
    
    async def health_check(self) -> PluginHealth:
        """健康检查"""
        return PluginHealth.HEALTHY
    
    async def get_metrics(self) -> Dict[str, Any]:
        """获取插件指标"""
        return {
            "assessment.total_reports": len(self._reports),
            "assessment.completed_reports": sum(
                1 for r in self._reports.values()
                if r.get("status") == "completed"
            ),
            "assessment.draft_reports": sum(
                1 for r in self._reports.values()
                if r.get("status") == "draft"
            )
        }
    
    def _load_templates(self) -> None:
        """加载报告模板"""
        self._templates = {
            "工业类": {
                "sections": self.REPORT_SECTIONS,
                "focus_areas": ["污染源分析", "清洁生产", "总量控制"],
                "required_attachments": [
                    "项目批复文件",
                    "地理位置图",
                    "平面布置图",
                    "工艺流程图",
                    "监测数据报告"
                ]
            },
            "基础设施类": {
                "sections": self.REPORT_SECTIONS,
                "focus_areas": ["生态影响", "景观影响", "社会影响"],
                "required_attachments": [
                    "规划选址意见",
                    "线路走向图",
                    "敏感目标分布图"
                ]
            },
            "房地产类": {
                "sections": self.REPORT_SECTIONS,
                "focus_areas": ["施工期管理", "入住期影响", "物业管理"],
                "required_attachments": [
                    "项目立项文件",
                    "总平面图",
                    "效果图"
                ]
            }
        }
        self._initialized = True
    
    async def _handle_assessment_generate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """处理环评报告生成事件"""
        action = data.get("action")
        
        if action == "create":
            result = await self.create_report(
                project_name=data.get("project_name"),
                project_type=data.get("project_type"),
                industry=data.get("industry"),
                location=data.get("location")
            )
            return result
        
        return data
    
    # 公开的工具方法
    async def create_report(
        self,
        project_name: str,
        project_type: str,
        industry: Optional[str] = None,
        location: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        创建环评报告项目。
        
        Args:
            project_name: 项目名称
            project_type: 项目类型
            industry: 所属行业
            location: 项目地点
            
        Returns:
            创建结果
        """
        import uuid
        
        report_id = f"report-{uuid.uuid4().hex[:8]}"
        
        # 获取模板
        template = self._templates.get(project_type, self._templates.get("工业类"))
        
        # 创建报告结构
        report = {
            "id": report_id,
            "project_name": project_name,
            "project_type": project_type,
            "industry": industry,
            "location": location,
            "status": "draft",
            "progress": 0,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "sections": {},
            "template": template,
            "issues": [],
            "warnings": []
        }
        
        # 初始化章节
        for section in template.get("sections", []):
            report["sections"][section["id"]] = {
                "id": section["id"],
                "title": section["title"],
                "required": section.get("required", False),
                "content": "",
                "status": "pending",
                "subsections": {}
            }
            
            for subsection in section.get("subsections", []):
                report["sections"][section["id"]]["subsections"][subsection["id"]] = {
                    "id": subsection["id"],
                    "title": subsection["title"],
                    "content": "",
                    "status": "pending"
                }
        
        self._reports[report_id] = report
        
        return {
            "success": True,
            "report_id": report_id,
            "message": f"环评报告项目 '{project_name}' 创建成功"
        }
    
    async def generate_section(
        self,
        report_id: str,
        section_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        生成报告章节内容。
        
        Args:
            report_id: 报告ID
            section_id: 章节ID
            context: 上下文信息
            
        Returns:
            生成结果
        """
        report = self._reports.get(report_id)
        if not report:
            return {
                "success": False,
                "error": f"Report not found: {report_id}"
            }
        
        section = report["sections"].get(section_id)
        if not section:
            return {
                "success": False,
                "error": f"Section not found: {section_id}"
            }
        
        # 生成章节内容（实际应用中会调用 AI 模型）
        content = self._generate_section_content(
            report, section, context or {}
        )
        
        section["content"] = content
        section["status"] = "completed"
        section["generated_at"] = datetime.now().isoformat()
        
        # 更新报告进度
        self._update_progress(report)
        report["updated_at"] = datetime.now().isoformat()
        
        return {
            "success": True,
            "report_id": report_id,
            "section_id": section_id,
            "content": content
        }
    
    def _generate_section_content(
        self,
        report: Dict[str, Any],
        section: Dict[str, Any],
        context: Dict[str, Any],
    ) -> str:
        """生成章节内容"""
        section_id = section["id"]
        project_name = report.get("project_name", "该项目")
        
        templates = {
            "overview": f"""## 项目概述

### 项目背景
{project_name}的建设符合国家产业政策和环境保护要求。项目所在地具有良好的基础设施条件，交通便利，有利于项目的建设和运营。

### 建设内容与规模
本项目主要建设内容包括主体工程、辅助工程和环保工程等。具体建设规模根据项目可行性研究报告确定。

### 选址分析
项目选址经过多方案比选，综合考虑环境影响、社会效益和经济效益，选定现址建设。
""",
            "environment_status": f"""## 环境现状调查

### 环境空气质量现状
根据监测数据，项目所在区域环境空气质量良好，各项指标均符合《环境空气质量标准》(GB 3095-2012)二级标准要求。

### 水环境质量现状
项目所在区域地表水环境质量符合《地表水环境质量标准》(GB 3838-2002)相应功能区要求。

### 声环境质量现状
项目所在区域声环境质量符合《声环境质量标准》(GB 3096-2008)相应功能区要求。

### 生态环境现状
项目所在区域生态环境现状调查结果将在详细勘察后补充。
""",
            "impact_analysis": f"""## 环境影响预测分析

### 施工期环境影响
施工期主要环境影响包括扬尘、噪声、施工废水和建筑垃圾等。通过采取有效的污染防治措施，可以减轻施工期对环境的影响。

### 运营期环境影响
运营期主要环境影响包括废气、废水、噪声和固体废物等。通过采取本报告提出的各项污染防治措施，运营期环境影响可控制在允许范围内。

### 事故风险分析
本项目在做好风险防范措施的前提下，环境风险水平可以接受。
""",
            "mitigation_measures": f"""## 环境保护措施

### 大气污染防治措施
采取密闭输送、洒水降尘、废气处理等措施，控制大气污染物排放。

### 水污染防治措施
实行雨污分流，建设污水处理设施，废水达标排放。

### 噪声控制措施
选用低噪声设备，采取隔声、消声等措施，控制噪声污染。

### 固体废物处置措施
分类收集、综合利用、安全处置固体废物。
""",
            "environmental_monitoring": f"""## 环境监测计划

### 监测项目
根据项目特点，确定主要监测项目包括废气、废水、噪声等。

### 监测方法与频次
按照国家和地方相关标准规范要求，制定监测方案。

### 监测机构要求
委托有资质的监测机构开展环境监测工作。
""",
            "conclusion": f"""## 结论与建议

### 主要结论
{project_name}的建设符合国家产业政策和环境保护要求。在落实本报告提出的各项环境保护措施后，对环境的影响可控制在允许范围内，从环境保护角度分析，项目建设是可行的。

### 改进建议
1. 严格执行环境保护"三同时"制度
2. 加强环境管理，确保各项污染防治设施正常运行
3. 定期开展环境监测，及时发现和解决环境问题
"""
        }
        
        return templates.get(section_id, f"## {section.get('title', '章节')}\n\n内容待填充。")
    
    def _update_progress(self, report: Dict[str, Any]) -> None:
        """更新报告进度"""
        total_sections = len(report["sections"])
        completed_sections = sum(
            1 for s in report["sections"].values()
            if s.get("status") == "completed"
        )
        
        if total_sections > 0:
            report["progress"] = int(completed_sections / total_sections * 100)
            
            if report["progress"] == 100:
                report["status"] = "completed"
    
    async def check_compliance(self, report_id: str) -> Dict[str, Any]:
        """
        合规性检查。
        
        Args:
            report_id: 报告ID
            
        Returns:
            检查结果
        """
        report = self._reports.get(report_id)
        if not report:
            return {
                "success": False,
                "error": f"Report not found: {report_id}"
            }
        
        issues = []
        warnings = []
        
        # 检查必填章节
        strict_mode = self.get_config("strict_mode", False)
        
        for section in report["sections"].values():
            if section.get("required") and not section.get("content"):
                issues.append({
                    "type": "missing_section",
                    "section_id": section["id"],
                    "title": section["title"],
                    "message": f"必填章节 '{section['title']}' 内容为空"
                })
            elif not section.get("content"):
                warnings.append({
                    "type": "incomplete_section",
                    "section_id": section["id"],
                    "title": section["title"],
                    "message": f"章节 '{section['title']}' 内容为空"
                })
        
        # 检查章节完整性
        for section in report["sections"].values():
            for subsection in section.get("subsections", {}).values():
                if not subsection.get("content"):
                    warnings.append({
                        "type": "missing_subsection",
                        "section_id": section["id"],
                        "subsection_id": subsection["id"],
                        "title": subsection["title"],
                        "message": f"子章节 '{subsection['title']}' 内容为空"
                    })
        
        # 保存检查结果
        report["issues"] = issues
        report["warnings"] = warnings
        report["compliance_checked_at"] = datetime.now().isoformat()
        
        return {
            "success": True,
            "report_id": report_id,
            "status": "passed" if len(issues) == 0 else "failed",
            "issues_count": len(issues),
            "warnings_count": len(warnings),
            "issues": issues,
            "warnings": warnings
        }
    
    async def get_report_outline(self, project_type: str) -> Dict[str, Any]:
        """
        获取报告大纲。
        
        Args:
            project_type: 项目类型
            
        Returns:
            报告大纲
        """
        template = self._templates.get(
            project_type,
            self._templates.get("工业类")
        )
        
        return {
            "success": True,
            "project_type": project_type,
            "outline": template.get("sections", []),
            "focus_areas": template.get("focus_areas", []),
            "required_attachments": template.get("required_attachments", [])
        }
    
    async def export_report(
        self,
        report_id: str,
        format: str = "markdown",
    ) -> Dict[str, Any]:
        """
        导出报告。
        
        Args:
            report_id: 报告ID
            format: 导出格式
            
        Returns:
            导出结果
        """
        report = self._reports.get(report_id)
        if not report:
            return {
                "success": False,
                "error": f"Report not found: {report_id}"
            }
        
        # 生成导出内容
        content = self._generate_export_content(report, format)
        
        # 保存到文件
        if self.context:
            export_dir = self.context.data_dir / "exports"
            export_dir.mkdir(parents=True, exist_ok=True)
            
            extension = {"markdown": "md", "html": "html", "docx": "docx"}.get(format, "txt")
            export_file = export_dir / f"{report_id}.{extension}"
            
            with open(export_file, "w", encoding="utf-8") as f:
                f.write(content)
            
            return {
                "success": True,
                "report_id": report_id,
                "format": format,
                "file_path": str(export_file),
                "content": content[:500] + "..." if len(content) > 500 else content
            }
        
        return {
            "success": True,
            "report_id": report_id,
            "format": format,
            "content": content
        }
    
    def _generate_export_content(self, report: Dict[str, Any], format: str) -> str:
        """生成导出内容"""
        lines = [
            f"# {report.get('project_name')} 环境影响评价报告",
            "",
            f"**项目类型**: {report.get('project_type')}",
            f"**所属行业**: {report.get('industry', '未指定')}",
            f"**项目地点**: {report.get('location', '未指定')}",
            f"**编制日期**: {report.get('created_at', '')[:10]}",
            "",
            "---",
            ""
        ]
        
        for section in report.get("sections", {}).values():
            lines.append(f"## {section.get('title', '章节')}")
            lines.append("")
            
            if section.get("content"):
                lines.append(section["content"])
            else:
                lines.append("*[内容待填充]*")
            
            lines.append("")
            
            for subsection in section.get("subsections", {}).values():
                lines.append(f"### {subsection.get('title', '子章节')}")
                lines.append("")
                
                if subsection.get("content"):
                    lines.append(subsection["content"])
                else:
                    lines.append("*[内容待填充]*")
                
                lines.append("")
        
        return "\n".join(lines)
