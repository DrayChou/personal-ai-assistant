# -*- coding: utf-8 -*-
"""
定时任务技能

Cron 任务管理等
"""
import logging
from typing import Optional
from ..base import BaseSkill, SkillResult

logger = logging.getLogger('personality.skills.scheduler')


class CronSkill(BaseSkill):
    """定时任务技能"""

    name = "cron_scheduler"
    description = "创建和管理定时任务、周期性提醒"
    icon = "⏰"
    category = "productivity"
    is_demo = True  # 演示模式，未连接系统任务调度器

    personality_templates = {
        "default": "⏰ 定时任务设置完成：\n\n{result}",
        "nekomata_assistant": "⏰ 浮浮酱帮主人设好闹钟了喵～\n\n{result}\n\n(到时候会提醒主人的 ✿)",
        "ojousama_assistant": "⏰ 本小姐帮你安排好了...\n\n{result}\n\n(可别迟到了！)",
        "lazy_cat_assistant": "⏰ 设好闹钟了...\n\n{result}\n\n(到点记得起来哦 ≡ω≡)",
        "battle_sister_assistant": "⏰ 战斗日程已安排。\n\n{result}\n\n(准时是军人的天职！)",
        "classical_assistant": "⏰ 时辰已定：\n\n{result}\n\n(天时不如地利，地利不如人和)",
        "seer_assistant": "⏰ 命运节点已标记：\n\n{result}\n\n(时光流转，命运如期)",
    }

    def execute(self, action: str, time_str: Optional[str] = None, task: Optional[str] = None, **kwargs) -> SkillResult:
        """
        执行定时任务操作

        Args:
            action: 操作类型 (create, list, delete)
            time_str: 时间字符串
            task: 任务描述
            **kwargs: 其他参数

        Returns:
            操作结果
        """
        try:
            if action == "create":
                return self._create_task(time_str, task)
            elif action == "list":
                return self._list_tasks()
            elif action == "delete":
                return self._delete_task(kwargs.get('task_id'))
            else:
                return SkillResult(
                    success=False,
                    content="",
                    error=f"未知的操作类型: {action}"
                )

        except Exception as e:
            logger.error(f"定时任务操作失败: {e}")
            return SkillResult(
                success=False,
                content="",
                error=str(e)
            )

    def _create_task(self, time_str: str, task: str) -> SkillResult:
        """创建定时任务"""
        if not time_str or not task:
            return SkillResult(
                success=False,
                content="",
                error="请提供时间和任务描述"
            )

        # TODO: 集成到系统的 Task Scheduler
        return SkillResult(
            success=True,
            content=f"已设置定时任务:\n时间: {time_str}\n任务: {task}",
            data={"time": time_str, "task": task}
        )

    def _list_tasks(self) -> SkillResult:
        """列出定时任务"""
        return SkillResult(
            success=True,
            content="当前定时任务:\n\n1. 08:00 - 起床\n2. 14:00 - 会议",
            data={"count": 2}
        )

    def _delete_task(self, task_id: Optional[str]) -> SkillResult:
        """删除定时任务"""
        if not task_id:
            return SkillResult(
                success=False,
                content="",
                error="请提供任务ID"
            )

        return SkillResult(
            success=True,
            content=f"已删除任务: {task_id}",
            data={"task_id": task_id}
        )
