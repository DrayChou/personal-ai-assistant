# -*- coding: utf-8 -*-
"""
搜索工具集

Web 搜索的 Function Calling 接口
"""
from typing import TYPE_CHECKING

from ..base import Tool, ToolResult, ToolParameter

if TYPE_CHECKING:
    from search import SearchTool


class WebSearchTool(Tool):
    """网络搜索"""

    name = "web_search"
    description = "搜索网络信息。当用户需要获取实时信息、查询最新数据时使用。"
    parameters = [
        ToolParameter(
            name="query",
            type="string",
            description="搜索查询词",
            required=True
        ),
        ToolParameter(
            name="num_results",
            type="integer",
            description="返回结果数量",
            required=False,
            default=5
        ),
        ToolParameter(
            name="summarize",
            type="boolean",
            description="是否总结结果",
            required=False,
            default=True
        )
    ]

    def __init__(self, search_tool: 'SearchTool'):
        super().__init__()
        self.search = search_tool

    async def execute(
        self,
        query: str,
        num_results: int = 5,
        summarize: bool = True
    ) -> ToolResult:
        """执行 Web 搜索"""
        try:
            results_text = self.search.search(
                query=query,
                num_results=num_results,
                summarize=summarize
            )

            return ToolResult(
                success=True,
                data={"query": query, "results": results_text},
                observation=f"🔍 搜索 '{query}' 完成"
            )

        except Exception as e:
            return ToolResult(
                success=False,
                observation=f"搜索失败: {str(e)}",
                error=str(e)
            )
