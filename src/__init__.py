# -*- coding: utf-8 -*-
"""
Personal AI Assistant

替代 OpenClaw 的个人智能助理
核心特性：
- 三层记忆架构（工作/长期/事件）
- 自动记忆捕获与整合
- 意图感知检索
- 全平台支持（SQLite-Vec）
- 任务管理与自动提取
- 混合调度系统
"""

__version__ = "1.0.0"
__author__ = "Personal AI Assistant Team"

# 核心模块导出
from src.memory.memory_system import MemorySystem
from src.chat.chat_session import ChatSession
from src.task.manager import TaskManager
from src.schedule.scheduler import HybridScheduler

__all__ = [
    "MemorySystem",
    "ChatSession",
    "TaskManager",
    "HybridScheduler",
    "__version__",
]
