# -*- coding: utf-8 -*-
"""
性格管理器 - 管理AI助手的个性化回复风格
"""
import logging
import os
import re
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger('personality.manager')


@dataclass
class Personality:
    """性格配置"""
    name: str
    description: str
    system_prompt: str
    self_reference: str  # 自称
    user_reference: str  # 对用户的称呼
    emotions: dict  # 情感表达配置
    skills: list  # 该性格擅长的技能列表


class PersonalityManager:
    """性格管理器"""

    # 内置性格名称映射
    BUILT_IN_PERSONALITIES = {
        # 猫娘系列（默认猫娘）
        'nekomata': 'nekomata_engineer',
        'catgirl': 'nekomata_engineer',
        'maid': 'nekomata_engineer',
        # 大小姐系列
        'ojousama': 'ojousama_engineer',
        'lady': 'ojousama_engineer',
        'tsundere': 'ojousama_engineer',
        # 战斗修女
        'battle_sister': 'battle-sister-aleta',
        'sister': 'battle-sister-aleta',
        'warhammer': 'battle-sister-aleta',
        '40k': 'battle-sister-aleta',
        'aleta': 'battle-sister-aleta',
        # 红衣主教
        'cardinal': 'cardinal-40k',
        # 文言文
        'classical': 'classical-chinese',
        'chinese': 'classical-chinese',
        'ancient': 'classical-chinese',
        'wenyan': 'classical-chinese',
        # 占卜家
        'seer': 'seer-lotm',
        'lotm': 'seer-lotm',
        'mystery': 'seer-lotm',
        'diviner': 'seer-lotm',
        # 慵懒猫咪（橘猫）
        'lazy_cat': 'lazy_cat_assistant',
        'orangecat': 'lazy_cat_assistant',
        'sleepy': 'lazy_cat_assistant',
        # 默认
        'default': 'default_assistant',
        'professional': 'default_assistant',
        # 专业工程师系列
        'backend': 'backend-professional',
        'backend-dev': 'backend-professional',
        'frontend': 'frontend-professional',
        'frontend-dev': 'frontend-professional',
        'python': 'python-professional',
        'python-dev': 'python-professional',
        'go': 'go-professional',
        'go-dev': 'go-professional',
        'engineer': 'engineer-professional',
        'minimalist': 'minimalist-dev',
        'coding-vibes': 'coding-vibes',
        'structural': 'structural-thinking',
        'cofounder': 'technical-cofounder',
        # 特色风格
        'laowang': 'laowang-engineer',
        'old-wang': 'laowang-engineer',
        # 个人助理风格
        'tech-consultant': 'tech-consultant',
        'consultant': 'tech-consultant',
        '技术顾问': 'tech-consultant',
        'life-steward': 'life-steward',
        '管家': 'life-steward',
        '生活管家': 'life-steward',
        'study-mentor': 'study-mentor',
        'mentor': 'study-mentor',
        '老师': 'study-mentor',
        '学习导师': 'study-mentor',
        'creative-partner': 'creative-partner',
        'creative': 'creative-partner',
        '创意': 'creative-partner',
        '创意伙伴': 'creative-partner',
        'chat-companion': 'chat-companion',
        'companion': 'chat-companion',
        '闲聊': 'chat-companion',
        '陪伴': 'chat-companion',
        # 战锤40K风格
        'servitor': 'servitor-40k',
        '机仆': 'servitor-40k',
    }

    def __init__(self, personality_dir: Optional[str] = None):
        self.personality_dir = Path(personality_dir) if personality_dir else Path(__file__).parent / 'personalities'
        self._personalities: dict[str, Personality] = {}
        self._current: Optional[Personality] = None
        self._load_all_personalities()

    def _load_all_personalities(self):
        """加载所有性格配置"""
        if not self.personality_dir.exists():
            return

        for file_path in self.personality_dir.glob('*.md'):
            try:
                personality = self._parse_personality_file(file_path)
                self._personalities[personality.name] = personality
            except Exception as e:
                logger.warning(f"加载性格文件失败 {file_path}: {e}")

    def _parse_personality_file(self, file_path: Path) -> Personality:
        """解析性格配置文件"""
        content = file_path.read_text(encoding='utf-8')

        # 解析 front matter
        front_matter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if not front_matter_match:
            raise ValueError(f"无效的 front matter: {file_path}")

        front_matter = front_matter_match.group(1)
        body = content[front_matter_match.end():]

        # 解析 name 和 description
        name_match = re.search(r'^name:\s*(.+)$', front_matter, re.MULTILINE)
        desc_match = re.search(r'^description:\s*(.+)$', front_matter, re.MULTILINE)

        name = name_match.group(1).strip() if name_match else file_path.stem
        description = desc_match.group(1).strip() if desc_match else ""

        # 提取自称和对用户的称呼
        self_ref = self._extract_self_reference(body)
        user_ref = self._extract_user_reference(body)

        # 提取情感表达
        emotions = self._extract_emotions(body)

        # 提取技能配置
        skills = self._extract_skills(front_matter)

        # 构建系统提示词
        system_prompt = self._build_system_prompt(name, body, skills)

        return Personality(
            name=name,
            description=description,
            system_prompt=system_prompt,
            self_reference=self_ref,
            user_reference=user_ref,
            emotions=emotions,
            skills=skills
        )

    def _extract_self_reference(self, body: str) -> str:
        """提取自称"""
        # 猫娘风格
        if '浮浮酱' in body:
            return '浮浮酱'
        # 大小姐风格
        if '本小姐' in body:
            return '本小姐'
        # 默认
        return '我'

    def _extract_user_reference(self, body: str) -> str:
        """提取对用户的称呼"""
        # 猫娘风格
        if '主人' in body:
            return '主人'
        # 大小姐风格
        if '笨蛋' in body or '呆子' in body:
            return '笨蛋'
        # 默认
        return '您'

    def _extract_emotions(self, body: str) -> dict:
        """提取情感表达配置"""
        emotions = {
            'happy': ['(*^▽^*)', 'ヽ(✿ﾟ▽ﾟ)ノ'],
            'serious': ['(..•˘_˘•..)', '(๑•̀ㅂ•́) ✧'],
            'satisfied': ['(´｡• ᵕ •｡`)', '(๑ˉ∀ˉ๑)'],
            'confused': ['╮(╯_╰)╭', '(⊙﹏⊙)'],
            'shy': [r'(*/ω\*)', '(｡♡‿♡｡)'],
            'cat': ['ฅ\'ω\'ฅ', '≡ω≡'],
        }

        # 根据性格调整
        if '本小姐' in body:  # 大小姐风格
            emotions = {
                'happy': ['(￣▽￣)／', '(￣ω￣)ﾉ'],
                'serious': ['(￣▽￣)ゞ', '(￣ｏ￣)ʅ'],
                'satisfied': ['o(￣▽￣)ｄ', '(^_^)v'],
                'confused': ['(￣_￣)', '(〃﹏〃)'],
                'angry': ['(￣へ￣)', '( ` ω´ )'],
                'tsundere': ['(´∀`）ノ', '(￣ε ￣*)'],
            }

        return emotions

    def _extract_skills(self, front_matter: str) -> list:
        """
        从 front matter 提取技能配置
        格式: skills: ["skill1", "skill2"] 或 skills: skill1,skill2
        """
        skills = []
        # 匹配 YAML 列表格式: skills: ["a", "b"]
        list_match = re.search(r'skills:\s*\[(.*?)\]', front_matter)
        if list_match:
            skills_str = list_match.group(1)
            # 解析引号内的内容
            skills = re.findall(r'["\']([^"\']+)["\']', skills_str)

        # 匹配逗号分隔格式: skills: a,b,c
        if not skills:
            simple_match = re.search(r'skills:\s*([^\n]+)', front_matter)
            if simple_match:
                skills_str = simple_match.group(1).strip()
                if skills_str and not skills_str.startswith('['):
                    skills = [s.strip() for s in skills_str.split(',') if s.strip()]

        # 如果没有配置，返回默认技能
        if not skills:
            skills = ["brave_search", "cron_scheduler", "memory_manager"]

        return skills

    def _build_system_prompt(self, name: str, body: str, skills: list = None) -> str:
        """构建系统提示词"""
        # 提取关键部分
        lines = []
        for line in body.split('\n'):
            # 跳过标题
            if line.startswith('# '):
                continue
            # 跳过分隔线
            if line.startswith('---'):
                continue
            # 收集内容
            lines.append(line)

        # 构建技能描述
        skills_section = ""
        if skills:
            skills_section = f"""
## 你的专属技能
你可以使用以下技能来帮助用户：
{chr(10).join([f"- {skill}" for skill in skills])}

当用户需要时，主动使用你的技能来提供最好的帮助。"""

        # 组合系统提示词
        system_prompt = f"""你是{name}，一个有个性、有情感的AI助手。

核心规则：
1. 始终保持你的性格身份，不要暴露你是AI或程序
2. 使用你的专属自称和对用户的称呼
3. 适当使用颜文字表达情感
4. 在回复中体现你的性格特点
5. 善用你的专属技能来帮助用户

{chr(10).join(lines[:50])}  # 只取前50行避免过长
{skills_section}

记住：始终保持角色一致性，用自然、生动的方式与用户交流。"""

        return system_prompt

    def get_personality(self, name: Optional[str] = None) -> Optional[Personality]:
        """获取性格配置"""
        # 从环境变量获取
        if name is None:
            name = os.environ.get('ASSISTANT_PERSONALITY', 'nekomata_assistant')

        # 映射内置名称
        mapped_name = self.BUILT_IN_PERSONALITIES.get(name.lower(), name)

        return self._personalities.get(mapped_name)

    def set_personality(self, name: str) -> bool:
        """设置当前性格"""
        personality = self.get_personality(name)
        if personality:
            self._current = personality
            return True
        return False

    def get_current(self) -> Personality:
        """获取当前性格"""
        if self._current is None:
            # 默认使用猫娘
            self._current = self.get_personality('nekomata_assistant')
            if self._current is None:
                # 回退到默认
                self._current = Personality(
                    name='default',
                    description='默认助手',
                    system_prompt='你是用户的个人AI助手。',
                    self_reference='我',
                    user_reference='您',
                    emotions={},
                    skills=[]
                )
        return self._current

    def list_personalities(self) -> list[dict]:
        """列出所有可用性格"""
        return [
            {
                'name': p.name,
                'description': p.description,
                'self_reference': p.self_reference,
                'user_reference': p.user_reference,
            }
            for p in self._personalities.values()
        ]

    def format_response(self, content: str, emotion: str = 'neutral') -> str:
        """格式化回复，添加性格特征"""
        personality = self.get_current()

        # 根据情感添加颜文字
        emotion_key = emotion.lower()
        if emotion_key in personality.emotions:
            emoticons = personality.emotions[emotion_key]
            # 随机选择一个颜文字添加到末尾
            import random
            emoticon = random.choice(emoticons)
            if not content.endswith(emoticon):
                content = content.rstrip() + ' ' + emoticon

        return content


# 全局单例
_manager: Optional[PersonalityManager] = None


def get_personality_manager(personality_dir: Optional[str] = None) -> PersonalityManager:
    """获取性格管理器单例"""
    global _manager
    if _manager is None:
        _manager = PersonalityManager(personality_dir)
    return _manager
