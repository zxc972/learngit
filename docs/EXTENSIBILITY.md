# 可扩展性架构设计文档

## 🎯 设计目标

为猴脑分割与分析pipeline项目提供高度可扩展的架构，支持：
- 快速集成新的分析工具
- 灵活的参数配置
- 统一的API接口
- 类型安全的参数验证

## 🏗️ 核心架构

### 1. 工具基类 (BaseTool)

所有分析工具都继承自 `BaseTool` 抽象基类：

```python
class BaseTool(ABC):
    @abstractmethod
    def validate_params(self, params: Dict) -> tuple[bool, str]:
        """验证输入参数"""
        pass
    
    @abstractmethod 
    def generate_script(self, params: Dict) -> str:
        """生成执行脚本"""
        pass
    
    @abstractmethod
    def get_parameter_schema(self) -> Dict:
        """获取参数模式定义（JSON Schema格式）"""
        pass
```

### 2. 工具注册表 (ToolRegistry)

集中管理所有可用工具：

```python
# 注册新工具
tool_registry.register_tool(YourNewTool())

# 获取工具
tool = tool_registry.get_tool('your_tool_name')

# 列出所有工具
tools = tool_registry.list_tools()
```

### 3. 统一API接口

所有工具通过相同的HTTP API使用：

- `GET /tools` - 获取所有工具
- `GET /tools/{tool_name}` - 获取工具信息
- `GET /tools/{tool_name}/schema` - 获取参数模式
- `POST /generate_script` - 生成脚本（支持所有工具）
- `POST /execute_script` - 执行脚本

## 🔧 添加新工具的步骤

### 步骤1：创建工具类

```python
from tools import BaseTool

class YourAnalysisTool(BaseTool):
    def __init__(self):
        super().__init__("your_tool_name", "1.0.0")
        self.description = "您的工具描述"
        self.required_params = ['param1', 'param2']
        self.optional_params = ['param3', 'param4']
    
    def validate_params(self, params: Dict) -> tuple[bool, str]:
        # 实现参数验证逻辑
        for param in self.required_params:
            if param not in params:
                return False, f"Missing required parameter: {param}"
        return True, "OK"
    
    def generate_script(self, params: Dict) -> str:
        # 实现脚本生成逻辑
        return f"#!/bin/bash\necho 'Running {self.name}...'"
    
    def get_parameter_schema(self) -> Dict:
        # 返回JSON Schema格式的参数定义
        return {
            "type": "object",
            "properties": {
                "param1": {"type": "string", "description": "参数1描述"},
                "param2": {"type": "string", "description": "参数2描述"}
            },
            "required": self.required_params
        }
```

### 步骤2：注册工具

在 `app_v2.py` 的 `init_tools()` 函数中添加：

```python
def init_tools():
    tool_registry.register_tool(PipelineTool())
    tool_registry.register_tool(YourAnalysisTool())  # 添加这行
    # ... 其他工具
```

### 步骤3：测试新工具

```python
# 检查工具是否注册成功
response = requests.get('http://localhost:5000/tools')
print(response.json())

# 生成脚本
params = {'param1': 'value1', 'param2': 'value2', 'tool_name': 'your_tool_name'}
response = requests.post('http://localhost:5000/generate_script', json=params)
```

## 📊 处理步骤配置化

### 配置驱动的处理步骤

使用 `ProcessingStep` 类实现配置化的处理步骤：

```python
steps_config = {
    'your_step': {
        'name': '您的处理步骤',
        'script': 'your_script.sh',
        'description': '步骤描述',
        'requires_gpu': False,
        'command_template': '''singularity exec {container_path} \\
            your_command --input {input_path} --output {output_path}''',
        'validation_rules': {
            'input_exists': {'type': 'file_exists', 'param': 'input_path'}
        }
    }
}
```

### 命令模板系统

支持灵活的命令模板，自动参数替换：

