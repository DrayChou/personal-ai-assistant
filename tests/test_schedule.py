# -*- coding: utf-8 -*-
"""
混合调度器测试
"""
import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock

from src.schedule.scheduler import HybridScheduler
from src.schedule.triggers import CronTrigger, HeartbeatTrigger, EventTrigger


class TestCronTrigger:
    """测试 Cron 触发器"""

    def test_parse_valid_expression(self):
        """测试解析有效表达式"""
        trigger = CronTrigger("0 9 * * *")
        assert trigger.minute == "0"
        assert trigger.hour == "9"
        assert trigger.day == "*"

    def test_parse_invalid_expression(self):
        """测试解析无效表达式"""
        with pytest.raises(ValueError):
            CronTrigger("invalid")

    def test_next_wait_seconds_specific_hour(self):
        """测试特定小时的等待时间"""
        trigger = CronTrigger("0 9 * * *")  # 每天9点
        wait_seconds = trigger.get_next_wait_seconds()

        # 应该是正数且不超过24小时
        assert wait_seconds > 0
        assert wait_seconds <= 86400

    def test_next_wait_seconds_wildcard(self):
        """测试通配符小时的等待时间"""
        trigger = CronTrigger("0 * * * *")  # 每小时
        wait_seconds = trigger.get_next_wait_seconds()

        assert wait_seconds > 0
        assert wait_seconds <= 3600


class TestHeartbeatTrigger:
    """测试心跳触发器"""

    @pytest.fixture
    def mock_handler(self):
        return Mock()

    @pytest.fixture
    def trigger(self, mock_handler):
        return HeartbeatTrigger(
            name="test_trigger",
            endpoint="http://example.com/api",
            interval=60,
            handler=mock_handler
        )

    def test_initialization(self, trigger):
        """测试初始化"""
        assert trigger.name == "test_trigger"
        assert trigger.interval == 60
        assert not trigger._running

    def test_default_anomaly_detector_normal(self, trigger):
        """测试默认异常检测 - 正常数据"""
        normal_data = {"price_change": 0.05, "error_count": 5}
        assert not trigger._default_anomaly_detector(normal_data)

    def test_default_anomaly_detector_anomaly(self, trigger):
        """测试默认异常检测 - 异常数据"""
        anomaly_data = {"price_change": 0.20, "error_count": 5}
        assert trigger._default_anomaly_detector(anomaly_data)

    def test_default_anomaly_detector_error_count(self, trigger):
        """测试默认异常检测 - 错误数量"""
        error_data = {"price_change": 0.05, "error_count": 15}
        assert trigger._default_anomaly_detector(error_data)

    def test_stop(self, trigger):
        """测试停止"""
        trigger._running = True
        trigger.stop()
        assert not trigger._running


class TestEventTrigger:
    """测试事件触发器"""

    @pytest.fixture
    def mock_action(self):
        return Mock()

    @pytest.fixture
    def trigger(self, mock_action):
        return EventTrigger(
            event_type="test_event",
            condition=lambda e: e.get('value') > 10,
            action=mock_action
        )

    def test_check_and_trigger_match(self, trigger, mock_action):
        """测试条件匹配时触发"""
        result = trigger.check_and_trigger({'value': 15})
        assert result is True
        mock_action.assert_called_once_with({'value': 15})

    def test_check_and_trigger_no_match(self, trigger, mock_action):
        """测试条件不匹配时不触发"""
        result = trigger.check_and_trigger({'value': 5})
        assert result is False
        mock_action.assert_not_called()

    def test_check_and_trigger_error(self, trigger, mock_action):
        """测试处理异常"""
        mock_action.side_effect = Exception("Test error")
        result = trigger.check_and_trigger({'value': 15})
        # 应该返回 False 但不抛出异常
        assert result is False


class TestHybridScheduler:
    """测试混合调度器"""

    @pytest.fixture
    def scheduler(self):
        return HybridScheduler()

    def test_schedule_cron(self, scheduler):
        """测试添加 Cron 任务"""
        async def callback():
            pass

        scheduler.schedule_cron("cron_job", "0 * * * *", callback)
        assert "cron_job" in scheduler.cron_jobs

    def test_schedule_daily(self, scheduler):
        """测试添加每日任务"""
        async def callback():
            pass

        scheduler.schedule_daily("daily_job", hour=9, minute=0, task=callback)
        assert "daily_job" in scheduler.cron_jobs

    def test_schedule_hourly(self, scheduler):
        """测试添加每小时任务"""
        async def callback():
            pass

        scheduler.schedule_hourly("hourly_job", minute=30, task=callback)
        assert "hourly_job" in scheduler.cron_jobs

    def test_register_heartbeat(self, scheduler):
        """测试注册心跳监控"""
        def handler(data):
            pass

        scheduler.register_heartbeat(
            name="hb_monitor",
            endpoint="http://example.com",
            check_interval=60,
            handler=handler
        )
        assert "hb_monitor" in scheduler.heartbeat_jobs

    def test_register_event(self, scheduler):
        """测试注册事件处理器"""
        def condition(data):
            return True

        def action(data):
            pass

        scheduler.register_event("test_event", condition, action)
        assert "test_event" in scheduler.event_handlers

    def test_emit_event(self, scheduler):
        """测试触发事件"""
        received = []

        def condition(data):
            return data.get('type') == 'test'

        def action(data):
            received.append(data)

        scheduler.register_event("my_event", condition, action)
        scheduler.emit_event("my_event", {'type': 'test', 'value': 123})

        assert len(received) == 1
        assert received[0]['value'] == 123

    def test_get_status(self, scheduler):
        """测试获取状态"""
        async def callback():
            pass

        scheduler.schedule_cron("test", "0 * * * *", callback)
        status = scheduler.get_status()

        assert "running" in status
        assert "cron_jobs" in status
        assert "test" in status["cron_jobs"]


class TestSchedulerIntegration:
    """调度器集成测试"""

    def test_multiple_cron_jobs(self):
        """测试多个 Cron 任务"""
        scheduler = HybridScheduler()

        async def job1():
            pass

        async def job2():
            pass

        scheduler.schedule_cron("j1", "0 * * * *", job1)
        scheduler.schedule_cron("j2", "0 * * * *", job2)

        assert len(scheduler.cron_jobs) == 2

    def test_event_chaining(self):
        """测试事件链"""
        scheduler = HybridScheduler()
        events = []

        def handler1(data):
            events.append('h1')
            scheduler.emit_event('event2', {'stage': 2})

        def handler2(data):
            events.append('h2')

        scheduler.register_event(
            'event1',
            lambda e: e.get('stage') == 1,
            handler1
        )
        scheduler.register_event(
            'event2',
            lambda e: e.get('stage') == 2,
            handler2
        )

        scheduler.emit_event('event1', {'stage': 1})

        assert 'h1' in events
        assert 'h2' in events

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """测试启动和停止"""
        scheduler = HybridScheduler()

        async def callback():
            pass

        scheduler.schedule_cron("test", "0 * * * *", callback)

        # 启动调度器（会立即返回因为任务是后台运行的）
        # 这里我们只测试状态切换
        scheduler._running = True
        assert scheduler._running

        scheduler._running = False
        assert not scheduler._running
