# -*- coding: utf-8 -*-
"""
性格配置系统 - 为AI助手提供个性化回复风格

支持的性格:
- nekomata_assistant: 猫娘助手 (默认)
- ojousama_assistant: 傲娇大小姐助手
- default_assistant: 专业助手
"""
from .manager import PersonalityManager, get_personality_manager
from .skills import (
    SkillRegistry,
    Skill,
    get_skill_registry,
    BaseSkill,
    SkillResult,
)

__all__ = [
    'PersonalityManager',
    'get_personality_manager',
    'SkillRegistry',
    'Skill',
    'get_skill_registry',
    'BaseSkill',
    'SkillResult',
]
