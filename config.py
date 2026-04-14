"""
配置文件 - Monkey Brain Pipeline API Server
"""

import os
from pathlib import Path

class Config:
    """基础配置类"""
    
    # 服务器配置
    HOST = os.environ.get('HOST', '0.0.0.0')
    PORT = int(os.environ.get('PORT', 5000))
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    # 文件路径配置
    TEMP_DIR = os.environ.get('TEMP_DIR', '/tmp')
    SCRIPT_DIR = os.path.join(TEMP_DIR, 'monkey_brain_scripts')
    LOG_DIR = os.environ.get('LOG_DIR', '/tmp/logs')
    
    # 默认路径配置（可被请求参数覆盖）
    DEFAULT_BASHROOT = os.environ.get('DEFAULT_BASHROOT', '/home/xuancheng/CYUPS_HOME-Chimpanzee')
    DEFAULT_CONTAINER = os.environ.get('DEFAULT_CONTAINER', '/data/xuancheng/CYUPS_1_3.sif')
    
    # 任务配置
    MAX_CONCURRENT_JOBS = int(os.environ.get('MAX_CONCURRENT_JOBS', 5))
    MAX_OUTPUT_LINES = int(os.environ.get('MAX_OUTPUT_LINES', 1000))
    JOB_TIMEOUT = int(os.environ.get('JOB_TIMEOUT', 7200))  # 2小时
    
    # 并行处理配置
    DEFAULT_PARALLEL_JOBS = int(os.environ.get('DEFAULT_PARALLEL_JOBS', 3))
    MAX_PARALLEL_JOBS = int(os.environ.get('MAX_PARALLEL_JOBS', 10))
    
    # 物种配置
    SUPPORTED_SPECIES = ['Macaque', 'Chimpanzee', 'Marmoset']
    
    # 处理步骤配置
    PROCESSING_STEPS = {
        'preprocess1': {
            'name': 'T1图像预处理',
            'script': 'Preprocess_1.sh',
            'description': 'T1图像预处理和去噪',
            'requires_gpu': False
        },
        'preprocess2_brain': {
            'name': '脑组织分割',
            'script': 'Preprocess_2_nnUNet.sh',
            'description': '脑组织分割（nnUNet）',
            'requires_gpu': True,
            'segmentation_type': 'brain'
        },
        'acpc': {
            'name': 'ACPC对齐',
            'script': 'ACPC_Alignment.sh',
            'description': 'ACPC对齐处理',
            'requires_gpu': False
        },
        'preprocess2_wm': {
            'name': '白质分割',
            'script': 'Preprocess_2_nnUNet.sh',
            'description': '白质分割（nnUNet）',
            'requires_gpu': True,
            'segmentation_type': 'wm'
        },
        'preprocess3_1': {
            'name': 'FreeSurfer预处理1',
            'script': 'Preprocess_3_1.sh',
            'description': 'FreeSurfer预处理步骤1',
            'requires_gpu': False
        },
        'preprocess3_2': {
            'name': 'FreeSurfer预处理2',
            'script': 'Preprocess_3_2.sh',
            'description': 'FreeSurfer预处理步骤2',
            'requires_gpu': False
        },
        'rescale': {
            'name': '图像重新缩放',
            'script': 'Rescale.sh',
            'description': '图像重新缩放处理',
            'requires_gpu': False
        },
        'freesurfer2caret': {
            'name': 'FreeSurfer转Caret',
            'script': 'Freesurfer2CaretandRegister.sh',
            'description': 'FreeSurfer到Caret格式转换',
            'requires_gpu': False
        }
    }
    
    # 预定义处理流程
    PREDEFINED_PIPELINES = {
        'full_pipeline': {
            'name': '完整处理流程',
            'steps': ['preprocess1', 'preprocess2_brain', 'acpc', 'preprocess2_wm', 
                     'preprocess3_1', 'preprocess3_2', 'rescale', 'freesurfer2caret'],
            'description': '完整的猴脑处理流程'
        },
        'preprocessing_only': {
            'name': '仅预处理',
            'steps': ['preprocess1', 'preprocess2_brain'],
            'description': '只进行基础预处理和脑组织分割'
        },
        'segmentation_pipeline': {
            'name': '分割流程',
            'steps': ['preprocess1', 'preprocess2_brain', 'acpc', 'preprocess2_wm'],
            'description': '预处理和分割流程'
        },
        'surface_pipeline': {
            'name': '表面重建流程',
            'steps': ['preprocess3_1', 'preprocess3_2', 'rescale', 'freesurfer2caret'],
            'description': 'FreeSurfer表面重建流程'
        }
    }
    
    @classmethod
    def init_directories(cls):
        """初始化必要的目录"""
        os.makedirs(cls.SCRIPT_DIR, exist_ok=True)
        os.makedirs(cls.LOG_DIR, exist_ok=True)

class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True
    
class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False
    
class TestingConfig(Config):
    """测试环境配置"""
    DEBUG = True
    TESTING = True

# 配置字典
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

