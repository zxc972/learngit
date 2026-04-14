"""
Pipeline工具 - 传统的批处理pipeline工具
"""

from typing import Dict, List
import os
from datetime import datetime
from pathlib import Path

from . import BaseTool, ProcessingStep

class PipelineTool(BaseTool):
    """Pipeline批处理工具"""
    
    def __init__(self):
        super().__init__("pipeline", "1.0.0")
        self.description = "猴脑分割与分析批处理pipeline"
        self.supported_species = ['Macaque', 'Chimpanzee', 'Marmoset']
        self.required_params = [
            'surf_workdir', 'container_path', 'bashroot_path', 
            'species', 'site_name'
        ]
        self.optional_params = [
            'subjects', 'subjid_list', 'processing_steps', 'parallel_jobs',
            'brain_size', 'reference', 'low_res_mesh'
        ]
        
        # 加载处理步骤配置
        self.processing_steps = self._load_processing_steps()
    
    def _load_processing_steps(self) -> Dict[str, ProcessingStep]:
        """加载处理步骤配置"""
        # 这里可以从配置文件加载，现在先硬编码
        steps_config = {
            'preprocess1': {
                'name': 'T1图像预处理',
                'script': 'Preprocess_1.sh',
                'description': 'T1图像预处理和去噪',
                'requires_gpu': False,
                'command_template': """singularity exec -B {surf_workdir}:{surf_workdir} {container_path} bash {bashroot_path}/Preprocess_1.sh \\
        -t1_path {surf_workdir}/{subjid}/T1 \\
        -out_path {surf_workdir}/{subjid} \\
        -species {species} \\
        -denoise""",
                'validation_rules': {
                    't1_path_exists': {
                        'type': 'custom',
                        'check': 'lambda params, subjid: Path(params["surf_workdir"]) / subjid / "T1" exists'
                    }
                }
            },
            'preprocess2_brain': {
                'name': '脑组织分割',
                'script': 'Preprocess_2_nnUNet.sh',
                'description': '脑组织分割（nnUNet）',
                'requires_gpu': True,
                'parameters': {'segmentation_type': 'brain'},
                'command_template': """singularity exec --nv -B {surf_workdir}:{surf_workdir} {container_path} bash {bashroot_path}/Preprocess_2_nnUNet.sh \\
        -out_path {surf_workdir}/{subjid} \\
        -site_name {site_name} \\
        -segmentation {segmentation_type} \\
        -clear_tmp"""
            },
            'acpc': {
                'name': 'ACPC对齐',
                'script': 'ACPC_Alignment.sh',
                'description': 'ACPC对齐处理',
                'requires_gpu': False,
                'parameters': {
                    'brain_size': '80',
                    'reference': 'NMT_brain_05.nii.gz'
                },
                'command_template': """singularity exec -B {surf_workdir}:{surf_workdir} {container_path} bash {bashroot_path}/ACPC_Alignment.sh \\
        -out_path {surf_workdir}/{subjid}/ \\
        -brainSize {brain_size} \\
        -species {species} \\
        -reference {reference}"""
            },
            'preprocess2_wm': {
                'name': '白质分割',
                'script': 'Preprocess_2_nnUNet.sh',
                'description': '白质分割（nnUNet）',
                'requires_gpu': True,
                'parameters': {'segmentation_type': 'wm'},
                'command_template': """singularity exec --nv -B {surf_workdir}:{surf_workdir} {container_path} bash {bashroot_path}/Preprocess_2_nnUNet.sh \\
        -out_path {surf_workdir}/{subjid} \\
        -site_name {site_name} \\
        -segmentation {segmentation_type} \\
        -clear_tmp"""
            },
            'preprocess3_1': {
                'name': 'FreeSurfer预处理1',
                'script': 'Preprocess_3_1.sh',
                'description': 'FreeSurfer预处理步骤1',
                'requires_gpu': False,
                'command_template': """singularity exec -B {surf_workdir}:{surf_workdir} {container_path} bash {bashroot_path}/Preprocess_3_1.sh \\
        -id {subjid} \\
        -out_path {surf_workdir}/{subjid} \\
        -species {species}"""
            },
            'preprocess3_2': {
                'name': 'FreeSurfer预处理2',
                'script': 'Preprocess_3_2.sh',
                'description': 'FreeSurfer预处理步骤2',
                'requires_gpu': False,
                'command_template': """singularity exec -B {surf_workdir}:{surf_workdir} {container_path} bash {bashroot_path}/Preprocess_3_2.sh \\
        -id {subjid} \\
        -out_path {surf_workdir}/{subjid}"""
            },
            'rescale': {
                'name': '图像重新缩放',
                'script': 'Rescale.sh',
                'description': '图像重新缩放处理',
                'requires_gpu': False,
                'command_template': """singularity exec -B {surf_workdir}:{surf_workdir} {container_path} bash {bashroot_path}/Rescale.sh \\
        -id {subjid} \\
        -out_path {surf_workdir}/{subjid} \\
        -species {species}"""
            },
            'freesurfer2caret': {
                'name': 'FreeSurfer转Caret',
                'script': 'Freesurfer2CaretandRegister.sh',
                'description': 'FreeSurfer到Caret格式转换',
                'requires_gpu': False,
                'parameters': {'low_res_mesh': '32'},
                'command_template': """singularity exec -B {surf_workdir}:{surf_workdir} {container_path} bash {bashroot_path}/Freesurfer2CaretandRegister.sh \\
        -id {subjid} \\
        -out_path {surf_workdir}/{subjid} \\
        -LowResMesh {low_res_mesh} \\
        -species {species}"""
            }
        }
        
        return {
            step_id: ProcessingStep(step_id, config)
            for step_id, config in steps_config.items()
        }
    
    def validate_params(self, params: Dict) -> tuple[bool, str]:
        """验证输入参数"""
        # 检查必需参数
        for field in self.required_params:
            if field not in params or not params[field]:
                return False, f"Missing required field: {field}"
        
        # 验证路径存在性
        paths_to_check = {
            'surf_workdir': params['surf_workdir'],
            'container_path': params['container_path'], 
            'bashroot_path': params['bashroot_path']
        }
        
        for name, path in paths_to_check.items():
            if not os.path.exists(path):
                return False, f"Path not found: {name} = {path}"
        
        # 验证物种
        if params['species'] not in self.supported_species:
            return False, f"Unsupported species: {params['species']}. Supported: {self.supported_species}"
        
        # 验证被试列表
        if 'subjid_list' in params:
            subjid_file = params['subjid_list']
            if subjid_file and not os.path.exists(subjid_file):
                return False, f"Subject list file not found: {subjid_file}"
        
        # 验证处理步骤
        if 'processing_steps' in params:
            steps = params['processing_steps']
            if not isinstance(steps, list) or not steps:
                return False, "processing_steps must be a non-empty list"
            
            for step in steps:
                if step not in self.processing_steps:
                    return False, f"Unknown processing step: {step}. Available: {list(self.processing_steps.keys())}"
        
        return True, "OK"
    
    def load_subjects(self, subjid_list_file: str) -> List[str]:
        """从文件加载被试列表"""
        if not subjid_list_file or not os.path.exists(subjid_list_file):
            return []
        
        subjects = []
        with open(subjid_list_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    subjects.append(line)
        return subjects
    
    def generate_script(self, params: Dict) -> str:
        """生成完整的批处理脚本"""
        # 加载被试列表
        subjects = []
        if 'subjid_list' in params and params['subjid_list']:
            subjects = self.load_subjects(params['subjid_list'])
        elif 'subjects' in params and params['subjects']:
            subjects = params['subjects']
        else:
            return "Error: No subjects specified"
        
        if not subjects:
            return "Error: No valid subjects found"
        
        # 获取处理步骤
        steps = params.get('processing_steps', list(self.processing_steps.keys()))
        
        # 验证处理步骤
        for step in steps:
            if step not in self.processing_steps:
                return f"Error: Unknown processing step: {step}"
        
        # 生成脚本头部
        script_lines = [
            "#!/bin/bash",
            "",
            "# Auto-generated monkey brain processing script",
            f"# Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"# Tool: {self.name} v{self.version}",
            "",
            "# 设置路径变量",
            f"surf={params['surf_workdir']}",
            f"container={params['container_path']}",
            f"bashroot={params['bashroot_path']}",
            "subjids=(" + ' '.join([f'"{s}"' for s in subjects]) + ")",
            "",
            "# 被试处理流程函数",
            "process_subject() {",
            "    subjid=$1",
            "    log_file=\"$surf/$subjid/preprocess_log.txt\"",
            "",
            "    echo \"🚀 开始处理被试 $subjid\" | tee \"$log_file\"",
            ""
        ]
        
        # 生成处理步骤
        for i, step_id in enumerate(steps, 1):
            step = self.processing_steps[step_id]
            
            # 合并参数（全局参数 + 步骤特定参数）
            step_params = {**params, **step.parameters}
            
            # 生成命令
            step_command = step.generate_command(step_params, '$subjid')
            
            script_lines.extend([
                f"    {step_command} 2>&1 | tee -a \"$log_file\"",
                f"    echo \"✅ [$subjid] Step {i} ({step_id}: {step.name}) 完成\" | tee -a \"$log_file\"",
                ""
            ])
        
        # 脚本尾部
        script_lines.extend([
            "    echo \"🎉 [$subjid] 处理流程完成\" | tee -a \"$log_file\"",
            "}",
            "",
            "export -f process_subject",
            "export surf container bashroot",
            "",
            f"# 并发运行 {params.get('parallel_jobs', 3)} 个任务",
            f"parallel -j {params.get('parallel_jobs', 3)} process_subject ::: \"${{subjids[@]}}\"",
            ""
        ])
        
        return '\n'.join(script_lines)
    
    def get_parameter_schema(self) -> Dict:
        """获取参数模式定义"""
        return {
            "type": "object",
            "properties": {
                "surf_workdir": {
                    "type": "string",
                    "description": "工作目录路径",
                    "required": True
                },
                "container_path": {
                    "type": "string", 
                    "description": "Singularity容器路径",
                    "required": True
                },
                "bashroot_path": {
                    "type": "string",
                    "description": "脚本根目录路径", 
                    "required": True
                },
                "species": {
                    "type": "string",
                    "enum": self.supported_species,
                    "description": "物种类型",
                    "required": True
                },
                "site_name": {
                    "type": "string",
                    "description": "站点名称",
                    "required": True
                },
                "subjects": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "被试列表"
                },
                "subjid_list": {
                    "type": "string",
                    "description": "被试列表文件路径"
                },
                "processing_steps": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": list(self.processing_steps.keys())
                    },
                    "description": "处理步骤列表"
                },
                "parallel_jobs": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 20,
                    "default": 3,
                    "description": "并行任务数量"
                },
                "brain_size": {
                    "type": "string",
                    "default": "80",
                    "description": "脑尺寸参数"
                },
                "reference": {
                    "type": "string", 
                    "default": "NMT_brain_05.nii.gz",
                    "description": "参考图像"
                },
                "low_res_mesh": {
                    "type": "string",
                    "default": "32",
                    "description": "低分辨率网格参数"
                }
            },
            "required": self.required_params
        }
    
    def get_processing_steps_info(self) -> Dict:
        """获取处理步骤信息"""
        return {
            step_id: {
                "name": step.name,
                "description": step.description,
                "requires_gpu": step.requires_gpu,
                "dependencies": step.dependencies,
                "parameters": step.parameters
            }
            for step_id, step in self.processing_steps.items()
        }
