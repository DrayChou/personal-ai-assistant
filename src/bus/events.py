# -*- coding: utf-8 -*-
"""
消息事件类型定义

参考 nanobot/bus/events.py
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class InboundMessage:
    """
    从聊天通道接收的消息

    Attributes:
        channel: 通道类型 (telegram, discord, cli)
        sender_id: 发送者ID
        chat_id: 聊天/频道ID
        content: 消息文本内容
        timestamp: 时间戳
        media: 媒体URL列表
        metadata: 通道特定的元数据
        session_key_override: 可选的会话键覆盖
    """
    channel: str
    sender_id: str
    chat_id: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    media: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    session_key_override: str | None = None

    @property
    def session_key(self) -> str:
        """生成唯一的会话标识键"""
        if self.session_key_override:
            return self.session_key_override
        return f"{self.channel}:{self.chat_id}"


@dataclass
class OutboundMessage:
    """
    发送到聊天通道的消息

    Attributes:
        channel: 目标通道
        chat_id: 目标聊天ID
        content: 消息内容
        reply_to: 回复的消息ID
        media: 媒体URL列表
        metadata: 通道特定的元数据
    """
    channel: str
    chat_id: str
    content: str
    reply_to: str | None = None
    media: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
