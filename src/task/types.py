# -*- coding: utf-8 -*-
"""
任务类型定义
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
import uuid


class TaskType(Enum):
    """任务类型"""
    IMMEDIATE = "immediate"      # 立即执行（用户直接指令）
    TODO = "todo"                # 待办事项
    SCHEDULED = "scheduled"      # 定时执行（指定时间）
    RECURRING = "recurring"      # 周期性执行（cron）
    TRIGGERED = "triggered"      # 事件触发（条件满足）
    DELEGATED = "delegated"      # 委托给他人（waiting on）


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"          # 待处理
    IN_PROGRESS = "in_progress"  # 进行中
    WAITING = "waiting"          # 等待中（等待他人/外部事件）
    BLOCKED = "blocked"          # 阻塞（有依赖未满足）
    COMPLETED = "completed"      # 已完成
    CANCELLED = "cancelled"      # 已取消
    ARCHIVED = "archived"        # 已归档


@dataclass(frozen=True)
class TaskPriority:
    """任务优先级"""
    urgency: float = 0.5         # 紧急度 (0-1)
    importance: float = 0.5      # 重要度 (0-1)
    impact: float = 0.5          # 影响度 (0-1)

    def calculate(self) -> float:
        """计算优先级分数 (0-100)"""
        return self.urgency * 0.4 + self.importance * 0.4 + self.impact * 0.2

    @classmethod
    def from_string(cls, level: str) -> "TaskPriority":
        """
        从字符串创建优先级

        Args:
            level: "high" | "medium" | "low"

        Returns:
            TaskPriority 对象
        """
        mapping = {
            "high": (0.8, 0.8, 0.6),
            "medium": (0.5, 0.5, 0.5),
            "low": (0.2, 0.3, 0.2),
        }
        u, i, imp = mapping.get(level.lower(), (0.5, 0.5, 0.5))
        return cls(urgency=u, importance=i, impact=imp)


@dataclass
class Task:
    """任务定义"""
    title: str
    description: str = ""
    task_type: TaskType = TaskType.IMMEDIATE
    status: TaskStatus = TaskStatus.PENDING

    # 标识
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    created_at: datetime = field(default_factory=datetime.now)

    # 时间
    due_date: Optional[datetime] = None
    scheduled_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # 优先级
    priority: TaskPriority = field(default_factory=TaskPriority)

    # 执行
    action: Optional[str] = None           # 要执行的动作
    action_params: dict = field(default_factory=dict)
    execution_result: Optional[str] = None

    # 关系
    assignee: Optional[str] = None         # 执行者（self/他人ID）
    delegator: Optional[str] = None        # 委托者
    dependencies: list[str] = field(default_factory=list)  # 依赖的任务ID
    waiting_for: Optional[str] = None      # 等待什么

    # 追踪
    source_conversation: Optional[str] = None  # 来源对话ID
    tags: list[str] = field(default_factory=list)
    reminder_count: int = 0
    last_reminder: Optional[datetime] = None
    metadata: dict = field(default_factory=dict)

    def calculate_priority_score(self) -> float:
        """计算优先级分数"""
        base_score = self.priority.calculate()

        # 逾期提升优先级
        if self.due_date and datetime.now() > self.due_date:
            hours_overdue = (datetime.now() - self.due_date).total_seconds() / 3600
            overdue_boost = min(30, hours_overdue * 2)  # 每小时+2分，最多+30
            base_score += overdue_boost

        return min(100.0, base_score)

    def is_overdue(self) -> bool:
        """是否已逾期"""
        if self.due_date and self.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]:
            return datetime.now() > self.due_date
        return False

    def days_until_due(self) -> Optional[float]:
        """距离截止日期还有多少天"""
        if self.due_date:
            hours = (self.due_date - datetime.now()).total_seconds() / 3600
            return hours / 24
        return None

    def complete(self, result: str = ""):
        """完成任务"""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now()
        self.execution_result = result

    def to_dict(self) -> dict[str, Any]:
        """序列化"""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "task_type": self.task_type.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "priority": {
                "urgency": self.priority.urgency,
                "importance": self.priority.importance,
                "impact": self.priority.impact,
                "score": self.calculate_priority_score(),
            },
            "assignee": self.assignee,
            "delegator": self.delegator,
            "dependencies": self.dependencies,
            "waiting_for": self.waiting_for,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        """反序列化"""
        priority_data = data.get("priority", {})
        priority = TaskPriority(
            urgency=priority_data.get("urgency", 0.5),
            importance=priority_data.get("importance", 0.5),
            impact=priority_data.get("impact", 0.5),
        )

        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            title=data["title"],
            description=data.get("description", ""),
            task_type=TaskType(data.get("task_type", "immediate")),
            status=TaskStatus(data.get("status", "pending")),
            created_at=datetime.fromisoformat(data.get("created_at", datetime.now().isoformat())),
            due_date=datetime.fromisoformat(data["due_date"]) if data.get("due_date") else None,
            scheduled_at=datetime.fromisoformat(data["scheduled_at"]) if data.get("scheduled_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            priority=priority,
            assignee=data.get("assignee"),
            delegator=data.get("delegator"),
            dependencies=data.get("dependencies", []),
            waiting_for=data.get("waiting_for"),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )
