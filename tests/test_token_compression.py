# -*- coding: utf-8 -*-
"""
Token 感知压缩测试
"""
import pytest

from src.memory.working_memory import (
    WorkingMemory,
    WorkingMemoryConfig,
    Message,
    estimate_tokens,
    summarize_messages,
    SUMMARY_TRIGGER_RATIO,
)


class TestEstimateTokens:
    """测试 Token 估算函数"""

    def test_empty_string(self):
        """测试空字符串"""
        assert estimate_tokens("") == 0

    def test_english_text(self):
        """测试英文文本"""
        # 英文约 0.25 tokens/char
        text = "Hello World"  # 11 chars
        tokens = estimate_tokens(text)
        assert tokens >= 1
        assert tokens <= 11

    def test_chinese_text(self):
        """测试中文文本"""
        # 中文约 0.5 tokens/char
        text = "你好世界"  # 4 chars
        tokens = estimate_tokens(text)
        assert tokens >= 1
        assert tokens <= 4

    def test_mixed_text(self):
        """测试混合文本"""
        text = "Hello 世界"  # 7 chars: 6 English + 1 space + 2 Chinese
        tokens = estimate_tokens(text)
        assert tokens >= 1

    def test_returns_minimum_one(self):
        """测试最小返回值为 1"""
        # 单个字符
        assert estimate_tokens("a") >= 1
        assert estimate_tokens("你") >= 1


class TestSummarizeMessages:
    """测试消息摘要函数"""

    def test_empty_messages(self):
        """测试空消息列表"""
        assert summarize_messages([]) == ""

    def test_keyword_extraction(self):
        """测试关键词提取"""
        messages = [
            {"content": "帮我搜索一下天气"},
            {"content": "创建一个新任务"},
        ]
        summary = summarize_messages(messages)
        assert "搜索信息" in summary
        assert "创建操作" in summary

    def test_fallback_count(self):
        """测试无关键词时返回消息计数"""
        messages = [
            {"content": "随机内容"},
            {"content": "其他内容"},
        ]
        summary = summarize_messages(messages)
        assert "2 条消息" in summary


class TestMessage:
    """测试 Message 数据类"""

    def test_to_dict(self):
        """测试转换为字典"""
        msg = Message(role="user", content="Hello")
        d = msg.to_dict()
        assert d["role"] == "user"
        assert d["content"] == "Hello"
        assert "timestamp" in d

    def test_default_timestamp(self):
        """测试默认时间戳"""
        msg = Message(role="assistant", content="Hi")
        assert msg.timestamp is not None


class TestWorkingMemoryMessages:
    """测试工作记忆消息管理"""

    def test_add_message(self):
        """测试添加消息"""
        wm = WorkingMemory()
        wm.add_message("user", "Hello")
        wm.add_message("assistant", "Hi there")

        assert len(wm.messages) == 2
        assert wm.messages[0].role == "user"
        assert wm.messages[1].role == "assistant"

    def test_get_messages_without_summary(self):
        """测试获取消息（不含摘要）"""
        wm = WorkingMemory()
        wm.add_message("user", "Hello")
        messages = wm.get_messages(include_summary=False)

        assert len(messages) == 1
        assert messages[0]["role"] == "user"

    def test_get_messages_with_empty_summary(self):
        """测试获取消息（摘要为空）"""
        wm = WorkingMemory()
        wm.add_message("user", "Hello")
        messages = wm.get_messages(include_summary=True)

        # 没有摘要，只返回原始消息
        assert len(messages) == 1


class TestTokenAwareCompression:
    """测试 Token 感知压缩"""

    def test_no_compression_below_threshold(self):
        """测试低于阈值不压缩"""
        config = WorkingMemoryConfig(
            max_tokens=10000,
            max_messages=20,
            enable_compression=True
        )
        wm = WorkingMemory(config=config)

        # 添加少量消息
        for i in range(5):
            wm.add_message("user", f"Message {i}")

        # 应该不会触发压缩
        assert len(wm.messages) == 5
        assert wm.get_summary() == ""

    def test_compression_by_message_count(self):
        """测试按消息数量压缩"""
        config = WorkingMemoryConfig(
            max_tokens=10000,
            max_messages=10,
            enable_compression=False  # 禁用 token 压缩，只按数量
        )
        wm = WorkingMemory(config=config)

        # 添加超过限制的消息
        for i in range(15):
            wm.add_message("user", f"Message {i}")

        # 应该截断到 max_messages
        assert len(wm.messages) <= config.max_messages

    def test_compression_by_token_count(self):
        """测试按 Token 数量压缩"""
        config = WorkingMemoryConfig(
            max_tokens=100,  # 很小的限制
            max_messages=100,
            enable_compression=True
        )
        wm = WorkingMemory(config=config)

        # 添加大量长消息
        for i in range(20):
            wm.add_message("user", f"This is a long message number {i} " * 10)

        # 应该触发压缩
        total_tokens = wm._calculate_total_tokens()
        # 压缩后应该在限制范围内或已生成摘要
        assert total_tokens <= config.max_tokens or wm.get_summary() != ""

    def test_system_message_preserved(self):
        """测试 system 消息被保留"""
        config = WorkingMemoryConfig(
            max_tokens=100,
            max_messages=5,
            enable_compression=True
        )
        wm = WorkingMemory(config=config)

        # 添加 system 消息
        wm.add_message("system", "System prompt")
        # 添加大量用户消息
        for i in range(10):
            wm.add_message("user", f"User message {i} " * 5)

        # system 消息应该被保留
        system_msgs = [m for m in wm.messages if m.role == "system"]
        assert len(system_msgs) == 1

    def test_compression_disabled(self):
        """测试禁用压缩"""
        config = WorkingMemoryConfig(
            max_tokens=100,
            max_messages=5,
            enable_compression=False
        )
        wm = WorkingMemory(config=config)

        # 添加消息
        for i in range(10):
            wm.add_message("user", f"Message {i}")

        # 禁用压缩时，只按数量截断
        assert len(wm.messages) <= config.max_messages


