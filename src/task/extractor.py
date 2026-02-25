# -*- coding: utf-8 -*-
"""
任务提取器

从对话中自动提取行动项（Action Items）
类似 OpenClaw + Fathom 的方案
"""
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Optional

from .types import Task, TaskType, TaskPriority

logger = logging.getLogger('task.extractor')


class TaskExtractor:
    """
    任务提取器

    从自然语言对话中提取：
    - 用户承诺要做的事
    - 对方承诺要做的事
    - 明确的截止日期
    - 依赖关系
    """

    # 时间关键词映射
    TIME_PATTERNS = {
        r'今天': 0,
        r'明天': 1,
        r'后天': 2,
        r'下周': 7,
        r'下月': 30,
        r'周末': lambda: (5 - datetime.now().weekday()) % 7 or 7,
    }

    def __init__(self, llm_client: Optional[callable] = None):
        self.llm_client = llm_client

    def extract_from_conversation(
        self,
        conversation: list[dict],
        conversation_id: Optional[str] = None
    ) -> list[Task]:
        """
        从对话中提取任务

        Args:
            conversation: 对话记录列表
                [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
            conversation_id: 对话ID

        Returns:
            提取的任务列表
        """
        if self.llm_client and len(conversation) >= 2:
            return self._llm_extract(conversation, conversation_id)
        else:
            return self._rule_based_extract(conversation, conversation_id)

    def _llm_extract(
        self,
        conversation: list[dict],
        conversation_id: Optional[str]
    ) -> list[Task]:
        """使用 LLM 提取任务"""
        # 格式化对话
        conv_text = "\n".join([
            f"{msg.get('role', 'unknown')}: {msg.get('content', '')}"
            for msg in conversation[-20:]  # 最近20条
        ])

        prompt = f"""分析以下对话，提取所有行动项（Action Items）：

{conv_text}

请区分：
1. 用户承诺要做的事（assignee: self）
2. 对方承诺要做的事（assignee: other）
3. 明确的时间要求
4. 是否有依赖关系

输出JSON格式：
{{
    "action_items": [
        {{
            "action": "具体行动描述",
            "assignee": "self" | "other",
            "due_date": "YYYY-MM-DD" | null,
            "urgency": 0.0-1.0,
            "importance": 0.0-1.0,
            "immediate": true | false
        }}
    ]
}}"""

        try:
            response = self.llm_client(prompt)
            data = json.loads(response)

            tasks = []
            for item in data.get("action_items", []):
                due_date = None
                if item.get("due_date"):
                    try:
                        due_date = datetime.fromisoformat(item["due_date"])
                    except ValueError:
                        pass

                priority = TaskPriority(
                    urgency=item.get("urgency", 0.5),
                    importance=item.get("importance", 0.5),
                )

                task = Task(
                    title=item["action"],
                    task_type=TaskType.IMMEDIATE if item.get("immediate") else TaskType.DELEGATED,
                    due_date=due_date,
                    priority=priority,
                    assignee=item.get("assignee", "self"),
                    source_conversation=conversation_id,
                    tags=["auto_extracted"]
                )
                tasks.append(task)

            return tasks

        except Exception as e:
            logger.warning(f"LLM提取失败: {e}，使用规则方法")
            return self._rule_based_extract(conversation, conversation_id)

    def _rule_based_extract(
        self,
        conversation: list[dict],
        conversation_id: Optional[str]
    ) -> list[Task]:
        """基于规则的提取（无需LLM）"""
        tasks = []

        # 合并所有文本
        full_text = " ".join([
            msg.get("content", "")
            for msg in conversation
        ])

        # 模式1: "我需要..." / "我要..." / "我会..."
        # 扩展：支持"记录"、"提醒"、"叫"、"闹钟"等
        patterns = [
            r'(?:我|我们)(?:需要|要|会|应该|得|想)([^。，！]+)',
            r'(?:记得|别忘了|记住|记录|提醒|叫)([^。，！]+)',
            r'(?:任务|TODO|todo|闹钟):?\s*([^。，！]+)',
            r'(?:帮我|请帮我)([^。，！]+)',
            r'(?:明天|后天|周末|下周|下月)([^。，！]+(?:点|分|:|\d+)[^。，！]*)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, full_text)
            for match in matches:
                title = match.strip()
                if len(title) < 3 or len(title) > 100:
                    continue

                # 解析时间
                due_date = self._parse_time_from_text(title)

                task = Task(
                    title=title,
                    task_type=TaskType.IMMEDIATE,
                    due_date=due_date,
                    assignee="self",
                    source_conversation=conversation_id,
                    tags=["rule_extracted"]
                )
                tasks.append(task)

        # 去重
        seen = set()
        unique_tasks = []
        for task in tasks:
            if task.title not in seen:
                seen.add(task.title)
                unique_tasks.append(task)

        return unique_tasks

    def _parse_time_from_text(self, text: str) -> Optional[datetime]:
        """从文本中解析时间"""
        now = datetime.now()

        for pattern, days in self.TIME_PATTERNS.items():
            if re.search(pattern, text):
                if callable(days):
                    days = days()
                return now + timedelta(days=days)

        # 尝试匹配 "X天后"
        match = re.search(r'(\d+)天后', text)
        if match:
            days = int(match.group(1))
            return now + timedelta(days=days)

        return None

    def extract_from_single_message(
        self,
        message: str,
        role: str = "user"
    ) -> list[Task]:
        """
        从单条消息中提取任务

        Args:
            message: 消息内容
            role: 角色 (user/assistant)

        Returns:
            任务列表
        """
        return self.extract_from_conversation(
            [{"role": role, "content": message}]
        )
