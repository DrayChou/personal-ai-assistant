# -*- coding: utf-8 -*-
"""
Chat 模块异常定义
"""
from typing import Optional


class LLMClientError(Exception):
    """LLM 客户端错误"""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class ModelNotSupportedError(LLMClientError):
    """模型不受支持错误"""
    pass


class APIKeyInvalidError(LLMClientError):
    """API Key 无效错误"""
    pass


class RateLimitError(LLMClientError):
    """请求频率限制错误"""
    pass
