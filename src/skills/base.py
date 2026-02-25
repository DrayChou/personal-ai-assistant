# -*- coding: utf-8 -*-
"""
Skills 系统 - 可配置的能力定义

借鉴 nanobot 的 Skills 设计理念：
- Markdown 文件定义能力
- YAML frontmatter 描述元数据
- 可热更新、可扩展

参考: docs/plans/optimization-proposal-v2.md
"""
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger('skills')


@dataclass
class Skill:
    """
    Skill 定义

    每个 Skill 描述一个能力领域：
    - name: 技能名称
    - description: 简短描述
    - content: 详细说明（Markdown）
    - always_load: 是否始终加载到系统提示
    - confirmation_required: 需要确认的工具列表
    """
    name: str
    description: str
    content: str = ""
    always_load: bool = False
    confirmation_required: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    path: Optional[Path] = None

    def get_prompt(self) -> str:
        """获取技能的系统提示"""
        return f"""## {self.name}

{self.description}

{self.content}"""


class SkillLoader:
    """
    Skill 加载器

    从 Markdown 文件加载 Skill 定义
    支持 YAML frontmatter
    """

    # YAML frontmatter 正则
    FRONTMATTER_PATTERN = re.compile(
        r'^---\s*\n(.*?)\n---\s*\n(.*)$',
        re.DOTALL
    )

    def __init__(self, skills_dir: str | Path):
        self.skills_dir = Path(skills_dir)
        self._skills: dict[str, Skill] = {}

    def load_all(self) -> dict[str, Skill]:
        """加载所有 Skills"""
        if not self.skills_dir.exists():
            logger.warning(f"Skills 目录不存在: {self.skills_dir}")
            return {}

        for skill_dir in self.skills_dir.iterdir():
            if skill_dir.is_dir():
                skill_file = skill_dir / "SKILL.md"
                if skill_file.exists():
                    try:
                        skill = self.load(skill_file)
                        self._skills[skill.name] = skill
                        logger.info(f"加载 Skill: {skill.name}")
                    except Exception as e:
                        logger.error(f"加载 Skill 失败 {skill_file}: {e}")

        return self._skills

    def load(self, skill_file: Path) -> Skill:
        """
        加载单个 Skill

        Args:
            skill_file: SKILL.md 文件路径

        Returns:
            Skill 实例
        """
        content = skill_file.read_text(encoding='utf-8')

        # 解析 frontmatter
        frontmatter, markdown = self._parse_frontmatter(content)

        # 提取字段
        name = frontmatter.get('name', skill_file.parent.name)
        description = frontmatter.get('description', '')
        always_load = frontmatter.get('always', False)
        confirmation_required = frontmatter.get('confirmation_required', [])
        tools = frontmatter.get('tools', [])

        return Skill(
            name=name,
            description=description,
            content=markdown.strip(),
            always_load=always_load,
            confirmation_required=confirmation_required,
            tools=tools,
            path=skill_file
        )

    def _parse_frontmatter(self, content: str) -> tuple[dict, str]:
        """解析 YAML frontmatter"""
        match = self.FRONTMATTER_PATTERN.match(content)
        if not match:
            return {}, content

        yaml_content = match.group(1)
        markdown = match.group(2)

        # 简单的 YAML 解析（避免引入依赖）
        frontmatter = {}
        for line in yaml_content.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()

                # 处理列表
                if value.startswith('[') and value.endswith(']'):
                    value = [
                        item.strip().strip('"\'')
                        for item in value[1:-1].split(',')
                        if item.strip()
                    ]

                frontmatter[key] = value

        return frontmatter, markdown

    def get_skill(self, name: str) -> Optional[Skill]:
        """获取指定 Skill"""
        return self._skills.get(name)

    def get_all_skills(self) -> list[Skill]:
        """获取所有 Skills"""
        return list(self._skills.values())

    def get_always_load_skills(self) -> list[Skill]:
        """获取需要始终加载的 Skills"""
        return [s for s in self._skills.values() if s.always_load]

    def get_tools_requiring_confirmation(self) -> set[str]:
        """获取需要确认的工具集合"""
        tools = set()
        for skill in self._skills.values():
            tools.update(skill.confirmation_required)
        return tools


class SkillRegistry:
    """
    Skill 注册表

    管理所有已加载的 Skills
    """

    def __init__(self, skills_dir: str | Path = "skills"):
        self.loader = SkillLoader(skills_dir)
        self._loaded = False

    def load(self) -> None:
        """加载所有 Skills"""
        if self._loaded:
            return

        self.loader.load_all()
        self._loaded = True
        logger.info(f"Skills 加载完成: {len(self.loader._skills)} 个")

    def get_skill(self, name: str) -> Optional[Skill]:
        """获取指定 Skill"""
        self._ensure_loaded()
        return self.loader.get_skill(name)

    def get_all_skills(self) -> list[Skill]:
        """获取所有 Skills"""
        self._ensure_loaded()
        return self.loader.get_all_skills()

    def get_always_load_skills(self) -> list[Skill]:
        """获取需要始终加载的 Skills"""
        self._ensure_loaded()
        return self.loader.get_always_load_skills()

    def get_tools_requiring_confirmation(self) -> set[str]:
        """获取需要确认的工具集合"""
        self._ensure_loaded()
        return self.loader.get_tools_requiring_confirmation()

    def build_skills_context(self) -> str:
        """
        构建 Skills 上下文

        将所有 always_load=True 的 Skills 合并到系统提示
        """
        self._ensure_loaded()

        parts = []
        for skill in self.get_always_load_skills():
            parts.append(skill.get_prompt())

        return "\n\n".join(parts)

    def _ensure_loaded(self) -> None:
        """确保已加载"""
        if not self._loaded:
            self.load()


# 全局实例
_skill_registry: Optional[SkillRegistry] = None


def get_skill_registry(skills_dir: str = "skills") -> SkillRegistry:
    """获取全局 Skill 注册表"""
    global _skill_registry
    if _skill_registry is None:
        _skill_registry = SkillRegistry(skills_dir)
    return _skill_registry
