# -*- coding: utf-8 -*-
"""
渠道适配器基类

定义统一的消息格式和适配器接口
"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger('channels.base')


class MessageType(Enum):
    """消息类型"""
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    AUDIO = "audio"
    VIDEO = "video"


@dataclass
class ChatMessage:
    """
    统一消息格式

    所有渠道的消息都会转换为这个统一格式
    """
    chat_id: str                   # 会话ID
    user_id: str                   # 用户ID
    content: str                   # 消息内容
    message_type: MessageType = MessageType.TEXT
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    reply_to: Optional[str] = None  # 回复的消息ID

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "chat_id": self.chat_id,
            "user_id": self.user_id,
            "content": self.content,
            "message_type": self.message_type.value,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "reply_to": self.reply_to,
        }


@dataclass
class ChatResponse:
    """
    统一响应格式

    所有渠道的响应都使用这个格式
    """
    content: str                           # 响应内容
    success: bool = True                   # 是否成功
    message_id: Optional[str] = None       # 消息ID
    metadata: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None            # 错误信息

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "content": self.content,
            "success": self.success,
            "message_id": self.message_id,
            "metadata": self.metadata,
            "error": self.error,
        }


class ChannelAdapter(ABC):
    """
    渠道适配器基类

    所有平台适配器都需要继承此类并实现抽象方法

    Example:
        class TelegramAdapter(ChannelAdapter):
            async def start(self):
                self.bot = telegram.Bot(self.config["token"])
                # ...

            async def stop(self):
                await self.bot.close()

            async def send_message(self, chat_id: str, content: str):
                await self.bot.send_message(chat_id, content)
    """

    def __init__(self, config: dict):
        """
        初始化适配器

        Args:
            config: 配置字典
        """
        self.config = config
        self._message_handlers: list[Callable] = []
        self._running = False
        logger.info(f"{self.__class__.__name__} 初始化")

    @abstractmethod
    async def start(self):
        """
        启动适配器

        子类需要实现具体的启动逻辑
        """
        pass

    @abstractmethod
    async def stop(self):
        """
        停止适配器

        子类需要实现具体的停止逻辑
        """
        pass

    @abstractmethod
    async def send_message(self, chat_id: str, content: str, **kwargs) -> ChatResponse:
        """
        发送消息

        Args:
            chat_id: 会话ID
            content: 消息内容
            **kwargs: 额外参数

        Returns:
            ChatResponse 响应对象
        """
        pass

    def on_message(self, handler: Callable[[ChatMessage], Any]):
        """
        注册消息处理器

        Args:
            handler: 消息处理函数，接收 ChatMessage 参数

        Example:
            async def handle_message(msg: ChatMessage):
                response = await agent.process(msg.content)
                return response

            adapter.on_message(handle_message)
        """
        self._message_handlers.append(handler)
        logger.debug(f"注册消息处理器: {handler.__name__}")

    def remove_handler(self, handler: Callable):
        """移除消息处理器"""
        if handler in self._message_handlers:
            self._message_handlers.remove(handler)

    async def _dispatch_message(self, message: ChatMessage) -> list[ChatResponse]:
        """
        分发消息到所有处理器

        Args:
            message: 统一消息对象

        Returns:
            所有处理器的响应列表
        """
        responses = []

        for handler in self._message_handlers:
            try:
                result = handler(message)

                # 处理异步函数
                if hasattr(result, '__await__'):
                    result = await result

                # 转换为 ChatResponse
                if isinstance(result, ChatResponse):
                    responses.append(result)
                elif isinstance(result, str):
                    responses.append(ChatResponse(content=result))
                elif result is not None:
                    responses.append(ChatResponse(content=str(result)))

            except Exception as e:
                logger.error(f"消息处理器 {handler.__name__} 执行失败: {e}")
                responses.append(ChatResponse(
                    content="",
                    success=False,
                    error=str(e)
                ))

        return responses

    @property
    def is_running(self) -> bool:
        """检查适配器是否正在运行"""
        return self._running

    def get_stats(self) -> dict:
        """
        获取适配器统计信息

        Returns:
            统计信息字典
        """
        return {
            "adapter": self.__class__.__name__,
            "running": self._running,
            "handlers": len(self._message_handlers),
        }
