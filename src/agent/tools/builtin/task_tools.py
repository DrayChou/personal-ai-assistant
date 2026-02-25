# -*- coding: utf-8 -*-
"""
任务工具集

任务管理的 Function Calling 接口
"""
from typing import TYPE_CHECKING
from datetime import datetime

from ..base import Tool, ToolResult, ToolParameter

if TYPE_CHECKING:
    from task import TaskManager


class CreateTaskTool(Tool):
    """创建任务"""

    name = "create_task"
    description = "创建新任务。当用户说'提醒我'、'明天要'、'记得'时使用。"
    parameters = [
        ToolParameter(
            name="title",
            type="string",
            description="任务标题",
            required=True
        ),
        ToolParameter(
            name="description",
            type="string",
            description="任务描述",
            required=False
        ),
        ToolParameter(
            name="due_date",
            type="string",
            description="截止时间(ISO格式)",
            required=False
        ),
        ToolParameter(
            name="priority",
            type="string",
            description="优先级: low/medium/high/urgent",
            required=False,
            default="medium",
            enum=["low", "medium", "high", "urgent"]
        )
    ]

    def __init__(self, task_manager: 'TaskManager'):
        super().__init__()
        self.tasks = task_manager

    async def execute(
        self,
        title: str,
        description: str = "",
        due_date: str = None,
        priority: str = "medium"
    ) -> ToolResult:
        """创建任务"""
        try:
            parsed_due = None
            if due_date:
                try:
                    parsed_due = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
                except ValueError:
                    pass

            task = self.tasks.create(
                title=title,
                description=description,
                due_date=parsed_due,
                priority=priority
            )

            return ToolResult(
                success=True,
                data={"task_id": task.id, "title": task.title},
                observation=f"✅ 已创建任务：{title}"
            )

        except Exception as e:
            return ToolResult(
                success=False,
                observation=f"创建任务失败: {str(e)}",
                error=str(e)
            )


class ListTasksTool(Tool):
    """列出任务"""

    name = "list_tasks"
    description = "列出任务。当用户说'有什么任务'、'查看任务'、'列出任务'时使用。"
    parameters = [
        ToolParameter(
            name="status",
            type="string",
            description="状态: pending/completed/all",
            required=False,
            default="pending",
            enum=["pending", "completed", "all"]
        ),
        ToolParameter(
            name="limit",
            type="integer",
            description="返回数量",
            required=False,
            default=10
        )
    ]

    def __init__(self, task_manager: 'TaskManager'):
        super().__init__()
        self.tasks = task_manager

    async def execute(self, status: str = "pending", limit: int = 10) -> ToolResult:
        """列出任务"""
        try:
            if status == "all":
                tasks = self.tasks.list_tasks()
            else:
                tasks = self.tasks.list_tasks(status=status)

            tasks = tasks[:limit]

            task_list = []
            for task in tasks:
                task_list.append({
                    "id": task.id,
                    "title": task.title,
                    "status": task.status.value if hasattr(task.status, 'value') else str(task.status),
                    "due_date": task.due_date.isoformat() if task.due_date else None,
                    "priority": task.priority.value if hasattr(task.priority, 'value') else str(task.priority)
                })

            count = len(task_list)
            status_text = {"pending": "待办", "completed": "已完成", "all": ""}.get(status, "")

            if count == 0:
                observation = f"📋 当前没有{status_text}任务"
            else:
                lines = [f"📋 找到 {count} 个{status_text}任务:"]
                for i, task in enumerate(task_list, 1):
                    priority_icon = {"high": "🔴", "urgent": "🔴", "medium": "🟡", "low": "🟢"}.get(
                        task.get("priority", "medium"), "⚪"
                    )
                    time_str = ""
                    if task.get("due_date"):
                        try:
                            dt = datetime.fromisoformat(task["due_date"].replace('Z', '+00:00'))
                            time_str = f" ⏰ {dt.strftime('%m-%d %H:%M')}"
                        except (ValueError, KeyError):
                            pass
                    lines.append(f"  {i}. {priority_icon} {task['title']}{time_str}")
                observation = "\n".join(lines)

            return ToolResult(
                success=True,
                data={"tasks": task_list, "count": count},
                observation=observation
            )

        except Exception as e:
            return ToolResult(
                success=False,
                observation=f"查询任务失败: {str(e)}",
                error=str(e)
            )


