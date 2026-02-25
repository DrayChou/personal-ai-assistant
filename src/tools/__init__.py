# -*- coding: utf-8 -*-
"""
工具系统 - MCP与Function Call集成

支持:
- MCP (Model Context Protocol) 工具
- OpenAI Function Calling
- 自定义工具注册
- 自动配置发现和加载
- Public APIs 搜索
"""
from .mcp_client import MCPClient, MCPTool
from .function_registry import FunctionRegistry, function_tool
from .tool_executor import ToolExecutor
from .mcp_config_manager import (
    MCPConfigManager,
    MCPServiceConfig,
    MCPSourceType,
    get_config_manager,
)
from .public_api_search import (
    PublicAPISearch,
    search_public_apis,
    list_api_categories,
    SEARCH_PUBLIC_APIS_SCHEMA,
    LIST_API_CATEGORIES_SCHEMA,
)

__all__ = [
    'MCPClient',
    'MCPTool',
    'FunctionRegistry',
    'function_tool',
    'ToolExecutor',
    'MCPConfigManager',
    'MCPServiceConfig',
    'MCPSourceType',
    'get_config_manager',
    'PublicAPISearch',
    'search_public_apis',
    'list_api_categories',
    'SEARCH_PUBLIC_APIS_SCHEMA',
    'LIST_API_CATEGORIES_SCHEMA',
]
