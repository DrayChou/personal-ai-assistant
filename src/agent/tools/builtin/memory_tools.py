# -*- coding: utf-8 -*-
"""
记忆工具集

记忆系统的 Function Calling 接口
"""
from typing import TYPE_CHECKING

from ..base import Tool, ToolResult, ToolParameter

if TYPE_CHECKING:
    from memory import MemorySystem


class SearchMemoryTool(Tool):
    """搜索记忆"""

    name = "search_memory"
    description = "搜索长期记忆。当用户问'我之前说过'、'记得吗'、'关于...的记忆'时使用。"
    parameters = [
        ToolParameter(
            name="query",
            type="string",
            description="搜索关键词",
            required=True
        ),
        ToolParameter(
            name="time_range",
            type="string",
            description="时间范围: today/week/month/all",
            required=False,
            default="all",
            enum=["today", "week", "month", "all"]
        ),
        ToolParameter(
            name="limit",
            type="integer",
            description="返回数量",
            required=False,
            default=5
        )
    ]

    def __init__(self, memory_system: 'MemorySystem'):
        super().__init__()
        self.memory = memory_system

    async def execute(self, query: str, time_range: str = "all", limit: int = 5) -> ToolResult:
        """搜索记忆"""
        try:
            results = self.memory.recall(query, top_k=limit)

            if not results or not results.strip():
                return ToolResult(
                    success=True,
                    data={"memories": [], "count": 0},
                    observation="没有找到相关记忆"
                )

            return ToolResult(
                success=True,
                data={"memories": results, "count": 1, "raw_text": True},
                observation="找到相关记忆"
            )

        except Exception as e:
            return ToolResult(
                success=False,
                observation=f"搜索记忆失败: {str(e)}",
                error=str(e)
            )


class AddMemoryTool(Tool):
    """添加记忆"""

    name = "add_memory"
    description = "添加新记忆。当用户说'记住'、'记录一下'、'保存这个信息'时使用。"
    parameters = [
        ToolParameter(
            name="content",
            type="string",
            description="要记忆的内容",
            required=True
        ),
        ToolParameter(
            name="category",
            type="string",
            description="分类: general/tech/people/projects/preferences",
            required=False,
            default="general",
            enum=["general", "tech", "people", "projects", "preferences"]
        ),
        ToolParameter(
            name="importance",
            type="integer",
            description="重要性(1-10)",
            required=False,
            default=5
        )
    ]

    def __init__(self, memory_system: 'MemorySystem'):
        super().__init__()
        self.memory = memory_system

    async def execute(self, content: str, category: str = "general", importance: int = 5) -> ToolResult:
        """添加记忆"""
        try:
            importance = max(1, min(10, importance))

            memory_id = self.memory.capture(
                content=content,
                memory_type="observation",
                confidence="fact" if importance >= 7 else "event",
                tags=[category]
            )

            return ToolResult(
                success=True,
                data={"memory_id": memory_id},
                observation=f"✅ 已记住：{content[:50]}{'...' if len(content) > 50 else ''}"
            )

        except Exception as e:
            return ToolResult(
                success=False,
                observation=f"添加记忆失败: {str(e)}",
                error=str(e)
            )


class SummarizeMemoriesTool(Tool):
    """总结记忆"""

    name = "summarize_memories"
    description = "总结特定主题的记忆。当用户说'总结一下'、'归纳一下'时使用。"
    parameters = [
        ToolParameter(
            name="topic",
            type="string",
            description="要总结的主题",
            required=True
        ),
        ToolParameter(
            name="time_range",
            type="string",
            description="时间范围: today/week/month/all",
            required=False,
            default="all",
            enum=["today", "week", "month", "all"]
        )
    ]

    def __init__(self, memory_system: 'MemorySystem'):
        super().__init__()
        self.memory = memory_system

    async def execute(self, topic: str, time_range: str = "all") -> ToolResult:
        """总结记忆"""
        try:
            results = self.memory.recall(topic, top_k=10)

            if not results or not results.strip():
                return ToolResult(
                    success=True,
                    data={"summary": None, "memories": []},
                    observation=f"没有找到关于'{topic}'的记忆"
                )

            return ToolResult(
                success=True,
                data={
                    "topic": topic,
                    "memories": results,
                    "raw_text": True
                },
                observation=f"找到关于'{topic}'的记忆"
            )

        except Exception as e:
            return ToolResult(
                success=False,
                observation=f"总结记忆失败: {str(e)}",
                error=str(e)
            )
