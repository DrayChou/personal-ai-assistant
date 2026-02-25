# -*- coding: utf-8 -*-
"""
ContextBuilder - 上下文构建器

借鉴 nanobot 的 ContextBuilder 设计理念：
- 模块化构建系统提示
- 清晰描述所有能力
- 让 LLM 理解自己的工具和规则

参考: docs/plans/optimization-proposal-v2.md
"""
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger('agent.context_builder')


@dataclass
class BuildContext:
    """构建上下文的输入"""
    user_input: str
    history: list[dict] = field(default_factory=list)
    memory_context: str = ""
    personality: Optional[dict] = None
    tools: list[Any] = field(default_factory=list)
    pending_confirmation: bool = False


class ContextBuilder:
    """
    上下文构建器

    职责：
    - 构建清晰的系统提示
    - 描述所有可用工具
    - 整合记忆和人格
    - 提供使用规则

    设计理念（借鉴 nanobot）：
    - 让 LLM 看到所有工具描述
    - 用简洁的语言描述功能
    - 不预设触发规则，让 LLM 自己判断
    """

    def __init__(
        self,
        personality_manager: Optional[Any] = None,
        memory_system: Optional[Any] = None
    ):
        self.personality_manager = personality_manager
        self.memory_system = memory_system

    def build(self, context: BuildContext) -> str:
        """
        构建系统提示

        Args:
            context: 构建上下文

        Returns:
            完整的系统提示
        """
        parts = []

        # 1. 身份定义
        parts.append(self._build_identity(context))

        # 2. 工具描述
        parts.append(self._build_tools_section(context))

        # 3. 记忆上下文
        if context.memory_context:
            parts.append(self._build_memory_section(context))

        # 4. 使用规则
        parts.append(self._build_rules_section(context))

        return "\n\n".join(parts)

    def _build_identity(self, context: BuildContext) -> str:
        """构建身份定义"""
        if context.personality:
            name = context.personality.get('name', 'AI 助手')
            description = context.personality.get('description', '')
            traits = context.personality.get('traits', [])

            traits_str = "、".join(traits[:5]) if traits else ""

            return f"""## 身份

你是{name}，{description}

性格特点：{traits_str}"""

        return """## 身份

你是一个友好的个人 AI 助手，可以帮助用户管理任务、记忆和日常事务。"""

    def _build_tools_section(self, context: BuildContext) -> str:
        """构建工具描述部分"""
        if not context.tools:
            return ""

        lines = ["## 可用工具", ""]
        lines.append("你可以使用以下工具帮助用户：")
        lines.append("")

        # 按类别分组
        task_tools = []
        memory_tools = []
        other_tools = []

        for tool in context.tools:
            name = tool.name if hasattr(tool, 'name') else str(tool)

            if 'task' in name.lower():
                task_tools.append(tool)
            elif 'memory' in name.lower():
                memory_tools.append(tool)
            else:
                other_tools.append(tool)

        # 任务管理工具
        if task_tools:
            lines.append("### 任务管理")
            for tool in task_tools:
                lines.append(self._format_tool(tool))
            lines.append("")

        # 记忆工具
        if memory_tools:
            lines.append("### 记忆管理")
            for tool in memory_tools:
                lines.append(self._format_tool(tool))
            lines.append("")

        # 其他工具
        if other_tools:
            lines.append("### 其他功能")
            for tool in other_tools:
                lines.append(self._format_tool(tool))
            lines.append("")

        return "\n".join(lines)

    def _format_tool(self, tool: Any) -> str:
        """格式化工具描述"""
        name = tool.name if hasattr(tool, 'name') else str(tool)
        description = tool.description if hasattr(tool, 'description') else ""

        # 简化描述（nanobot 风格）
        desc = description.split('\n')[0] if description else ""  # 只取第一行
        if len(desc) > 100:
            desc = desc[:97] + "..."

        return f"- `{name}`: {desc}"

    def _build_memory_section(self, context: BuildContext) -> str:
        """构建记忆上下文部分"""
        return f"""## 相关记忆

{context.memory_context}"""

    def _build_rules_section(self, context: BuildContext) -> str:
        """构建规则部分"""
        rules = """## 重要规则

### 1. 自然对话优先
- 如果用户只是闲聊或问候，直接友好回复，不要调用工具
- 如果不确定用户意图，可以询问澄清

### 2. 工具使用原则
- 根据用户需求选择最合适的工具
- 如果需要多个工具，可以连续调用
- 如果工具执行失败，向用户解释原因

### 3. 确认机制
- 删除操作会自动要求确认
- 等待用户明确回复「是」或「否」后再执行"""

        return rules

    def build_for_confirmation(self, action_description: str) -> str:
        """
        构建确认提示

        Args:
            action_description: 操作描述

        Returns:
            确认提示
        """
        return f"""⚠️ 需要确认

即将执行: {action_description}

请回复「是」确认执行，或「否」取消操作。"""

    def build_tool_result(self, tool_name: str, result: Any) -> str:
        """
        构建工具结果提示

        Args:
            tool_name: 工具名称
            result: 执行结果

        Returns:
            结果提示
        """
        if hasattr(result, 'success') and result.success:
            content = result.content if hasattr(result, 'content') else str(result)
            return f"✅ {tool_name} 执行成功：{content}"
        else:
            content = result.content if hasattr(result, 'content') else str(result)
            return f"❌ {tool_name} 执行失败：{content}"


def create_context_builder(
    personality_manager: Optional[Any] = None,
    memory_system: Optional[Any] = None
) -> ContextBuilder:
    """
    创建 ContextBuilder 实例

    Args:
        personality_manager: 人格管理器
        memory_system: 记忆系统

    Returns:
        ContextBuilder 实例
    """
    return ContextBuilder(
        personality_manager=personality_manager,
        memory_system=memory_system
    )
