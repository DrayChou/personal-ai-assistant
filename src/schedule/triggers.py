# -*- coding: utf-8 -*-
"""
触发器定义
"""
import asyncio
import inspect
import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, Optional

import urllib.request

logger = logging.getLogger('schedule.triggers')


class BaseTrigger(ABC):
    """触发器基类"""

    @abstractmethod
    async def run(self):
        """运行触发器"""
        pass


class CronTrigger(BaseTrigger):
    """Cron 触发器"""

    def __init__(
        self,
        cron_expr: str,
        timezone: str = "Asia/Shanghai",
        handler: Optional[Callable[[], Any]] = None
    ):
        self.cron_expr = cron_expr
        self.timezone = timezone
        self.handler = handler
        self.minute, self.hour, self.day, self.month, self.weekday = self._parse(cron_expr)
        self._running = False

    async def run(self):
        """运行 Cron 触发器"""
        self._running = True
        logger.info(f"CronTrigger 启动: {self.cron_expr}")

        while self._running:
            try:
                wait_seconds = self.get_next_wait_seconds()
                logger.debug(f"下次执行等待: {wait_seconds:.0f}秒")

                # 等待到下次执行时间
                await asyncio.sleep(wait_seconds)

                # 执行处理器
                if self.handler:
                    if inspect.iscoroutinefunction(self.handler):
                        await self.handler()
                    else:
                        self.handler()

            except asyncio.CancelledError:
                logger.info("CronTrigger 被取消")
                break
            except Exception as e:
                logger.error(f"CronTrigger 错误: {e}")
                await asyncio.sleep(60)  # 出错后等待1分钟

        logger.info("CronTrigger 停止")

    def stop(self):
        """停止触发器"""
        self._running = False

    def _parse(self, expr: str) -> tuple:
        """解析 Cron 表达式"""
        parts = expr.split()
        if len(parts) != 5:
            raise ValueError(f"无效的 Cron 表达式: {expr}")
        return parts

    def get_next_wait_seconds(self) -> float:
        """获取距离下次执行的等待秒数"""
        now = datetime.now()

        # 简化的实现：假设每小时检查一次
        # 实际应根据 cron 表达式计算
        next_run = now.replace(minute=0, second=0, microsecond=0)

        if self.hour != "*":
            target_hour = int(self.hour)
            next_run = next_run.replace(hour=target_hour)

            if next_run <= now:
                next_run += timedelta(days=1)
        else:
            next_run += timedelta(hours=1)

        return (next_run - now).total_seconds()


class HeartbeatTrigger(BaseTrigger):
    """
    Heartbeat 触发器

    低功耗待机，事件驱动响应
    """

    def __init__(
        self,
        name: str,
        endpoint: str,
        interval: int,
        handler: Callable[[dict], Any],
        anomaly_detector: Optional[Callable[[dict], bool]] = None
    ):
        self.name = name
        self.endpoint = endpoint
        self.interval = interval
        self.handler = handler
        self.anomaly_detector = anomaly_detector or self._default_anomaly_detector
        self._running = False

    def _default_anomaly_detector(self, data: dict) -> bool:
        """默认异常检测"""
        # 简单的异常检测示例
        if data.get('price_change', 0) > 0.15:  # 15%变化
            return True
        if data.get('error_count', 0) > 10:
            return True
        return False

    async def run(self):
        """运行 Heartbeat 监控"""
        self._running = True
        logger.info(f"Heartbeat {self.name} 启动")

        while self._running:
            try:
                # 获取简报
                briefing = await self._fetch_briefing()

                # 检查异常
                if self.anomaly_detector(briefing):
                    logger.warning(f"Heartbeat {self.name} 检测到异常")
                    if inspect.iscoroutinefunction(self.handler):
                        await self.handler(briefing)
                    else:
                        self.handler(briefing)

                # 低功耗等待
                await asyncio.sleep(self.interval)

            except asyncio.CancelledError:
                logger.info(f"Heartbeat {self.name} 被取消")
                break
            except Exception as e:
                logger.error(f"Heartbeat {self.name} 错误: {e}")
                await asyncio.sleep(self.interval)

        logger.info(f"Heartbeat {self.name} 停止")

    async def _fetch_briefing(self) -> dict:
        """获取简报"""
        if self.endpoint.startswith('http'):
            # HTTP 端点
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, self._http_fetch)
        elif callable(self.endpoint):
            # 函数端点
            if inspect.iscoroutinefunction(self.endpoint):
                return await self.endpoint()
            else:
                return self.endpoint()
        else:
            return {}

    def _http_fetch(self) -> dict:
        """HTTP 请求获取简报"""
        try:
            req = urllib.request.Request(
                self.endpoint,
                headers={'Accept': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                import json
                return json.loads(response.read().decode('utf-8'))
        except Exception as e:
            logger.error(f"HTTP 请求失败: {e}")
            return {"error": str(e)}

    def stop(self):
        """停止触发器"""
        self._running = False


class EventTrigger(BaseTrigger):
    """事件触发器"""

    def __init__(
        self,
        event_type: str,
        condition: Callable[[dict], bool],
        action: Callable[[dict], Any]
    ):
        self.event_type = event_type
        self.condition = condition
        self.action = action

    async def run(self):
        """事件触发器不需要持续运行"""
        pass

    def check_and_trigger(self, event_data: dict):
        """检查条件并触发"""
        try:
            if self.condition(event_data):
                if inspect.iscoroutinefunction(self.action):
                    asyncio.create_task(self.action(event_data))
                else:
                    self.action(event_data)
                return True
        except Exception as e:
            logger.error(f"事件处理失败: {e}")
        return False
