#!/usr/bin/env python3
"""
简化的距离分析报告生成器
使用外部HTML模板，避免在bash脚本中嵌入大量HTML代码
"""

import sys
import os
import json
import glob
from datetime import datetime
import argparse

def load_template(template_path):
    """加载HTML模板"""
    with open(template_path, 'r', encoding='utf-8') as f:
        return f.read()

def generate_subject_result_html(subject_id, stats_file, heatmap_file):
    """生成单个被试的结果HTML"""
    
    # 加载统计数据
    stats = {}
    if os.path.exists(stats_file):
        try:
            with open(stats_file, 'r') as f:
                stats = json.load(f)
        except:
            pass
    
    # 检查热图文件
    heatmap_exists = os.path.exists(heatmap_file)
    heatmap_filename = os.path.basename(heatmap_file) if heatmap_exists else ""
    
    html = f'''
    <div class="subject-card">
        <div class="subject-header">
            {subject_id}
        </div>
        <div class="subject-content">
    '''
    
    if heatmap_exists:
        html += f'''
            <div class="heatmap-container">
                <img src="heatmaps/{heatmap_filename}" alt="{subject_id} Enhanced Heatmap">
                <p><strong>Enhanced Distance Analysis Heatmap</strong></p>
            </div>
        '''
    
    if stats:
        html += '''
            <table class="stats-table">
                <tr><th>Metric</th><th>Euclidean</th><th>Geodesic</th></tr>
        '''
        
        euclidean = stats.get('euclidean_stats', {})
        geodesic = stats.get('geodesic_stats', {})
        
        for metric in ['mean', 'std', 'min', 'max']:
            euc_val = euclidean.get(metric, 'N/A')
            geo_val = geodesic.get(metric, 'N/A')
            if isinstance(euc_val, float):
                euc_val = f"{euc_val:.3f}"
            if isinstance(geo_val, float):
                geo_val = f"{geo_val:.3f}"
            html += f'<tr><td>{metric.title()}</td><td>{euc_val}</td><td>{geo_val}</td></tr>'
        
        # 添加相关性
        correlation = stats.get('correlation', 'N/A')
        if isinstance(correlation, float):
            correlation = f"{correlation:.3f}"
        html += f'<tr><td><strong>Correlation</strong></td><td colspan="2">{correlation}</td></tr>'
        
        html += '</table>'
    
    html += '''
        </div>
    </div>
    '''
    
    return html

def main():
    parser = argparse.ArgumentParser(description='Generate distance analysis report')
    parser.add_argument('--batch_dir', required=True, help='Batch directory path')
    parser.add_argument('--template', required=True, help='HTML template path')
    parser.add_argument('--subjects', required=True, help='Comma-separated subject list')
    parser.add_argument('--surface_type', required=True, help='Surface type')
    parser.add_argument('--hemisphere', required=True, help='Hemisphere')
    parser.add_argument('--work_directory', required=True, help='Work directory')
    parser.add_argument('--parcellation_file', required=True, help='Parcellation file')
    parser.add_argument('--max_parallel', required=True, help='Max parallel subjects')
    
    args = parser.parse_args()
    
    # 加载模板
    template = load_template(args.template)
    
    # 解析被试列表
    subjects = [s.strip() for s in args.subjects.split(',') if s.strip()]
    
    # 生成被试结果HTML
    subject_results_html = ""
    successful_subjects = 0
    
    for subject in subjects:
        stats_file = os.path.join(args.batch_dir, f"{subject}_distance_stats.json")
        heatmap_file = os.path.join(args.batch_dir, "heatmaps", f"{subject}_enhanced_heatmap.png")
        
        subject_results_html += generate_subject_result_html(subject, stats_file, heatmap_file)
        
        # 检查是否成功
        if os.path.exists(stats_file):
            successful_subjects += 1
    
    # 计算统计信息
    total_subjects = len(subjects)
    success_rate = (successful_subjects / total_subjects * 100) if total_subjects > 0 else 0
    
    # 替换模板变量
    html_content = template
    replacements = {
        '{{ANALYSIS_TITLE}}': f"{args.surface_type.title()} Surface - {args.hemisphere.upper()} Hemisphere",
        '{{TOTAL_SUBJECTS}}': str(total_subjects),
        '{{SUCCESSFUL_SUBJECTS}}': str(successful_subjects),
        '{{SUCCESS_RATE}}': f"{success_rate:.1f}",
        '{{PROCESSING_TIME}}': "~2 min",  # 可以后续优化为实际时间
        '{{WORK_DIRECTORY}}': args.work_directory,
        '{{PARCELLATION_FILE}}': os.path.basename(args.parcellation_file),
        '{{SURFACE_TYPE}}': args.surface_type.title(),
        '{{HEMISPHERE}}': args.hemisphere.upper(),
        '{{MAX_PARALLEL}}': args.max_parallel,
        '{{SUBJECT_RESULTS}}': subject_results_html,
        '{{TIMESTAMP}}': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    for placeholder, value in replacements.items():
        html_content = html_content.replace(placeholder, str(value))
    
    # 保存报告
    output_file = os.path.join(args.batch_dir, "comprehensive_analysis_report.html")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"✅ HTML报告已生成: {output_file}")

if __name__ == "__main__":
    main()
