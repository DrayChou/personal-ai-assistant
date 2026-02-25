# -*- coding: utf-8 -*-
"""
记忆系统集成测试
验证 MemorySystem 端到端功能，包括 Fallback 切换
"""
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime

import pytest

from src.memory import (
    MemorySystem,
    MemoryEntry,
    MemoryConfidence,
    MemoryType,
    FallbackMemoryClient,
)


class TestMemorySystemIntegration:
    """MemorySystem 集成测试"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as d:
            yield d

    @pytest.fixture
    def memory_system(self, temp_dir):
        """创建 MemorySystem 实例"""
        return MemorySystem(data_dir=temp_dir)

    def test_basic_capture_and_recall(self, memory_system):
        """测试基本记忆捕获和检索"""
        # 捕获记忆
        memory_id = memory_system.capture(
            content="Python 是一种编程语言",
            memory_type=MemoryType.FACT,
            confidence=MemoryConfidence.FACT
        )

        assert memory_id != ""

        # 检索记忆
        context = memory_system.recall("Python", top_k=5)
        assert "Python" in context

    def test_working_memory_integration(self, memory_system):
        """测试工作记忆集成"""
        # 捕获高置信度事实
        memory_system.capture(
            content="用户喜欢使用 Python",
            memory_type=MemoryType.FACT,
            confidence=MemoryConfidence.FACT
        )

        # 检查工作记忆是否包含
        wm_context = memory_system.working_memory.get_full_context()
        assert "Python" in wm_context

    def test_stats_tracking(self, memory_system):
        """测试统计跟踪"""
        # 捕获多条记忆
        for i in range(5):
            memory_system.capture(
                content=f"测试记忆 {i}",
                memory_type=MemoryType.OBSERVATION
            )

        stats = memory_system.get_stats()
        assert stats["memories_added"] == 5

    def test_context_manager(self, temp_dir):
        """测试上下文管理器"""
        with MemorySystem(data_dir=temp_dir) as ms:
            ms.capture("测试内容", memory_type=MemoryType.OBSERVATION)
            stats = ms.get_stats()
            assert stats["memories_added"] == 1


class TestFallbackIntegration:
    """Fallback 机制集成测试"""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    def test_fallback_mode_detection(self, temp_dir):
        """测试 Fallback 模式检测"""
        # 模拟主存储初始化失败
        with patch('src.memory.memory_system.LongTermMemory') as mock_ltm:
            mock_ltm.side_effect = Exception("模拟初始化失败")

            ms = MemorySystem(data_dir=str(temp_dir))

            # 应该处于 Fallback 模式
            assert ms._using_fallback is True
            assert ms._fallback_client is not None

            ms.close()

    def test_store_fallback_on_failure(self, temp_dir):
        """测试主存储失败时切换 Fallback"""
        ms = MemorySystem(data_dir=str(temp_dir))

        # 模拟主存储失败
        original_store = ms.long_term_memory.store
        ms.long_term_memory.store = MagicMock(side_effect=Exception("存储失败"))

        # 捕获记忆应该切换到 Fallback
        memory_id = ms.capture(
            content="Fallback 测试记忆",
            memory_type=MemoryType.OBSERVATION
        )

        # 应该成功（使用 Fallback）
        assert memory_id != ""
        assert ms._using_fallback is True

        # 恢复原方法并关闭
        ms.long_term_memory.store = original_store
        ms.close()

    def test_retrieve_fallback_on_failure(self, temp_dir):
        """测试主存储检索失败时使用 Fallback"""
        ms = MemorySystem(data_dir=str(temp_dir))

        # 先正常存储
        ms.capture(
            content="测试检索内容",
            memory_type=MemoryType.OBSERVATION
        )

        # 模拟检索失败
        original_retrieve = ms.retrieval.retrieve_for_context
        ms.retrieval.retrieve_for_context = MagicMock(side_effect=Exception("检索失败"))

        # 检索应该不崩溃（可能使用 Fallback 或返回空）
        context = ms.recall("测试", top_k=5)
        assert isinstance(context, str)

        # 恢复并关闭
        ms.retrieval.retrieve_for_context = original_retrieve
        ms.close()

    def test_fallback_persistence(self, temp_dir):
        """测试 Fallback 数据持久化"""
        # 第一次会话：使用 Fallback 存储
        with patch('src.memory.memory_system.LongTermMemory') as mock_ltm:
            mock_ltm.side_effect = Exception("初始化失败")

            ms1 = MemorySystem(data_dir=str(temp_dir))
            ms1.capture(
                content="持久化测试内容",
                memory_type=MemoryType.OBSERVATION
            )
            ms1.close()

        # 验证 Fallback 文件存在
        fallback_dir = temp_dir / "fallback"
        json_files = list(fallback_dir.glob("*.json"))
        assert len(json_files) > 0


class TestTokenAwareMemory:
    """Token 感知记忆测试"""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as d:
            yield d

    @pytest.fixture
    def memory_system(self, temp_dir):
        return MemorySystem(data_dir=temp_dir)

    def test_working_memory_token_limit(self, memory_system):
        """测试工作记忆 Token 限制"""
        wm = memory_system.working_memory

        # 添加大量消息
        for i in range(50):
            wm.add_message("user", f"这是一条测试消息，内容较长，用于测试 Token 限制 {i}" * 5)

        # 应该触发压缩
        stats = wm.get_stats()
        # 消息数量应该被限制
        assert stats["message_count"] <= wm.config.max_messages or stats["has_summary"] is True

    def test_message_compression_preserves_recent(self, memory_system):
        """测试压缩保留最近消息"""
        wm = memory_system.working_memory

        # 添加 system 消息
        wm.add_message("system", "系统提示")

        # 添加大量用户消息
        for i in range(20):
            wm.add_message("user", f"用户消息 {i}")

        # 压缩后应该保留 system 消息
        system_msgs = [m for m in wm.messages if m.role == "system"]
        assert len(system_msgs) == 1


class TestMemorySystemExport:
    """导出功能测试"""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as d:
            yield d

    @pytest.fixture
    def memory_system(self, temp_dir):
        return MemorySystem(data_dir=temp_dir)

    def test_export_to_jsonl(self, memory_system, temp_dir):
        """测试 JSONL 导出"""
        # 捕获记忆
        for i in range(3):
            memory_system.capture(
                content=f"导出测试记忆 {i}",
                memory_type=MemoryType.OBSERVATION
            )

        # 导出
        output_path = memory_system.export()
        assert Path(output_path).exists()

        # 验证内容
        with open(output_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            assert len(lines) == 3


class TestMemorySystemEdgeCases:
    """边界情况测试"""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as d:
            yield d

    @pytest.fixture
    def memory_system(self, temp_dir):
        return MemorySystem(data_dir=temp_dir)

    def test_empty_recall(self, memory_system):
        """测试空记忆检索"""
        context = memory_system.recall("不存在的查询", top_k=5)
        # 应该返回空字符串或工作记忆上下文
        assert isinstance(context, str)

    def test_special_characters_in_content(self, memory_system):
        """测试特殊字符"""
        memory_id = memory_system.capture(
            content="包含特殊字符: <>&\"'测试\n换行\t制表符",
            memory_type=MemoryType.OBSERVATION
        )
        assert memory_id != ""

    def test_unicode_content(self, memory_system):
        """测试 Unicode 内容"""
        memory_id = memory_system.capture(
            content="Unicode 测试: 🎉 你好世界 مرحبا 日本語",
            memory_type=MemoryType.OBSERVATION
        )
        assert memory_id != ""

    def test_large_content(self, memory_system):
        """测试大内容"""
        large_content = "A" * 10000
        memory_id = memory_system.capture(
            content=large_content,
            memory_type=MemoryType.OBSERVATION
        )
        assert memory_id != ""

    def test_concurrent_operations(self, memory_system):
        """测试并发操作模拟"""
        # 快速连续操作
        ids = []
        for i in range(10):
            mid = memory_system.capture(
                content=f"并发测试 {i}",
                memory_type=MemoryType.OBSERVATION
            )
            ids.append(mid)

        # 所有操作应该成功
        assert all(mid != "" for mid in ids)
