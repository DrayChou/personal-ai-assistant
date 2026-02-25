# -*- coding: utf-8 -*-
"""
JSONL 格式的会话存储

与 claw0 兼容的 Session Store 实现
"""
import json
import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

logger = logging.getLogger('chat.session_store')


@dataclass
class Session:
    """
    会话对象

    Session Key 格式 (与 claw0 兼容):
    - agent:<agent_id>:main                    - 所有DM共用
    - agent:<agent_id>:direct:<peer_id>        - 每个发送者独立
    - agent:<agent_id>:<channel>:direct:<peer_id> - 按通道隔离
    """
    session_key: str
    agent_id: str = "main"
    channel: str = "cli"
    peer_id: str = "user"
    messages: list[dict] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at

    @classmethod
    def from_key(cls, session_key: str, **kwargs) -> "Session":
        """
        从 session_key 解析创建 Session

        支持的格式:
        - agent:<agent_id>:<channel>:<peer_id>        - 4部分, channel 为自定义值
        - agent:<agent_id>:direct:<peer_id>            - 4部分, 旧格式, channel=cli
        - agent:<agent_id>:<channel>:direct:<peer_id> - 5部分, 标准格式
        - agent:<agent_id>:main                       - 3部分, 共用会话

        Args:
            session_key: 格式如 "agent:main:cli:user123"
            **kwargs: 其他属性 (agent_id/channel/peer_id 会覆盖解析值)

        Returns:
            Session 对象
        """
        parts = session_key.split(":")

        # 从 key 解析默认值
        parsed = {
            "agent_id": parts[1] if len(parts) > 1 else "main",
            "channel": "cli",
            "peer_id": "user",
        }

        # 解析 channel 和 peer_id
        if len(parts) >= 5:
            # 标准5部分格式: agent:id:channel:direct:peer
            parsed["channel"] = parts[2]
            parsed["peer_id"] = parts[4]
        elif len(parts) == 4:
            if parts[2] == "direct":
                # 旧4部分格式: agent:id:direct:peer
                parsed["channel"] = "cli"
                parsed["peer_id"] = parts[3]
            else:
                # 简化4部分格式: agent:id:channel:peer
                parsed["channel"] = parts[2]
                parsed["peer_id"] = parts[3]
        elif len(parts) == 3:
            # 3部分格式: agent:id:channel (peer 默认为 user)
            parsed["channel"] = parts[2]

        # kwargs 中的值优先于解析值
        return cls(
            session_key=session_key,
            agent_id=kwargs.pop("agent_id", parsed["agent_id"]),
            channel=kwargs.pop("channel", parsed["channel"]),
            peer_id=kwargs.pop("peer_id", parsed["peer_id"]),
            **kwargs
        )

    def add_message(self, role: str, content: str, metadata: Optional[dict] = None) -> None:
        """
        添加消息

        Args:
            role: 角色 (user/assistant/system)
            content: 消息内容
            metadata: 元数据
        """
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        }
        if metadata:
            message["metadata"] = metadata
        self.messages.append(message)
        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        """从字典创建"""
        # 过滤掉未知的字段
        valid_fields = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**valid_fields)

    def get_recent_messages(self, limit: int = 10) -> list[dict]:
        """获取最近的消息"""
        return self.messages[-limit:]