class TestWorkingMemoryStats:
    """测试工作记忆统计"""

    def test_get_stats(self):
        """测试获取统计信息"""
        wm = WorkingMemory()
        wm.add_message("user", "Hello")
        wm.set_identity("Test identity")

        stats = wm.get_stats()

        assert "message_count" in stats
        assert "message_tokens" in stats
        assert "slot_count" in stats
        assert "slot_tokens" in stats
        assert "total_tokens" in stats
        assert "max_tokens" in stats
        assert "usage_ratio" in stats
        assert "within_limit" in stats

        assert stats["message_count"] == 1
        assert stats["within_limit"] is True

    def test_is_within_limit(self):
        """测试限制检查"""
        config = WorkingMemoryConfig(max_tokens=10000)
        wm = WorkingMemory(config=config)

        wm.add_message("user", "Test")
        assert wm.is_within_limit() is True


class TestWorkingMemorySlots:
    """测试工作记忆槽位"""

    def test_set_identity(self):
        """测试设置身份"""
        wm = WorkingMemory()
        wm.set_identity("I am a helpful assistant")

        assert wm.slots["identity"].content == "I am a helpful assistant"

    def test_set_context(self):
        """测试设置上下文"""
        wm = WorkingMemory()
        wm.set_context("Current conversation context")

        assert wm.slots["context"].content == "Current conversation context"

    def test_add_fact(self):
        """测试添加事实"""
        wm = WorkingMemory()
        wm.add_fact("User likes Python")
        wm.add_fact("User lives in Beijing")

        facts = wm.slots["facts"].content
        assert "Python" in facts
        assert "Beijing" in facts

    def test_get_full_context(self):
        """测试获取完整上下文"""
        wm = WorkingMemory()
        wm.set_identity("Assistant")
        wm.set_context("Current chat")
        wm.add_fact("Fact 1")

        context = wm.get_full_context()

        assert "身份" in context or "identity" in context.lower()
        assert "Assistant" in context

    def test_write_custom_slot(self):
        """测试写入自定义槽位"""
        wm = WorkingMemory()
        wm.write_slot("custom", "Custom content", priority=0.8)

        assert "custom" in wm.slots
        assert wm.slots["custom"].content == "Custom content"

    def test_read_slot(self):
        """测试读取槽位"""
        wm = WorkingMemory()
        wm.set_identity("Test")

        slot = wm.read_slot("identity")
        assert slot is not None
        assert slot.content == "Test"

        # 不存在的槽位
        assert wm.read_slot("nonexistent") is None


class TestWorkingMemoryClear:
    """测试清空功能"""

    def test_clear_context(self):
        """测试清空上下文"""
        wm = WorkingMemory()
        wm.add_message("user", "Hello")
        wm.set_context("Context")

        wm.clear_context()

        assert len(wm.messages) == 0
        assert wm.slots["context"].content == ""
        assert wm.get_summary() == ""

    def test_clear_all(self):
        """测试清空所有"""
        wm = WorkingMemory()
        wm.set_identity("Identity")
        wm.set_context("Context")
        wm.add_fact("Fact")
        wm.add_message("user", "Hello")

        wm.clear_all()

        assert len(wm.messages) == 0
        for slot in wm.slots.values():
            assert slot.content == ""


class TestWorkingMemoryCompact:
    """测试智能压缩功能"""

    def test_compact_without_llm(self):
        """测试无 LLM 的压缩"""
        config = WorkingMemoryConfig(max_tokens=50)
        wm = WorkingMemory(config=config)

        # 填充大量内容
        wm.set_context("A" * 1000)
        wm.add_fact("B" * 1000)

        wm.compact()

        # 应该被压缩
        assert wm.is_within_limit() or estimate_tokens(wm.slots["context"].content) < 1000

    def test_identity_not_compacted(self):
        """测试身份槽位不被压缩"""
        config = WorkingMemoryConfig(max_tokens=50)
        wm = WorkingMemory(config=config)

        long_identity = "I" * 1000
        wm.set_identity(long_identity)

        wm.compact()

        # 身份槽位应该保持不变
        assert wm.slots["identity"].content == long_identity
