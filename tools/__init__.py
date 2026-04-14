"""
工具模块 - 可扩展的分析工具框架
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import json
from pathlib import Path

class BaseTool(ABC):
    """分析工具基类"""
    
    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version
        self.description = ""
        self.supported_species = []
        self.required_params = []
        self.optional_params = []
    
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
        """获取参数模式定义"""
        pass
    
    def get_info(self) -> Dict:
        """获取工具信息"""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "supported_species": self.supported_species,
            "required_params": self.required_params,
            "optional_params": self.optional_params,
            "parameter_schema": self.get_parameter_schema()
        }

class ProcessingStep:
    """处理步骤类 - 可配置的步骤定义"""
    
    def __init__(self, step_id: str, config: Dict):
        self.step_id = step_id
        self.name = config.get('name', step_id)
        self.script = config.get('script', '')
        self.description = config.get('description', '')
        self.requires_gpu = config.get('requires_gpu', False)
        self.dependencies = config.get('dependencies', [])
        self.parameters = config.get('parameters', {})
        self.command_template = config.get('command_template', '')
        self.validation_rules = config.get('validation_rules', {})
    
    def generate_command(self, params: Dict, subjid: str) -> str:
        """生成步骤命令"""
        if self.command_template:
            # 合并参数，步骤参数优先级更高
            format_params = {**params, **self.parameters, 'subjid': subjid}
            return self.command_template.format(**format_params)
        else:
            # 后向兼容：调用传统方法
            return self._generate_legacy_command(params, subjid)
    
    def _generate_legacy_command(self, params: Dict, subjid: str) -> str:
        """传统命令生成方法（后向兼容）"""
        # 这里保留原来的硬编码逻辑作为后备
        return f"# Legacy command for {self.step_id}"
    
    def validate_step_params(self, params: Dict) -> tuple[bool, str]:
        """验证步骤特定参数"""
        for rule_name, rule_config in self.validation_rules.items():
            if not self._check_validation_rule(params, rule_name, rule_config):
                return False, f"Validation failed for rule: {rule_name}"
        return True, "OK"
    
    def _check_validation_rule(self, params: Dict, rule_name: str, rule_config: Dict) -> bool:
        """检查验证规则"""
        # 实现各种验证规则
        rule_type = rule_config.get('type')
        if rule_type == 'required':
            return rule_config.get('param') in params
        elif rule_type == 'file_exists':
            path = params.get(rule_config.get('param'))
            return path and Path(path).exists()
        # 可以添加更多规则类型
        return True

class ToolRegistry:
    """工具注册表 - 管理所有可用工具"""
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
    
    def register_tool(self, tool: BaseTool):
        """注册工具"""
        self._tools[tool.name] = tool
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """获取工具"""
        return self._tools.get(name)
    
    def list_tools(self) -> List[str]:
        """列出所有工具"""
        return list(self._tools.keys())
    
    def get_all_tools_info(self) -> Dict[str, Dict]:
        """获取所有工具信息"""
        return {name: tool.get_info() for name, tool in self._tools.items()}

# 全局工具注册表
tool_registry = ToolRegistry()
