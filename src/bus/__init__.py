# -*- coding: utf-8 -*-
"""
消息总线 - 用于解耦通道与Agent
"""
from .events import InboundMessage, OutboundMessage
from .message_bus import MessageBus

__all__ = [
    'InboundMessage',
    'OutboundMessage',
    'MessageBus',
]
