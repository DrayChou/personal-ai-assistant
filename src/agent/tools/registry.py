# -*- coding: utf-8 -*-
"""
工具注册表

统一管理所有可用工具
"""
import logging
from typing import Optional

from .base import Tool, ToolResult

logger = logging.getLogger('agent.tools.registry')


class ToolRegistry:
    """
    工具注册表

    负责：
    1. 工具注册与发现
    2. 工具查询
    3. Schema 生成
    """

    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._schemas: list[dict] = []

    def register(self, tool: Tool) -> 'ToolRegistry':
        """
        注册工具

        Args:
            tool: 工具实例

        Returns:
            self 支持链式调用
        """
        if tool.name in self._tools:
            # 移除旧的 schema
            self._schemas = [
                s for s in self._schemas
                if s.get('function', {}).get('name') != tool.name
            ]
            logger.warning(f"工具 {tool.name} 已存在，将被覆盖")

        self._tools[tool.name] = tool
        self._schemas.append(tool.get_schema())

        logger.debug(f"注册工具: {tool.name}")
        return self

    def register_multiple(self, tools: list[Tool]) -> 'ToolRegistry':
        """
        批量注册工具

        Args:
            tools: 工具列表

        Returns:
            self 支持链式调用
        """
        for tool in tools:
            self.register(tool)
        return self

    def get(self, name: str) -> Optional[Tool]:
        """
        获取工具

        Args:
            name: 工具名

        Returns:
            工具实例或 None
        """
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        """
        检查工具是否存在

        Args:
            name: 工具名

        Returns:
            是否存在
        """
        return name in self._tools

    def list_tools(self) -> list[Tool]:
        """
        列出所有工具

        Returns:
            工具列表
        """
        return list(self._tools.values())

    def get_schemas(self) -> list[dict]:
        """
        获取所有工具的 Function Calling Schema

        Returns:
            Schema 列表
        """
        return self._schemas.copy()

    def get_names(self) -> list[str]:
        """
        获取所有工具名

        Returns:
            工具名列表
        """
        return list(self._tools.keys())

    async def execute(
        self,
        tool_name: str,
        timeout: float = 30.0,
        **params
    ) -> ToolResult:
        """
        执行工具（使用安全执行模式）

        Args:
            tool_name: 工具名
            timeout: 超时时间（秒），默认30秒
            **params: 参数

        Returns:
            ToolResult

        Raises:
            ToolNotFoundError: 当工具不存在时（可选抛出）
        """
        tool = self.get(tool_name)
        if not tool:
            error_msg = f"工具 '{tool_name}' 不存在"
            # 记录错误但返回 ToolResult 以保持兼容性
            logger.error(error_msg)
            return ToolResult(
                success=False,
                data=None,
                observation=error_msg,
                error=error_msg
            )

        # 使用安全执行模式
        try:
            return await tool.execute_safe(timeout=timeout, **params)
        except Exception as e:
            logger.exception(f"工具 '{tool_name}' 执行失败")
            return ToolResult(
                success=False,
                data=None,
                observation=f"执行失败: {str(e)}",
                error=str(e)
            )

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)

    def __repr__(self) -> str:
        return f"<ToolRegistry tools={list(self._tools.keys())}>"
