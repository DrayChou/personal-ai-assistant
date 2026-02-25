# -*- coding: utf-8 -*-
"""
渠道适配器测试
"""
import asyncio
import pytest

from src.channels import (
    ChannelAdapter,
    ChatMessage,
    ChatResponse,
    ConsoleAdapter,
    get_channel,
)
from src.channels.base import MessageType


class TestChatMessage:
    """测试统一消息格式"""

    def test_create_message(self):
        """测试创建消息"""
        msg = ChatMessage(
            chat_id="test_chat",
            user_id="test_user",
            content="Hello World"
        )

        assert msg.chat_id == "test_chat"
        assert msg.user_id == "test_user"
        assert msg.content == "Hello World"
        assert msg.message_type == MessageType.TEXT
        assert msg.timestamp is not None

    def test_message_to_dict(self):
        """测试消息转换为字典"""
        msg = ChatMessage(
            chat_id="chat_1",
            user_id="user_1",
            content="Test message",
            metadata={"key": "value"}
        )

        d = msg.to_dict()

        assert d["chat_id"] == "chat_1"
        assert d["user_id"] == "user_1"
        assert d["content"] == "Test message"
        assert d["metadata"]["key"] == "value"

    def test_message_with_reply(self):
        """测试带回复的消息"""
        msg = ChatMessage(
            chat_id="chat_1",
            user_id="user_1",
            content="Reply content",
            reply_to="original_msg_id"
        )

        assert msg.reply_to == "original_msg_id"


class TestChatResponse:
    """测试统一响应格式"""

    def test_success_response(self):
        """测试成功响应"""
        response = ChatResponse(
            content="Success",
            success=True,
            message_id="msg_123"
        )

        assert response.success is True
        assert response.content == "Success"
        assert response.error is None

    def test_error_response(self):
        """测试错误响应"""
        response = ChatResponse(
            content="",
            success=False,
            error="Something went wrong"
        )

        assert response.success is False
        assert response.error == "Something went wrong"

    def test_response_to_dict(self):
        """测试响应转换为字典"""
        response = ChatResponse(
            content="Test",
            success=True,
            message_id="msg_1",
            metadata={"sent": True}
        )

        d = response.to_dict()

        assert d["content"] == "Test"
        assert d["success"] is True
        assert d["message_id"] == "msg_1"


class TestConsoleAdapter:
    """测试控制台适配器"""

    @pytest.fixture
    def adapter(self):
        """创建适配器实例"""
        return ConsoleAdapter({
            "user_id": "test_user",
            "chat_id": "test_chat",
            "welcome": "Test Welcome"
        })

    def test_adapter_initialization(self, adapter):
        """测试适配器初始化"""
        assert adapter.user_id == "test_user"
        assert adapter.chat_id == "test_chat"
        assert adapter.welcome == "Test Welcome"
        assert adapter.is_running is False

    def test_get_stats(self, adapter):
        """测试获取统计信息"""
        stats = adapter.get_stats()

        assert stats["adapter"] == "ConsoleAdapter"
        assert stats["running"] is False
        assert stats["handlers"] == 0

    def test_register_handler(self, adapter):
        """测试注册消息处理器"""
        def handler(msg: ChatMessage):
            return "response"

        adapter.on_message(handler)

        assert len(adapter._message_handlers) == 1

    def test_remove_handler(self, adapter):
        """测试移除消息处理器"""
        def handler(msg: ChatMessage):
            return "response"

        adapter.on_message(handler)
        adapter.remove_handler(handler)

        assert len(adapter._message_handlers) == 0

    @pytest.mark.asyncio
    async def test_send_message(self, adapter):
        """测试发送消息"""
        await adapter.start()

        response = await adapter.send_message(
            chat_id="test_chat",
            content="Test message"
        )

        assert response.success is True
        assert response.content == "Test message"

        await adapter.stop()

    @pytest.mark.asyncio
    async def test_send_message_when_stopped(self, adapter):
        """测试适配器停止时发送消息"""
        response = await adapter.send_message(
            chat_id="test_chat",
            content="Test message"
        )

        assert response.success is False
        assert "未运行" in response.error

    @pytest.mark.asyncio
    async def test_dispatch_message(self, adapter):
        """测试消息分发"""
        received = []

        async def handler(msg: ChatMessage):
            received.append(msg)
            return f"Echo: {msg.content}"

        adapter.on_message(handler)
        await adapter.start()

        message = ChatMessage(
            chat_id="test_chat",
            user_id="test_user",
            content="Hello"
        )

        responses = await adapter._dispatch_message(message)

        assert len(responses) == 1
        assert "Echo" in responses[0].content
        assert len(received) == 1

        await adapter.stop()

    @pytest.mark.asyncio
    async def test_handler_exception(self, adapter):
        """测试处理器异常处理"""
        def error_handler(msg: ChatMessage):
            raise ValueError("Handler error")

        adapter.on_message(error_handler)
        await adapter.start()

        message = ChatMessage(
            chat_id="test_chat",
            user_id="test_user",
            content="Hello"
        )

        responses = await adapter._dispatch_message(message)

        assert len(responses) == 1
        assert responses[0].success is False

        await adapter.stop()


class TestGetChannel:
    """测试工厂函数"""

    def test_get_console_channel(self):
        """测试获取控制台适配器"""
        adapter = get_channel("console", {})

        assert isinstance(adapter, ConsoleAdapter)

    def test_get_unsupported_channel(self):
        """测试获取不支持的渠道"""
        with pytest.raises(ValueError) as exc_info:
            get_channel("unsupported", {})

        assert "不支持的渠道" in str(exc_info.value)


class TestMessageType:
    """测试消息类型枚举"""

    def test_message_types(self):
        """测试消息类型"""
        assert MessageType.TEXT.value == "text"
        assert MessageType.IMAGE.value == "image"
        assert MessageType.FILE.value == "file"
        assert MessageType.AUDIO.value == "audio"
        assert MessageType.VIDEO.value == "video"


class TestAdapterLifecycle:
    """测试适配器生命周期"""

    @pytest.fixture
    def adapter(self):
        return ConsoleAdapter({})

    @pytest.mark.asyncio
    async def test_start_stop(self, adapter):
        """测试启动和停止"""
        assert adapter.is_running is False

        await adapter.start()
        assert adapter.is_running is True

        await adapter.stop()
        assert adapter.is_running is False

    @pytest.mark.asyncio
    async def test_double_start(self, adapter):
        """测试重复启动"""
        await adapter.start()
        await adapter.start()  # 应该不报错

        assert adapter.is_running is True
        await adapter.stop()

    @pytest.mark.asyncio
    async def test_double_stop(self, adapter):
        """测试重复停止"""
        await adapter.start()
        await adapter.stop()
        await adapter.stop()  # 应该不报错

        assert adapter.is_running is False
