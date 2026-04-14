"""
项目配置模板 - 解决可移植性问题
复制此文件为 config_local.py 并根据您的环境修改配置
"""

import os
from pathlib import Path

# =============================================================================
# 基础路径配置 - 请根据您的环境修改
# =============================================================================

# 当前用户的主目录 (自动检测)
USER_HOME = str(Path.home())

# 项目根目录 (自动检测)
PROJECT_ROOT = str(Path(__file__).parent.absolute())

# =============================================================================
# 服务配置
# =============================================================================

# Flask 服务端口
SERVER_PORT = int(os.environ.get('MONKEY_BRAIN_PORT', 8000))

# Flask 主机地址 (0.0.0.0 允许外部访问, 127.0.0.1 仅本地访问)
SERVER_HOST = os.environ.get('MONKEY_BRAIN_HOST', '0.0.0.0')

# 调试模式
DEBUG_MODE = os.environ.get('MONKEY_BRAIN_DEBUG', 'false').lower() == 'true'

# =============================================================================
# 路径配置 - 请根据您的环境修改这些路径
# =============================================================================

# CYUPS 工具包根目录 (请修改为您的CYUPS安装路径)
DEFAULT_BASHROOT = os.environ.get('CYUPS_HOME', 
                                  os.path.join(USER_HOME, 'CYUPS_HOME-Chimpanzee'))

# 默认容器路径 (请修改为您的容器文件路径)
DEFAULT_CONTAINER = os.environ.get('CONTAINER_PATH', 
                                   '/data/CYUPS_1_3.sif')  # 请修改此路径

# 模板文件路径
TEMPLATE_DIR = os.path.join(PROJECT_ROOT, 'templates')
DISTANCE_ANALYSIS_TEMPLATE = os.path.join(TEMPLATE_DIR, 'distance_analysis_report.html')

# 脚本文件路径
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, 'scripts')
DISTANCE_REPORT_GENERATOR = os.path.join(SCRIPTS_DIR, 'generate_distance_report.py')

# =============================================================================
# 临时目录配置
# =============================================================================

# 临时文件目录
TEMP_DIR = os.environ.get('MONKEY_BRAIN_TEMP', '/tmp')

# 脚本执行目录
SCRIPTS_EXEC_DIR = os.path.join(TEMP_DIR, 'monkey_brain_scripts')

# 日志目录
LOG_DIR = os.environ.get('MONKEY_BRAIN_LOG', os.path.join(TEMP_DIR, 'monkey_brain_logs'))

# =============================================================================
# 默认工作配置 - 可选修改
# =============================================================================

# 默认数据目录 (用于测试，请根据您的数据位置修改)
DEFAULT_DATA_DIR = os.environ.get('MONKEY_BRAIN_DATA', 
                                  '/data')  # 请根据您的数据目录修改

# 默认输出目录
DEFAULT_OUTPUT_DIR = os.environ.get('MONKEY_BRAIN_OUTPUT', 
                                    os.path.join(USER_HOME, 'monkey_brain_results'))

# =============================================================================
# 计算资源配置
# =============================================================================

# 默认最大并行数
DEFAULT_MAX_PARALLEL = int(os.environ.get('MONKEY_BRAIN_MAX_PARALLEL', '2'))

# 默认内存限制 (GB)
DEFAULT_MEMORY_LIMIT = int(os.environ.get('MONKEY_BRAIN_MEMORY_LIMIT', '8'))

# =============================================================================
# 网络和安全配置
# =============================================================================

# 允许的CORS域名 (用于跨域访问)
ALLOWED_ORIGINS = os.environ.get('MONKEY_BRAIN_CORS', '*').split(',')

# API密钥 (可选，用于API访问控制)
API_KEY = os.environ.get('MONKEY_BRAIN_API_KEY', None)

# =============================================================================
# 功能开关
# =============================================================================

# 启用报告查看器
ENABLE_REPORT_VIEWER = os.environ.get('ENABLE_REPORT_VIEWER', 'true').lower() == 'true'

# 启用详细日志
ENABLE_VERBOSE_LOGGING = os.environ.get('ENABLE_VERBOSE_LOGGING', 'false').lower() == 'true'

# 启用性能监控
ENABLE_PERFORMANCE_MONITORING = os.environ.get('ENABLE_PERFORMANCE_MONITORING', 'false').lower() == 'true'

# =============================================================================
# 自动创建必要目录
# =============================================================================

def ensure_directories():
    """确保必要的目录存在"""
    directories = [
        SCRIPTS_EXEC_DIR,
        LOG_DIR,
        DEFAULT_OUTPUT_DIR,
        TEMPLATE_DIR,
        SCRIPTS_DIR
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        # 设置适当的权限
        os.chmod(directory, 0o755)

# =============================================================================
# 配置验证
# =============================================================================

def validate_config():
    """验证配置的有效性"""
    errors = []
    
    # 检查必需的路径
    if not os.path.exists(DEFAULT_BASHROOT):
        errors.append(f"CYUPS工具包路径不存在: {DEFAULT_BASHROOT}")
    
    if not os.path.exists(DEFAULT_CONTAINER):
        errors.append(f"容器文件不存在: {DEFAULT_CONTAINER}")
    
    # 检查端口范围
    if not (1024 <= SERVER_PORT <= 65535):
        errors.append(f"端口号无效: {SERVER_PORT} (应在1024-65535范围内)")
    
    # 检查权限
    try:
        test_file = os.path.join(TEMP_DIR, 'test_permission')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
    except Exception as e:
        errors.append(f"临时目录无写入权限: {TEMP_DIR} ({e})")
    
    return errors

# =============================================================================
# 配置信息显示
# =============================================================================

def print_config_summary():
    """打印配置摘要"""
    print("🔧 Monkey Brain 项目配置:")
    print(f"  📁 项目根目录: {PROJECT_ROOT}")
    print(f"  🏠 用户主目录: {USER_HOME}")
    print(f"  🌐 服务地址: http://{SERVER_HOST}:{SERVER_PORT}")
    print(f"  🔧 CYUPS路径: {DEFAULT_BASHROOT}")
    print(f"  📦 容器路径: {DEFAULT_CONTAINER}")
    print(f"  📂 临时目录: {TEMP_DIR}")
    print(f"  📊 报告查看器: {'启用' if ENABLE_REPORT_VIEWER else '禁用'}")
    
    # 验证配置
    errors = validate_config()
    if errors:
        print("\n❌ 配置验证失败:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("\n✅ 配置验证通过")

if __name__ == '__main__':
    ensure_directories()
    print_config_summary()






