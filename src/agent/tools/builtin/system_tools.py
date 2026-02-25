# -*- coding: utf-8 -*-
"""
系统工具集

系统级别的功能工具
"""
from typing import TYPE_CHECKING

from ..base import Tool, ToolResult, ToolParameter

if TYPE_CHECKING:
    from personality import PersonalityManager


class SwitchPersonalityTool(Tool):
    """切换性格"""

    name = "switch_personality"
    description = "切换助手性格。当用户说'切换性格'、'变成猫娘'、'换一个性格'时使用。"
    parameters = [
        ToolParameter(
            name="personality_name",
            type="string",
            description="性格名称",
            required=True,
            enum=["nekomata_assistant", "ojousama_assistant", "default_assistant"]
        )
    ]

    def __init__(self, personality_manager: 'PersonalityManager'):
        super().__init__()
        self.personality = personality_manager

    async def execute(self, personality_name: str) -> ToolResult:
        """切换人格"""
        try:
            success = self.personality.set_personality(personality_name)

            if success:
                current = self.personality.get_current()
                return ToolResult(
                    success=True,
                    data={"personality": personality_name},
                    observation=f"✅ 已切换为 {current.name} 性格！自称：{current.self_reference}"
                )
            else:
                available = ", ".join(
                    p['name'] for p in self.personality.list_personalities()
                )
                return ToolResult(
                    success=False,
                    observation=f"切换失败，可用性格：{available}",
                    error="Invalid personality name"
                )

        except Exception as e:
            return ToolResult(
                success=False,
                observation=f"切换性格失败: {str(e)}",
                error=str(e)
            )


class ClearHistoryTool(Tool):
    """清空对话历史"""

    name = "clear_history"
    description = "清空对话历史。当用户说'清空对话'、'清除历史'、'重新开始'时使用。"
    parameters = [
        ToolParameter(
            name="confirm",
            type="boolean",
            description="确认清空",
            required=False,
            default=False
        )
    ]

    def __init__(self, chat_session=None):
        super().__init__()
        self.chat_session = chat_session

    async def execute(self, confirm: bool = False) -> ToolResult:
        """清空历史"""
        if not confirm:
            return ToolResult(
                success=True,
                data={"needs_confirmation": True},
                observation="⚠️ 确定要清空对话历史吗？"
            )

        try:
            if self.chat_session:
                self.chat_session.clear_history()

            return ToolResult(
                success=True,
                data={"cleared": True},
                observation="✅ 对话历史已清空"
            )

        except Exception as e:
            return ToolResult(
                success=False,
                observation=f"清空失败: {str(e)}",
                error=str(e)
            )
