# 猴脑自动分割与分析 Pipeline

基于 Dify 集成的可扩展猴脑分析工具平台。

## 🚀 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 启动服务器
```bash
python start.py
```

### 3. 测试功能
```bash
cd tests
python test_v2_client.py
```

## 📁 项目结构

```
monkey_brain_segmentation_pipeline/
├── app.py              # 主服务器
├── start.py            # 快速启动脚本
├── config.py           # 配置管理
├── requirements.txt    # 依赖包
├── tools/              # 工具模块
│   ├── __init__.py     # 基础框架
│   └── pipeline_tool.py # Pipeline工具
├── docs/               # 文档
├── examples/           # 示例配置
├── tests/              # 测试文件
└── scripts/            # 辅助脚本
```

## 🔧 主要功能

- ✅ **脚本生成**: 根据参数自动生成批处理脚本
- ✅ **异步执行**: 支持脚本异步执行和状态监控
- ✅ **可扩展架构**: 轻松添加新的分析工具
- ✅ **HTTP API**: 标准REST接口，易于集成
- ✅ **Dify兼容**: 专为Dify Agent设计
- ✅ **距离分析**: 脑区间欧氏距离和测地距离计算
- ✅ **可视化生成**: 自动生成热图和分析图表

## 📝 API 接口

### 基础接口
- `GET /health` - 健康检查
- `GET /tools` - 获取所有工具
- `POST /generate_script` - 生成脚本
- `POST /execute_script` - 执行脚本
- `GET /job_status/{id}` - 查询任务状态

### 使用示例

**Pipeline工具（批处理）：**
```python
import requests

# 生成脚本
params = {
    'tool_name': 'pipeline',
    'surf_workdir': '/path/to/work',
    'container_path': '/path/to/container.sif',
    'bashroot_path': '/path/to/scripts',
    'species': 'Macaque',
    'site_name': 'KM',
    'subjects': ['ION001', 'ION002'],
    'processing_steps': ['preprocess1', 'preprocess2_brain']
}

response = requests.post('http://localhost:8000/generate_script', json=params)
script_info = response.json()

# 执行脚本
exec_response = requests.post('http://localhost:8000/execute_script', 
                             json={'script_path': script_info['script_path']})
job_id = exec_response.json()['job_id']

# 查看状态
status = requests.get(f'http://localhost:8000/job_status/{job_id}').json()
```

**距离计算工具：**
```python
import requests

# 距离分析
params = {
    'tool_name': 'distance_calculation',
    'surface_file': '/data/surface.surf.gii',
    'parcellation_file': '/data/parcellation.dlabel.nii',
    'output_dir': '/results/distance_analysis',
    'generate_visualization': True
}

response = requests.post('http://localhost:8000/generate_script', json=params)
script_info = response.json()

# 执行并监控
exec_response = requests.post('http://localhost:8000/execute_script', 
                             json={'script_path': script_info['script_path']})
job_id = exec_response.json()['job_id']
```

## 🔧 添加新工具

详细步骤请查看 [可扩展性文档](EXTENSIBILITY.md)

简要步骤：
1. 创建工具类继承 `BaseTool`
2. 在 `app.py` 中注册工具
3. 立即通过API使用

## 📞 支持

如有问题，请查看文档或提交issue。