```python
command_template = """singularity exec -B {surf_workdir}:{surf_workdir} {container_path} \\
    bash {bashroot_path}/{script} \\
    --input {surf_workdir}/{subjid}/input \\
    --output {surf_workdir}/{subjid}/output \\
    --species {species}"""
```

## 🔒 参数验证框架

### JSON Schema支持

每个工具定义标准的JSON Schema来验证参数：

```python
def get_parameter_schema(self) -> Dict:
    return {
        "type": "object",
        "properties": {
            "input_directory": {
                "type": "string",
                "description": "输入目录路径",
                "pattern": "^/.*"  # 必须是绝对路径
            },
            "analysis_type": {
                "type": "string", 
                "enum": ["type1", "type2", "type3"],
                "description": "分析类型"
            },
            "threshold": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "default": 0.5
            }
        },
        "required": ["input_directory", "analysis_type"]
    }
```

### 自定义验证规则

支持复杂的自定义验证逻辑：

```python
def validate_params(self, params: Dict) -> tuple[bool, str]:
    # 基础验证
    basic_valid, msg = super().validate_params(params)
    if not basic_valid:
        return False, msg
    
    # 自定义验证
    if params['analysis_type'] == 'advanced':
        if 'advanced_params' not in params:
            return False, "Advanced analysis requires advanced_params"
    
    return True, "OK"
```

## 🚀 脚本类型支持

### 多种脚本类型

- **Bash脚本** (`.sh`): 传统pipeline处理
- **Python脚本** (`.py`): 数据分析、可视化
- **R脚本** (`.R`): 统计分析
- **其他脚本**: 可通过配置支持

### 自动脚本类型检测

系统根据工具类型自动选择合适的脚本格式和执行方式。

## 📈 批量处理支持

### 批量脚本生成

```python
requests_list = [
    {'tool_name': 'pipeline', 'subjects': ['S001', 'S002']},
    {'tool_name': 'analysis', 'analysis_type': 'morphometry'},
    {'tool_name': 'visualization', 'viz_type': 'slice_view'}
]

response = requests.post('/batch_generate', json={'requests': requests_list})
```

## 🔌 插件化架构

### 工具发现机制

可以通过目录扫描自动发现新工具：

```python
def auto_discover_tools(tools_directory: str):
    """自动发现并注册工具目录中的所有工具"""
    for file in Path(tools_directory).glob("*_tool.py"):
        # 动态导入和注册工具
        module = importlib.import_module(f"tools.{file.stem}")
        # 自动注册实现了BaseTool的类
```

## 🎨 配置文件支持

### YAML/JSON配置

支持通过配置文件定义工具和步骤：

```yaml
tools:
  my_analysis_tool:
    name: "我的分析工具"
    version: "1.0.0"
    description: "自定义分析工具"
    script_template: "/path/to/template.sh"
    required_params:
      - input_path
      - output_path
    optional_params:
      - threshold
```

## 🔧 实际使用示例

### 1. 添加新的统计分析工具

```python
class AdvancedStatsTool(BaseTool):
    def __init__(self):
        super().__init__("advanced_stats", "1.0.0")
        # ... 实现各个方法
```

### 2. 添加新的质量控制工具

```python
class QualityAssessmentTool(BaseTool):
    def __init__(self):
        super().__init__("quality_assessment", "1.0.0")
        # ... 实现各个方法
```

### 3. 添加机器学习工具

```python
class MLAnalysisTool(BaseTool):
    def __init__(self):
        super().__init__("ml_analysis", "1.0.0")
        # ... 实现各个方法
```

## ✅ 扩展性优势

1. **零修改集成**: 新工具无需修改现有代码
2. **统一接口**: 所有工具使用相同的API
3. **类型安全**: JSON Schema确保参数正确性
4. **配置驱动**: 通过配置文件快速定义新功能
5. **插件化**: 支持运行时动态加载新工具
6. **向后兼容**: 保持与现有系统的兼容性

这个架构确保了系统的高度可扩展性，您后续添加任何新的分析工具都会非常简单和直接！
