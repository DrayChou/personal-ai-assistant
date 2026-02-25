# -*- coding: utf-8 -*-
"""
消息总线 - 异步消息分发

参考 nanobot 的消息总线实现
"""
import asyncio
import logging
from typing import Callable, Awaitable

from .events import InboundMessage, OutboundMessage

logger = logging.getLogger('bus')


class MessageBus:
    """
    消息总线

    负责：
    1. 接收来自各通道的入站消息
    2. 将出站消息分发到对应通道
    3. 解耦通道与Agent
    """

    def __init__(self):
        # 入站消息处理器列表
        self._inbound_handlers: list[Callable[[InboundMessage], Awaitable[None]]] = []
        # 出站消息处理器 (每个通道一个)
        self._outbound_handlers: dict[str, Callable[[OutboundMessage], Awaitable[None]]] = {}
        # 运行状态
        self._running = False

    def subscribe_inbound(self, handler: Callable[[InboundMessage], Awaitable[None]]) -> None:
        """
        订阅入站消息

        Args:
            handler: 异步处理函数
        """
        self._inbound_handlers.append(handler)
        logger.debug(f"入站消息处理器已订阅，当前数量: {len(self._inbound_handlers)}")

    def unsubscribe_inbound(self, handler: Callable[[InboundMessage], Awaitable[None]]) -> None:
        """取消订阅入站消息"""
        if handler in self._inbound_handlers:
            self._inbound_handlers.remove(handler)

    def register_outbound_handler(
        self,
        channel: str,
        handler: Callable[[OutboundMessage], Awaitable[None]]
    ) -> None:
        """
        注册出站消息处理器

        Args:
            channel: 通道名称
            handler: 发送消息的异步函数
        """
        self._outbound_handlers[channel] = handler
        logger.debug(f"出站消息处理器已注册: {channel}")

    async def publish_inbound(self, message: InboundMessage) -> None:
        """
        发布入站消息

        所有订阅的处理器都会收到消息
        """
        logger.debug(f"入站消息: {message.channel}:{message.sender_id}")

        # 并行调用所有处理器
        if self._inbound_handlers:
            await asyncio.gather(*[
                self._safe_call(handler, message)
                for handler in self._inbound_handlers
            ])

    async def publish_outbound(self, message: OutboundMessage) -> None:
        """
        发布出站消息

        根据 channel 路由到对应处理器
        """
        handler = self._outbound_handlers.get(message.channel)
        if handler:
            await self._safe_call(handler, message)
        else:
            logger.warning(f"无出站处理器: {message.channel}")

    async def _safe_call(self, handler, message) -> None:
        """安全调用处理器，捕获异常"""
        try:
            await handler(message)
        except Exception as e:
            logger.exception(f"消息处理器错误: {e}")
