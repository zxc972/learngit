#!/usr/bin/env python3
"""
报告生成工具
专门负责为各种分析结果生成HTML报告
"""

from . import BaseTool
from typing import Dict, Any, List
import os
import json
from datetime import datetime

class ReportGenerationTool(BaseTool):
    """报告生成工具类"""
    
    def __init__(self):
        super().__init__("report_generator", "1.0.0")
        self.description = "Generate comprehensive HTML reports for analysis results"
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        """获取参数schema"""
        return {
            "type": "object",
            "properties": {
                "analysis_type": {
                    "type": "string",
                    "enum": ["distance_analysis", "covariance_analysis", "gradient_analysis"],
                    "description": "Analysis type for report generation"
                },
                "batch_directory": {
                    "type": "string",
                    "description": "Path to the batch analysis results directory"
                },
                "template_type": {
                    "type": "string", 
                    "enum": ["comprehensive", "summary", "comparison"],
                    "default": "comprehensive",
                    "description": "Type of report template to use"
                },
                "metadata": {
                    "type": "object",
                    "properties": {
                        "surface_type": {"type": "string"},
                        "hemisphere": {"type": "string"},
                        "work_directory": {"type": "string"},
                        "parcellation_file": {"type": "string"},
                        "subjects": {"type": "array", "items": {"type": "string"}},
                        "max_parallel": {"type": "integer"}
                    },
                    "description": "Analysis metadata for report context"
                }
            },
            "required": ["analysis_type", "batch_directory"]
        }
    
    def validate_params(self, params: Dict[str, Any]) -> tuple[bool, str]:
        """验证参数"""
        if not params.get("batch_directory"):
            return False, "batch_directory is required"
        
        if not os.path.exists(params["batch_directory"]):
            return False, f"Batch directory does not exist: {params['batch_directory']}"
        
        analysis_type = params.get("analysis_type")
        if analysis_type not in ["distance_analysis", "covariance_analysis", "gradient_analysis"]:
            return False, f"Unsupported analysis type: {analysis_type}"
        
        return True, "Parameters valid"
    
    def generate_script(self, params: Dict[str, Any]) -> str:
        """生成报告生成脚本"""
        
        analysis_type = params["analysis_type"]
        batch_dir = params["batch_directory"]
        template_type = params.get("template_type", "comprehensive")
        metadata = params.get("metadata", {})
        
        # 根据分析类型选择报告生成器
        if analysis_type == "distance_analysis":
            generator_script = self._generate_distance_report_script(batch_dir, template_type, metadata)
        elif analysis_type == "covariance_analysis":
            generator_script = self._generate_covariance_report_script(batch_dir, template_type, metadata)
        elif analysis_type == "gradient_analysis":
            generator_script = self._generate_gradient_report_script(batch_dir, template_type, metadata)
        else:
            raise ValueError(f"Unsupported analysis type: {analysis_type}")
        
        # 生成完整的bash脚本
        script_content = f'''#!/bin/bash

# Auto-generated report generation script
# Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# Tool: {self.name} v{self.version}

echo "🚀 开始生成分析报告..."
echo "   分析类型: {analysis_type}"
echo "   模板类型: {template_type}"
echo "   批量目录: {batch_dir}"
echo ""

{generator_script}

echo ""
echo "✅ 报告生成完成！"
'''
        
        return script_content
    
    def _generate_distance_report_script(self, batch_dir: str, template_type: str, metadata: Dict) -> str:
        """生成距离分析报告脚本"""
        
        subjects = metadata.get("subjects", [])
        subjects_str = ",".join(subjects) if subjects else "auto-detect"
        
        surface_type = metadata.get("surface_type", "unknown")
        hemisphere = metadata.get("hemisphere", "unknown")
        work_directory = metadata.get("work_directory", "unknown")
        parcellation_file = metadata.get("parcellation_file", "unknown")
        max_parallel = metadata.get("max_parallel", 1)
        
        script = f'''
# 距离分析报告生成
BATCH_DIR="{batch_dir}"
TEMPLATE_PATH="/home/xuancheng/monkey_brain_segmentation_pipeline/templates/distance_analysis_report.html"
REPORT_GENERATOR="/home/xuancheng/monkey_brain_segmentation_pipeline/scripts/generate_distance_report.py"

# 检查必要文件
if [ ! -d "$BATCH_DIR" ]; then
    echo "❌ 批量目录不存在: $BATCH_DIR"
    exit 1
fi

if [ ! -f "$TEMPLATE_PATH" ]; then
    echo "❌ 模板文件不存在: $TEMPLATE_PATH"
    exit 1
fi

if [ ! -f "$REPORT_GENERATOR" ]; then
    echo "❌ 报告生成器不存在: $REPORT_GENERATOR"
    exit 1
fi

# 检查热图目录
HEATMAPS_DIR="$BATCH_DIR/heatmaps"
if [ ! -d "$HEATMAPS_DIR" ]; then
    echo "❌ 热图目录不存在: $HEATMAPS_DIR"
    exit 1
fi

# 统计可用数据
HEATMAP_COUNT=$(find "$HEATMAPS_DIR" -name "*_enhanced_heatmap.png" | wc -l)
STATS_COUNT=$(find "$HEATMAPS_DIR" -name "*_distance_stats.json" | wc -l)

echo "📊 发现数据文件:"
echo "   热图文件: $HEATMAP_COUNT"
echo "   统计文件: $STATS_COUNT"

# 生成报告
echo "🔧 执行报告生成..."
python3 "$REPORT_GENERATOR" \\
    --batch_dir "$BATCH_DIR" \\
    --template "$TEMPLATE_PATH" \\
    --subjects "{subjects_str}" \\
    --surface_type "{surface_type}" \\
    --hemisphere "{hemisphere}" \\
    --work_directory "{work_directory}" \\
    --parcellation_file "{parcellation_file}" \\
    --max_parallel "{max_parallel}"

# 检查生成结果
REPORT_FILE="$BATCH_DIR/comprehensive_analysis_report.html"
if [ -f "$REPORT_FILE" ]; then
    REPORT_SIZE=$(stat -f%z "$REPORT_FILE" 2>/dev/null || stat -c%s "$REPORT_FILE" 2>/dev/null || echo "unknown")
    echo "✅ HTML报告已生成: $REPORT_FILE ($REPORT_SIZE bytes)"
    
    # 生成简单的摘要文件
    echo "📋 生成摘要文件..."
    cat > "$BATCH_DIR/analysis_summary.txt" << EOF
Monkey Brain Distance Analysis Report
====================================
Generated: $(date)
Analysis Type: Distance Analysis ({surface_type} surface, {hemisphere} hemisphere)
Batch Directory: $BATCH_DIR
Subjects: {subjects_str}
Heatmaps Generated: $HEATMAP_COUNT
Statistics Files: $STATS_COUNT
HTML Report: $REPORT_FILE
Report Size: $REPORT_SIZE bytes

Status: Completed Successfully
EOF
    
    echo "✅ 摘要文件已生成: $BATCH_DIR/analysis_summary.txt"
    
    # 生成集成报告JSON (用于API返回)
    cat > "$BATCH_DIR/integrated_report.json" << EOF
{{
    "analysis_type": "distance_analysis",
    "surface_type": "{surface_type}",
    "hemisphere": "{hemisphere}",
    "generated_time": "$(date -Iseconds)",
    "batch_directory": "$BATCH_DIR",
    "reports": {{
        "html_report": "$REPORT_FILE",
        "summary_report": "$BATCH_DIR/analysis_summary.txt"
    }},
    "statistics": {{
        "heatmaps_generated": $HEATMAP_COUNT,
        "stats_files_generated": $STATS_COUNT,
        "subjects_processed": {len(subjects) if subjects else "auto"}
    }},
    "metadata": {{
        "work_directory": "{work_directory}",
        "parcellation_file": "{parcellation_file}",
        "max_parallel": {max_parallel}
    }}
}}
EOF
    
    echo "✅ 集成报告JSON已生成: $BATCH_DIR/integrated_report.json"
else
    echo "❌ 报告生成失败!"
    exit 1
fi
'''
        return script
    
    def _generate_covariance_report_script(self, batch_dir: str, template_type: str, metadata: Dict) -> str:
        """生成协变分析报告脚本（预留）"""
        return f'''
# 协变分析报告生成 (待实现)
echo "🚧 协变分析报告生成功能正在开发中..."
echo "   批量目录: {batch_dir}"
echo "   模板类型: {template_type}"
'''
    
    def _generate_gradient_report_script(self, batch_dir: str, template_type: str, metadata: Dict) -> str:
        """生成梯度分析报告脚本（预留）"""
        return f'''
# 梯度分析报告生成 (待实现)
echo "🚧 梯度分析报告生成功能正在开发中..."
echo "   批量目录: {batch_dir}"
echo "   模板类型: {template_type}"
'''

    def get_help_text(self) -> str:
        """获取帮助文本"""
        return """
报告生成工具 (Report Generation Tool)

功能：
- 为各种脑分析结果生成专业的HTML报告
- 支持多种分析类型：距离分析、协变分析、梯度分析
- 提供多种报告模板：综合报告、摘要报告、对比报告

支持的分析类型：
1. distance_analysis - 测地距离与欧氏距离分析报告
2. covariance_analysis - 协变网络分析报告 (开发中)
3. gradient_analysis - 梯度分析报告 (开发中)

使用示例：
{
    "analysis_type": "distance_analysis",
    "batch_directory": "/data/results/batch_distance_pial_R_20250820_141855",
    "template_type": "comprehensive",
    "metadata": {
        "surface_type": "pial",
        "hemisphere": "R", 
        "subjects": ["ION001", "ION002", "ION003"],
        "work_directory": "/data/xuancheng/ION_test_monkey",
        "parcellation_file": "/data/parcellation.gii",
        "max_parallel": 3
    }
}

输出：
- comprehensive_analysis_report.html - 主要HTML报告
- analysis_summary.txt - 文本摘要
- integrated_report.json - 结构化报告数据
"""
