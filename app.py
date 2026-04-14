#!/usr/bin/env python3
"""
Monkey Brain Segmentation Pipeline HTTP API Server for Dify Integration
可扩展的分析工具集成平台
"""

from flask import Flask, request, jsonify, send_file, render_template_string, send_from_directory

# 导入配置系统
try:
    from config_local import *
    print("✅ 使用本地配置文件")
except ImportError:
    try:
        from config_template import *
        print("⚠️  使用模板配置文件")
    except ImportError:
        print("❌ 配置文件不存在，使用内置默认配置")
        SERVER_PORT = 8000
        SERVER_HOST = '0.0.0.0'
        DEBUG_MODE = False
        SCRIPTS_EXEC_DIR = '/tmp/monkey_brain_scripts'
        LOG_DIR = '/tmp/monkey_brain_logs'
from flask_cors import CORS
import os
import subprocess
import threading
import uuid
import json
import time
from datetime import datetime
from typing import Dict, List, Optional
import logging
from pathlib import Path

# 导入工具模块
from tools import tool_registry, BaseTool
from tools.pipeline_tool import PipelineTool
from tools.parallel_batch_distance_tool import ParallelBatchDistanceCalculationTool
from tools.report_generation_tool import ReportGenerationTool

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# 全局变量存储任务状态
job_status: Dict[str, Dict] = {}
job_lock = threading.Lock()

def init_tools():
    """初始化工具注册表"""
    # 注册核心工具
    tool_registry.register_tool(PipelineTool())  # 原有的pipeline工具
    tool_registry.register_tool(ParallelBatchDistanceCalculationTool())  # 并行距离计算工具 v2.0
    tool_registry.register_tool(ReportGenerationTool())  # 报告生成工具
    
    logger.info(f"Initialized {len(tool_registry.list_tools())} tools: {tool_registry.list_tools()}")

def execute_script_async(job_id: str, script_path: str, params: Dict):
    """异步执行脚本"""
    try:
        with job_lock:
            job_status[job_id]['status'] = 'running'
            job_status[job_id]['start_time'] = datetime.now().isoformat()
        
        logger.info(f"Starting job {job_id}: {script_path}")
        
        # 根据脚本类型选择执行方式
        if script_path.endswith('.py'):
            # Python脚本
            cmd = ['python3', script_path]
        else:
            # Bash脚本
            cmd = ['bash', script_path]
        
        # 执行脚本
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=os.path.dirname(script_path)
        )
        
        output_lines = []
        for line in iter(process.stdout.readline, ''):
            output_lines.append(line.rstrip())
            # 更新实时输出
            with job_lock:
                job_status[job_id]['output'] = '\n'.join(output_lines[-100:])  # 只保留最后100行
        
        process.wait()
        
        with job_lock:
            job_status[job_id]['status'] = 'completed' if process.returncode == 0 else 'failed'
            job_status[job_id]['end_time'] = datetime.now().isoformat()
            job_status[job_id]['return_code'] = process.returncode
            job_status[job_id]['output'] = '\n'.join(output_lines)
        
        logger.info(f"Job {job_id} completed with return code {process.returncode}")
        
    except Exception as e:
        logger.error(f"Job {job_id} failed with exception: {str(e)}")
        with job_lock:
            job_status[job_id]['status'] = 'failed'
            job_status[job_id]['error'] = str(e)
            job_status[job_id]['end_time'] = datetime.now().isoformat()

@app.route('/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'active_jobs': len([j for j in job_status.values() if j['status'] == 'running']),
        'available_tools': tool_registry.list_tools()
    })

@app.route('/tools', methods=['GET'])
def get_tools():
    """获取所有可用工具接口"""
    return jsonify({
        'tools': tool_registry.get_all_tools_info(),
        'total_tools': len(tool_registry.list_tools())
    })

@app.route('/tools/<tool_name>', methods=['GET'])
def get_tool_info(tool_name: str):
    """获取特定工具信息接口"""
    tool = tool_registry.get_tool(tool_name)
    if not tool:
        return jsonify({'error': f'Tool not found: {tool_name}'}), 404
    
    return jsonify(tool.get_info())

