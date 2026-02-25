# -*- coding: utf-8 -*-
"""
社交媒体技能

Twitter 等社媒操作
"""
import os
import logging
from ..base import BaseSkill, SkillResult

logger = logging.getLogger('personality.skills.social')


class TwitterSkill(BaseSkill):
    """Twitter 操作技能"""

    name = "twitter"
    description = "获取 Twitter 时间线、发布推文、搜索推文"
    icon = "🐦"
    category = "social"
    is_demo = True  # 演示模式，需要配置 TWITTER_BEARER_TOKEN 才能使用真实功能

    personality_templates = {
        "default": "🐦 Twitter 操作结果：\n\n{result}",
        "nekomata_assistant": "🐦 浮浮酱在 Twitter 上找到这些喵～\n\n{result}\n\n(铲屎官们都在聊什么呢 ✿)",
        "ojousama_assistant": "🐦 本小姐看了眼 Twitter...\n\n{result}\n\n(这些话题还挺有意思的嘛 ￣ω￣)",
        "lazy_cat_assistant": "🐦 Twitter 上看看...\n\n{result}\n\n(还是睡觉比较舒服 ≡ω≡)",
        "battle_sister_assistant": "🐦 社交情报收集完毕。\n\n{result}\n\n(为了帝国的宣传！)",
        "classical_assistant": "🐦 社交媒体游历所得：\n\n{result}\n\n(兼听则明，偏信则暗)",
        "seer_assistant": "🐦 灵界社交网络探查：\n\n{result}\n\n(众生之声，皆为命运之线)",
    }

    def __init__(self, config: dict = None):
        super().__init__(config)
        self.bearer_token = config.get('bearer_token') if config else os.getenv('TWITTER_BEARER_TOKEN')

    def execute(self, action: str = "timeline", **kwargs) -> SkillResult:
        """
        执行 Twitter 操作

        Args:
            action: 操作类型 (timeline, search, post)
            **kwargs: 其他参数

        Returns:
            操作结果
        """
        if not self.bearer_token:
            return SkillResult(
                success=False,
                content="",
                error="未配置 Twitter API Token，请在 .env 中设置 TWITTER_BEARER_TOKEN"
            )

        try:
            if action == "timeline":
                return self._get_timeline()
            elif action == "search":
                return self._search_tweets(kwargs.get('query', ''))
            elif action == "post":
                return self._post_tweet(kwargs.get('text', ''))
            else:
                return SkillResult(
                    success=False,
                    content="",
                    error=f"未知的操作类型: {action}"
                )

        except Exception as e:
            logger.error(f"Twitter 操作失败: {e}")
            return SkillResult(
                success=False,
                content="",
                error=str(e)
            )

    def _get_timeline(self) -> SkillResult:
        """获取时间线"""
        # TODO: 集成 Twitter API v2
        return SkillResult(
            success=True,
            content="Twitter 时间线（模拟数据）:\n\n1. 推文 1\n2. 推文 2",
            data={"action": "timeline"}
        )

    def _search_tweets(self, query: str) -> SkillResult:
        """搜索推文"""
        return SkillResult(
            success=True,
            content=f"关于 '{query}' 的推文搜索结果",
            data={"query": query, "action": "search"}
        )

    def _post_tweet(self, text: str) -> SkillResult:
        """发布推文"""
        return SkillResult(
            success=True,
            content=f"已发布推文: {text[:50]}...",
            data={"text": text, "action": "post"}
        )
