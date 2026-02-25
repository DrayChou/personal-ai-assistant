# -*- coding: utf-8 -*-
"""
Session Store 测试
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from src.chat.session_store import Session, SessionStore


class TestSession:
    """测试 Session 数据类"""

    def test_create_session(self):
        """测试创建会话"""
        session = Session(
            session_key="agent:main:cli:user123",
            agent_id="main",
            channel="cli",
            peer_id="user123",
        )
        assert session.session_key == "agent:main:cli:user123"
        assert session.created_at != ""

    def test_from_key(self):
        """测试从 key 解析"""
        session = Session.from_key("agent:main:telegram:user456")
        assert session.agent_id == "main"
        assert session.channel == "telegram"
        assert session.peer_id == "user456"

    def test_add_message(self):
        """测试添加消息"""
        session = Session(session_key="test")
        session.add_message("user", "hello")
        session.add_message("assistant", "hi")

        assert len(session.messages) == 2
        assert session.messages[0]["role"] == "user"
        assert session.messages[1]["role"] == "assistant"
        assert session.updated_at != session.created_at

    def test_get_recent_messages(self):
        """测试获取最近消息"""
        session = Session(session_key="test")
        for i in range(20):
            session.add_message("user", f"msg{i}")

        recent = session.get_recent_messages(5)
        assert len(recent) == 5
        assert recent[-1]["content"] == "msg19"

    def test_to_from_dict(self):
        """测试序列化反序列化"""
        session = Session(
            session_key="test",
            agent_id="main",
            messages=[{"role": "user", "content": "hello"}],
        )
        data = session.to_dict()
        session2 = Session.from_dict(data)

        assert session2.session_key == "test"
        assert session2.agent_id == "main"
        assert len(session2.messages) == 1


class TestSessionStore:
    """测试 Session Store"""

    @pytest.fixture
    def temp_dir(self):
        """临时目录"""
        path = tempfile.mkdtemp()
        yield path
        shutil.rmtree(path)

    def test_get_or_create(self, temp_dir):
        """测试获取或创建"""
        store = SessionStore(base_dir=temp_dir)
        session = store.get_or_create("telegram:user123")

        assert session.session_key == "telegram:user123"
        assert session.channel == "cli"  # 默认

        # 再次获取应该返回同一个
        session2 = store.get_or_create("telegram:user123")
        assert session is session2

    def test_persist_and_load(self, temp_dir):
        """测试持久化和加载"""
        # 创建并保存
        store1 = SessionStore(base_dir=temp_dir)
        session = store1.get_or_create("test:session")
        session.add_message("user", "hello")
        store1.save(session)

        # 重新加载
        store2 = SessionStore(base_dir=temp_dir)
        loaded = store2.get("test:session")

        assert loaded is not None
        assert len(loaded.messages) == 1
        assert loaded.messages[0]["content"] == "hello"

    def test_list_sessions(self, temp_dir):
        """测试列会话"""
        store = SessionStore(base_dir=temp_dir)

        # 创建多个会话
        for i in range(5):
            session = store.get_or_create(f"session{i}", agent_id="main" if i < 3 else "other")
            session.add_message("user", f"msg{i}")
            store.save(session)

        # 列出所有
        all_sessions = store.list_sessions()
        assert len(all_sessions) == 5

        # 按 agent 过滤
        main_sessions = store.list_sessions(agent_id="main")
        assert len(main_sessions) == 3

    def test_delete_session(self, temp_dir):
        """测试删除会话"""
        store = SessionStore(base_dir=temp_dir)
        session = store.get_or_create("to_delete")
        store.save(session)

        assert store.get("to_delete") is not None

        # 删除
        result = store.delete("to_delete")
        assert result is True
        assert store.get("to_delete") is None

        # 再次删除应该返回 False
        result = store.delete("to_delete")
        assert result is False

    def test_archive_old_sessions(self, temp_dir):
        """测试归档旧会话"""
        store = SessionStore(base_dir=temp_dir)

        # 创建一个旧会话 (手动修改时间)
        old_session = store.get_or_create("old:session")
        old_session.updated_at = "2020-01-01T00:00:00"
        store.save(old_session)

        # 创建一个新会话
        new_session = store.get_or_create("new:session")
        store.save(new_session)

        # 归档超过 30 天的
        archived = store.archive_old_sessions(days=30)
        assert archived == 1

        # 旧会话应该被归档
        assert store.get("old:session") is None
        assert store.get("new:session") is not None
