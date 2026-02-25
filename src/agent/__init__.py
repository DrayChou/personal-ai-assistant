# -*- coding: utf-8 -*-
"""
Agent 系统

基于 Supervisor 模式的智能体架构
支持 Function Calling 和 Multi-Step Agent 执行
"""

from .supervisor import SupervisorAgent, ExecutionMode, ExecutionPlan, Step
from .simple_agent import SimpleAgent, AgentContext, PendingAction
from .context_builder import ContextBuilder, BuildContext, create_context_builder
from .tools.base import Tool, ToolResult
from .tools.registry import ToolRegistry
from .factory import create_agent_system
from .llm_adapter import LLMAdapter, LLMResponse, ToolCall, create_llm_adapter

__all__ = [
    'SupervisorAgent',
    'SimpleAgent',
    'AgentContext',
    'PendingAction',
    'ContextBuilder',
    'BuildContext',
    'create_context_builder',
    'ExecutionMode',
    'ExecutionPlan',
    'Step',
    'Tool',
    'ToolResult',
    'ToolRegistry',
    'create_agent_system',
    'LLMAdapter',
    'LLMResponse',
    'ToolCall',
    'create_llm_adapter',
]
