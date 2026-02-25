# -*- coding: utf-8 -*-
"""
混合调度器

结合 Cron 的定时能力和 Heartbeat 的事件响应能力
"""
import asyncio
import inspect
import logging
from collections.abc import Callable
from typing import Any, Optional

from .triggers import CronTrigger, HeartbeatTrigger

logger = logging.getLogger('schedule.scheduler')


class HybridScheduler:
    """
    混合调度器

    三种调度方式：
    1. Cron - 定时执行（传统方式）
    2. Heartbeat - 监控触发（Simmer模式）
    3. Event - 事件触发
    """

    def __init__(self):
        self.cron_jobs: dict[str, tuple[CronTrigger, Callable]] = {}
        self.heartbeat_jobs: dict[str, HeartbeatTrigger] = {}
        self.event_handlers: dict[str, list[tuple[Callable, Callable]]] = {}
        self._running = False
        self._tasks: list[asyncio.Task] = []

    def schedule_cron(
        self,
        name: str,
        cron_expr: str,
        task: Callable,
        timezone: str = "Asia/Shanghai"
    ):
        """
        添加 Cron 定时任务

        Args:
            name: 任务名称
            cron_expr: Cron 表达式 (如 "0 23 * * *" 每天23点)
            task: 执行函数
            timezone: 时区
        """
        trigger = CronTrigger(cron_expr, timezone)
        self.cron_jobs[name] = (trigger, task)
        logger.info(f"添加 Cron 任务: {name} ({cron_expr})")

    def schedule_daily(
        self,
        name: str,
        hour: int,
        minute: int,
        task: Callable
    ):
        """
        添加每日定时任务

        Args:
            name: 任务名称
            hour: 小时 (0-23)
            minute: 分钟 (0-59)
            task: 执行函数
        """
        cron_expr = f"{minute} {hour} * * *"
        self.schedule_cron(name, cron_expr, task)

    def schedule_hourly(
        self,
        name: str,
        minute: int,
        task: Callable
    ):
        """
        添加每小时定时任务

        Args:
            name: 任务名称
            minute: 分钟 (0-59)
            task: 执行函数
        """
        cron_expr = f"{minute} * * * *"
        self.schedule_cron(name, cron_expr, task)

    def register_heartbeat(
        self,
        name: str,
        endpoint: str,
        check_interval: int,
        handler: Callable[[dict], Any],
        anomaly_detector: Optional[Callable[[dict], bool]] = None
    ):
        """
        注册 Heartbeat 监控

        Simmer模式：99%时间低功耗待机，事件触发即时响应

        Args:
            name: 监控名称
            endpoint: 监控端点（URL或函数）
            check_interval: 检查间隔（秒）
            handler: 异常处理函数
            anomaly_detector: 异常检测函数（可选）
        """
        trigger = HeartbeatTrigger(
            name=name,
            endpoint=endpoint,
            interval=check_interval,
            handler=handler,
            anomaly_detector=anomaly_detector
        )
        self.heartbeat_jobs[name] = trigger
        logger.info(f"添加 Heartbeat 监控: {name} (间隔: {check_interval}s)")

    def register_event(
        self,
        event_type: str,
        condition: Callable[[dict], bool],
        action: Callable[[dict], Any]
    ):
        """
        注册事件处理器

        Args:
            event_type: 事件类型
            condition: 条件函数
            action: 执行函数
        """
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append((condition, action))
        logger.info(f"添加事件处理器: {event_type}")

    def emit_event(self, event_type: str, data: dict):
        """
        触发事件

        Args:
            event_type: 事件类型
            data: 事件数据
        """
        handlers = self.event_handlers.get(event_type, [])
        triggered = 0

        for condition, action in handlers:
            try:
                if condition(data):
                    action(data)
                    triggered += 1
            except Exception as e:
                logger.error(f"事件处理失败: {e}")

        if triggered > 0:
            logger.debug(f"事件 {event_type} 触发了 {triggered} 个处理器")

    async def start(self):
        """启动调度器"""
        self._running = True
        logger.info("调度器启动")

        # 启动 Cron 任务
        for name, (trigger, task) in self.cron_jobs.items():
            t = asyncio.create_task(
                self._run_cron_job(name, trigger, task),
                name=f"cron_{name}"
            )
            self._tasks.append(t)

        # 启动 Heartbeat 监控
        for name, trigger in self.heartbeat_jobs.items():
            t = asyncio.create_task(
                trigger.run(),
                name=f"heartbeat_{name}"
            )
            self._tasks.append(t)

        # 等待所有任务
        try:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        except asyncio.CancelledError:
            logger.info("调度器任务被取消")

    async def stop(self):
        """停止调度器"""
        self._running = False

        # 取消所有任务
        for task in self._tasks:
            task.cancel()

        # 等待取消完成
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        logger.info("调度器停止")

    async def stop_all(self):
        """停止所有调度器任务（别名）"""
        await self.stop()

    async def _run_cron_job(
        self,
        name: str,
        trigger: CronTrigger,
        task: Callable
    ):
        """运行 Cron 任务"""
        while self._running:
            try:
                # 等待下次执行时间
                wait_seconds = trigger.get_next_wait_seconds()
                if wait_seconds > 0:
                    await asyncio.sleep(wait_seconds)

                if not self._running:
                    break

                # 执行任务
                logger.debug(f"执行 Cron 任务: {name}")
                if inspect.iscoroutinefunction(task):
                    await task()
                else:
                    task()

            except Exception as e:
                logger.error(f"Cron 任务 {name} 执行失败: {e}")
                await asyncio.sleep(60)  # 错误后等待1分钟

    def get_status(self) -> dict[str, Any]:
        """获取调度器状态"""
        return {
            "running": self._running,
            "cron_jobs": list(self.cron_jobs.keys()),
            "heartbeat_jobs": list(self.heartbeat_jobs.keys()),
            "event_types": list(self.event_handlers.keys()),
            "active_tasks": len(self._tasks),
        }
