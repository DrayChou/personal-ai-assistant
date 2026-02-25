# -*- coding: utf-8 -*-
"""
聊天工具

用于闲聊、问候等直接回复场景
"""
from ..base import Tool, ToolResult, ToolParameter


class ChatTool(Tool):
    """
    聊天工具

    当用户没有明确任务需求，只是打招呼或闲聊时使用。
    不执行具体操作，只是标记需要 LLM 直接回复。
    """

    name = "chat"
    description = "闲聊、问候、情感交流。当用户没有明确任务需求，只是打招呼或闲聊时使用"
    parameters = [
        ToolParameter(
            name="message",
            type="string",
            description="用户的输入消息",
            required=True
        )
    ]

    async def execute(self, message: str, **kwargs) -> ToolResult:
        """
        执行聊天

        Args:
            message: 用户消息

        Returns:
            ToolResult 标记为直接回复
        """
        return ToolResult(
            success=True,
            data={"type": "direct_response", "input": message},
            observation="直接回复用户"
        )
