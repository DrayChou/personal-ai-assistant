# -*- coding: utf-8 -*-
"""
技能基类定义

所有性格技能都需要继承 BaseSkill
"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger('personality.skills')


@dataclass
class SkillResult:
    """技能执行结果"""
    success: bool
    content: str
    data: Optional[Any] = None
    error: Optional[str] = None


class BaseSkill(ABC):
    """
    技能基类

    所有性格技能都需要继承此类并实现 execute 方法
    """

    # 技能元数据
    name: str = ""
    description: str = ""
    icon: str = "🔧"
    category: str = "general"

    # 演示模式标记 - 表示技能是否使用真实 API 还是模拟数据
    is_demo: bool = True

    # 性格特定的提示词模板
    # 不同性格可以定义不同的输出风格
    personality_templates = {
        "default": "{result}",
    }

    def __init__(self, config: dict = None):
        self.config = config or {}
        if self.is_demo:
            logger.debug(f"技能 '{self.name}' 以演示模式初始化")

    @abstractmethod
    def execute(self, **kwargs) -> SkillResult:
        """执行技能"""
        raise NotImplementedError

    def format_for_personality(self, result: SkillResult, personality_name: str) -> str:
        """
        根据性格格式化结果

        Args:
            result: 技能执行结果
            personality_name: 性格名称

        Returns:
            格式化后的文本
        """
        # 获取性格特定的模板
        template = self.personality_templates.get(
            personality_name,
            self.personality_templates.get("default", "{result}")
        )

        return template.format(
            result=result.content,
            icon=self.icon,
            name=self.name,
        )

    def get_schema(self) -> dict:
        """
        获取技能的 JSON Schema（用于 Function Calling）
        """
        return {
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "category": self.category,
        }