class SessionStore:
    """
    JSONL 格式的会话存储

    文件结构:
    data/sessions/
    ├── sessions.jsonl      # 活跃会话 (最近30天)
    ├── archive/            # 归档会话
    └── transcripts/        # 完整对话记录 (按会话ID)
        ├── session-001.jsonl
        └── session-002.jsonl
    """

    def __init__(self, base_dir: str = "./data/sessions"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir = self.base_dir / "archive"
        self.archive_dir.mkdir(exist_ok=True)
        self.transcript_dir = self.base_dir / "transcripts"
        self.transcript_dir.mkdir(exist_ok=True)

        # 内存缓存
        self._sessions: dict[str, Session] = {}
        self._load_sessions()

    def _load_sessions(self) -> None:
        """从 JSONL 加载会话"""
        sessions_file = self.base_dir / "sessions.jsonl"
        if not sessions_file.exists():
            return

        try:
            with open(sessions_file, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        session = Session.from_dict(data)
                        self._sessions[session.session_key] = session
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.warning(f"加载会话失败 (行 {line_num}): {e}")
            logger.info(f"已加载 {len(self._sessions)} 个会话")
        except Exception as e:
            logger.error(f"加载会话文件失败: {e}")

    def _save_sessions(self) -> None:
        """保存会话到 JSONL"""
        sessions_file = self.base_dir / "sessions.jsonl"
        try:
            with open(sessions_file, "w", encoding="utf-8") as f:
                for session in self._sessions.values():
                    f.write(json.dumps(session.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"保存会话失败: {e}")

    def _save_transcript(self, session: Session) -> None:
        """保存完整对话记录"""
        if not session.messages:
            return

        # 生成安全的文件名
        safe_key = session.session_key.replace(":", "_")
        transcript_file = self.transcript_dir / f"{safe_key}.jsonl"

        try:
            with open(transcript_file, "a", encoding="utf-8") as f:
                for msg in session.messages:
                    f.write(json.dumps(msg, ensure_ascii=False) + "\n")
            # 清空已保存的消息 (可选)
            # session.messages = []
        except Exception as e:
            logger.error(f"保存对话记录失败: {e}")

    def get_or_create(
        self,
        session_key: str,
        agent_id: str = "main",
        channel: str = "cli",
        peer_id: str = "user",
    ) -> Session:
        """
        获取或创建会话

        Args:
            session_key: 会话键
            agent_id: Agent ID
            channel: 通道
            peer_id: 用户ID

        Returns:
            Session 对象
        """
        if session_key in self._sessions:
            return self._sessions[session_key]

        session = Session.from_key(
            session_key,
            agent_id=agent_id,
            channel=channel,
            peer_id=peer_id,
        )
        self._sessions[session_key] = session
        return session

    def get(self, session_key: str) -> Optional[Session]:
        """获取会话"""
        return self._sessions.get(session_key)

    def save(self, session: Session) -> None:
        """
        保存会话

        同时更新内存缓存、JSONL 文件和对话记录
        """
        self._sessions[session.session_key] = session
        self._save_sessions()
        self._save_transcript(session)

    def list_sessions(
        self,
        agent_id: Optional[str] = None,
        channel: Optional[str] = None,
        limit: int = 100,
    ) -> list[Session]:
        """
        列出会话

        Args:
            agent_id: 过滤 Agent ID
            channel: 过滤通道
            limit: 最大数量

        Returns:
            Session 列表
        """
        sessions = list(self._sessions.values())

        if agent_id:
            sessions = [s for s in sessions if s.agent_id == agent_id]
        if channel:
            sessions = [s for s in sessions if s.channel == channel]

        # 按更新时间排序
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions[:limit]

    def delete(self, session_key: str) -> bool:
        """
        删除会话

        Args:
            session_key: 会话键

        Returns:
            是否成功删除
        """
        if session_key not in self._sessions:
            return False

        del self._sessions[session_key]
        self._save_sessions()

        # 可选: 删除对话记录文件
        safe_key = session_key.replace(":", "_")
        transcript_file = self.transcript_dir / f"{safe_key}.jsonl"
        if transcript_file.exists():
            transcript_file.unlink()

        return True

    def clear(self) -> None:
        """清空所有会话 (谨慎使用)"""
        self._sessions.clear()
        self._save_sessions()

    def iter_sessions(self) -> Iterator[Session]:
        """迭代所有会话"""
        yield from self._sessions.values()

    def archive_old_sessions(self, days: int = 30) -> int:
        """
        归档旧会话

        Args:
            days: 归档阈值天数

        Returns:
            归档数量
        """
        cutoff = datetime.now().timestamp() - (days * 24 * 3600)
        to_archive = []

        for key, session in list(self._sessions.items()):
            try:
                updated = datetime.fromisoformat(session.updated_at).timestamp()
                if updated < cutoff:
                    to_archive.append((key, session))
            except (ValueError, TypeError):
                continue

        for key, session in to_archive:
            # 归档到单独文件
            archive_file = self.archive_dir / f"{session.session_key.replace(':', '_')}.json"
            try:
                with open(archive_file, "w", encoding="utf-8") as f:
                    json.dump(session.to_dict(), f, ensure_ascii=False)
                del self._sessions[key]
            except Exception as e:
                logger.error(f"归档会话失败 {key}: {e}")

        if to_archive:
            self._save_sessions()
            logger.info(f"归档了 {len(to_archive)} 个旧会话")

        return len(to_archive)

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "total_sessions": len(self._sessions),
            "total_messages": sum(len(s.messages) for s in self._sessions.values()),
            "base_dir": str(self.base_dir),
        }
