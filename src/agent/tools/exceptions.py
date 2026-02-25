# -*- coding: utf-8 -*-
"""
工具系统异常类

定义工具执行过程中的标准异常类型
"""
from typing import Optional


class ToolError(Exception):
    """工具基础异常"""

    def __init__(self, message: str, tool_name: Optional[str] = None):
        super().__init__(message)
        self.tool_name = tool_name
        self.message = message


class ToolNotFoundError(ToolError):
    """工具不存在异常"""

    def __init__(self, tool_name: str):
        super().__init__(
            message=f"工具 '{tool_name}' 不存在",
            tool_name=tool_name
        )


class ToolExecutionError(ToolError):
    """工具执行异常"""

    def __init__(
        self,
        tool_name: str,
        message: str,
        cause: Optional[Exception] = None
    ):
        super().__init__(message=message, tool_name=tool_name)
        self.cause = cause


class ToolValidationError(ToolError):
    """工具参数验证异常"""

    def __init__(self, tool_name: str, param_name: str, message: str):
        super().__init__(
            message=f"工具 '{tool_name}' 参数 '{param_name}' 验证失败: {message}",
            tool_name=tool_name
        )
        self.param_name = param_name


class ToolTimeoutError(ToolExecutionError):
    """工具执行超时异常"""

    def __init__(self, tool_name: str, timeout: float):
        super().__init__(
            tool_name=tool_name,
            message=f"工具 '{tool_name}' 执行超时 ({timeout}s)"
        )
        self.timeout = timeout
