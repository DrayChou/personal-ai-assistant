# -*- coding: utf-8 -*-
"""
任务管理系统

支持：
- 任务类型：立即执行、定时执行、周期性执行、事件触发、委托
- 任务状态：待处理、进行中、等待中、阻塞、已完成、已归档
- 优先级算法：紧急度 × 重要度 × 影响度
- 自动从对话中提取任务
"""
from .types import Task, TaskType, TaskStatus, TaskPriority
from .manager import TaskManager
from .extractor import TaskExtractor

__all__ = [
    'Task',
    'TaskType',
    'TaskStatus',
    'TaskPriority',
    'TaskManager',
    'TaskExtractor',
]