class CompleteTaskTool(Tool):
    """完成任务"""

    name = "complete_task"
    description = "完成任务。当用户说'完成任务'、'标记完成'、'做完了'时使用。"
    parameters = [
        ToolParameter(
            name="task_id",
            type="string",
            description="任务ID",
            required=False
        ),
        ToolParameter(
            name="title_keyword",
            type="string",
            description="任务标题关键词",
            required=False
        )
    ]

    def __init__(self, task_manager: 'TaskManager'):
        super().__init__()
        self.tasks = task_manager

    async def execute(self, task_id: str = None, title_keyword: str = None) -> ToolResult:
        """完成任务"""
        try:
            if task_id:
                success = self.tasks.complete_task(task_id)
                if success:
                    return ToolResult(
                        success=True,
                        data={"task_id": task_id},
                        observation="✅ 任务已标记为完成"
                    )
                else:
                    return ToolResult(
                        success=False,
                        observation="未找到该任务",
                        error="Task not found"
                    )

            if title_keyword:
                candidates = [
                    t for t in self.tasks.list_tasks(status="pending")
                    if title_keyword.lower() in t.title.lower()
                ]

                if len(candidates) == 0:
                    return ToolResult(
                        success=False,
                        observation=f"未找到包含'{title_keyword}'的任务",
                        error="No matching tasks"
                    )
                elif len(candidates) == 1:
                    self.tasks.complete_task(candidates[0].id)
                    return ToolResult(
                        success=True,
                        data={"task_id": candidates[0].id, "title": candidates[0].title},
                        observation=f"✅ 任务'{candidates[0].title}'已完成"
                    )
                else:
                    return ToolResult(
                        success=True,
                        data={
                            "needs_selection": True,
                            "candidates": [{"id": t.id, "title": t.title} for t in candidates[:5]]
                        },
                        observation=f"找到 {len(candidates)} 个匹配任务，请指定具体任务"
                    )

            return ToolResult(
                success=False,
                observation="请提供任务ID或标题关键词",
                error="Missing task identifier"
            )

        except Exception as e:
            return ToolResult(
                success=False,
                observation=f"完成任务失败: {str(e)}",
                error=str(e)
            )


class DeleteTasksTool(Tool):
    """删除任务"""

    name = "delete_tasks"
    description = "删除任务。当用户说'清理'、'删除'、'移除'、'清空'任务时使用。"
    parameters = [
        ToolParameter(
            name="task_ids",
            type="array",
            description="要删除的任务ID列表",
            required=False
        ),
        ToolParameter(
            name="delete_all",
            type="boolean",
            description="是否删除所有任务",
            required=False,
            default=False
        ),
        ToolParameter(
            name="confirmed",
            type="boolean",
            description="用户已确认删除",
            required=False,
            default=False
        )
    ]

    def __init__(self, task_manager: 'TaskManager'):
        super().__init__()
        self.tasks = task_manager

    async def execute(
        self,
        task_ids: list = None,
        delete_all: bool = False,
        confirmed: bool = False
    ) -> ToolResult:
        """删除任务"""
        try:
            # 没有确认，返回任务列表供确认
            if not confirmed:
                pending = self.tasks.list_tasks(status="pending")

                if not pending:
                    return ToolResult(
                        success=True,
                        data={"needs_confirmation": False, "count": 0},
                        observation="当前没有待办任务"
                    )

                task_lines = [f"  {i}. {t.title}" for i, t in enumerate(pending[:10], 1)]
                task_list_str = "\n".join(task_lines)

                return ToolResult(
                    success=True,
                    data={
                        "needs_confirmation": True,
                        "tasks": [{"id": t.id, "title": t.title} for t in pending[:10]],
                        "count": len(pending)
                    },
                    observation=f"🗑️ 准备删除以下 {len(pending)} 个任务:\n{task_list_str}\n\n⚠️ 确认删除？(输入 yes)"
                )

            # 执行删除
            if delete_all:
                pending = self.tasks.list_tasks(status="pending")
                count = sum(1 for t in pending if self.tasks.delete(t.id))

                return ToolResult(
                    success=True,
                    data={"deleted_count": count},
                    observation=f"✅ 已删除 {count} 个任务"
                )

            if task_ids:
                count = sum(1 for tid in task_ids if self.tasks.delete(tid))

                return ToolResult(
                    success=True,
                    data={"deleted_count": count},
                    observation=f"✅ 已删除 {count} 个任务"
                )

            return ToolResult(
                success=False,
                observation="请指定要删除的任务",
                error="No task specified"
            )

        except Exception as e:
            return ToolResult(
                success=False,
                observation=f"删除任务失败: {str(e)}",
                error=str(e)
            )
