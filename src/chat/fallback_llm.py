# -*- coding: utf-8 -*-
"""
LLM Provider Fallback 机制

支持主 LLM 失败时自动切换到备用 LLM
"""
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Generator, Optional

from .llm_client import LLMClient, create_llm_client
from .exceptions import LLMClientError

logger = logging.getLogger('chat.llm.fallback')


class FallbackStrategy(Enum):
    """Fallback 策略"""
    FAIL_FAST = "fail_fast"        # 主 LLM 失败立即报错
    FALLBACK_ONCE = "fallback_once"  # 主 LLM 失败后尝试一次 Fallback
    ALWAYS_FALLBACK = "always_fallback"  # 每次都尝试 Fallback


@dataclass
class FallbackConfig:
    """
    Fallback 配置

    Example:
        config = FallbackConfig(
            provider="openai",
            api_key="sk-xxx",
            model="gpt-4o-mini",
            fallback_enabled=True,
            fallback_provider="ollama",
            fallback_base_url="http://localhost:11434",
            fallback_model="qwen2.5:14b"
        )
    """
    # 主 LLM 配置
    provider: str = "openai"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: str = "gpt-4o-mini"

    # Fallback 配置
    fallback_enabled: bool = False
    fallback_provider: str = "ollama"
    fallback_api_key: Optional[str] = None
    fallback_base_url: str = "http://localhost:11434"
    fallback_model: str = "qwen2.5:14b"

    # 策略配置
    strategy: FallbackStrategy = FallbackStrategy.FALLBACK_ONCE
    max_retries: int = 1           # 最大重试次数
    retry_delay: float = 1.0       # 重试延迟（秒）
    timeout: int = 120             # 请求超时（秒）


@dataclass
class FallbackStats:
    """Fallback 统计信息"""
    total_requests: int = 0
    primary_success: int = 0
    primary_failures: int = 0
    fallback_requests: int = 0
    fallback_success: int = 0
    fallback_failures: int = 0
    last_error: Optional[str] = None
    using_fallback: bool = False


