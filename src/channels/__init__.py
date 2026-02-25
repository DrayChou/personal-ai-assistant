# -*- coding: utf-8 -*-
"""
渠道适配器模块

提供多平台消息统一处理能力
"""
from .base import ChannelAdapter, ChatMessage, ChatResponse
from .console import ConsoleAdapter

__all__ = [
    'ChannelAdapter',
    'ChatMessage',
    'ChatResponse',
    'ConsoleAdapter',
    'get_channel',
]


def get_channel(name: str, config: dict) -> ChannelAdapter:
    """
    工厂函数: 获取渠道适配器

    Args:
        name: 渠道名称 (console, telegram, discord, feishu)
        config: 配置字典

    Returns:
        ChannelAdapter 实例

    Raises:
        ValueError: 不支持的渠道
    """
    channels = {
        "console": ConsoleAdapter,
    }

    adapter_class = channels.get(name)
    if adapter_class is None:
        raise ValueError(f"不支持的渠道: {name}")

    return adapter_class(config)
