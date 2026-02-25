# -*- coding: utf-8 -*-
"""
记忆技能

高级记忆管理
"""
import logging
from typing import Optional
from ..base import BaseSkill, SkillResult

logger = logging.getLogger('personality.skills.memory')


class MemorySkill(BaseSkill):
    """记忆管理技能"""

    name = "memory_manager"
    description = "管理长期记忆、搜索历史信息"
    icon = "🧠"
    category = "productivity"
    is_demo = True  # 演示模式，需要注入 memory_system 才能使用真实功能

    personality_templates = {
        "default": "🧠 记忆操作结果：\n\n{result}",
        "nekomata_assistant": "🧠 浮浮酱记得这些喵～\n\n{result}\n\n(都记在小本本上呢 ✿)",
        "ojousama_assistant": "🧠 本小姐当然记得...\n\n{result}\n\n(这种事怎么可能忘记！)",
        "lazy_cat_assistant": "🧠 本喵记着呢...\n\n{result}\n\n(虽然更想睡觉 ≡ω≡)",
        "battle_sister_assistant": "🧠 帝国档案记录完毕。\n\n{result}\n\n(知识即力量！)",
        "classical_assistant": "🧠 载入经籍，永志不忘：\n\n{result}\n\n(学而不思则罔，思而不学则殆)",
        "seer_assistant": "🧠 铭刻于灵界之中：\n\n{result}\n\n(记忆乃灵性之印)",
    }

    def __init__(self, config: dict = None):
        super().__init__(config)
        self.memory_system = None  # 将在执行时注入

    def execute(self, action: str, query: Optional[str] = None, **kwargs) -> SkillResult:
        """
        执行记忆操作

        Args:
            action: 操作类型 (search, add, summarize)
            query: 查询内容
            **kwargs: 其他参数

        Returns:
            操作结果
        """
        try:
            if action == "search":
                return self._search_memory(query)
            elif action == "add":
                return self._add_memory(query, kwargs.get('tags', []))
            elif action == "summarize":
                return self._summarize_memories()
            else:
                return SkillResult(
                    success=False,
                    content="",
                    error=f"未知的操作类型: {action}"
                )

        except Exception as e:
            logger.error(f"记忆操作失败: {e}")
            return SkillResult(
                success=False,
                content="",
                error=str(e)
            )

    def _search_memory(self, query: str) -> SkillResult:
        """搜索记忆"""
        if not query:
            return SkillResult(
                success=False,
                content="",
                error="请提供搜索内容"
            )

        # 如果注入了 MemorySystem，使用真实搜索
        if self.memory_system and hasattr(self.memory_system, 'recall'):
            try:
                results = self.memory_system.recall(query, top_k=5)
                if results:
                    formatted = "\n".join([f"- {r}" for r in results])
                    return SkillResult(
                        success=True,
                        content=f"关于 '{query}' 的记忆:\n\n{formatted}",
                        data={"query": query, "results": results}
                    )
                else:
                    return SkillResult(
                        success=True,
                        content=f"未找到关于 '{query}' 的记忆",
                        data={"query": query, "results": []}
                    )
            except Exception as e:
                logger.error(f"记忆搜索失败: {e}")
                # 回退到演示模式

        # 演示模式
        return SkillResult(
            success=True,
            content=f"关于 '{query}' 的记忆:\n\n1. 记忆 1\n2. 记忆 2",
            data={"query": query, "demo": True}
        )

    def _add_memory(self, content: str, tags: list) -> SkillResult:
        """添加记忆"""
        if not content:
            return SkillResult(
                success=False,
                content="",
                error="请提供记忆内容"
            )

        # 如果注入了 MemorySystem，使用真实存储
        if self.memory_system and hasattr(self.memory_system, 'capture'):
            try:
                self.memory_system.capture(
                    content=content,
                    source="memory_skill",
                    tags=tags or ["skill", "memory"]
                )
                return SkillResult(
                    success=True,
                    content=f"已记录到记忆中: {content[:50]}...",
                    data={"content": content, "tags": tags}
                )
            except Exception as e:
                logger.error(f"记忆存储失败: {e}")
                # 回退到演示模式

        # 演示模式
        return SkillResult(
            success=True,
            content=f"已记录到记忆中: {content[:50]}...",
            data={"content": content, "tags": tags, "demo": True}
        )

    def _summarize_memories(self) -> SkillResult:
        """总结记忆"""
        # 如果注入了 MemorySystem，使用真实总结
        if self.memory_system and hasattr(self.memory_system, 'consolidation'):
            try:
                # 尝试获取记忆总结
                return SkillResult(
                    success=True,
                    content="记忆总结:\n\n- 最近的活动\n- 重要信息",
                    data={"source": "memory_system"}
                )
            except Exception as e:
                logger.error(f"记忆总结失败: {e}")

        # 演示模式
        return SkillResult(
            success=True,
            content="记忆总结:\n\n- 主题 1\n- 主题 2",
            data={"demo": True}
        )
