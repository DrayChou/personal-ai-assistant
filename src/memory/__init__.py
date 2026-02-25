# -*- coding: utf-8 -*-
"""
记忆系统 - 两层架构实现
参考 SimpleMem + OpenClaw 最佳实践
"""
from .types import MemoryEntry, MemoryConfidence, MemoryType, WorkingMemorySlot
from .working_memory import (
    WorkingMemory,
    WorkingMemoryConfig,
    Message,
    estimate_tokens,
    summarize_messages,
)
from .long_term_memory import LongTermMemory
from .consolidation import MemoryConsolidation
from .retrieval import MemoryRetrieval, RetrievalResult
from .memory_system import MemorySystem
from .markdown_exporter import MarkdownExporter
from .auto_consolidation import AutoConsolidationScheduler, ConsolidationResult
from .fallback_client import FallbackMemoryClient

__all__ = [
    'MemoryEntry',
    'MemoryConfidence',
    'MemoryType',
    'WorkingMemory',
    'WorkingMemoryConfig',
    'WorkingMemorySlot',
    'Message',
    'estimate_tokens',
    'summarize_messages',
    'LongTermMemory',
    'MemoryConsolidation',
    'MemoryRetrieval',
    'RetrievalResult',
    'MemorySystem',
    'MarkdownExporter',
    'AutoConsolidationScheduler',
    'ConsolidationResult',
    'FallbackMemoryClient',
]