@app.route('/tools/<tool_name>/schema', methods=['GET'])
def get_tool_schema(tool_name: str):
    """获取工具参数模式接口"""
    tool = tool_registry.get_tool(tool_name)
    if not tool:
        return jsonify({'error': f'Tool not found: {tool_name}'}), 404
    
    return jsonify({
        'tool_name': tool_name,
        'parameter_schema': tool.get_parameter_schema()
    })

@app.route('/generate_script', methods=['POST'])
def generate_script():
    """生成脚本接口（支持多种工具）"""
    try:
        params = request.get_json()
        if not params:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        # 获取工具名称
        tool_name = params.get('tool_name', 'pipeline')  # 默认使用pipeline工具
        tool = tool_registry.get_tool(tool_name)
        
        if not tool:
            return jsonify({'error': f'Tool not found: {tool_name}'}), 400
        
        # 获取工具参数 - 支持两种格式:
        # 1. 嵌套格式: {"tool_name": "pipeline", "parameters": {...}}
        # 2. 平铺格式: {"tool_name": "pipeline", "surf_workdir": "...", ...}
        if 'parameters' in params:
            tool_params = params['parameters']
        else:
            # 平铺格式：复制除tool_name外的所有参数
            tool_params = {k: v for k, v in params.items() if k != 'tool_name'}
        
        # 验证参数
        is_valid, message = tool.validate_params(tool_params)
        if not is_valid:
            return jsonify({'error': message}), 400
        
        # 生成脚本
        script_content = tool.generate_script(tool_params)
        
        if script_content.startswith('Error:'):
            return jsonify({'error': script_content}), 400
        
        # 确定脚本文件扩展名（目前只支持bash脚本，后续可扩展）
        script_ext = '.sh'
        
        # 生成脚本文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        script_filename = f"{tool_name}_{timestamp}{script_ext}"
        script_path = os.path.join(SCRIPTS_EXEC_DIR, script_filename)
        
        # 保存脚本文件
        with open(script_path, 'w') as f:
            f.write(script_content)
        os.chmod(script_path, 0o755)
        
        return jsonify({
            'success': True,
            'tool_name': tool_name,
            'script_content': script_content,
            'script_path': script_path,
            'script_filename': script_filename,
            'parameters_used': params,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error generating script: {str(e)}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/execute_script', methods=['POST'])
def execute_script():
    """执行脚本接口"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        script_path = data.get('script_path')
        if not script_path or not os.path.exists(script_path):
            return jsonify({'error': 'Script file not found'}), 400
        
        # 生成任务ID
        job_id = str(uuid.uuid4())
        
        # 初始化任务状态
        with job_lock:
            job_status[job_id] = {
                'status': 'pending',
                'script_path': script_path,
                'created_time': datetime.now().isoformat(),
                'output': '',
                'parameters': data.get('parameters', {}),
                'tool_name': data.get('tool_name', 'unknown')
            }
        
        # 启动异步执行
        thread = threading.Thread(
            target=execute_script_async,
            args=(job_id, script_path, data.get('parameters', {}))
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'job_id': job_id,
            'message': 'Script execution started',
            'status_url': f'/job_status/{job_id}'
        })
        
    except Exception as e:
        logger.error(f"Error executing script: {str(e)}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/job_status/<job_id>', methods=['GET'])
def get_job_status(job_id: str):
    """获取任务状态接口"""
    with job_lock:
        if job_id not in job_status:
            return jsonify({'error': 'Job not found'}), 404
        
        return jsonify({
            'job_id': job_id,
            **job_status[job_id]
        })

@app.route('/list_jobs', methods=['GET'])
def list_jobs():
    """列出所有任务接口"""
    with job_lock:
        return jsonify({
            'jobs': [
                {'job_id': job_id, **info}
                for job_id, info in job_status.items()
            ],
            'total_jobs': len(job_status)
        })

@app.route('/cancel_job/<job_id>', methods=['POST'])
def cancel_job(job_id: str):
    """取消任务接口"""
    with job_lock:
        if job_id not in job_status:
            return jsonify({'error': 'Job not found'}), 404
        
        if job_status[job_id]['status'] not in ['pending', 'running']:
            return jsonify({'error': 'Job cannot be cancelled'}), 400
        
        job_status[job_id]['status'] = 'cancelled'
        job_status[job_id]['end_time'] = datetime.now().isoformat()
        
        return jsonify({
            'success': True,
            'message': f'Job {job_id} cancelled'
        })

# 兼容性接口 - 保持与v1的兼容
@app.route('/available_steps', methods=['GET'])
def get_available_steps():
    """获取可用处理步骤接口（Pipeline工具兼容性）"""
    pipeline_tool = tool_registry.get_tool('pipeline')
    if not pipeline_tool:
        return jsonify({'error': 'Pipeline tool not found'}), 500
    
    return jsonify({
        'available_steps': list(pipeline_tool.processing_steps.keys()),
        'step_descriptions': {
            step_id: step.description 
            for step_id, step in pipeline_tool.processing_steps.items()
        },
        'processing_steps_info': pipeline_tool.get_processing_steps_info()
    })

# 新增工具特定接口
@app.route('/tools/pipeline/steps', methods=['GET'])
def get_pipeline_steps():
    """获取Pipeline工具的处理步骤"""
    pipeline_tool = tool_registry.get_tool('pipeline')
    if not pipeline_tool:
        return jsonify({'error': 'Pipeline tool not found'}), 500
    
    return jsonify(pipeline_tool.get_processing_steps_info())

@app.route('/calculate_distance', methods=['POST'])
def calculate_distance():
    """单个被试距离计算接口"""
    try:
        params = request.get_json()
        if not params:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        # 必需参数
        surface_file = params.get('surface_file')
        parcellation_file = params.get('parcellation_file')
        output_dir = params.get('output_directory') or params.get('output_dir')  # 兼容两种参数名
        
        if not all([surface_file, parcellation_file, output_dir]):
            return jsonify({'error': 'Missing required parameters: surface_file, parcellation_file, output_directory'}), 400
        
        # 调用原始距离计算脚本
        from pathlib import Path
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 提取被试ID
        surface_path = Path(surface_file)
        subject_id = surface_path.name.split('.')[0]
        
        # 构建命令
        euclidean_output = output_path / f"{subject_id}_euclidean_distance.csv"
        geodesic_output = output_path / f"{subject_id}_geodesic_distance.csv"
        
        cmd = [
            'python3', 
            '/home/xuancheng/monkey_tools/individual_distance_calculate/Individual_Distance_Calculate.py',
            '--surface', surface_file,
            '--parcellation', parcellation_file,
            '--output_euclidean', str(euclidean_output),
            '--output_geodesic', str(geodesic_output)
        ]
        
        # 执行命令 (增加超时到30分钟，适应复杂分区文件)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        
        if result.returncode == 0:
            # 检查输出文件
            euclidean_file = output_path / f"{subject_id}_euclidean_distance.csv"
            geodesic_file = output_path / f"{subject_id}_geodesic_distance.csv"
            
            return jsonify({
                'success': True,
                'message': 'Distance calculation completed successfully',
                'subject_id': subject_id,
                'output_files': {
                    'euclidean_distance': str(euclidean_file) if euclidean_file.exists() else None,
                    'geodesic_distance': str(geodesic_file) if geodesic_file.exists() else None
                },
                'processing_info': {
                    'surface_file': surface_file,
                    'parcellation_file': parcellation_file,
                    'output_directory': output_dir
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Distance calculation failed',
                'stderr': result.stderr,
                'stdout': result.stdout
            }), 500
            
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Distance calculation timed out'}), 500
    except Exception as e:
        logger.error(f"Error in distance calculation: {str(e)}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/distance_analysis', methods=['POST'])
def distance_analysis():
    """核心距离分析接口 - 并行计算+热图生成+报告"""
    try:
        params = request.get_json()
        if not params:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        # 使用并行批量距离计算工具
        tool = tool_registry.get_tool('parallel_batch_distance')
        if not tool:
            return jsonify({'error': 'Parallel batch distance calculation tool not found'}), 500
        
        # 验证参数
        is_valid, message = tool.validate_params(params)
        if not is_valid:
            return jsonify({'error': message}), 400
        
        # 生成脚本
        script_content = tool.generate_script(params)
        
        # 创建任务
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        job_id = f"distance_analysis_{timestamp}"
        
        script_dir = Path(SCRIPTS_EXEC_DIR)
        script_dir.mkdir(exist_ok=True)
        script_path = script_dir / f"{job_id}.sh"
        
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        script_path.chmod(0o755)
        
        # 初始化任务状态
        with job_lock:
            job_status[job_id] = {
                'status': 'processing',
                'created_time': datetime.now().isoformat(),
                'script_path': str(script_path),
                'params': params
            }
        
        # 启动异步执行
        import threading
        thread = threading.Thread(target=execute_script_async, args=(job_id, str(script_path), params))
        thread.daemon = True
        thread.start()
        
        max_parallel = params.get('max_parallel_subjects', 2)
        subject_count = len(params.get('subject_list', []))
        estimated_time_per_subject = 2  # 假设每个被试2分钟
        estimated_total_minutes = (subject_count * estimated_time_per_subject) / max_parallel
        
        return jsonify({
            'success': True,
            'message': 'Distance analysis started (parallel computing + heatmaps + report)',
            'job_id': job_id,
            'status': 'processing',
            'analysis_config': {
                'subjects': subject_count,
                'max_parallel_subjects': max_parallel,
                'surface_type': params.get('surface_type'),
                'includes_heatmaps': True,
                'includes_report': True
            },
            'estimated_time': f"约 {estimated_total_minutes:.1f} 分钟",
            'monitor_url': f'/job_status/{job_id}'
        })
        
    except Exception as e:
        logger.error(f"Error in distance analysis: {str(e)}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

# 其他端点已删除，使用统一的 /distance_analysis 端点

@app.route('/preview_batch_subjects', methods=['POST'])
def preview_batch_subjects():
    """预览批量处理将要处理的被试列表"""
    try:
        params = request.get_json()
        if not params:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        work_directory = params.get('work_directory')
        if not work_directory or not Path(work_directory).exists():
            return jsonify({'error': f'Work directory not found: {work_directory}'}), 400
        
        # 获取批量工具进行预览
        tool = tool_registry.get_tool('enhanced_batch_distance')
        if not tool:
            return jsonify({'error': 'Enhanced batch distance calculation tool not found'}), 500
        
        # 查找被试
        subjects = tool._find_subjects(work_directory, params.get('subject_list'))
        
        # 检查每个被试的文件
        subject_info = []
        surface_type = params.get('surface_type', 'midthickness')
        
        # 从分区文件解析信息
        parcellation_info = tool._parse_parcellation_info(params.get('parcellation_file', ''))
        hemisphere = parcellation_info.get('hemisphere', 'L')
        resolution = parcellation_info.get('resolution', '32k')
        
        for subject in subjects:
            surface_file = tool._find_surface_file(
                work_directory, subject, surface_type, hemisphere, resolution
            )
            subject_info.append({
                'subject_id': subject,
                'surface_file': surface_file,
                'has_surface_file': surface_file is not None
            })
        
        # 统计
        total_subjects = len(subjects)
        valid_subjects = sum(1 for info in subject_info if info['has_surface_file'])
        
        return jsonify({
            'success': True,
            'work_directory': work_directory,
            'total_subjects': total_subjects,
            'valid_subjects': valid_subjects,
            'invalid_subjects': total_subjects - valid_subjects,
            'subjects': subject_info,
            'parameters': {
                'surface_type': surface_type,
                'hemisphere': hemisphere,
                'resolution': resolution
            }
        })
        
    except Exception as e:
        logger.error(f"Error in preview batch subjects: {str(e)}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/batch_generate', methods=['POST'])
def batch_generate():
    """批量生成脚本接口"""
    try:
        data = request.get_json()
        if not data or 'requests' not in data:
            return jsonify({'error': 'No batch requests provided'}), 400
        
        results = []
        for i, req in enumerate(data['requests']):
            try:
                tool_name = req.get('tool_name', 'pipeline')
                tool = tool_registry.get_tool(tool_name)
                
                if not tool:
                    results.append({
                        'index': i,
                        'success': False,
                        'error': f'Tool not found: {tool_name}'
                    })
                    continue
                
                # 验证参数
                is_valid, message = tool.validate_params(req)
                if not is_valid:
                    results.append({
                        'index': i,
                        'success': False,
                        'error': message
                    })
                    continue
                
                # 生成脚本
                script_content = tool.generate_script(req)
                if script_content.startswith('Error:'):
                    results.append({
                        'index': i,
                        'success': False,
                        'error': script_content
                    })
                    continue
                
                # 保存脚本
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                script_ext = '.sh'  # 目前只支持bash脚本
                script_filename = f"{tool_name}_{i}_{timestamp}{script_ext}"
                script_path = os.path.join(SCRIPTS_EXEC_DIR, script_filename)
                
                with open(script_path, 'w') as f:
                    f.write(script_content)
                os.chmod(script_path, 0o755)
                
                results.append({
                    'index': i,
                    'success': True,
                    'tool_name': tool_name,
                    'script_path': script_path,
                    'script_filename': script_filename
                })
                
            except Exception as e:
                results.append({
                    'index': i,
                    'success': False,
                    'error': str(e)
                })
        
        return jsonify({
            'success': True,
            'results': results,
            'total_requests': len(data['requests']),
            'successful_requests': len([r for r in results if r['success']])
        })
        
    except Exception as e:
        logger.error(f"Error in batch generation: {str(e)}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

# =============================================================================
# 报告查看相关端点
# =============================================================================

@app.route('/reports')
def list_reports():
    """列出所有可用的分析报告"""
    try:
        reports = []
        # 扫描工作目录中的批量分析结果
        work_dirs = [
            "/data/xuancheng/ION_test_monkey",
            "/data/xuancheng/KM_test_monkey"
        ]
        
        for work_dir in work_dirs:
            if not os.path.exists(work_dir):
                continue
                
            # 查找所有批量分析目录
            for item in os.listdir(work_dir):
                if item.startswith('batch_distance_'):
                    batch_dir = os.path.join(work_dir, item)
                    if os.path.isdir(batch_dir):
                        # 检查是否有HTML报告
                        html_report = os.path.join(batch_dir, 'comprehensive_analysis_report.html')
                        if os.path.exists(html_report):
                            # 解析批量目录名获取信息
                            parts = item.split('_')
                            if len(parts) >= 4:
                                surface_type = parts[2]
                                hemisphere = parts[3]
                                timestamp = '_'.join(parts[4:]) if len(parts) > 4 else "unknown"
                                
                                # 获取文件修改时间
                                mtime = os.path.getmtime(html_report)
                                created_time = datetime.fromtimestamp(mtime)
                                
                                # 读取统计信息
                                stats_info = {}
                                try:
                                    integrated_json = os.path.join(batch_dir, 'integrated_report.json')
                                    if os.path.exists(integrated_json):
                                        with open(integrated_json, 'r') as f:
                                            stats_info = json.load(f)
                                except:
                                    pass
                                
                                reports.append({
                                    'id': item,
                                    'title': f"Distance Analysis - {surface_type.title()} {hemisphere.upper()}",
                                    'surface_type': surface_type,
                                    'hemisphere': hemisphere,
                                    'timestamp': timestamp,
                                    'created_time': created_time.isoformat(),
                                    'created_time_readable': created_time.strftime("%Y-%m-%d %H:%M:%S"),
                                    'work_directory': work_dir,
                                    'batch_directory': batch_dir,
                                    'html_report': html_report,
                                    'stats': stats_info
                                })
        
        # 按创建时间降序排序
        reports.sort(key=lambda x: x['created_time'], reverse=True)
        
        # 生成报告列表页面HTML
        html_template = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Monkey Brain Analysis Reports</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .header {
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }
        .header h1 {
            font-size: 2.5em;
            margin: 0;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .header p {
            font-size: 1.2em;
            opacity: 0.9;
            margin: 10px 0;
        }
        .reports-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
            gap: 20px;
        }
        .report-card {
            background: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 8px 25px rgba(0,0,0,0.15);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            border: 1px solid #e1e8ed;
        }
        .report-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 12px 35px rgba(0,0,0,0.2);
        }
        .report-header {
            display: flex;
            align-items: center;
            margin-bottom: 15px;
        }
        .report-icon {
            font-size: 2.5em;
            margin-right: 15px;
        }
        .report-title {
            font-size: 1.3em;
            font-weight: bold;
            color: #333;
            margin: 0;
        }
        .report-details {
            color: #666;
            margin-bottom: 15px;
            line-height: 1.6;
        }
        .report-stats {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 15px;
            border-left: 4px solid #007bff;
        }
        .stat-item {
            display: inline-block;
            margin-right: 20px;
            margin-bottom: 5px;
        }
        .stat-label {
            font-weight: bold;
            color: #555;
        }
        .stat-value {
            color: #007bff;
            font-weight: bold;
        }
        .view-button {
            background: linear-gradient(135deg, #007bff, #0056b3);
            color: white;
            padding: 12px 25px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 1em;
            font-weight: bold;
            text-decoration: none;
            display: inline-block;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(0,123,255,0.3);
        }
        .view-button:hover {
            background: linear-gradient(135deg, #0056b3, #004085);
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0,123,255,0.4);
        }
        .empty-state {
            text-align: center;
            color: white;
            padding: 60px 20px;
        }
        .empty-state h2 {
            font-size: 2em;
            margin-bottom: 10px;
        }
        .refresh-button {
            background: rgba(255,255,255,0.2);
            color: white;
            border: 2px solid white;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            margin-top: 20px;
            text-decoration: none;
            display: inline-block;
            transition: all 0.3s ease;
        }
        .refresh-button:hover {
            background: white;
            color: #667eea;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧠 Monkey Brain Analysis Reports</h1>
            <p>View and explore your distance analysis results</p>
        </div>
        
        {% if reports %}
        <div class="reports-grid">
            {% for report in reports %}
            <div class="report-card">
                <div class="report-header">
                    <div class="report-icon">📊</div>
                    <div>
                        <h3 class="report-title">{{ report.title }}</h3>
                    </div>
                </div>
                
                <div class="report-details">
                    <strong>Created:</strong> {{ report.created_time_readable }}<br>
                    <strong>Surface:</strong> {{ report.surface_type.title() }} ({{ report.hemisphere.upper() }})<br>
                    <strong>Timestamp:</strong> {{ report.timestamp }}
                </div>
                
                {% if report.stats %}
                <div class="report-stats">
                    {% if report.stats.processing_summary %}
                    <div class="stat-item">
                        <span class="stat-label">Subjects:</span>
                        <span class="stat-value">{{ report.stats.processing_summary.total_subjects }}</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Success Rate:</span>
                        <span class="stat-value">{{ "%.1f"|format(report.stats.processing_summary.success_rate) }}%</span>
                    </div>
                    {% endif %}
                    {% if report.stats.heatmap_summary %}
                    <div class="stat-item">
                        <span class="stat-label">Heatmaps:</span>
                        <span class="stat-value">{{ report.stats.heatmap_summary.successful_heatmaps }}</span>
                    </div>
                    {% endif %}
                </div>
                {% endif %}
                
                <a href="/reports/{{ report.id }}" class="view-button">
                    📈 View Report
                </a>
            </div>
            {% endfor %}
        </div>
        {% else %}
        <div class="empty-state">
            <h2>📂 No Reports Found</h2>
            <p>No analysis reports have been generated yet.</p>
            <p>Run a distance analysis to create your first report!</p>
            <a href="/reports" class="refresh-button">🔄 Refresh</a>
        </div>
        {% endif %}
    </div>
</body>
</html>
        '''
        
        return render_template_string(html_template, reports=reports)
        
    except Exception as e:
        logger.error(f"Error listing reports: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/reports/<report_id>')
def view_report(report_id):
    """查看特定的分析报告"""
    try:
        # 查找报告文件
        work_dirs = [
            "/data/xuancheng/ION_test_monkey",
            "/data/xuancheng/KM_test_monkey"
        ]
        
        for work_dir in work_dirs:
            batch_dir = os.path.join(work_dir, report_id)
            if os.path.exists(batch_dir):
                html_report = os.path.join(batch_dir, 'comprehensive_analysis_report.html')
                if os.path.exists(html_report):
                    # 读取HTML文件内容并修改图片路径
                    with open(html_report, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # 修改图片路径，使其指向静态文件服务
                    content = content.replace(
                        'src="heatmaps/',
                        f'src="/reports/{report_id}/heatmaps/'
                    )
                    
                    return content
        
        return "Report not found", 404
        
    except Exception as e:
        logger.error(f"Error viewing report {report_id}: {e}")
        return f"Error loading report: {str(e)}", 500

@app.route('/reports/<report_id>/heatmaps/<filename>')
def serve_heatmap(report_id, filename):
    """提供热图文件服务"""
    try:
        work_dirs = [
            "/data/xuancheng/ION_test_monkey",
            "/data/xuancheng/KM_test_monkey"
        ]
        
        for work_dir in work_dirs:
            batch_dir = os.path.join(work_dir, report_id)
            heatmaps_dir = os.path.join(batch_dir, 'heatmaps')
            if os.path.exists(heatmaps_dir):
                return send_from_directory(heatmaps_dir, filename)
        
        return "File not found", 404
        
    except Exception as e:
        logger.error(f"Error serving heatmap {report_id}/{filename}: {e}")
        return "Error serving file", 500

@app.route('/reports/<report_id>/download')
def download_report(report_id):
    """下载完整的报告包"""
    try:
        work_dirs = [
            "/data/xuancheng/ION_test_monkey",
            "/data/xuancheng/KM_test_monkey"
        ]
        
        for work_dir in work_dirs:
            batch_dir = os.path.join(work_dir, report_id)
            if os.path.exists(batch_dir):
                html_report = os.path.join(batch_dir, 'comprehensive_analysis_report.html')
                if os.path.exists(html_report):
                    return send_file(
                        html_report, 
                        as_attachment=True, 
                        download_name=f'{report_id}_report.html'
                    )
        
        return "Report not found", 404
        
    except Exception as e:
        logger.error(f"Error downloading report {report_id}: {e}")
        return "Error downloading report", 500

if __name__ == '__main__':
    # 初始化工具
    init_tools()
    
    # 确保必要目录存在
    try:
        ensure_directories()
        print("✅ 必要目录已创建")
    except NameError:
        # 如果函数不存在，手动创建目录
        os.makedirs(SCRIPTS_EXEC_DIR, exist_ok=True)
        os.makedirs(LOG_DIR, exist_ok=True)
        print("✅ 基本目录已创建")
    
    # 使用配置系统的端口设置
    port = SERVER_PORT
    debug = DEBUG_MODE
    host = SERVER_HOST
    
    # 打印配置信息
    print("🔧 服务配置:")
    print(f"  🌐 地址: http://{host}:{port}")
    print(f"  📁 脚本目录: {SCRIPTS_EXEC_DIR}")
    print(f"  📊 报告查看器: http://{host}:{port}/reports")
    print(f"  🐛 调试模式: {debug}")
    
    logger.info(f"Starting Monkey Brain Pipeline API Server on port {port}")
    logger.info(f"Available tools: {tool_registry.list_tools()}")
    logger.info(f"Report viewer available at: http://{host}:{port}/reports")
    app.run(host=host, port=port, debug=debug)
