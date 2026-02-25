# -*- coding: utf-8 -*-
"""
长期记忆存储 - 基于 SQLite-Vec
支持语义检索 + 关键词检索 + 混合检索
"""
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .types import MemoryEntry, MemoryConfidence, MemoryType

logger = logging.getLogger('memory.long_term')


class LongTermMemory:
    """
    长期记忆存储器

    使用 SQLite-Vec 实现向量检索
    备选：纯 SQLite 关键词检索
    """

    def __init__(self, db_path: str, embedding_dim: int = 768):
        self.db_path = Path(db_path)
        self.embedding_dim = embedding_dim
        self._conn: Optional[sqlite3.Connection] = None
        self._vec_available = False

        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            import sqlite_vec
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.enable_load_extension(True)
            sqlite_vec.load(self._conn)
            self._conn.enable_load_extension(False)
            self._vec_available = True
            self._create_vec_tables()
            logger.info(f"SQLite-Vec 初始化成功: {self.db_path}")
        except ImportError:
            logger.warning("SQLite-Vec 未安装，使用纯SQLite回退模式")
            self._conn = sqlite3.connect(str(self.db_path))
            self._create_fallback_tables()

    def _create_vec_tables(self):
        """创建向量表"""
        # 向量表
        self._conn.execute(f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_memories USING vec0(
                memory_id TEXT PRIMARY KEY,
                embedding FLOAT[{self.embedding_dim}]
            )
        """)

        # 元数据表
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS memory_metadata (
                memory_id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                memory_type TEXT,
                confidence_level TEXT,
                created_at TEXT,
                last_accessed TEXT,
                initial_confidence REAL,
                current_confidence REAL,
                access_count INTEGER,
                source TEXT,
                tags TEXT,
                metadata TEXT
            )
        """)

        # 索引
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_time
            ON memory_metadata(created_at)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_type
            ON memory_metadata(memory_type)
        """)

        self._conn.commit()

    def _create_fallback_tables(self):
        """创建回退表（无向量支持）"""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS memory_metadata (
                memory_id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                memory_type TEXT,
                confidence_level TEXT,
                created_at TEXT,
                last_accessed TEXT,
                initial_confidence REAL,
                current_confidence REAL,
                access_count INTEGER,
                source TEXT,
                tags TEXT,
                metadata TEXT
            )
        """)
        self._conn.commit()

    def store(self, entry: MemoryEntry, embedding: Optional[list[float]] = None) -> bool:
        """
        存储记忆

        Args:
            entry: 记忆条目
            embedding: 嵌入向量（可选，如果为None则不存储向量）

        Returns:
            是否成功
        """
        try:
            # 确定要使用的嵌入向量（参数优先，否则使用 entry.embedding）
            embedding_to_use = embedding or entry.embedding

            # 插入向量（如果可用）
            if self._vec_available and embedding_to_use:
                try:
                    import sqlite_vec
                    embedding_bytes = sqlite_vec.serialize_float32(embedding_to_use)
                    self._conn.execute("""
                        INSERT INTO vec_memories (memory_id, embedding)
                        VALUES (?, ?)
                    """, (entry.id, embedding_bytes))
                except Exception as e:
                    logger.debug(f"向量插入失败: {e}")

            # 插入元数据
            self._conn.execute("""
                INSERT OR REPLACE INTO memory_metadata
                (memory_id, content, memory_type, confidence_level, created_at,
                 last_accessed, initial_confidence, current_confidence,
                 access_count, source, tags, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.id,
                entry.content,
                entry.memory_type.value,
                entry.confidence_level.name,
                entry.created_at.isoformat(),
                entry.last_accessed.isoformat(),
                entry.initial_confidence,
                entry.current_confidence,
                entry.access_count,
                entry.source,
                json.dumps(entry.tags),
                json.dumps(entry.metadata)
            ))

            self._conn.commit()
            return True
        except Exception as e:
            logger.error(f"存储记忆失败: {e}")
            return False

    def search_by_vector(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        min_confidence: float = 0.0
    ) -> list[tuple[MemoryEntry, float]]:
        """
        向量相似度搜索

        Args:
            query_embedding: 查询向量
            top_k: 返回数量
            min_confidence: 最小置信度

        Returns:
            [(记忆条目, 相似度分数), ...]
        """
        if not self._vec_available:
            logger.warning("SQLite-Vec 不可用，跳过向量搜索")
            return []

        try:
            import sqlite_vec

            # 将列表转换为 SQLite-Vec 支持的格式
            query_bytes = sqlite_vec.serialize_float32(query_embedding)

            cursor = self._conn.execute("""
                SELECT
                    m.memory_id, m.content, m.memory_type, m.confidence_level,
                    m.created_at, m.last_accessed, m.initial_confidence,
                    m.current_confidence, m.access_count, m.source, m.tags, m.metadata,
                    distance
                FROM vec_memories v
                JOIN memory_metadata m ON v.memory_id = m.memory_id
                WHERE v.embedding MATCH ?
                    AND k = ?
                    AND m.current_confidence >= ?
                ORDER BY distance
            """, (query_bytes, top_k, min_confidence))

            results = []
            for row in cursor.fetchall():
                entry = self._row_to_entry(row)
                # distance越小越相似，转换为0-1分数
                score = 1.0 / (1.0 + row[12])
                results.append((entry, score))

            return results
        except Exception as e:
            logger.error(f"向量搜索失败: {e}")
            return []

    def search_by_keyword(
        self,
        keyword: str,
        top_k: int = 10
    ) -> list[MemoryEntry]:
        """
        关键词搜索

        Args:
            keyword: 关键词
            top_k: 返回数量

        Returns:
            记忆条目列表
        """
        try:
            cursor = self._conn.execute("""
                SELECT * FROM memory_metadata
                WHERE content LIKE ?
                ORDER BY current_confidence DESC, created_at DESC
                LIMIT ?
            """, (f"%{keyword}%", top_k))

            return [self._row_to_entry(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"关键词搜索失败: {e}")
            return []

    def get_recent(self, limit: int = 10) -> list[MemoryEntry]:
        """获取最近记忆"""
        try:
            cursor = self._conn.execute("""
                SELECT * FROM memory_metadata
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))

            return [self._row_to_entry(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"获取最近记忆失败: {e}")
            return []

    def get_before(self, cutoff: datetime) -> list[MemoryEntry]:
        """获取指定时间之前的记忆"""
        try:
            cursor = self._conn.execute("""
                SELECT * FROM memory_metadata
                WHERE created_at < ?
                ORDER BY created_at DESC
            """, (cutoff.isoformat(),))

            return [self._row_to_entry(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"获取历史记忆失败: {e}")
            return []

    def get_after(self, cutoff: datetime) -> list[MemoryEntry]:
        """获取指定时间之后的记忆（用于获取某段时间内的记忆）"""
        try:
            cursor = self._conn.execute("""
                SELECT * FROM memory_metadata
                WHERE created_at >= ?
                ORDER BY created_at DESC
            """, (cutoff.isoformat(),))

            return [self._row_to_entry(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"获取记忆失败: {e}")
            return []

    def update(self, entry: MemoryEntry) -> bool:
        """更新记忆"""
        try:
            self._conn.execute("""
                UPDATE memory_metadata SET
                    content = ?, memory_type = ?, confidence_level = ?,
                    last_accessed = ?, current_confidence = ?, access_count = ?,
                    tags = ?, metadata = ?
                WHERE memory_id = ?
            """, (
                entry.content,
                entry.memory_type.value,
                entry.confidence_level.name,
                entry.last_accessed.isoformat(),
                entry.current_confidence,
                entry.access_count,
                json.dumps(entry.tags),
                json.dumps(entry.metadata),
                entry.id
            ))
            self._conn.commit()
            return True
        except Exception as e:
            logger.error(f"更新记忆失败: {e}")
            return False

    def delete(self, memory_id: str) -> bool:
        """删除记忆"""
        try:
            self._conn.execute(
                "DELETE FROM memory_metadata WHERE memory_id = ?",
                (memory_id,)
            )
            if self._vec_available:
                try:
                    self._conn.execute(
                        "DELETE FROM vec_memories WHERE memory_id = ?",
                        (memory_id,)
                    )
                except Exception as e:
                    logger.debug(f"Vector delete failed (may not exist): {e}")
            self._conn.commit()
            return True
        except Exception as e:
            logger.error(f"删除记忆失败: {e}")
            return False

    def count(self) -> int:
        """获取记忆总数"""
        try:
            cursor = self._conn.execute("SELECT COUNT(*) FROM memory_metadata")
            return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"获取记忆数失败: {e}")
            return 0

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        try:
            total = self.count()

            # 按类型统计
            cursor = self._conn.execute("""
                SELECT memory_type, COUNT(*) FROM memory_metadata
                GROUP BY memory_type
            """)
            by_type = {row[0]: row[1] for row in cursor.fetchall()}

            # 按置信度统计
            cursor = self._conn.execute("""
                SELECT
                    CASE
                        WHEN current_confidence >= 0.8 THEN 'high'
                        WHEN current_confidence >= 0.5 THEN 'medium'
                        ELSE 'low'
                    END,
                    COUNT(*)
                FROM memory_metadata
                GROUP BY 1
            """)
            by_confidence = {row[0]: row[1] for row in cursor.fetchall()}

            return {
                "total": total,
                "by_type": by_type,
                "by_confidence": by_confidence,
                "vec_available": self._vec_available,
            }
        except Exception as e:
            logger.error(f"获取统计失败: {e}")
            return {"total": 0, "by_type": {}, "by_confidence": {}}

    def _row_to_entry(self, row) -> MemoryEntry:
        """将数据库行转换为 MemoryEntry"""
        return MemoryEntry(
            id=row[0],
            content=row[1],
            memory_type=MemoryType(row[2]) if row[2] else MemoryType.OBSERVATION,
            confidence_level=MemoryConfidence[row[3]] if row[3] else MemoryConfidence.EVENT,
            created_at=datetime.fromisoformat(row[4]) if row[4] else datetime.now(),
            last_accessed=datetime.fromisoformat(row[5]) if row[5] else datetime.now(),
            initial_confidence=row[6] if row[6] is not None else 1.0,
            current_confidence=row[7] if row[7] is not None else 1.0,
            access_count=row[8] if row[8] is not None else 0,
            source=row[9],
            tags=json.loads(row[10]) if row[10] else [],
            metadata=json.loads(row[11]) if row[11] else {},
        )

    def export_to_jsonl(self, output_path: str):
        """导出为 JSONL 格式"""
        try:
            cursor = self._conn.execute("SELECT * FROM memory_metadata")
            with open(output_path, 'w', encoding='utf-8') as f:
                for row in cursor.fetchall():
                    entry = self._row_to_entry(row)
                    f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + '\n')
            logger.info(f"导出完成: {output_path}")
        except Exception as e:
            logger.error(f"导出失败: {e}")

    def retrieve(self, memory_id: str) -> Optional[MemoryEntry]:
        """
        通过ID检索记忆

        Args:
            memory_id: 记忆ID

        Returns:
            记忆条目，不存在返回 None
        """
        try:
            cursor = self._conn.execute(
                "SELECT * FROM memory_metadata WHERE memory_id = ?",
                (memory_id,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_entry(row)
            return None
        except Exception as e:
            logger.error(f"检索记忆失败: {e}")
            return None

    def search_similar(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        min_confidence: float = 0.0
    ) -> list[MemoryEntry]:
        """
        相似度搜索（仅返回条目列表）

        Args:
            query_embedding: 查询向量
            top_k: 返回数量
            min_confidence: 最小置信度

        Returns:
            记忆条目列表
        """
        results = self.search_by_vector(query_embedding, top_k, min_confidence)
        return [entry for entry, _ in results]

    def close(self):
        """关闭连接"""
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
