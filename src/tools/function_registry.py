# -*- coding: utf-8 -*-
"""
Function Registry - 工具函数注册表

支持:
- 装饰器注册工具函数
- 参数验证
- 自动文档生成
"""
import inspect
import logging
from typing import Dict, List, Callable, Optional, Any, get_type_hints
from dataclasses import dataclass, field
from functools import wraps

logger = logging.getLogger('tools.registry')


@dataclass
class FunctionMetadata:
    """函数元数据"""
    name: str
    description: str
    parameters: Dict[str, Any]
    required: List[str]
    func: Callable
    examples: List[Dict] = field(default_factory=list)


class FunctionRegistry:
    """
    函数注册表

    管理和调用工具函数
    """

    def __init__(self):
        self._functions: Dict[str, FunctionMetadata] = {}
        self._hooks: Dict[str, List[Callable]] = {
            "before_call": [],
            "after_call": [],
            "on_error": []
        }

    def register(
        self,
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None,
        examples: Optional[List[Dict]] = None
    ) -> str:
        """
        注册函数

        Args:
            func: 要注册的函数
            name: 函数名称（默认使用函数名）
            description: 函数描述（默认使用docstring）
            examples: 使用示例

        Returns:
            注册的函数名
        """
        func_name = name or func.__name__
        func_desc = description or (func.__doc__ or "")[:200]

        # 解析参数
        sig = inspect.signature(func)
        type_hints = get_type_hints(func)

        parameters = {"type": "object", "properties": {}, "required": []}
        required = []

        for param_name, param in sig.parameters.items():
            param_type = type_hints.get(param_name, str)
            param_schema = self._type_to_schema(param_type)

            if param.default is inspect.Parameter.empty:
                required.append(param_name)

            parameters["properties"][param_name] = param_schema

        parameters["required"] = required

        self._functions[func_name] = FunctionMetadata(
            name=func_name,
            description=func_desc,
            parameters=parameters,
            required=required,
            func=func,
            examples=examples or []
        )

        logger.info(f"已注册函数: {func_name}")
        return func_name

    def unregister(self, name: str) -> bool:
        """注销函数"""
        if name in self._functions:
            del self._functions[name]
            logger.info(f"已注销函数: {name}")
            return True
        return False

    def get(self, name: str) -> Optional[FunctionMetadata]:
        """获取函数元数据"""
        return self._functions.get(name)

    def list_functions(self) -> List[FunctionMetadata]:
        """列出所有函数"""
        return list(self._functions.values())

    def get_openai_schema(self) -> List[Dict]:
        """获取OpenAI格式的函数定义"""
        return [
            {
                "type": "function",
                "function": {
                    "name": meta.name,
                    "description": meta.description,
                    "parameters": meta.parameters
                }
            }
            for meta in self._functions.values()
        ]

    async def call(self, name: str, arguments: Dict[str, Any]) -> Any:
        """
        调用函数

        Args:
            name: 函数名
            arguments: 函数参数

        Returns:
            函数返回值
        """
        meta = self._functions.get(name)
        if not meta:
            raise ValueError(f"未知函数: {name}")

        # 执行before hooks
        for hook in self._hooks["before_call"]:
            try:
                hook(name, arguments)
            except Exception as e:
                logger.warning(f"Before hook error: {e}")

        try:
            # 调用函数
            if inspect.iscoroutinefunction(meta.func):
                result = await meta.func(**arguments)
            else:
                result = meta.func(**arguments)

            # 执行after hooks
            for hook in self._hooks["after_call"]:
                try:
                    hook(name, arguments, result)
                except Exception as e:
                    logger.warning(f"After hook error: {e}")

            return result

        except Exception as e:
            # 执行error hooks
            for hook in self._hooks["on_error"]:
                try:
                    hook(name, arguments, e)
                except Exception as hook_error:
                    logger.warning(f"Error hook failed: {hook_error}")
            raise

    def add_hook(self, event: str, callback: Callable) -> None:
        """添加钩子"""
        if event in self._hooks:
            self._hooks[event].append(callback)

    def _type_to_schema(self, t: type) -> Dict:
        """将Python类型转换为JSON Schema"""
        type_map = {
            str: {"type": "string"},
            int: {"type": "integer"},
            float: {"type": "number"},
            bool: {"type": "boolean"},
            list: {"type": "array"},
            dict: {"type": "object"},
        }

        # 处理Optional类型
        origin = getattr(t, "__origin__", None)
        if origin is not None:
            args = getattr(t, "__args__", ())
            if origin is list and args:
                return {"type": "array", "items": self._type_to_schema(args[0])}
            if origin is dict and len(args) >= 2:
                return {"type": "object", "additionalProperties": self._type_to_schema(args[1])}

        return type_map.get(t, {"type": "string"})


# 全局注册表
_global_registry = FunctionRegistry()


def function_tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    examples: Optional[List[Dict]] = None
):
    """
    装饰器：将函数注册为工具

    示例:
        @function_tool(description="获取天气")
        def get_weather(city: str) -> str:
            return f"{city}天气晴朗"
    """
    def decorator(func: Callable) -> Callable:
        _global_registry.register(func, name, description, examples)

        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator


def get_registry() -> FunctionRegistry:
    """获取全局注册表"""
    return _global_registry


# 预定义的实用工具函数
@function_tool(description="获取当前时间")
def get_current_time(format: str = "%Y-%m-%d %H:%M:%S") -> str:
    """获取当前时间"""
    from datetime import datetime
    return datetime.now().strftime(format)


@function_tool(description="计算器")
def calculator(expression: str) -> str:
    """安全计算数学表达式"""
    try:
        # 只允许基本运算
        allowed_chars = set("0123456789+-*/.() ")
        if not all(c in allowed_chars for c in expression):
            return "错误: 表达式包含非法字符"

        result = eval(expression, {"__builtins__": {}}, {})
        return f"结果: {result}"
    except Exception as e:
        return f"计算错误: {e}"


@function_tool(description="文本长度统计")
def text_stats(text: str) -> Dict:
    """统计文本信息"""
    return {
        "length": len(text),
        "words": len(text.split()),
        "lines": len(text.splitlines())
    }


@function_tool(description="搜索 Public APIs - 查找免费公共API服务（天气、汇率、加密货币、新闻、翻译等）")
def search_public_apis(keyword: str, category: str = None, auth_required: bool = None) -> str:
    """
    搜索 GitHub public-apis 仓库中的免费公共 API

    Args:
        keyword: 搜索关键词，如 weather, currency, crypto, news, translate, joke
        category: 按类别筛选（可选），如 Weather, Currency, News
        auth_required: 是否需要API Key（可选），True=需要认证，False=免认证

    Returns:
        格式化的API列表
    """
    from .public_api_search import PublicAPISearch
    searcher = PublicAPISearch()
    results = searcher.search(keyword, category, auth_required)
    return searcher.format_result(results)


@function_tool(description="列出 Public APIs 的所有类别")
def list_api_categories() -> str:
    """列出所有可用的API类别"""
    from .public_api_search import PublicAPISearch
    searcher = PublicAPISearch()
    categories = searcher.list_categories()
    return "可用的API类别:\n" + "\n".join(f"- {cat}" for cat in categories)
