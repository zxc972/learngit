# 🧠 距离计算工具使用指南

## 概述

距离计算工具是猴脑分割流水线的第一个分析工具，用于计算脑区间的欧氏距离和测地距离，并提供可视化分析功能。

## 功能特点

- ✅ **双重距离计算**：支持欧氏距离和测地距离计算
- ✅ **自动可视化**：生成热图和对比分析图
- ✅ **并行计算**：支持多核并行处理
- ✅ **灵活配置**：可自定义输出路径和计算参数
- ✅ **Dify集成**：完全兼容Dify Agent工作流

## API接口

### 工具信息查询

```bash
# 获取工具列表
GET http://localhost:8000/tools

# 获取距离计算工具详细信息
GET http://localhost:8000/tools/distance_calculation

# 获取参数模式
GET http://localhost:8000/tools/distance_calculation/schema
```

### 脚本生成与执行

```bash
# 生成脚本
POST http://localhost:8000/generate_script

# 执行脚本
POST http://localhost:8000/execute_script

# 查询任务状态
GET http://localhost:8000/job_status/{job_id}
```

## 参数说明

### 必需参数

| 参数 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `surface_file` | string | 表面文件路径 (.surf.gii) | `/data/surface.surf.gii` |
| `parcellation_file` | string | 分区文件路径 (.dlabel.nii) | `/data/parcellation.dlabel.nii` |

### 可选参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `output_euclidean` | string | 自动生成 | 欧氏距离矩阵输出文件 |
| `output_geodesic` | string | 自动生成 | 测地距离矩阵输出文件 |
| `output_dir` | string | `/tmp` | 输出目录 |
| `n_jobs` | integer | `-1` | 并行任务数(-1=所有核心) |
| `use_workbench` | boolean | `false` | 是否使用Workbench |
| `medial_mask` | string | - | 中央区域掩码文件 |
| `generate_visualization` | boolean | `true` | 是否生成可视化 |

## 使用示例

### 1. 基础使用

```json
{
  "tool_name": "distance_calculation",
  "surface_file": "/data/monkey_surface.surf.gii",
  "parcellation_file": "/data/monkey_parcellation.dlabel.nii",
  "output_dir": "/results/distance_analysis"
}
```

### 2. 完整配置

```json
{
  "tool_name": "distance_calculation",
  "surface_file": "/data/subject001_surface.gii",
  "parcellation_file": "/data/subject001_parcels.nii",
  "output_euclidean": "/results/subject001_euclidean.csv",
  "output_geodesic": "/results/subject001_geodesic.csv", 
  "n_jobs": 8,
  "use_workbench": true,
  "generate_visualization": true
}
```

### 3. Dify Agent集成

```json
{
  "tool_name": "distance_calculation",
  "surface_file": "{{user_surface_file}}",
  "parcellation_file": "{{user_parcellation_file}}",
  "output_dir": "/tmp/{{session_id}}_distance_results",
  "n_jobs": 4,
  "generate_visualization": true
}
```

## 输出文件

执行完成后，工具会生成以下文件：

### 数据文件
- `euclidean_dist_TIMESTAMP.csv` - 欧氏距离矩阵
- `geodesic_dist_TIMESTAMP.csv` - 测地距离矩阵

### 可视化文件（如果启用）
- `euclidean_heatmap_TIMESTAMP.png` - 欧氏距离热图
- `geodesic_heatmap_TIMESTAMP.png` - 测地距离热图  
- `distance_comparison_TIMESTAMP.png` - 距离对比分析图

## Python API示例

```python
import requests
import json

# 1. 生成脚本
params = {
    "tool_name": "distance_calculation",
    "surface_file": "/path/to/surface.surf.gii",
    "parcellation_file": "/path/to/parcellation.dlabel.nii",
    "output_dir": "/results",
    "generate_visualization": True
}

response = requests.post('http://localhost:8000/generate_script', json=params)
script_info = response.json()

# 2. 执行脚本
exec_params = {
    "script_path": script_info['script_path'],
    "tool_name": "distance_calculation"
}

exec_response = requests.post('http://localhost:8000/execute_script', json=exec_params)
job_id = exec_response.json()['job_id']

# 3. 监控执行状态
import time
while True:
    status_response = requests.get(f'http://localhost:8000/job_status/{job_id}')
    status = status_response.json()['status']
    
    if status in ['completed', 'failed', 'cancelled']:
        break
    time.sleep(2)

print(f"任务完成，状态: {status}")
```

## curl命令示例

```bash
# 1. 检查服务状态
curl -X GET http://localhost:8000/health

# 2. 获取工具信息
curl -X GET http://localhost:8000/tools/distance_calculation

# 3. 生成脚本
curl -X POST http://localhost:8000/generate_script \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "distance_calculation",
    "surface_file": "/data/surface.surf.gii",
    "parcellation_file": "/data/parcellation.dlabel.nii",
    "output_dir": "/results"
  }'

# 4. 执行脚本
curl -X POST http://localhost:8000/execute_script \
  -H "Content-Type: application/json" \
  -d '{
    "script_path": "/tmp/distance_calculation_20250815_140500.sh",
    "tool_name": "distance_calculation"
  }'

# 5. 查询任务状态
curl -X GET http://localhost:8000/job_status/{job_id}
```

## 依赖环境

工具运行需要以下Python包：

```bash
pip install brainsmash matplotlib seaborn numpy
```

## 错误处理

常见错误及解决方案：

| 错误信息 | 原因 | 解决方案 |
|----------|------|----------|
| `Surface file not found` | 表面文件路径错误 | 检查文件路径是否正确 |
| `Parcellation file not found` | 分区文件路径错误 | 检查文件路径是否正确 |
| `Missing brainsmash library` | 缺少依赖库 | `pip install brainsmash` |
| `Permission denied` | 输出目录权限不足 | 检查目录写入权限 |

## 性能优化

- **并行计算**：设置 `n_jobs` 参数使用多核心
- **内存管理**：大矩阵计算时适当调整并行数
- **存储优化**：使用SSD存储提高I/O性能

## 最佳实践

1. **文件路径**：使用绝对路径避免路径错误
2. **输出目录**：预先创建输出目录并检查权限
3. **任务监控**：使用任务ID监控长时间运行的计算
4. **资源管理**：根据数据大小调整并行参数
5. **结果验证**：计算完成后检查输出文件的完整性

## 故障排除

如果遇到问题，请检查：

1. ✅ 服务是否正常运行 (`/health` 接口)
2. ✅ 输入文件是否存在且可读
3. ✅ 输出目录是否有写入权限
4. ✅ Python依赖是否已安装
5. ✅ 系统资源是否充足（内存、磁盘空间）

## 技术支持

如需技术支持，请提供：
- 完整的错误信息
- 输入参数配置
- 系统环境信息
- 日志文件内容
