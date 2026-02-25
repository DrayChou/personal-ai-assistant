# -*- coding: utf-8 -*-
"""
Skills 系统

可配置的能力定义系统
"""

from .base import (
    Skill,
    SkillLoader,
    SkillRegistry,
    get_skill_registry
)

__all__ = [
    'Skill',
    'SkillLoader',
    'SkillRegistry',
    'get_skill_registry',
]
