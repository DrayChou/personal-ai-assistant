# -*- coding: utf-8 -*-
"""
LLM Provider Fallback 测试
"""
import pytest
from unittest.mock import MagicMock, patch

from src.chat.fallback_llm import (
    FallbackLLMClient,
    FallbackConfig,
    FallbackStrategy,
    FallbackStats,
    create_fallback_client,
)
from src.chat.exceptions import LLMClientError


class TestFallbackConfig:
    """测试 Fallback 配置"""

    def test_default_config(self):
        """测试默认配置"""
        config = FallbackConfig()

        assert config.provider == "openai"
        assert config.model == "gpt-4o-mini"
        assert config.fallback_enabled is False
        assert config.fallback_provider == "ollama"

    def test_custom_config(self):
        """测试自定义配置"""
        config = FallbackConfig(
            provider="minimax",
            api_key="test_key",
            model="MiniMax-M2.5",
            fallback_enabled=True,
            fallback_provider="ollama",
            fallback_model="qwen2.5:14b"
        )

        assert config.provider == "minimax"
        assert config.api_key == "test_key"
        assert config.fallback_enabled is True

    def test_fallback_strategy(self):
        """测试 Fallback 策略"""
        config = FallbackConfig(strategy=FallbackStrategy.FAIL_FAST)
        assert config.strategy == FallbackStrategy.FAIL_FAST


class TestFallbackStats:
    """测试 Fallback 统计"""

    def test_initial_stats(self):
        """测试初始统计"""
        stats = FallbackStats()

        assert stats.total_requests == 0
        assert stats.primary_success == 0
        assert stats.using_fallback is False

    def test_stats_tracking(self):
        """测试统计跟踪"""
        stats = FallbackStats()
        stats.total_requests = 10
        stats.primary_success = 8
        stats.primary_failures = 2

        assert stats.total_requests == 10
        assert stats.primary_success == 8


