# -*- coding: utf-8 -*-
"""
内置工具集

常用功能的工具实现
"""

from .chat_tool import ChatTool
from .memory_tools import SearchMemoryTool, AddMemoryTool, SummarizeMemoriesTool
from .task_tools import CreateTaskTool, ListTasksTool, CompleteTaskTool, DeleteTasksTool
from .search_tools import WebSearchTool
from .system_tools import SwitchPersonalityTool, ClearHistoryTool

__all__ = [
    # 聊天
    'ChatTool',
    # 记忆
    'SearchMemoryTool',
    'AddMemoryTool',
    'SummarizeMemoriesTool',
    # 任务
    'CreateTaskTool',
    'ListTasksTool',
    'CompleteTaskTool',
    'DeleteTasksTool',
    # 搜索
    'WebSearchTool',
    # 系统
    'SwitchPersonalityTool',
    'ClearHistoryTool',
]
