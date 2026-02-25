# -*- coding: utf-8 -*-
"""
工具基类

定义 Function Calling 标准接口
"""
import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional
from datetime import datetime


logger = logging.getLogger('agent.tools.base')

# 参数限制常量
MAX_STRING_LENGTH = 10000  # 字符串参数最大长度
MAX_ARRAY_LENGTH = 100     # 数组参数最大长度
MAX_INTEGER_VALUE = 10**9  # 整数最大值


@dataclass
class ToolResult:
    """
    工具执行结果

    Attributes:
        success: 是否成功
        data: 返回数据
        observation: 执行观察，用于 Agent 反思
        error: 错误信息
        metadata: 额外元数据
    """
    success: bool
    data: Any
    observation: str
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'success': self.success,
            'data': self.data,
            'observation': self.observation,
            'error': self.error,
            'metadata': self.metadata,
        }


@dataclass
class ToolParameter:
    """
    工具参数定义

    Attributes:
        name: 参数名
        type: 参数类型 (string, integer, number, boolean, array, object)
        description: 参数描述
        required: 是否必需
        default: 默认值
        enum: 可选值列表
        max_length: 字符串/数组最大长度
        min_value: 数值最小值
        max_value: 数值最大值
    """
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[list] = None
    max_length: Optional[int] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None

    def to_schema(self) -> dict:
        """转换为 JSON Schema 格式"""
        schema = {
            'type': self.type,
            'description': self.description,
        }
        if self.enum:
            schema['enum'] = self.enum
        if self.max_length is not None:
            schema['maxLength'] = self.max_length
        if self.min_value is not None:
            schema['minimum'] = self.min_value
        if self.max_value is not None:
            schema['maximum'] = self.max_value
        return schema


class Tool(ABC):
    """
    工具基类

    所有 Agent 可调用的功能必须继承此类
    支持 OpenAI Function Calling 标准格式
    """

    # 工具元数据
    name: str = ""
    description: str = ""
    parameters: list[ToolParameter] = field(default_factory=list)

    def __init__(self):
        """初始化工具"""
        if not self.name:
            raise ValueError(f"工具 {self.__class__.__name__} 必须定义 name")
        if not self.description:
            raise ValueError(f"工具 {self.__class__.__name__} 必须定义 description")

    def get_schema(self) -> dict:
        """
        获取 Function Calling Schema

        Returns:
            OpenAI Function Calling 格式
        """
        properties = {}
        required = []

        for param in self.parameters:
            properties[param.name] = param.to_schema()
            if param.required:
                required.append(param.name)

        return {
            'type': 'function',
            'function': {
                'name': self.name,
                'description': self.description,
                'parameters': {
                    'type': 'object',
                    'properties': properties,
                    'required': required,
                }
            }
        }

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """
        执行工具

        Args:
            **kwargs: 参数值

        Returns:
            ToolResult 执行结果
        """
        pass

    async def execute_safe(self, timeout: float = 30.0, **kwargs) -> ToolResult:
        """
        带异常边界保护的执行

        自动处理：
        - 参数验证
        - 异常捕获
        - 执行日志
        - 超时处理

        Args:
            timeout: 超时时间（秒），默认30秒
            **kwargs: 参数值

        Returns:
            ToolResult
        """
        start_time = time.time()
        tool_name = self.name

        try:
            # 参数验证
            valid, error = self.validate_params(kwargs)
            if not valid:
                logger.warning(f"[{tool_name}] 参数验证失败: {error}")
                return ToolResult(
                    success=False,
                    data=None,
                    observation=f"参数错误: {error}",
                    error=error
                )

            # 执行（带超时）
            logger.debug(f"[{tool_name}] 开始执行, 参数: {kwargs}, 超时: {timeout}s")
            result = await asyncio.wait_for(
                self.execute(**kwargs),
                timeout=timeout
            )

            # 记录日志
            duration = time.time() - start_time
            logger.info(
                f"[{tool_name}] 执行完成",
                extra={
                    "tool": tool_name,
                    "success": result.success,
                    "duration": duration,
                    "params": kwargs
                }
            )

            # 添加元数据
            result.metadata["duration"] = duration
            result.metadata["timestamp"] = datetime.now().isoformat()

            return result

        except asyncio.TimeoutError:
            duration = time.time() - start_time
            logger.error(f"[{tool_name}] 执行超时 ({timeout}s)")
            return ToolResult(
                success=False,
                data=None,
                observation=f"执行超时，操作耗时超过 {timeout} 秒",
                error=f"Timeout after {timeout}s",
                metadata={
                    "duration": duration,
                    "timestamp": datetime.now().isoformat(),
                    "exception_type": "TimeoutError"
                }
            )

        except Exception as e:
            duration = time.time() - start_time
            logger.exception(f"[{tool_name}] 执行异常")

            return ToolResult(
                success=False,
                data=None,
                observation=f"执行异常: {str(e)}",
                error=str(e),
                metadata={
                    "duration": duration,
                    "timestamp": datetime.now().isoformat(),
                    "exception_type": type(e).__name__
                }
            )

    def validate_params(self, params: dict) -> tuple[bool, Optional[str]]:
        """
        验证参数

        包括：
        - 必需参数检查
        - 类型验证
        - 枚举值验证
        - 长度/范围限制

        Args:
            params: 参数字典

        Returns:
            (是否有效, 错误信息)
        """
        for param in self.parameters:
            value = params.get(param.name)

            # 必需参数检查
            if param.required and value is None:
                return False, f"缺少必需参数: {param.name}"

            if value is None:
                continue

            # 类型验证
            type_valid, type_error = self._validate_type(param, value)
            if not type_valid:
                return False, type_error

            # 枚举值验证
            if param.enum and value not in param.enum:
                return False, f"参数 {param.name} 值 '{value}' 无效，可选值: {param.enum}"

            # 字符串长度限制
            if param.type == "string":
                max_len = param.max_length or MAX_STRING_LENGTH
                if isinstance(value, str) and len(value) > max_len:
                    return False, f"参数 {param.name} 超过最大长度 {max_len}"

            # 数组长度限制
            if param.type == "array":
                max_len = param.max_length or MAX_ARRAY_LENGTH
                if isinstance(value, list) and len(value) > max_len:
                    return False, f"参数 {param.name} 超过最大数组长度 {max_len}"

            # 数值范围验证
            if param.type in ("integer", "number"):
                if not isinstance(value, (int, float)):
                    return False, f"参数 {param.name} 必须是数字"
                if param.min_value is not None and value < param.min_value:
                    return False, f"参数 {param.name} 不能小于 {param.min_value}"
                if param.max_value is not None and value > param.max_value:
                    return False, f"参数 {param.name} 不能大于 {param.max_value}"
                # 全局整数上限
                if param.type == "integer" and abs(value) > MAX_INTEGER_VALUE:
                    return False, f"参数 {param.name} 超出允许范围"

        return True, None

    def _validate_type(self, param: ToolParameter, value: Any) -> tuple[bool, Optional[str]]:
        """验证参数类型"""
        type_mapping = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        expected_type = type_mapping.get(param.type)
        if expected_type is None:
            return True, None  # 未知类型跳过验证

        # integer 也接受 bool=False/True 的情况（Python 中 bool 是 int 子类）
        if param.type == "integer" and isinstance(value, bool):
            return False, f"参数 {param.name} 必须是整数，不能是布尔值"

        if not isinstance(value, expected_type):
            return False, f"参数 {param.name} 类型错误，期望 {param.type}，实际 {type(value).__name__}"

        return True, None

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name}>"
