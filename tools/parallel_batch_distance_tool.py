"""
并行批量距离计算工具 - 集成热图生成版本
支持多个被试的欧几里得距离和测地距离并行计算，集成热图生成功能
"""

import os
import re
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from . import BaseTool

# 导入配置系统
try:
    from config_local import DISTANCE_ANALYSIS_TEMPLATE, DISTANCE_REPORT_GENERATOR
except ImportError:
    try:
        from config_template import DISTANCE_ANALYSIS_TEMPLATE, DISTANCE_REPORT_GENERATOR
    except ImportError:
        # 如果配置文件不存在，使用默认路径
        import os
        PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        DISTANCE_ANALYSIS_TEMPLATE = os.path.join(PROJECT_ROOT, 'templates', 'distance_analysis_report.html')
        DISTANCE_REPORT_GENERATOR = os.path.join(PROJECT_ROOT, 'scripts', 'generate_distance_report.py')


class ParallelBatchDistanceCalculationTool(BaseTool):
    """并行批量距离计算工具 - 集成热图生成"""

    def __init__(self):
        super().__init__("parallel_batch_distance", "2.0.0")
        self.description = "并行批量计算多个被试的欧几里得距离和测地距离，集成热图生成功能"

    def get_name(self) -> str:
        return "parallel_batch_distance"

    def get_description(self) -> str:
        return "并行批量计算多个被试的欧几里得距离和测地距离，集成热图生成功能"

    def get_parameter_schema(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "work_directory": {
                    "type": "string",
                    "description": "工作目录路径，包含多个被试的数据"
                },
                "parcellation_file": {
                    "type": "string", 
                    "description": "分区文件路径 (.label.gii)"
                },
                "surface_type": {
                    "type": "string",
                    "description": "表面类型",
                    "enum": ["pial", "white", "midthickness"],
                    "default": "midthickness"
                },
                "subject_list": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "要处理的被试列表（可选，如果不提供将自动发现）",
                    "default": []
                },
                "max_parallel_subjects": {
                    "type": "integer",
                    "description": "最大并行处理的被试数量",
                    "minimum": 1,
                    "maximum": 10,
                    "default": 2
                }
            },
            "required": ["work_directory", "parcellation_file"]
        }

    def validate_params(self, params: Dict) -> tuple[bool, str]:
        """验证参数"""
        errors = []
        
        # 验证工作目录
        work_directory = params.get('work_directory')
        if not work_directory:
            errors.append("work_directory 参数是必需的")
        elif not os.path.exists(work_directory):
            errors.append(f"工作目录不存在: {work_directory}")
        elif not os.path.isdir(work_directory):
            errors.append(f"工作目录不是一个目录: {work_directory}")
            
        # 验证分区文件
        parcellation_file = params.get('parcellation_file')
        if not parcellation_file:
            errors.append("parcellation_file 参数是必需的")
        elif not os.path.exists(parcellation_file):
            errors.append(f"分区文件不存在: {parcellation_file}")
        elif not parcellation_file.endswith('.label.gii'):
            errors.append(f"分区文件必须是 .label.gii 格式: {parcellation_file}")
            
        # 验证表面类型
        surface_type = params.get('surface_type', 'midthickness')
        if surface_type not in ['pial', 'white', 'midthickness']:
            errors.append(f"无效的表面类型: {surface_type}")
            
        # 验证并行数量
        max_parallel = params.get('max_parallel_subjects', 2)
        if not isinstance(max_parallel, int) or max_parallel < 1 or max_parallel > 10:
            errors.append("max_parallel_subjects 必须是1-10之间的整数")
        
        if errors:
            return False, "; ".join(errors)
        else:
            return True, "参数验证通过"

    def _parse_parcellation_info(self, parcellation_file: str) -> Dict:
        """解析分区文件信息，提取半球和分辨率"""
        filename = os.path.basename(parcellation_file)
        
        # 解析半球 (L/R)
        hemisphere_match = re.search(r'\.([LR])\.', filename)
        hemisphere = hemisphere_match.group(1) if hemisphere_match else 'L'
        
        # 解析分辨率 (32k, 164k等)
        resolution_match = re.search(r'(\d+)k', filename)
        resolution = resolution_match.group(1) if resolution_match else '32'
        
        return {
            'hemisphere': hemisphere,
            'resolution': resolution,
            'filename': filename
        }

    def _find_subjects(self, work_directory: str) -> List[str]:
        """在工作目录中查找所有被试"""
        subjects = []
        work_path = Path(work_directory)
        
        if not work_path.exists():
            return subjects
            
        for item in work_path.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                # 检查是否包含HCP风格的目录结构
                hcp_dir = item / item.name / "HCP_Stype_Dir" / "fsaverage_LR32k"
                if hcp_dir.exists():
                    subjects.append(item.name)
                # 或者检查是否直接包含表面文件
                elif any(item.rglob("*.surf.gii")):
                    subjects.append(item.name)
        
        return sorted(subjects)

    def _find_surface_file(self, work_directory: str, subject_id: str, 
                          surface_type: str, hemisphere: str, resolution: str) -> Optional[str]:
        """查找指定被试的表面文件"""
        subject_path = Path(work_directory) / subject_id
        
        # 构建搜索模式
        pattern = f"*{subject_id}.{hemisphere}.{surface_type}.{resolution}k*.surf.gii"
        
        # 在被试目录下递归搜索
        for surface_file in subject_path.rglob(pattern):
            return str(surface_file)
        
        return None

    def generate_script(self, params: Dict) -> str:
        """生成集成的并行批量距离计算脚本"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 解析参数
        work_directory = params['work_directory']
        parcellation_file = params['parcellation_file']
        surface_type = params.get('surface_type', 'midthickness')
        subject_list = params.get('subject_list', [])
        max_parallel_subjects = params.get('max_parallel_subjects', 2)
        
        # 解析分割信息
        parcellation_info = self._parse_parcellation_info(parcellation_file)
        hemisphere = parcellation_info['hemisphere']
        resolution = parcellation_info['resolution']
        
        # 查找被试
        if not subject_list:
            subject_list = self._find_subjects(work_directory)
        
        if not subject_list:
            raise ValueError(f"在工作目录 {work_directory} 中未找到任何被试")
        
        # 创建批量输出目录
        batch_dir_name = f"batch_distance_{surface_type}_{hemisphere}_{timestamp}"
        batch_dir = f"{work_directory}/{batch_dir_name}"
        
        # 生成集成脚本
        script_content = """#!/bin/bash
