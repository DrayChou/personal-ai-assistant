# -*- coding: utf-8 -*-
"""
技能注册表

管理所有可用的性格技能
"""
import logging
from typing import Dict, List, Type, Optional
from dataclasses import dataclass
from .base import BaseSkill, SkillResult

logger = logging.getLogger('personality.skills')


@dataclass
class Skill:
    """技能注册信息"""
    name: str
    description: str
    icon: str
    category: str
    skill_class: Type[BaseSkill]
    enabled: bool = True


class SkillRegistry:
    """
    技能注册表

    管理和发现所有可用的性格技能
    """

    # 技能分类
    CATEGORIES = {
        "search": "🔍 搜索与信息获取",
        "social": "🐦 社交媒体",
        "development": "💻 开发与代码",
        "creative": "🎨 创意与生成",
        "automation": "🤖 自动化与工具",
        "productivity": "⏰ 生产力与任务",
    }

    def __init__(self):
        self._skills: Dict[str, Skill] = {}
        self._instances: Dict[str, BaseSkill] = {}
        self._load_builtin_skills()

    def _load_builtin_skills(self):
        """加载内置技能"""
        # 延迟导入避免循环依赖
        try:
            from .builtin.search import BraveSearchSkill, ExaSearchSkill
            from .builtin.browser import BrowserAutomationSkill
            from .builtin.social import TwitterSkill
            from .builtin.code import CodeAgentSkill
            from .builtin.creative import ImageGenSkill
            from .builtin.github import GitHubAITrendsSkill
            from .builtin.scheduler import CronSkill
            from .builtin.memory import MemorySkill

            # 注册搜索技能
            self.register(BraveSearchSkill)
            self.register(ExaSearchSkill)

            # 注册浏览器自动化
            self.register(BrowserAutomationSkill)

            # 注册社交媒体
            self.register(TwitterSkill)

            # 注册开发技能
            self.register(CodeAgentSkill)

            # 注册创意技能
            self.register(ImageGenSkill)

            # 注册 GitHub 技能
            self.register(GitHubAITrendsSkill)

            # 注册定时任务
            self.register(CronSkill)

            # 注册记忆技能
            self.register(MemorySkill)

            logger.info(f"已加载 {len(self._skills)} 个内置技能")

        except ImportError as e:
            logger.warning(f"部分内置技能加载失败: {e}")

    def register(self, skill_class: Type[BaseSkill]) -> bool:
        """
        注册技能

        Args:
            skill_class: 技能类（继承 BaseSkill）

        Returns:
            是否注册成功
        """
        try:
            # 创建临时实例获取元数据
            temp_instance = skill_class()

            skill = Skill(
                name=temp_instance.name or skill_class.__name__,
                description=temp_instance.description,
                icon=temp_instance.icon,
                category=temp_instance.category,
                skill_class=skill_class,
            )

            self._skills[skill.name] = skill
            logger.debug(f"注册技能: {skill.name}")
            return True

        except Exception as e:
            logger.error(f"注册技能失败: {e}")
            return False

    def get(self, name: str) -> Optional[Skill]:
        """获取技能信息"""
        return self._skills.get(name)

    def get_instance(self, name: str, config: dict = None) -> Optional[BaseSkill]:
        """
        获取技能实例

        Args:
            name: 技能名称
            config: 技能配置

        Returns:
            技能实例
        """
        skill = self._skills.get(name)
        if not skill:
            return None

        # 检查是否有缓存实例
        cache_key = f"{name}:{hash(str(config))}"
        if cache_key in self._instances:
            return self._instances[cache_key]

        # 创建新实例
        try:
            instance = skill.skill_class(config)
            self._instances[cache_key] = instance
            return instance
        except Exception as e:
            logger.error(f"创建技能实例失败 {name}: {e}")
            return None

    def list_skills(self, category: str = None, enabled_only: bool = True) -> List[Skill]:
        """
        列出所有技能

        Args:
            category: 按类别筛选
            enabled_only: 只显示启用的技能

        Returns:
            技能列表
        """
        skills = self._skills.values()

        if enabled_only:
            skills = [s for s in skills if s.enabled]

        if category:
            skills = [s for s in skills if s.category == category]

        return list(skills)

    def list_categories(self) -> Dict[str, str]:
        """列出所有技能类别"""
        return self.CATEGORIES.copy()

    def execute(self, name: str, personality: str = "default", **kwargs) -> SkillResult:
        """
        执行技能

        Args:
            name: 技能名称
            personality: 性格名称（用于格式化输出）
            **kwargs: 技能参数

        Returns:
            执行结果
        """
        instance = self.get_instance(name)
        if not instance:
            return SkillResult(
                success=False,
                content="",
                error=f"技能不存在: {name}"
            )

        try:
            result = instance.execute(**kwargs)

            # 根据性格格式化
            if result.success:
                result.content = instance.format_for_personality(result, personality)

            return result

        except Exception as e:
            logger.error(f"执行技能失败 {name}: {e}")
            return SkillResult(
                success=False,
                content="",
                error=str(e)
            )

    def get_function_schemas(self) -> List[dict]:
        """
        获取所有技能的 Function Calling Schema

        Returns:
            OpenAI Function Schema 列表
        """
        schemas = []
        for skill in self._skills.values():
            if skill.enabled:
                instance = self.get_instance(skill.name)
                if instance:
                    schemas.append(instance.get_schema())
        return schemas


# 全局注册表
_registry: Optional[SkillRegistry] = None


def get_skill_registry() -> SkillRegistry:
    """获取技能注册表单例"""
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
    return _registry
