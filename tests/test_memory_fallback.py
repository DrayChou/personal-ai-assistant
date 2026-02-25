# -*- coding: utf-8 -*-
"""
记忆系统 Fallback 机制测试
"""
import json
import tempfile
from pathlib import Path
from datetime import datetime

import pytest

from src.memory.fallback_client import FallbackMemoryClient
from src.memory.types import MemoryEntry, MemoryConfidence, MemoryType


class TestFallbackMemoryClient:
    """测试 FallbackMemoryClient"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    @pytest.fixture
    def client(self, temp_dir):
        """创建客户端实例"""
        return FallbackMemoryClient(temp_dir)

    @pytest.fixture
    def sample_entry(self):
        """创建示例记忆条目"""
        return MemoryEntry(
            content="这是一条测试记忆",
            memory_type=MemoryType.OBSERVATION,
            confidence_level=MemoryConfidence.EVENT,
            created_at=datetime.now(),
            last_accessed=datetime.now(),
        )

    def test_init(self, temp_dir):
        """测试初始化"""
        client = FallbackMemoryClient(temp_dir)
        assert client.data_dir == temp_dir
        assert client.index_path == temp_dir / "index.json"
        assert isinstance(client._index, dict)

    def test_init_creates_directory(self):
        """测试初始化时创建目录"""
        with tempfile.TemporaryDirectory() as d:
            new_dir = Path(d) / "new_subdir"
            client = FallbackMemoryClient(new_dir)
            assert new_dir.exists()

    def test_store(self, client, sample_entry):
        """测试存储记忆"""
        result = client.store(sample_entry)
        assert result is True

        # 验证文件存在
        file_path = client.data_dir / f"{sample_entry.id}.json"
        assert file_path.exists()

        # 验证索引更新
        assert sample_entry.id in client._index

    def test_retrieve(self, client, sample_entry):
        """测试检索记忆"""
        client.store(sample_entry)

        retrieved = client.retrieve(sample_entry.id)
        assert retrieved is not None
        assert retrieved.content == sample_entry.content
        assert retrieved.memory_type == sample_entry.memory_type

    def test_retrieve_nonexistent(self, client):
        """测试检索不存在的记忆"""
        result = client.retrieve("nonexistent_id")
        assert result is None

    def test_search(self, client):
        """测试搜索"""
        entries = [
            MemoryEntry(content="Python 是一种编程语言", memory_type=MemoryType.OBSERVATION),
            MemoryEntry(content="JavaScript 也是一种编程语言", memory_type=MemoryType.OBSERVATION),
            MemoryEntry(content="今天天气不错", memory_type=MemoryType.OBSERVATION),
        ]
        for entry in entries:
            client.store(entry)

        results = client.search("编程语言", top_k=5)
        assert len(results) >= 2

        # 检查结果包含关键词
        for entry, score in results:
            assert "编程语言" in entry.content

    def test_search_no_results(self, client):
        """测试无结果的搜索"""
        entry = MemoryEntry(content="这是一条记忆")
        client.store(entry)

        results = client.search("不存在的关键词", top_k=5)
        assert len(results) == 0

    def test_search_by_keyword(self, client):
        """测试关键词搜索"""
        entries = [
            MemoryEntry(content="Python 编程"),
            MemoryEntry(content="Java 编程"),
            MemoryEntry(content="吃饭"),
        ]
        for entry in entries:
            client.store(entry)

        results = client.search_by_keyword("编程", top_k=10)
        assert len(results) == 2

    def test_get_recent(self, client):
        """测试获取最近记忆"""
        entries = [
            MemoryEntry(content=f"记忆 {i}", memory_type=MemoryType.OBSERVATION)
            for i in range(5)
        ]
        for entry in entries:
            client.store(entry)

        recent = client.get_recent(limit=3)
        assert len(recent) == 3

    def test_delete(self, client, sample_entry):
        """测试删除记忆"""
        client.store(sample_entry)
        assert sample_entry.id in client._index

        result = client.delete(sample_entry.id)
        assert result is True
        assert sample_entry.id not in client._index

        # 文件应该被删除
        file_path = client.data_dir / f"{sample_entry.id}.json"
        assert not file_path.exists()

    def test_count(self, client):
        """测试计数"""
        assert client.count() == 0

        entries = [MemoryEntry(content=f"记忆 {i}") for i in range(3)]
        for entry in entries:
            client.store(entry)

        assert client.count() == 3

    def test_get_stats(self, client):
        """测试统计信息"""
        stats = client.get_stats()
        assert "total" in stats
        assert "storage_type" in stats
        assert stats["storage_type"] == "file"

    def test_clear(self, client):
        """测试清空"""
        entries = [MemoryEntry(content=f"记忆 {i}") for i in range(3)]
        for entry in entries:
            client.store(entry)

        assert client.count() == 3
        client.clear()
        assert client.count() == 0

    def test_persistence(self, temp_dir):
        """测试持久化"""
        # 创建并存储
        client1 = FallbackMemoryClient(temp_dir)
        entry = MemoryEntry(content="持久化测试")
        client1.store(entry)
        client1.close()

        # 重新加载
        client2 = FallbackMemoryClient(temp_dir)
        assert client2.count() == 1

        retrieved = client2.retrieve(entry.id)
        assert retrieved is not None
        assert retrieved.content == "持久化测试"

    def test_context_manager(self, temp_dir):
        """测试上下文管理器"""
        with FallbackMemoryClient(temp_dir) as client:
            entry = MemoryEntry(content="上下文测试")
            client.store(entry)

        # 退出后应该能重新加载
        client2 = FallbackMemoryClient(temp_dir)
        assert client2.count() == 1


class TestFallbackMemoryClientWithConfidence:
    """测试置信度过滤"""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    @pytest.fixture
    def client(self, temp_dir):
        return FallbackMemoryClient(temp_dir)

    def test_search_with_min_confidence(self, client):
        """测试置信度过滤"""
        high_confidence = MemoryEntry(
            content="高置信度记忆",
            current_confidence=0.9
        )
        low_confidence = MemoryEntry(
            content="低置信度记忆",
            current_confidence=0.3
        )

        client.store(high_confidence)
        client.store(low_confidence)

        # 过滤低置信度
        results = client.search("记忆", top_k=5, min_confidence=0.5)
        assert len(results) == 1
        assert results[0][0].current_confidence >= 0.5


class TestFallbackMemoryClientEdgeCases:
    """边界情况测试"""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    @pytest.fixture
    def client(self, temp_dir):
        return FallbackMemoryClient(temp_dir)

    def test_empty_query(self, client):
        """测试空查询"""
        entry = MemoryEntry(content="测试内容")
        client.store(entry)

        results = client.search("", top_k=5)
        # 空查询不应该崩溃
        assert isinstance(results, list)

    def test_special_characters_in_content(self, client):
        """测试特殊字符"""
        entry = MemoryEntry(
            content="包含特殊字符: <>&\"'测试\n换行"
        )
        result = client.store(entry)
        assert result is True

        retrieved = client.retrieve(entry.id)
        assert retrieved is not None
        assert "<>&\"'测试" in retrieved.content

    def test_unicode_content(self, client):
        """测试 Unicode 内容"""
        entry = MemoryEntry(
            content="Unicode 测试: 🎉 你好世界 مرحبا"
        )
        result = client.store(entry)
        assert result is True

        retrieved = client.retrieve(entry.id)
        assert retrieved is not None
        assert "🎉" in retrieved.content

    def test_large_content(self, client):
        """测试大内容"""
        large_content = "A" * 10000
        entry = MemoryEntry(content=large_content)
        result = client.store(entry)
        assert result is True

        retrieved = client.retrieve(entry.id)
        assert retrieved is not None
        assert len(retrieved.content) == 10000

    def test_delete_nonexistent(self, client):
        """测试删除不存在的记忆"""
        result = client.delete("nonexistent_id")
        # 应该返回 True（幂等操作）
        assert result is True
