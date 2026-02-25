# -*- coding: utf-8 -*-
"""
上下文构建器

将记忆系统和工作记忆整合到 LLM 上下文中
"""
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from memory import MemorySystem

logger = logging.getLogger('chat.context')


class ContextBuilder:
    """
    上下文构建器

    构建发送到 LLM 的完整上下文：
    - 系统提示（身份、能力）
    - 工作记忆（当前上下文）
    - 相关长期记忆
    - 当前对话
    """

    SYSTEM_PROMPT = """你是一个个人智能助理，帮助用户管理日常事务、记录重要信息、提供建议。

你有以下能力：
1. 记住用户的偏好和重要信息
2. 从对话中提取任务和待办事项
3. 回顾历史对话和知识

回复时：
- 简洁明了
- 如需要更多背景信息，可以询问
- 重要决策建议用户确认
"""

    def __init__(self, memory_system: "MemorySystem", personality_manager=None):
        self.memory = memory_system
        self.personality = personality_manager

    def build(
        self,
        user_message: str,
        conversation_history: list[dict],
        max_tokens: int = 3500
    ) -> list[dict]:
        """
        构建完整上下文

        Args:
            user_message: 用户当前消息
            conversation_history: 对话历史
            max_tokens: 最大Token数

        Returns:
            消息列表，用于 LLM API
        """
        messages = []

        # 1. 系统提示 + 身份信息 + 相关记忆
        system_content = self._build_system_content()

        # 2. 检索相关记忆并合并到系统提示
        memory_context = self.memory.recall(user_message, top_k=5)
        if memory_context:
            system_content += f"\n\n【相关历史信息】\n{memory_context}"

        # MiniMax 不支持多条 system 消息，合并为一条
        messages.append({"role": "system", "content": system_content})

        # 4. 添加对话历史（保留最近N条）
        # 估算剩余token
        used_tokens = self._estimate_tokens(str(messages))
        remaining_tokens = max_tokens - used_tokens

        # 保留最近的对话
        recent_history = self._trim_history(
            conversation_history,
            remaining_tokens
        )
        messages.extend(recent_history)

        # 5. 添加当前用户消息
        messages.append({"role": "user", "content": user_message})

        return messages

    def _build_system_content(self) -> str:
        """构建系统提示内容"""
        parts = []

        # 1. 添加性格系统提示（如果有）
        if self.personality:
            from personality import get_personality_manager
            pm = get_personality_manager() if self.personality is True else self.personality
            personality = pm.get_current()
            parts.append(personality.system_prompt)
        else:
            parts.append(self.SYSTEM_PROMPT)

        # 2. 添加工作记忆中的身份信息
        identity = self.memory.working_memory.slots.get('identity')
        if identity and identity.content:
            parts.append(f"\n【用户身份/偏好】\n{identity.content}")

        return "\n".join(parts)

    def _estimate_tokens(self, text: str) -> int:
        """估算Token数"""
        # 粗略估算：1 token ≈ 0.75 字符（中文）
        return int(len(text) / 0.75)

    def _trim_history(
        self,
        history: list[dict],
        max_tokens: int
    ) -> list[dict]:
        """裁剪对话历史以适应Token限制"""
        result = []
        current_tokens = 0

        # 从后往前添加（保留最近的）
        for msg in reversed(history):
            msg_tokens = self._estimate_tokens(str(msg))

            if current_tokens + msg_tokens > max_tokens:
                break

            result.insert(0, msg)
            current_tokens += msg_tokens

        return result
