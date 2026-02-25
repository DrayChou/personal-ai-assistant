# -*- coding: utf-8 -*-
"""
性格技能系统 - 为不同性格提供专属能力

每个性格可以配置自己擅长的技能，例如：
- 猫娘：擅长浏览器搜索、图像生成
- 大小姐：擅长查 GitHub 趋势、Twitter 资讯
- 战斗修女：擅长代码审查、定时任务
"""
from .registry import SkillRegistry, Skill, get_skill_registry
from .base import BaseSkill, SkillResult

__all__ = [
    'SkillRegistry',
    'Skill',
    'get_skill_registry',
    'BaseSkill',
    'SkillResult',
]
