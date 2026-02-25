# -*- coding: utf-8 -*-
"""
工具装饰器测试
"""
import asyncio
import pytest

from src.agent.tools.decorators import (
    tool,
    tool_class,
    _extract_parameters,
    _extract_description,
    _python_type_to_json,
)
from src.agent.tools.base import ToolResult, ToolParameter


class TestTypeConversion:
    """测试类型转换"""

    def test_basic_types(self):
        """测试基本类型转换"""
        assert _python_type_to_json(str) == "string"
        assert _python_type_to_json(int) == "integer"
        assert _python_type_to_json(float) == "number"
        assert _python_type_to_json(bool) == "boolean"
        assert _python_type_to_json(list) == "array"
        assert _python_type_to_json(dict) == "object"

    def test_optional_types(self):
        """测试 Optional 类型转换"""
        from typing import Optional

        assert _python_type_to_json(Optional[str]) == "string"
        assert _python_type_to_json(Optional[int]) == "integer"


class TestParameterExtraction:
    """测试参数提取"""

    def test_extract_simple_params(self):
        """测试提取简单参数"""
        def func(name: str, age: int):
            pass

        params = _extract_parameters(func)
        assert len(params) == 2

        name_param = next(p for p in params if p.name == "name")
        assert name_param.type == "string"
        assert name_param.required is True

        age_param = next(p for p in params if p.name == "age")
        assert age_param.type == "integer"
        assert age_param.required is True

    def test_extract_with_defaults(self):
        """测试提取带默认值的参数"""
        def func(query: str, limit: int = 10):
            pass

        params = _extract_parameters(func)
        query_param = next(p for p in params if p.name == "query")
        limit_param = next(p for p in params if p.name == "limit")

        assert query_param.required is True
        assert limit_param.required is False
        assert limit_param.default == 10

    def test_extract_optional_params(self):
        """测试提取 Optional 参数"""
        from typing import Optional

        def func(query: str, filter: Optional[str] = None):
            pass

        params = _extract_parameters(func)
        filter_param = next(p for p in params if p.name == "filter")

        assert filter_param.required is False
        assert filter_param.default is None


class TestDescriptionExtraction:
    """测试描述提取"""

    def test_extract_from_docstring(self):
        """测试从 docstring 提取描述"""
        def search():
            """搜索网络信息"""
            pass

        desc = _extract_description(search)
        assert desc == "搜索网络信息"

    def test_extract_multiline_docstring(self):
        """测试从多行 docstring 提取描述"""
        def search():
            """搜索网络信息

            详细说明...
            """
            pass

        desc = _extract_description(search)
        assert desc == "搜索网络信息"

    def test_no_docstring(self):
        """测试没有 docstring"""
        def search():
            pass

        desc = _extract_description(search)
        assert "search" in desc


class TestToolDecorator:
    """测试 @tool 装饰器"""

    def test_basic_decorator(self):
        """测试基本装饰器"""
        @tool()
        def get_time() -> str:
            """获取当前时间"""
            return "2024-01-01 12:00:00"

        assert get_time.name == "get_time"
        assert get_time.description == "获取当前时间"
        assert len(get_time.parameters) == 0

    def test_decorator_with_params(self):
        """测试带参数的装饰器"""
        @tool(description="搜索网络")
        def search(query: str, limit: int = 5) -> str:
            """搜索"""
            return f"results for {query}"

        assert search.name == "search"
        assert search.description == "搜索网络"
        assert len(search.parameters) == 2

    def test_custom_name(self):
        """测试自定义名称"""
        @tool(name="web_search")
        def search(query: str) -> str:
            """搜索"""
            return ""

        assert search.name == "web_search"

    @pytest.mark.asyncio
    async def test_sync_function(self):
        """测试同步函数"""
        @tool()
        def add(a: int, b: int) -> int:
            """加法"""
            return a + b

        result = await add.execute(a=1, b=2)
        assert result.success is True
        assert result.data["result"] == 3

    @pytest.mark.asyncio
    async def test_async_function(self):
        """测试异步函数"""
        @tool()
        async def async_add(a: int, b: int) -> int:
            """异步加法"""
            await asyncio.sleep(0.01)
            return a + b

        result = await async_add.execute(a=1, b=2)
        assert result.success is True
        assert result.data["result"] == 3

    @pytest.mark.asyncio
    async def test_function_error(self):
        """测试函数异常"""
        @tool()
        def raise_error():
            """抛出异常"""
            raise ValueError("test error")

        result = await raise_error.execute()
        assert result.success is False
        assert "test error" in result.error

    @pytest.mark.asyncio
    async def test_return_tool_result(self):
        """测试返回 ToolResult"""
        @tool()
        def custom_result() -> ToolResult:
            """自定义结果"""
            return ToolResult(
                success=True,
                data={"key": "value"},
                observation="自定义观察"
            )

        result = await custom_result.execute()
        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.observation == "自定义观察"


class TestToolClassDecorator:
    """测试 @tool_class 装饰器"""

    def test_class_decorator(self):
        """测试类装饰器"""
        @tool_class
        class Calculator:
            """计算器工具"""

            def __call__(self, a: int, b: int) -> int:
                return a + b

        assert Calculator.name == "calculator"
        assert Calculator.description == "计算器工具"
        assert len(Calculator.parameters) == 2

    @pytest.mark.asyncio
    async def test_class_execute(self):
        """测试类实例执行"""
        @tool_class
        class Calculator:
            """计算器"""

            def __call__(self, a: int, b: int) -> int:
                return a * b

        calc = Calculator()
        result = await calc.execute(a=3, b=4)
        assert result.success is True
        assert result.data["result"] == 12


class TestSchemaGeneration:
    """测试 Schema 生成"""

    def test_get_schema(self):
        """测试获取 OpenAI Schema"""
        @tool(description="搜索工具")
        def search(query: str, limit: int = 10) -> str:
            """搜索"""
            return ""

        schema = search.get_schema()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "search"
        assert schema["function"]["description"] == "搜索工具"

        params = schema["function"]["parameters"]
        assert params["type"] == "object"
        assert "query" in params["properties"]
        assert "limit" in params["properties"]
        assert "query" in params["required"]
        assert "limit" not in params["required"]
