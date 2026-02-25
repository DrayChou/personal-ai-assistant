# -*- coding: utf-8 -*-
"""
Agent 工具系统

统一的工具接口，支持 Function Calling 标准
"""

from .base import Tool, ToolResult, ToolParameter
from .registry import ToolRegistry
from .decorators import tool, tool_class, register_tool
from .exceptions import (
    ToolError,
    ToolNotFoundError,
    ToolExecutionError,
    ToolValidationError,
    ToolTimeoutError,
)

__all__ = [
    'Tool',
    'ToolResult',
    'ToolParameter',
    'ToolRegistry',
    'tool',
    'tool_class',
    'register_tool',
    'ToolError',
    'ToolNotFoundError',
    'ToolExecutionError',
    'ToolValidationError',
    'ToolTimeoutError',
]