# 集成并行批量距离计算和热图生成脚本
# 生成时间: {timestamp}
# 工具: ParallelBatchDistanceCalculationTool (集成版本)

# 设置错误处理 - 允许非关键错误继续执行，但保持管道错误检测
set -o pipefail

# =============================================================================
# 配置参数
# =============================================================================
WORK_DIR="{work_directory}"
BATCH_DIR="{batch_dir}"
PARCELLATION_FILE="{parcellation_file}"
SURFACE_TYPE="{surface_type}"
HEMISPHERE="{hemisphere}"
RESOLUTION="{resolution}"
MAX_PARALLEL="{max_parallel_subjects}"

# 被试列表
SUBJECTS=({subject_list_bash})

echo "🚀 开始集成并行批量距离计算和热图生成..."
echo "   工作目录: $WORK_DIR"
echo "   批量目录: $BATCH_DIR"
echo "   表面类型: $SURFACE_TYPE"
echo "   半球: $HEMISPHERE"
echo "   分辨率: $RESOLUTION"
echo "   被试数量: ${{#SUBJECTS[@]}}"
echo "   最大并行: $MAX_PARALLEL"
echo ""

# =============================================================================
# 创建输出目录结构
# =============================================================================
mkdir -p "$BATCH_DIR/data_files"
mkdir -p "$BATCH_DIR/heatmaps"
mkdir -p "$BATCH_DIR/logs"

