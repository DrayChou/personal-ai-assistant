# -*- coding: utf-8 -*-
"""
Tool Executor - 工具执行器

统一执行各种工具：
- MCP工具
- 注册函数
- 外部API
"""
import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from .mcp_client import MCPClient
from .function_registry import FunctionRegistry

logger = logging.getLogger('tools.executor')


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    result: Any
    tool_name: str
    execution_time: float
    error: Optional[str] = None


class ToolExecutor:
    """
    工具执行器

    统一管理所有工具的调用
    """

    def __init__(
        self,
        mcp_client: Optional[MCPClient] = None,
        function_registry: Optional[FunctionRegistry] = None
    ):
        self.mcp = mcp_client or MCPClient()
        self.registry = function_registry
        self._execution_history: List[Dict] = []

    async def execute(
        self,
        tool_call: Dict[str, Any]
    ) -> ToolResult:
        """
        执行工具调用

        Args:
            tool_call: 工具调用定义
                {
                    "name": "tool_name",
                    "arguments": {...}
                }

        Returns:
            执行结果
        """
        import time
        start_time = time.time()

        tool_name = tool_call.get("name", "")
        arguments = tool_call.get("arguments", {})

        try:
            # 1. 尝试MCP工具 - 支持所有已配置的MCP服务
            if self.mcp and tool_name in self.mcp.list_tools():
                result = await self.mcp.call_tool(tool_name, arguments)
                execution_time = time.time() - start_time

                self._log_execution(tool_name, arguments, result, execution_time)

                return ToolResult(
                    success="error" not in result,
                    result=result,
                    tool_name=tool_name,
                    execution_time=execution_time,
                    error=result.get("error")
                )

            # 2. 尝试注册的函数
            if self.registry:
                meta = self.registry.get(tool_name)
                if meta:
                    result = await self.registry.call(tool_name, arguments)
                    execution_time = time.time() - start_time

                    self._log_execution(tool_name, arguments, result, execution_time)

                    return ToolResult(
                        success=True,
                        result=result,
                        tool_name=tool_name,
                        execution_time=execution_time
                    )

            # 3. 未找到工具
            return ToolResult(
                success=False,
                result=None,
                tool_name=tool_name,
                execution_time=time.time() - start_time,
                error=f"未找到工具: {tool_name}"
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"工具执行失败 {tool_name}: {e}")

            return ToolResult(
                success=False,
                result=None,
                tool_name=tool_name,
                execution_time=execution_time,
                error=str(e)
            )

    async def execute_batch(
        self,
        tool_calls: List[Dict[str, Any]]
    ) -> List[ToolResult]:
        """批量执行工具调用"""
        import asyncio
        tasks = [self.execute(tc) for tc in tool_calls]
        return await asyncio.gather(*tasks)

    def _log_execution(
        self,
        tool_name: str,
        arguments: Dict,
        result: Any,
        execution_time: float
    ) -> None:
        """记录执行历史"""
        self._execution_history.append({
            "tool": tool_name,
            "arguments": arguments,
            "result": result,
            "execution_time": execution_time
        })

        # 限制历史记录数量
        if len(self._execution_history) > 100:
            self._execution_history = self._execution_history[-100:]

    def get_execution_history(self) -> List[Dict]:
        """获取执行历史"""
        return self._execution_history.copy()

    def get_available_tools(self) -> List[Dict]:
        """获取所有可用工具"""
        tools = []

        # MCP工具
        tools.extend(self.mcp.get_available_functions())

        # 注册函数
        if self.registry:
            tools.extend(self.registry.get_openai_schema())

        return tools

    def format_result_for_llm(self, result: ToolResult) -> str:
        """格式化结果为LLM可理解的文本"""
        if result.success:
            return f"[工具执行成功] {result.tool_name}:\n{json.dumps(result.result, ensure_ascii=False, indent=2)}"
        else:
            return f"[工具执行失败] {result.tool_name}: {result.error}"


class LLMToolHandler:
    """
    LLM工具调用处理器

    处理LLM返回的function_call
    """

    def __init__(self, executor: ToolExecutor):
        self.executor = executor

    async def handle_function_call(
        self,
        function_call: Dict[str, Any]
    ) -> str:
        """
        处理函数调用

        Args:
            function_call: OpenAI格式的function_call
                {
                    "name": "tool_name",
                    "arguments": "{...}"
                }

        Returns:
            执行结果文本
        """
        try:
            # 解析参数
            if isinstance(function_call.get("arguments"), str):
                arguments = json.loads(function_call["arguments"])
            else:
                arguments = function_call.get("arguments", {})

            tool_call = {
                "name": function_call.get("name"),
                "arguments": arguments
            }

            result = await self.executor.execute(tool_call)
            return self.executor.format_result_for_llm(result)

        except json.JSONDecodeError as e:
            return f"参数解析错误: {e}"
        except Exception as e:
            return f"处理失败: {e}"

    async def handle_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]]
    ) -> List[str]:
        """处理多个工具调用"""
        results = []
        for tc in tool_calls:
            function_call = tc.get("function", tc)
            result = await self.handle_function_call(function_call)
            results.append(result)
        return results
