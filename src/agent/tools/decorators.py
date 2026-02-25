# -*- coding: utf-8 -*-
"""
工具装饰器

提供简洁的工具定义方式，自动从函数签名生成 OpenAI Function Schema
"""
import asyncio
import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, get_type_hints

from .base import Tool, ToolParameter, ToolResult

logger = logging.getLogger('agent.tools.decorators')


# Python 类型到 JSON Schema 类型的映射
TYPE_MAP = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
    # 支持 Optional 类型
    Optional[str]: "string",
    Optional[int]: "integer",
    Optional[float]: "number",
    Optional[bool]: "boolean",
    Optional[list]: "array",
    Optional[dict]: "object",
}


def _python_type_to_json(py_type: Any) -> str:
    """将 Python 类型转换为 JSON Schema 类型"""
    if py_type in TYPE_MAP:
        return TYPE_MAP[py_type]

    # 处理 typing 模块的类型
    type_str = str(py_type)

    # Optional[X] 或 Union[X, None]
    if 'Optional' in type_str or 'Union' in type_str:
        # 提取内部类型
        if hasattr(py_type, '__args__'):
            inner_type = py_type.__args__[0]
            return _python_type_to_json(inner_type)

    # List[X]
    if 'list' in type_str.lower():
        return "array"

    # Dict[X, Y]
    if 'dict' in type_str.lower():
        return "object"

    # 默认为 string
    return "string"


def _extract_parameters(func: Callable) -> list[ToolParameter]:
    """从函数签名提取参数定义"""
    params = []
    sig = inspect.signature(func)

    # 获取类型提示
    try:
        type_hints = get_type_hints(func)
    except Exception:
        type_hints = {}

    for name, param in sig.parameters.items():
        # 跳过 self 和 cls
        if name in ('self', 'cls'):
            continue

        # 获取类型
        param_type = type_hints.get(name, str)
        json_type = _python_type_to_json(param_type)

        # 判断是否必需
        required = param.default == inspect.Parameter.empty

        # 获取默认值
        default = None if required else param.default

        # 创建参数
        params.append(ToolParameter(
            name=name,
            type=json_type,
            description=f"参数 {name}",
            required=required,
            default=default
        ))

    return params


def _extract_description(func: Callable) -> str:
    """从 docstring 提取描述"""
    doc = func.__doc__ or ""
    # 取第一个非空行作为描述
    lines = [line.strip() for line in doc.strip().split('\n') if line.strip()]
    return lines[0] if lines else f"执行 {func.__name__}"


@dataclass
class DecoratedTool(Tool):
    """装饰器创建的工具类"""
    _func: Callable = field(default=None)
    _is_async: bool = field(default=False)
    _timeout: float = field(default=30.0)

    def __post_init__(self):
        if not self.name:
            self.name = self._func.__name__ if self._func else "unknown"

    async def execute(self, **kwargs) -> ToolResult:
        """执行工具函数"""
        try:
            if self._is_async:
                result = await asyncio.wait_for(
                    self._func(**kwargs),
                    timeout=self._timeout
                )
            else:
                result = self._func(**kwargs)

            # 处理返回值
            if isinstance(result, ToolResult):
                return result
            elif isinstance(result, dict):
                return ToolResult(
                    success=True,
                    data=result,
                    observation=str(result)
                )
            else:
                return ToolResult(
                    success=True,
                    data={"result": result},
                    observation=str(result)
                )

        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                data=None,
                observation=f"执行超时 ({self._timeout}s)",
                error="TimeoutError"
            )
        except Exception as e:
            logger.exception(f"工具 {self.name} 执行失败")
            return ToolResult(
                success=False,
                data=None,
                observation=f"执行失败: {str(e)}",
                error=str(e)
            )


def tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    timeout: float = 30.0,
    parameters: Optional[list[ToolParameter]] = None
) -> Callable:
    """
    装饰器: 将函数转换为工具

    自动从函数签名提取参数定义，从 docstring 提取描述。

    Args:
        name: 工具名称 (默认使用函数名)
        description: 工具描述 (默认从 docstring 提取)
        timeout: 执行超时时间 (秒)
        parameters: 自定义参数列表 (默认从函数签名提取)

    Returns:
        装饰后的工具实例

    Example:
        @tool(description="搜索网络信息")
        async def web_search(query: str, num_results: int = 5) -> str:
            '''使用搜索引擎搜索网络信息

            Args:
                query: 搜索关键词
                num_results: 返回结果数量
            '''
            ...
    """
    def decorator(func: Callable) -> DecoratedTool:
        # 提取参数
        if parameters:
            params = parameters
        else:
            params = _extract_parameters(func)

        # 提取描述
        desc = description or _extract_description(func)

        # 判断是否是异步函数
        is_async = inspect.iscoroutinefunction(func)

        # 创建工具实例
        tool_instance = DecoratedTool(
            _func=func,
            _is_async=is_async,
            _timeout=timeout
        )

        # 设置工具属性
        tool_instance.name = name or func.__name__
        tool_instance.description = desc
        tool_instance.parameters = params

        # 保留原函数的引用
        tool_instance._original_func = func

        return tool_instance

    return decorator


def tool_class(cls: type) -> type:
    """
    类装饰器: 将类转换为工具

    类需要实现 __call__ 方法作为执行入口。

    Example:
        @tool_class
        class WebSearch:
            '''搜索网络信息'''

            def __init__(self, api_key: str = None):
                self.api_key = api_key

            def __call__(self, query: str, num_results: int = 5) -> str:
                ...
    """
    # 提取 __call__ 方法的签名
    call_method = cls.__call__
    params = _extract_parameters(call_method)
    desc = _extract_description(cls)

    # 添加工具属性
    cls.name = cls.__name__.lower()
    cls.description = desc
    cls.parameters = params

    # 添加 execute 方法
    async def execute(self, **kwargs) -> ToolResult:
        try:
            if inspect.iscoroutinefunction(call_method):
                result = await call_method(self, **kwargs)
            else:
                result = call_method(self, **kwargs)

            if isinstance(result, ToolResult):
                return result
            else:
                return ToolResult(
                    success=True,
                    data={"result": result},
                    observation=str(result)
                )
        except Exception as e:
            return ToolResult(
                success=False,
                observation=f"执行失败: {str(e)}",
                error=str(e)
            )

    cls.execute = execute

    return cls


# 便捷函数：将装饰器工具注册到注册表
def register_tool(registry, tool_instance: Tool) -> Tool:
    """
    将装饰器创建的工具注册到工具注册表

    Args:
        registry: ToolRegistry 实例
        tool_instance: 装饰器创建的工具实例

    Returns:
        注册后的工具实例
    """
    registry.register(tool_instance)
    return tool_instance