class TestFallbackLLMClient:
    """测试 FallbackLLMClient"""

    @pytest.fixture
    def config(self):
        """创建测试配置"""
        return FallbackConfig(
            provider="openai",
            api_key="test_key",
            model="gpt-4o-mini",
            fallback_enabled=True,
            fallback_provider="ollama",
            fallback_model="qwen2.5:14b"
        )

    @pytest.fixture
    def config_no_fallback(self):
        """创建无 Fallback 的配置"""
        return FallbackConfig(
            provider="openai",
            api_key="test_key",
            model="gpt-4o-mini",
            fallback_enabled=False
        )

    def test_client_initialization(self, config):
        """测试客户端初始化"""
        client = FallbackLLMClient(config)

        assert client.config == config
        assert client._primary is not None
        assert client._fallback is not None

    def test_client_without_fallback(self, config_no_fallback):
        """测试无 Fallback 的客户端"""
        client = FallbackLLMClient(config_no_fallback)

        assert client._fallback is None

    def test_primary_client_access(self, config):
        """测试访问主客户端"""
        client = FallbackLLMClient(config)

        assert client.primary_client is not None

    def test_fallback_client_access(self, config):
        """测试访问 Fallback 客户端"""
        client = FallbackLLMClient(config)

        assert client.fallback_client is not None

    def test_get_stats(self, config):
        """测试获取统计"""
        client = FallbackLLMClient(config)
        stats = client.get_stats()

        assert "total_requests" in stats
        assert "primary_success" in stats
        assert "fallback_enabled" in stats
        assert stats["fallback_enabled"] is True

    def test_reset_stats(self, config):
        """测试重置统计"""
        client = FallbackLLMClient(config)
        client.stats.total_requests = 10

        client.reset_stats()

        assert client.stats.total_requests == 0

    @patch('src.chat.fallback_llm.create_llm_client')
    def test_generate_primary_success(self, mock_create, config):
        """测试主 LLM 成功"""
        # Mock 主客户端
        mock_primary = MagicMock()
        mock_primary.generate.return_value = "Primary response"

        # Mock Fallback 客户端
        mock_fallback = MagicMock()

        def create_side_effect(provider, **kwargs):
            if provider == "openai":
                return mock_primary
            return mock_fallback

        mock_create.side_effect = create_side_effect

        client = FallbackLLMClient(config)
        result = client.generate([{"role": "user", "content": "Hello"}])

        assert result == "Primary response"
        assert client.stats.primary_success == 1
        mock_primary.generate.assert_called_once()
        mock_fallback.generate.assert_not_called()

    @patch('src.chat.fallback_llm.create_llm_client')
    def test_generate_fallback_on_failure(self, mock_create, config):
        """测试主 LLM 失败时切换 Fallback"""
        # Mock 主客户端失败
        mock_primary = MagicMock()
        mock_primary.generate.side_effect = Exception("Primary failed")

        # Mock Fallback 客户端成功
        mock_fallback = MagicMock()
        mock_fallback.generate.return_value = "Fallback response"

        def create_side_effect(provider, **kwargs):
            if provider == "openai":
                return mock_primary
            return mock_fallback

        mock_create.side_effect = create_side_effect

        client = FallbackLLMClient(config)
        result = client.generate([{"role": "user", "content": "Hello"}])

        assert result == "Fallback response"
        assert client.stats.primary_failures == 1
        assert client.stats.fallback_success == 1
        assert client.stats.using_fallback is True

    @patch('src.chat.fallback_llm.create_llm_client')
    def test_generate_no_fallback_raises(self, mock_create, config_no_fallback):
        """测试无 Fallback 时主 LLM 失败抛出异常"""
        mock_primary = MagicMock()
        mock_primary.generate.side_effect = Exception("Primary failed")

        mock_create.return_value = mock_primary

        client = FallbackLLMClient(config_no_fallback)

        with pytest.raises(Exception) as exc_info:
            client.generate([{"role": "user", "content": "Hello"}])

        assert "Primary failed" in str(exc_info.value)

    @patch('src.chat.fallback_llm.create_llm_client')
    def test_both_fail_raises_error(self, mock_create, config):
        """测试主 LLM 和 Fallback 都失败时抛出异常"""
        mock_primary = MagicMock()
        mock_primary.generate.side_effect = Exception("Primary failed")

        mock_fallback = MagicMock()
        mock_fallback.generate.side_effect = Exception("Fallback failed")

        def create_side_effect(provider, **kwargs):
            if provider == "openai":
                return mock_primary
            return mock_fallback

        mock_create.side_effect = create_side_effect

        client = FallbackLLMClient(config)

        with pytest.raises(LLMClientError) as exc_info:
            client.generate([{"role": "user", "content": "Hello"}])

        assert "都失败" in str(exc_info.value)

    @patch('src.chat.fallback_llm.create_llm_client')
    def test_stream_generate_primary_success(self, mock_create, config):
        """测试流式生成主 LLM 成功"""
        mock_primary = MagicMock()
        mock_primary.stream_generate.return_value = iter(["Hello", " World"])

        mock_fallback = MagicMock()

        def create_side_effect(provider, **kwargs):
            if provider == "openai":
                return mock_primary
            return mock_fallback

        mock_create.side_effect = create_side_effect

        client = FallbackLLMClient(config)
        result = list(client.stream_generate([{"role": "user", "content": "Hi"}]))

        assert result == ["Hello", " World"]
        assert client.stats.primary_success == 1


class TestCreateFallbackClient:
    """测试工厂函数"""

    def test_create_simple(self):
        """测试简单创建"""
        client = create_fallback_client(
            provider="openai",
            api_key="test_key"
        )

        assert client is not None
        assert client.config.provider == "openai"

    def test_create_with_fallback(self):
        """测试带 Fallback 创建"""
        client = create_fallback_client(
            provider="minimax",
            api_key="test_key",
            fallback_enabled=True,
            fallback_provider="ollama"
        )

        assert client.config.fallback_enabled is True
        assert client.config.fallback_provider == "ollama"


class TestFallbackStrategy:
    """测试 Fallback 策略"""

    def test_strategy_values(self):
        """测试策略值"""
        assert FallbackStrategy.FAIL_FAST.value == "fail_fast"
        assert FallbackStrategy.FALLBACK_ONCE.value == "fallback_once"
        assert FallbackStrategy.ALWAYS_FALLBACK.value == "always_fallback"
