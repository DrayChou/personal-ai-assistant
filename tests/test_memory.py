# -*- coding: utf-8 -*-
"""
记忆系统测试
"""
import sys
import pytest
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from src.memory.types import MemoryType, MemoryConfidence, MemoryEntry
from src.memory.working_memory import WorkingMemory, WorkingMemoryConfig
from src.memory.long_term_memory import LongTermMemory

# 检查 SQLite-Vec 是否可用
SQLITE_VEC_AVAILABLE = False
try:
    import sqlite_vec
    SQLITE_VEC_AVAILABLE = True
except ImportError:
    pass


class TestMemoryTypes:
    """测试记忆类型定义"""

    def test_memory_confidence_decay(self):
        """测试置信度衰减计算"""
        # FACT: 半衰期87天
        fact = MemoryConfidence.FACT
        assert fact.get_decayed_confidence(0) == 1.0  # 初始值
        assert abs(fact.get_decayed_confidence(87) - 0.5) < 0.01  # 半衰期（近似）

        # EVENT: 半衰期5天
        event = MemoryConfidence.EVENT
        assert event.get_decayed_confidence(0) == 1.0
        assert abs(event.get_decayed_confidence(5) - 0.5) < 0.1  # 放宽精度要求


class TestWorkingMemory:
    """测试工作记忆"""

    @pytest.fixture
    def wm(self):
        return WorkingMemory(WorkingMemoryConfig(max_slots=3))

    def test_slot_management(self, wm):
        """测试槽位管理"""
        # 写入槽位
        wm.write_slot("location", "北京", 0.8)

        # 读取槽位
        slot = wm.read_slot("location")
        assert slot is not None
        assert slot.content == "北京"

        # 槽位数量限制
        wm.write_slot("hobby", "编程", 0.7)
        wm.write_slot("new", "新内容", 0.95)  # 应该淘汰置信度最低的

        assert len(wm.slots) == 3  # identity(默认) + location + new
        assert "hobby" not in wm.slots  # 置信度0.7最低，被挤出

    def test_context_management(self, wm):
        """测试上下文管理"""
        wm.set_context("当前对话主题：编程")
        assert wm.get_context() == "当前对话主题：编程"


class TestLongTermMemory:
    """测试长期记忆"""

    @pytest.fixture
    def ltm(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            yield LongTermMemory(str(db_path))

    def test_store_and_retrieve(self, ltm):
        """测试存储和检索"""
        entry = MemoryEntry(
            id="test_001",
            content="Python是编程语言",
            memory_type=MemoryType.KNOWLEDGE,
            confidence_level=MemoryConfidence.FACT,
            embedding=[0.1] * 768
        )

        ltm.store(entry)
        retrieved = ltm.retrieve("test_001")

        assert retrieved is not None
        assert retrieved.content == "Python是编程语言"

    @pytest.mark.skipif(not SQLITE_VEC_AVAILABLE, reason="SQLite-Vec not installed")
    def test_similarity_search(self, ltm):
        """测试相似度搜索（需要 SQLite-Vec）"""
        # 存储多条记忆
        entries = [
            MemoryEntry(
                id=f"test_{i}",
                content=f"内容{i}",
                memory_type=MemoryType.KNOWLEDGE,
                confidence_level=MemoryConfidence.FACT,
                embedding=[0.1 if j == i else 0.0 for j in range(768)]
            )
            for i in range(5)
        ]

        for entry in entries:
            ltm.store(entry)

        # 搜索
        query_embedding = [0.1] + [0.0] * 767
        results = ltm.search_similar(query_embedding, top_k=3)

        assert len(results) == 3
        assert results[0].id == "test_0"  # 最相似


class TestMemoryIntegration:
    """集成测试"""

    @pytest.mark.skipif(not SQLITE_VEC_AVAILABLE, reason="SQLite-Vec not installed")
    def test_memory_workflow(self):
        """测试完整记忆流程（需要 SQLite-Vec）"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建工作记忆
            wm = WorkingMemory(WorkingMemoryConfig())

            # 创建长期记忆
            ltm = LongTermMemory(str(Path(tmpdir) / "memory.db"))

            # 1. 捕获到工作记忆
            wm.write_slot("fact_1", "重要信息", 0.95)

            # 2. 创建长期记忆条目
            entry = MemoryEntry(
                id="mem_001",
                content="重要信息",
                memory_type=MemoryType.KNOWLEDGE,
                confidence_level=MemoryConfidence.FACT,
                source="test",
                embedding=[0.1] * 768
            )

            # 3. 存储到长期记忆
            ltm.store(entry)

            # 4. 检索验证
            results = ltm.search_similar([0.1] * 768, top_k=1)
            assert len(results) == 1
            assert results[0].content == "重要信息"
