# -*- coding: utf-8 -*-
"""
任务管理器

管理任务的生命周期、状态流转、优先级计算
"""
from __future__ import annotations
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from .types import Task, TaskType, TaskStatus, TaskPriority

logger = logging.getLogger('task.manager')


class TaskManager:
    """
    任务管理器

    功能：
    - CRUD 任务
    - 优先级排序
    - 状态流转
    - 逾期检查
    - 依赖管理
    """

    def __init__(self, storage_path: str = "./data/tasks.jsonl"):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.tasks: dict[str, Task] = {}
        self._load_tasks()

    def _load_tasks(self):
        """从文件加载任务"""
        if not self.storage_path.exists():
            return

        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    task = Task.from_dict(data)
                    self.tasks[task.id] = task
            logger.info(f"已加载 {len(self.tasks)} 个任务")
        except Exception as e:
            logger.error(f"加载任务失败: {e}")

    def _save_tasks(self):
        """保存任务到文件"""
        try:
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                for task in self.tasks.values():
                    f.write(json.dumps(task.to_dict(), ensure_ascii=False) + '\n')
        except Exception as e:
            logger.error(f"保存任务失败: {e}")

    def create(
        self,
        title: str,
        description: str = "",
        task_type: TaskType | str = TaskType.IMMEDIATE,
        due_date: Optional[datetime] = None,
        scheduled_at: Optional[datetime] = None,
        priority: Optional[TaskPriority | str] = None,
        assignee: Optional[str] = None,
        tags: Optional[list[str]] = None,
        source_conversation: Optional[str] = None
    ) -> Task:
        """
        创建任务

        Args:
            title: 任务标题
            description: 任务描述
            task_type: 任务类型
            due_date: 截止日期
            scheduled_at: 定时执行时间
            priority: 优先级
            assignee: 执行者
            tags: 标签
            source_conversation: 来源对话ID

        Returns:
            创建的任务
        """
        # 处理字符串 task_type
        if isinstance(task_type, str):
            task_type = TaskType(task_type)

        # 处理字符串 priority
        if isinstance(priority, str):
            priority = TaskPriority.from_string(priority)
        elif priority is None:
            priority = TaskPriority()

        task = Task(
            title=title,
            description=description,
            task_type=task_type,
            due_date=due_date,
            scheduled_at=scheduled_at,
            priority=priority,
            assignee=assignee or "self",
            tags=tags or [],
            source_conversation=source_conversation
        )

        self.tasks[task.id] = task
        self._save_tasks()

        logger.info(f"创建任务: {task.id} - {title}")
        return task

    def get(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        return self.tasks.get(task_id)

    def update(self, task: Task) -> bool:
        """更新任务"""
        if task.id in self.tasks:
            self.tasks[task.id] = task
            self._save_tasks()
            return True
        return False

    def delete(self, task_id: str) -> bool:
        """删除任务"""
        if task_id in self.tasks:
            del self.tasks[task_id]
            self._save_tasks()
            return True
        return False

    def complete(self, task_id: str, result: str = "") -> bool:
        """
        完成任务

        Args:
            task_id: 任务ID
            result: 执行结果
        """
        task = self.tasks.get(task_id)
        if not task:
            return False

        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now()
        task.execution_result = result

        self._save_tasks()
        logger.info(f"完成任务: {task_id}")
        return True

    def complete_task(self, task_id: str, result: str = "") -> bool:
        """完成任务（别名）"""
        return self.complete(task_id, result)

    def list_tasks(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        task_type: Optional[str] = None,
    ) -> list[Task]:
        """
        列出任务（别名，支持字符串参数）

        Args:
            status: 状态筛选 (pending/completed/...)
            priority: 优先级筛选 (high/medium/low)
            task_type: 类型筛选
        """
        # 获取所有任务
        result = list(self.tasks.values())

        # 状态筛选
        if status:
            result = [t for t in result if t.status.value == status]

        # 优先级筛选
        if priority:
            priority_mapping = {"high": (0.7, 1.0), "medium": (0.4, 0.7), "low": (0.0, 0.4)}
            min_p, max_p = priority_mapping.get(priority, (0.0, 1.0))
            result = [
                t for t in result
                if min_p <= t.priority.calculate() < max_p
            ]

        # 类型筛选
        if task_type:
            result = [t for t in result if t.task_type.value == task_type]

        return result

    def start(self, task_id: str) -> bool:
        """开始执行任务"""
        task = self.tasks.get(task_id)
        if not task:
            return False

        if task.status == TaskStatus.PENDING:
            task.status = TaskStatus.IN_PROGRESS
            self._save_tasks()
            logger.info(f"开始任务: {task_id}")
            return True
        return False

    def block(self, task_id: str, reason: str) -> bool:
        """阻塞任务"""
        task = self.tasks.get(task_id)
        if not task:
            return False

        task.status = TaskStatus.BLOCKED
        task.metadata["block_reason"] = reason
        self._save_tasks()
        logger.info(f"任务阻塞: {task_id} - {reason}")
        return True

    def unblock(self, task_id: str) -> bool:
        """解除阻塞"""
        task = self.tasks.get(task_id)
        if not task:
            return False

        if task.status == TaskStatus.BLOCKED:
            task.status = TaskStatus.PENDING
            task.metadata.pop("block_reason", None)
            self._save_tasks()
            logger.info(f"任务解阻塞: {task_id}")
            return True
        return False

    def wait_for(self, task_id: str, waiting_for: str) -> bool:
        """
        设置任务为等待状态

        Args:
            task_id: 任务ID
            waiting_for: 等待什么（如"对方回复"、"文件下载完成"）
        """
        task = self.tasks.get(task_id)
        if not task:
            return False

        task.status = TaskStatus.WAITING
        task.waiting_for = waiting_for
        self._save_tasks()
        logger.info(f"任务等待: {task_id} - {waiting_for}")
        return True

    def list(
        self,
        status: Optional[TaskStatus] = None,
        task_type: Optional[TaskType] = None,
        assignee: Optional[str] = None,
        tags: Optional[list[str]] = None,
        sort_by_priority: bool = True
    ) -> list[Task]:
        """
        列出任务

        Args:
            status: 筛选状态
            task_type: 筛选类型
            assignee: 筛选执行者
            tags: 筛选标签
            sort_by_priority: 按优先级排序

        Returns:
            任务列表
        """
        result = list(self.tasks.values())

        # 筛选
        if status:
            result = [t for t in result if t.status == status]
        if task_type:
            result = [t for t in result if t.task_type == task_type]
        if assignee:
            result = [t for t in result if t.assignee == assignee]
        if tags:
            result = [t for t in result if any(tag in t.tags for tag in tags)]

        # 排序
        if sort_by_priority:
            result.sort(key=lambda t: t.calculate_priority_score(), reverse=True)

        return result

    def get_pending_tasks(self, limit: int = 10) -> list[Task]:
        """获取待处理任务（按优先级）"""
        tasks = self.list(status=TaskStatus.PENDING)
        return tasks[:limit]

    def get_overdue_tasks(self) -> list[Task]:
        """获取已逾期任务"""
        return [t for t in self.tasks.values() if t.is_overdue()]

    def get_today_tasks(self) -> list[Task]:
        """获取今日任务"""
        today = datetime.now().date()
        return [
            t for t in self.tasks.values()
            if t.due_date and t.due_date.date() == today
            and t.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]
        ]

    def check_dependencies(self, task_id: str) -> bool:
        """
        检查任务依赖是否满足

        Returns:
            True if all dependencies are completed
        """
        task = self.tasks.get(task_id)
        if not task:
            return False

        for dep_id in task.dependencies:
            dep_task = self.tasks.get(dep_id)
            if not dep_task:
                return False
            if dep_task.status != TaskStatus.COMPLETED:
                return False

        return True

    def archive_old_tasks(self, days: int = 14) -> int:
        """
        归档旧任务

        Args:
            days: 超过多少天的已完成/已取消任务会被归档

        Returns:
            归档的任务数
        """
        cutoff = datetime.now() - timedelta(days=days)
        archived = 0

        for task in list(self.tasks.values()):
            if task.status in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]:
                # 检查完成时间或创建时间
                check_time = task.completed_at or task.created_at
                if check_time < cutoff:
                    task.status = TaskStatus.ARCHIVED
                    archived += 1

        if archived > 0:
            self._save_tasks()
            logger.info(f"归档了 {archived} 个旧任务")

        return archived

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        total = len(self.tasks)
        by_status = {}
        by_type = {}

        for task in self.tasks.values():
            by_status[task.status.value] = by_status.get(task.status.value, 0) + 1
            by_type[task.task_type.value] = by_type.get(task.task_type.value, 0) + 1

        overdue = len(self.get_overdue_tasks())

        return {
            "total": total,
            "by_status": by_status,
            "by_type": by_type,
            "overdue": overdue,
        }

    def get_summary(self) -> str:
        """获取任务摘要（用于展示）"""
        lines = ["📋 任务概览"]

        stats = self.get_stats()
        lines.append(f"总任务: {stats['total']}")
        lines.append(f"逾期: {stats['overdue']}")

        # 待处理任务
        pending = self.get_pending_tasks(5)
        if pending:
            lines.append("\n🔥 优先级最高的待办:")
            for task in pending:
                score = task.calculate_priority_score()
                due = f"(截止: {task.due_date.strftime('%m-%d')})" if task.due_date else ""
                lines.append(f"  [{score:.0f}] {task.title} {due}")

        # 今日任务
        today = self.get_today_tasks()
        if today:
            lines.append(f"\n📅 今日任务 ({len(today)}):")
            for task in today:
                lines.append(f"  - {task.title}")

        return "\n".join(lines)