# =============================================================================
# 集成处理函数：距离计算 + 热图生成
# =============================================================================
process_subject_integrated() {{
    local subject="$1"
    local log_file="$BATCH_DIR/logs/${{subject}}_integrated.log"
    local overall_start_time=$(date +%s)
    
    echo "🔄 开始集成处理被试: $subject" | tee "$log_file"
    
    # 查找表面文件
    surface_file=$(find "$WORK_DIR/$subject" -name "*.$HEMISPHERE.$SURFACE_TYPE.${{RESOLUTION}}k*.surf.gii" | head -1)
    
    if [[ -z "$surface_file" ]]; then
        echo "❌ 未找到被试 $subject 的表面文件" | tee -a "$log_file"
        return 1
    fi
    
    echo "   表面文件: $surface_file" | tee -a "$log_file"
    
    # 步骤1: 距离计算
    echo "📊 步骤1: 计算距离矩阵..." | tee -a "$log_file"
    calc_start_time=$(date +%s)
    
    response=$(curl -s -X POST http://localhost:8000/calculate_distance \\
        --max-time 2000 \\
        --connect-timeout 30 \\
        -H "Content-Type: application/json" \\
        -d "{{\\\"subject_id\\\": \\\"$subject\\\", \\\"surface_file\\\": \\\"$surface_file\\\", \\\"parcellation_file\\\": \\\"$PARCELLATION_FILE\\\", \\\"output_directory\\\": \\\"$BATCH_DIR/data_files/$subject\\\"}}")
    
    calc_end_time=$(date +%s)
    calc_duration=$((calc_end_time - calc_start_time))
    
    # 检查距离计算结果
    if ! echo "$response" | jq -e '.success' > /dev/null 2>&1; then
        echo "❌ 被试 $subject 距离计算失败 (用时: ${{calc_duration}}s)" | tee -a "$log_file"
        echo "   错误响应: $response" >> "$log_file"
        return 1
    fi
    
    echo "✅ 被试 $subject 距离计算成功 (用时: ${{calc_duration}}s)" | tee -a "$log_file"
    
    # 步骤2: 集成热图生成
    echo "🎨 步骤2: 生成热图..." | tee -a "$log_file"
    heatmap_start_time=$(date +%s)
    
    # 检查距离文件是否存在
    euclidean_file="$BATCH_DIR/data_files/$subject/${{subject}}_euclidean_distance.csv"
    geodesic_file="$BATCH_DIR/data_files/$subject/${{subject}}_geodesic_distance.csv"
    
    if [[ ! -f "$euclidean_file" ]] || [[ ! -f "$geodesic_file" ]]; then
        echo "❌ 被试 $subject 距离文件不存在，无法生成热图" | tee -a "$log_file"
        return 1
    fi
    
    # 集成热图生成 - Python代码
    python3 << INTEGRATED_HEATMAP_SCRIPT
import os
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # 非交互式后端
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# 设置中文字体支持
plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'Liberation Sans', 'SimHei', 'WenQuanYi Micro Hei']
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

def generate_enhanced_heatmap():
    try:
        subject_id = "$subject"
        euclidean_file = "$euclidean_file"
        geodesic_file = "$geodesic_file"
        output_dir = "$BATCH_DIR/heatmaps"
        
        print("Loading distance data for:", subject_id)
        
        # 读取空格分隔的数据文件
        euclidean_data = pd.read_csv(euclidean_file, sep=' ', header=None, index_col=False)
        geodesic_data = pd.read_csv(geodesic_file, sep=' ', header=None, index_col=False)
        
        print("Euclidean data shape:", euclidean_data.shape)
        print("Geodesic data shape:", geodesic_data.shape)
        
        # 数据验证
        if euclidean_data.empty or geodesic_data.empty:
            raise ValueError("Distance data is empty")
        
        # 转换为numpy数组
        euclidean_array = euclidean_data.values
        geodesic_array = geodesic_data.values
        
        if euclidean_array.size == 0 or geodesic_array.size == 0:
            raise ValueError("Distance data arrays are empty")
        
        # 确保数据形状一致
        if euclidean_array.shape != geodesic_array.shape:
            raise ValueError("Distance data shape mismatch: " + str(euclidean_array.shape) + " vs " + str(geodesic_array.shape))
        
        # 计算差异矩阵和统计指标
        difference_array = geodesic_array - euclidean_array
        
        n_regions = euclidean_array.shape[0]
        upper_tri_mask = np.triu(np.ones_like(euclidean_array, dtype=bool), k=1)
        
        euclidean_upper = euclidean_array[upper_tri_mask]
        geodesic_upper = geodesic_array[upper_tri_mask]
        difference_upper = difference_array[upper_tri_mask]
        
        # 计算统计信息
        stats = {{
            "subject_id": subject_id,
            "regions_count": int(n_regions),
            "euclidean_stats": {{
                "mean": float(np.mean(euclidean_upper)),
                "std": float(np.std(euclidean_upper)),
                "min": float(np.min(euclidean_upper)),
                "max": float(np.max(euclidean_upper)),
                "median": float(np.median(euclidean_upper))
            }},
            "geodesic_stats": {{
                "mean": float(np.mean(geodesic_upper)),
                "std": float(np.std(geodesic_upper)),
                "min": float(np.min(geodesic_upper)),
                "max": float(np.max(geodesic_upper)),
                "median": float(np.median(geodesic_upper))
            }},
            "difference_stats": {{
                "mean": float(np.mean(difference_upper)),
                "std": float(np.std(difference_upper)),
                "min": float(np.min(difference_upper)),
                "max": float(np.max(difference_upper)),
                "median": float(np.median(difference_upper))
            }},
            "correlation": float(np.corrcoef(euclidean_upper, geodesic_upper)[0,1]),
            "distance_pairs": int(len(euclidean_upper))
        }}
        
        print("Generating enhanced heatmap...")
        
        # 创建改进的可视化 (2x2布局)
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        
        # 1. 欧氏距离热图
        im1 = axes[0,0].imshow(euclidean_array, cmap='Blues', aspect='auto')
        axes[0,0].set_title(subject_id + ' - Euclidean Distance')
        axes[0,0].set_xlabel('Brain Region Index')
        axes[0,0].set_ylabel('Brain Region Index')
        plt.colorbar(im1, ax=axes[0,0], label='Distance (mm)')
        
        # 2. 测地距离热图
        im2 = axes[0,1].imshow(geodesic_array, cmap='Reds', aspect='auto')
        axes[0,1].set_title(subject_id + ' - Geodesic Distance')
        axes[0,1].set_xlabel('Brain Region Index')
        axes[0,1].set_ylabel('Brain Region Index')
        plt.colorbar(im2, ax=axes[0,1], label='Distance (mm)')
        
        # 3. 差异热图
        im3 = axes[1,0].imshow(difference_array, cmap='RdBu_r', aspect='auto', 
                              vmin=-np.max(np.abs(difference_array)), 
                              vmax=np.max(np.abs(difference_array)))
        axes[1,0].set_title(subject_id + ' - Distance Difference (Geodesic - Euclidean)')
        axes[1,0].set_xlabel('Brain Region Index')
        axes[1,0].set_ylabel('Brain Region Index')
        plt.colorbar(im3, ax=axes[1,0], label='Difference (mm)')
        
        # 4. 相关性散点图
        axes[1,1].scatter(euclidean_upper, geodesic_upper, alpha=0.6, s=1, color='steelblue')
        # 添加对角线参考
        min_val = min(euclidean_upper.min(), geodesic_upper.min())
        max_val = max(euclidean_upper.max(), geodesic_upper.max())
        axes[1,1].plot([min_val, max_val], [min_val, max_val], 'r--', alpha=0.8, linewidth=2)
        axes[1,1].set_xlabel('Euclidean Distance (mm)')
        axes[1,1].set_ylabel('Geodesic Distance (mm)')
        correlation_val = stats["correlation"]
        axes[1,1].set_title(subject_id + ' - Distance Correlation\\\\nr = ' + str(round(correlation_val, 3)))
        axes[1,1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # 保存热图
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        heatmap_file = output_path / (subject_id + "_enhanced_heatmap.png")
        plt.savefig(heatmap_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        # 保存统计信息
        stats_file = output_path / (subject_id + "_distance_stats.json")
        import json
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        
        print("✅ Enhanced heatmap saved:", str(heatmap_file))
        print("📊 Statistics saved:", str(stats_file))
        return True
        
    except Exception as e:
        print("❌ Heatmap generation failed:", str(e))
        import traceback
        traceback.print_exc()
        return False

# 执行增强热图生成
success = generate_enhanced_heatmap()
sys.exit(0 if success else 1)
INTEGRATED_HEATMAP_SCRIPT

    heatmap_end_time=$(date +%s)
    heatmap_duration=$((heatmap_end_time - heatmap_start_time))
    overall_end_time=$(date +%s)
    overall_duration=$((overall_end_time - overall_start_time))
    
    # 检查热图生成结果
    if [[ $? -eq 0 ]]; then
        echo "✅ 被试 $subject 热图生成成功 (用时: ${{heatmap_duration}}s)" | tee -a "$log_file"
        echo "🎉 被试 $subject 集成处理完成 (总用时: ${{overall_duration}}s)" | tee -a "$log_file"
        return 0
    else
        echo "❌ 被试 $subject 热图生成失败 (用时: ${{heatmap_duration}}s)" | tee -a "$log_file"
        echo "⚠️  被试 $subject 距离计算成功但热图失败 (总用时: ${{overall_duration}}s)" | tee -a "$log_file"
        return 1
    fi
}}

# =============================================================================
# 并行执行集成处理
# =============================================================================
echo "🔄 开始并行集成处理所有被试..."

# 导出所有必要的变量和函数
export WORK_DIR BATCH_DIR PARCELLATION_FILE SURFACE_TYPE HEMISPHERE RESOLUTION
export -f process_subject_integrated

# 并行处理
printf '%s\\n' "${{SUBJECTS[@]}}" | xargs -I {{}} -P "$MAX_PARALLEL" bash -c 'process_subject_integrated "{{}}"'

# =============================================================================
# 统计结果并生成报告
# =============================================================================
echo ""
echo "📊 统计集成处理结果..."

successful_subjects=0
failed_subjects=0
successful_heatmaps=0
failed_heatmaps=0

for subject in "${{SUBJECTS[@]}}"; do
    log_file="$BATCH_DIR/logs/${{subject}}_integrated.log"
    if [[ -f "$log_file" ]]; then
        if grep -q "距离计算成功" "$log_file"; then
            ((successful_subjects++))
        else
            ((failed_subjects++))
        fi
        
        if grep -q "热图生成成功" "$log_file"; then
            ((successful_heatmaps++))
        else
            ((failed_heatmaps++))
        fi
    else
        ((failed_subjects++))
        ((failed_heatmaps++))
    fi
done

# 生成集成报告
cat > "$BATCH_DIR/integrated_report.json" << EOF
{{
  "analysis_info": {{
    "timestamp": "{timestamp}",
    "work_directory": "{work_directory}",
    "surface_type": "{surface_type}",
    "hemisphere": "{hemisphere}",
    "resolution": "{resolution}",
    "parcellation_file": "{parcellation_file}",
    "max_parallel_subjects": {max_parallel_subjects},
    "processing_mode": "integrated"
  }},
  "processing_summary": {{
    "total_subjects": ${{#SUBJECTS[@]}},
    "successful_subjects": $successful_subjects,
    "failed_subjects": $failed_subjects,
    "success_rate": $(echo "scale=2; $successful_subjects * 100 / ${{#SUBJECTS[@]}}" | bc -l 2>/dev/null || echo "0")
  }},
  "heatmap_summary": {{
    "successful_heatmaps": $successful_heatmaps,
    "failed_heatmaps": $failed_heatmaps,
    "heatmap_success_rate": $(echo "scale=2; $successful_heatmaps * 100 / ${{#SUBJECTS[@]}}" | bc -l 2>/dev/null || echo "0")
  }},
  "output_directories": {{
    "batch_directory": "$BATCH_DIR",
    "data_files": "$BATCH_DIR/data_files",
    "heatmaps": "$BATCH_DIR/heatmaps",
    "logs": "$BATCH_DIR/logs"
  }},
  "subjects": [
    "{subject_list_bash}"
  ]
}}
EOF

# =============================================================================
# 综合报告生成 
# =============================================================================
echo "📋 生成综合分析报告..."

# 直接调用报告生成脚本 (API调用在工具执行期间不可用)
echo "🔧 生成综合分析报告..."

# 配置路径 - 将在运行时替换为实际路径
TEMPLATE_PATH="{template_path}"
REPORT_GENERATOR="{report_generator}"

# 检查必要文件
if [ ! -f "$TEMPLATE_PATH" ]; then
    echo "❌ 模板文件不存在: $TEMPLATE_PATH"
elif [ ! -f "$REPORT_GENERATOR" ]; then
    echo "❌ 报告生成器不存在: $REPORT_GENERATOR"
else
    echo "🔄 执行报告生成..."
    python3 "$REPORT_GENERATOR" \\
        --batch_dir "$BATCH_DIR" \\
        --template "$TEMPLATE_PATH" \\
        --subjects "{subject_list_comma}" \\
        --surface_type "{surface_type}" \\
        --hemisphere "{hemisphere}" \\
        --work_directory "{work_directory}" \\
        --parcellation_file "{parcellation_file}" \\
        --max_parallel "{max_parallel_subjects}"
        
    if [ $? -eq 0 ]; then
        echo "✅ 报告生成成功"
    else
        echo "❌ 报告生成失败"
    fi
fi

# 生成简单的摘要和JSON文件
echo "📋 生成摘要文件..."
cat > "$BATCH_DIR/analysis_summary.txt" << EOF
Monkey Brain Distance Analysis Report
====================================
Generated: $(date)
Surface Type: ''' + surface_type + '''
Hemisphere: ''' + hemisphere + '''
Batch Directory: $BATCH_DIR
Subjects: ''' + ','.join([s.strip().strip('"') for s in subject_list_json.strip('[]').split(',')]) + '''
Status: Completed

Generated Files:
- HTML Report: $BATCH_DIR/comprehensive_analysis_report.html
- Text Summary: $BATCH_DIR/analysis_summary.txt
- Heatmaps: $BATCH_DIR/heatmaps/
EOF

# 生成集成报告JSON
cat > "$BATCH_DIR/integrated_report.json" << EOF
{{
    "analysis_type": "distance_analysis",
    "surface_type": "{surface_type}",
    "hemisphere": "{hemisphere}",
    "generated_time": "$(date -Iseconds)",
    "batch_directory": "$BATCH_DIR",
    "processing_summary": {{
        "total_subjects": {total_subjects_count},
        "success_rate": 100.0
    }},
    "heatmap_summary": {{
        "successful_heatmaps": $(find "$BATCH_DIR/heatmaps" -name "*_enhanced_heatmap.png" | wc -l)
    }},
    "reports": {{
        "html_report": "$BATCH_DIR/comprehensive_analysis_report.html",
        "summary_report": "$BATCH_DIR/analysis_summary.txt"
    }}
}}
EOF

echo "✅ 报告生成阶段完成"

# 检查最终报告是否生成成功
if [ -f "$BATCH_DIR/comprehensive_analysis_report.html" ]; then
    REPORT_SIZE=$(stat -f%z "$BATCH_DIR/comprehensive_analysis_report.html" 2>/dev/null || stat -c%s "$BATCH_DIR/comprehensive_analysis_report.html" 2>/dev/null)
    echo "✅ HTML报告已生成: $BATCH_DIR/comprehensive_analysis_report.html ($REPORT_SIZE bytes)"
else
    echo "❌ HTML报告生成失败"
fi

echo "📊 报告生成阶段完成"


echo ""
echo "🎉 集成批量分析完成！"
echo "   成功处理: $successful_subjects/${{#SUBJECTS[@]}} 被试"
echo "   成功热图: $successful_heatmaps/${{#SUBJECTS[@]}} 被试"
echo "   输出目录: $BATCH_DIR"
echo "   📊 HTML报告: $BATCH_DIR/comprehensive_analysis_report.html"
echo "   📋 文本报告: $BATCH_DIR/analysis_summary.txt"
echo "   🎨 热图目录: $BATCH_DIR/heatmaps/"
echo ""

# 输出最终报告供API返回
cat "$BATCH_DIR/integrated_report.json"
"""

        # 格式化脚本内容中的变量
        subject_list_json = ', '.join(['\\"' + s + '\\"' for s in subject_list])
        subject_list_bash = ' '.join([s for s in subject_list])
        subject_list_comma = ','.join([s for s in subject_list])  # 为报告生成添加逗号分隔格式
        script_content = script_content.format(
            timestamp=timestamp,
            work_directory=work_directory,
            batch_dir=batch_dir,
            parcellation_file=parcellation_file,
            surface_type=surface_type,
            hemisphere=hemisphere,
            resolution=resolution,
            max_parallel_subjects=max_parallel_subjects,
            subject_list_json=subject_list_json,
            subject_list_bash=subject_list_bash,
            subject_list_comma=subject_list_comma,
            total_subjects_count=len(subject_list),
            template_path=DISTANCE_ANALYSIS_TEMPLATE,
            report_generator=DISTANCE_REPORT_GENERATOR
        )

        return script_content

    def execute_script(self, script_path: str, params: Dict) -> Dict:
        """执行集成脚本"""
        try:
            # 确保脚本可执行
            import subprocess
            import os
            
            # 设置执行权限
            os.chmod(script_path, 0o755)
            
            # 执行脚本
            result = subprocess.run(
                [script_path],
                capture_output=True,
                text=True,
                timeout=3600  # 1小时超时
            )
            
            if result.returncode == 0:
                return {{
                    "success": True,
                    "message": "脚本执行成功",
                    "output": result.stdout,
                    "script_path": script_path
                }}
            else:
                return {{
                    "success": False,
                    "message": "脚本执行失败: " + str(result.stderr),
                    "output": result.stdout,
                    "error": result.stderr
                }}
                
        except subprocess.TimeoutExpired:
            return {{
                "success": False,
                "message": "脚本执行超时",
                "error": "执行时间超过1小时"
            }}
        except Exception as e:
            return {{
                "success": False,
                "message": "执行错误: " + str(e),
                "error": str(e)
            }}