class FallbackLLMClient(LLMClient):
    """
    支持 Fallback 的 LLM 客户端

    当主 LLM 失败时，自动切换到备用 LLM

    Example:
        config = FallbackConfig(
            provider="minimax",
            api_key="xxx",
            fallback_enabled=True,
            fallback_provider="ollama"
        )

        client = FallbackLLMClient(config)

        # 自动使用 Fallback
        response = client.generate(messages)
    """

    def __init__(self, config: FallbackConfig):
        """
        初始化 Fallback LLM 客户端

        Args:
            config: Fallback 配置
        """
        self.config = config
        self.stats = FallbackStats()

        # 创建主 LLM 客户端
        self._primary = self._create_client(
            provider=config.provider,
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.model
        )

        # 创建 Fallback LLM 客户端
        self._fallback: Optional[LLMClient] = None
        if config.fallback_enabled:
            self._fallback = self._create_client(
                provider=config.fallback_provider,
                api_key=config.fallback_api_key,
                base_url=config.fallback_base_url,
                model=config.fallback_model
            )
            logger.info(f"Fallback LLM 已启用: {config.fallback_provider}/{config.fallback_model}")

        logger.info(f"LLM 客户端初始化: {config.provider}/{config.model}")

    def _create_client(
        self,
        provider: str,
        api_key: Optional[str],
        base_url: Optional[str],
        model: str
    ) -> LLMClient:
        """创建 LLM 客户端"""
        kwargs: dict[str, Any] = {"model": model}

        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["base_url"] = base_url

        return create_llm_client(provider, **kwargs)

    def generate(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        response_format: Optional[dict] = None
    ) -> str:
        """
        生成回复（带 Fallback）

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大 token 数
            response_format: 响应格式

        Returns:
            生成的回复

        Raises:
            LLMClientError: 主 LLM 和 Fallback LLM 都失败时
        """
        self.stats.total_requests += 1

        # 尝试主 LLM
        try:
            result = self._primary.generate(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format
            )
            self.stats.primary_success += 1
            self.stats.using_fallback = False
            return result

        except Exception as e:
            self.stats.primary_failures += 1
            self.stats.last_error = str(e)
            logger.warning(f"主 LLM 调用失败: {e}")

            # 检查是否启用 Fallback
            if not self.config.fallback_enabled or not self._fallback:
                raise

            # 检查策略
            if self.config.strategy == FallbackStrategy.FAIL_FAST:
                raise

            # 尝试 Fallback
            logger.info("切换到 Fallback LLM")
            self.stats.fallback_requests += 1

            try:
                result = self._fallback.generate(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format
                )
                self.stats.fallback_success += 1
                self.stats.using_fallback = True
                return result

            except Exception as fallback_error:
                self.stats.fallback_failures += 1
                logger.error(f"Fallback LLM 也失败: {fallback_error}")
                raise LLMClientError(
                    f"主 LLM 和 Fallback LLM 都失败: "
                    f"主={str(e)[:100]}, Fallback={str(fallback_error)[:100]}"
                )

    def stream_generate(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Generator[str, None, None]:
        """
        流式生成回复（带 Fallback）

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大 token 数

        Yields:
            生成的文本片段
        """
        self.stats.total_requests += 1

        # 尝试主 LLM
        try:
            has_content = False
            for chunk in self._primary.stream_generate(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            ):
                has_content = True
                yield chunk

            if has_content:
                self.stats.primary_success += 1
                self.stats.using_fallback = False
                return

        except Exception as e:
            self.stats.primary_failures += 1
            self.stats.last_error = str(e)
            logger.warning(f"主 LLM 流式调用失败: {e}")

            # 检查是否启用 Fallback
            if not self.config.fallback_enabled or not self._fallback:
                raise

            # 尝试 Fallback
            logger.info("切换到 Fallback LLM (流式)")
            self.stats.fallback_requests += 1

            try:
                for chunk in self._fallback.stream_generate(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                ):
                    yield chunk

                self.stats.fallback_success += 1
                self.stats.using_fallback = True

            except Exception as fallback_error:
                self.stats.fallback_failures += 1
                logger.error(f"Fallback LLM 流式也失败: {fallback_error}")
                raise LLMClientError(
                    f"主 LLM 和 Fallback LLM 流式都失败: "
                    f"主={str(e)[:100]}, Fallback={str(fallback_error)[:100]}"
                )

    def get_stats(self) -> dict:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        return {
            "total_requests": self.stats.total_requests,
            "primary_success": self.stats.primary_success,
            "primary_failures": self.stats.primary_failures,
            "primary_success_rate": (
                self.stats.primary_success / self.stats.total_requests * 100
                if self.stats.total_requests > 0 else 0
            ),
            "fallback_enabled": self.config.fallback_enabled,
            "fallback_requests": self.stats.fallback_requests,
            "fallback_success": self.stats.fallback_success,
            "fallback_failures": self.stats.fallback_failures,
            "using_fallback": self.stats.using_fallback,
            "last_error": self.stats.last_error,
        }

    def reset_stats(self):
        """重置统计信息"""
        self.stats = FallbackStats()

    @property
    def primary_client(self) -> LLMClient:
        """获取主 LLM 客户端"""
        return self._primary

    @property
    def fallback_client(self) -> Optional[LLMClient]:
        """获取 Fallback LLM 客户端"""
        return self._fallback


def create_fallback_client(
    provider: str = "openai",
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: str = "gpt-4o-mini",
    fallback_enabled: bool = False,
    fallback_provider: str = "ollama",
    fallback_base_url: str = "http://localhost:11434",
    fallback_model: str = "qwen2.5:14b",
    **kwargs
) -> FallbackLLMClient:
    """
    创建支持 Fallback 的 LLM 客户端

    Args:
        provider: 主 LLM 提供商
        api_key: API Key
        base_url: API 基础 URL
        model: 主模型名称
        fallback_enabled: 是否启用 Fallback
        fallback_provider: Fallback 提供商
        fallback_base_url: Fallback 基础 URL
        fallback_model: Fallback 模型名称
        **kwargs: 其他参数

    Returns:
        FallbackLLMClient 实例

    Example:
        # 简单使用
        client = create_fallback_client(
            provider="openai",
            api_key="sk-xxx",
            fallback_enabled=True
        )

        # 完整配置
        client = create_fallback_client(
            provider="minimax",
            api_key="xxx",
            model="MiniMax-M2.5",
            fallback_enabled=True,
            fallback_provider="ollama",
            fallback_model="qwen2.5:14b"
        )
    """
    config = FallbackConfig(
        provider=provider,
        api_key=api_key,
        base_url=base_url,
        model=model,
        fallback_enabled=fallback_enabled,
        fallback_provider=fallback_provider,
        fallback_base_url=fallback_base_url,
        fallback_model=fallback_model,
    )

    return FallbackLLMClient(config)
