# -*- coding: utf-8 -*-
"""
Agent 系统初始化与整合

提供便捷的 Agent 系统创建函数
"""
from typing import TYPE_CHECKING, Optional

from . import SupervisorAgent, ToolRegistry
from .tools.builtin import (
    ChatTool,
    SearchMemoryTool, AddMemoryTool, SummarizeMemoriesTool,
    CreateTaskTool, ListTasksTool, CompleteTaskTool, DeleteTasksTool,
    WebSearchTool,
    SwitchPersonalityTool, ClearHistoryTool,
)

if TYPE_CHECKING:
    from memory import MemorySystem
    from task import TaskManager
    from search import SearchTool
    from personality import PersonalityManager


def create_agent_system(
    llm_client,
    memory_system: 'MemorySystem',
    task_manager: 'TaskManager',
    search_tool: Optional['SearchTool'] = None,
    personality_manager: Optional['PersonalityManager'] = None,
    chat_session=None,
    fast_path_classifier=None
) -> SupervisorAgent:
    """
    创建并配置 Agent 系统

    Args:
        llm_client: LLM 客户端
        memory_system: 记忆系统
        task_manager: 任务管理器
        search_tool: 搜索工具（可选）
        personality_manager: 人格管理器（可选）
        chat_session: 对话会话（用于清空历史，可选）
        fast_path_classifier: 快速路径分类器（可选）

    Returns:
        配置好的 SupervisorAgent
    """
    # 创建工具注册表
    registry = ToolRegistry()

    # 基础工具
    tools = [
        # 系统工具
        ChatTool(),

        # 记忆工具
        SearchMemoryTool(memory_system),
        AddMemoryTool(memory_system),
        SummarizeMemoriesTool(memory_system),

        # 任务工具
        CreateTaskTool(task_manager),
        ListTasksTool(task_manager),
        CompleteTaskTool(task_manager),
        DeleteTasksTool(task_manager),
    ]

    # 可选工具
    if search_tool:
        tools.append(WebSearchTool(search_tool))

    if personality_manager:
        tools.append(SwitchPersonalityTool(personality_manager))

    if chat_session:
        tools.append(ClearHistoryTool(chat_session))

    # 注册所有工具
    registry.register_multiple(tools)

    # 创建 Supervisor Agent
    agent = SupervisorAgent(
        llm_client=llm_client,
        tool_registry=registry,
        fast_path_classifier=fast_path_classifier,
        memory_system=memory_system,
        max_steps=10,
        retry_attempts=3,
        retry_delay=1.0,
        enable_memory_context=True,
        context_memory_limit=5
    )

    return agent
