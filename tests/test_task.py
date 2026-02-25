# -*- coding: utf-8 -*-
"""
任务系统测试
"""
import pytest
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from src.task.types import Task, TaskPriority, TaskStatus, TaskType
from src.task.manager import TaskManager


class TestTaskTypes:
    """测试任务类型"""

    def test_task_creation(self):
        """测试任务创建"""
        task = Task(
            title="测试任务",
            description="这是一个测试任务",
            task_type=TaskType.TODO,
            priority=TaskPriority.from_string("high")
        )

        assert task.title == "测试任务"
        assert task.status == TaskStatus.PENDING
        assert task.priority.urgency == 0.8

    def test_task_completion(self):
        """测试任务完成"""
        task = Task(title="测试任务")
        assert task.status == TaskStatus.PENDING

        task.complete()
        assert task.status == TaskStatus.COMPLETED
        assert task.completed_at is not None


class TestTaskManager:
    """测试任务管理器"""

    @pytest.fixture
    def manager(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "tasks.jsonl"
            yield TaskManager(str(storage_path))

    def test_create_task(self, manager):
        """测试创建任务"""
        task = manager.create(
            title="新任务",
            description="任务描述",
            priority="high"
        )

        assert task.title == "新任务"
        assert task.id in manager.tasks

    def test_complete_task(self, manager):
        """测试完成任务"""
        task = manager.create(title="待完成任务")
        assert task.status.value == "pending"

        manager.complete_task(task.id)
        task = manager.get(task.id)
        assert task.status.value == "completed"

    def test_list_tasks_by_status(self, manager):
        """测试按状态列出任务"""
        # 创建多个任务
        task1 = manager.create(title="任务1")
        task2 = manager.create(title="任务2")
        task3 = manager.create(title="任务3")

        # 完成一个
        manager.complete_task(task1.id)

        # 按状态筛选
        pending = manager.list_tasks(status="pending")
        completed = manager.list_tasks(status="completed")

        assert len(pending) == 2
        assert len(completed) == 1

    def test_priority_filter(self, manager):
        """测试优先级筛选"""
        manager.create(title="高优先级", priority="high")
        manager.create(title="中优先级", priority="medium")
        manager.create(title="低优先级", priority="low")

        high_tasks = manager.list_tasks(priority="high")
        assert len(high_tasks) == 1
        assert high_tasks[0].title == "高优先级"
