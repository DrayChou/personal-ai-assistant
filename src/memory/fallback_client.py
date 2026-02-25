# -*- coding: utf-8 -*-
"""
Fallback Memory Client

当主存储不可用时使用的降级客户端
基于简单文件存储，支持基本的 CRUD 操作
"""
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from .types import MemoryEntry, MemoryConfidence, MemoryType

logger = logging.getLogger('memory.fallback')


class FallbackMemoryClient:
    """
    降级记忆客户端 - 简单文件存储

    当主存储（SQLite-Vec）不可用时使用
    特点：
    - 零依赖，纯文件操作
    - 支持关键词搜索
    - 适合临时降级场景
    """

    def __init__(self, data_dir: Path):
        """
        初始化降级客户端

        Args:
            data_dir: 数据存储目录
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.data_dir / "index.json"

        # 加载或创建索引
        self._index: dict[str, dict] = self._load_index()

        logger.info(f"FallbackMemoryClient 初始化: {self.data_dir}")

    def _load_index(self) -> dict[str, dict]:
        """加载索引文件"""
        if self.index_path.exists():
            try:
                with open(self.index_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"加载索引失败: {e}，创建新索引")
        return {}

    def _save_index(self):
        """保存索引文件"""
        try:
            with open(self.index_path, 'w', encoding='utf-8') as f:
                json.dump(self._index, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存索引失败: {e}")

    def store(self, entry: MemoryEntry, embedding: Optional[list[float]] = None) -> bool:
        """
        存储记忆

        Args:
            entry: 记忆条目
            embedding: 嵌入向量（降级模式下忽略）

        Returns:
            是否成功
        """
        try:
            memory_id = entry.id
            file_path = self.data_dir / f"{memory_id}.json"

            # 保存记忆文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(entry.to_dict(), f, ensure_ascii=False, indent=2)

            # 更新索引
            self._index[memory_id] = {
                "id": memory_id,
                "content_preview": entry.content[:100],
                "memory_type": entry.memory_type.value,
                "confidence_level": entry.confidence_level.name,
                "created_at": entry.created_at.isoformat(),
            }
            self._save_index()

            logger.debug(f"存储记忆 (Fallback): {memory_id}")
            return True
        except Exception as e:
            logger.error(f"存储记忆失败 (Fallback): {e}")
            return False

    def retrieve(self, memory_id: str) -> Optional[MemoryEntry]:
        """
        检索记忆

        Args:
            memory_id: 记忆ID

        Returns:
            记忆条目，不存在返回 None
        """
        file_path = self.data_dir / f"{memory_id}.json"
        if not file_path.exists():
            return None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return self._dict_to_entry(data)
        except Exception as e:
            logger.error(f"检索记忆失败 (Fallback): {e}")
            return None

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_confidence: float = 0.0
    ) -> list[tuple[MemoryEntry, float]]:
        """
        简单搜索（关键词匹配）

        Args:
            query: 查询字符串
            top_k: 返回数量
            min_confidence: 最小置信度

        Returns:
            [(记忆条目, 分数), ...]
        """
        results = []
        query_lower = query.lower()
        query_terms = set(query_lower.split())

        # 遍历所有记忆文件
        for file_path in self.data_dir.glob("*.json"):
            if file_path.name == "index.json":
                continue

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                entry = self._dict_to_entry(data)

                # 置信度过滤
                if entry.current_confidence < min_confidence:
                    continue

                # 关键词匹配计算分数
                content_lower = entry.content.lower()
                matches = sum(1 for term in query_terms if term in content_lower)

                if matches > 0:
                    # 简单评分：匹配词数 / 查询词数
                    score = matches / len(query_terms)
                    results.append((entry, score))

            except Exception as e:
                logger.debug(f"读取记忆文件失败: {file_path}: {e}")
                continue

        # 按分数排序，返回 top_k
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def search_by_keyword(self, keyword: str, top_k: int = 10) -> list[MemoryEntry]:
        """
        关键词搜索

        Args:
            keyword: 关键词
            top_k: 返回数量

        Returns:
            记忆条目列表
        """
        results = self.search(keyword, top_k=top_k)
        return [entry for entry, _ in results]

    def get_recent(self, limit: int = 10) -> list[MemoryEntry]:
        """
        获取最近记忆

        Args:
            limit: 返回数量

        Returns:
            记忆条目列表
        """
        # 从索引按时间排序
        sorted_ids = sorted(
            self._index.keys(),
            key=lambda x: self._index[x].get("created_at", ""),
            reverse=True
        )

        entries = []
        for memory_id in sorted_ids[:limit]:
            entry = self.retrieve(memory_id)
            if entry:
                entries.append(entry)

        return entries

    def delete(self, memory_id: str) -> bool:
        """
        删除记忆

        Args:
            memory_id: 记忆ID

        Returns:
            是否成功
        """
        try:
            file_path = self.data_dir / f"{memory_id}.json"
            if file_path.exists():
                file_path.unlink()

            if memory_id in self._index:
                del self._index[memory_id]
                self._save_index()

            return True
        except Exception as e:
            logger.error(f"删除记忆失败 (Fallback): {e}")
            return False

    def count(self) -> int:
        """获取记忆总数"""
        return len(self._index)

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "total": self.count(),
            "storage_type": "file",
            "data_dir": str(self.data_dir),
        }

    def _dict_to_entry(self, data: dict) -> MemoryEntry:
        """将字典转换为 MemoryEntry"""
        return MemoryEntry(
            id=data.get("id", str(uuid.uuid4())[:8]),
            content=data.get("content", ""),
            memory_type=MemoryType(data.get("memory_type", "observation")),
            confidence_level=MemoryConfidence[data.get("confidence_level", "EVENT")],
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            last_accessed=datetime.fromisoformat(data["last_accessed"]) if data.get("last_accessed") else datetime.now(),
            initial_confidence=data.get("initial_confidence", 1.0),
            current_confidence=data.get("current_confidence", 1.0),
            access_count=data.get("access_count", 0),
            source=data.get("source"),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )

    def clear(self):
        """清空所有记忆"""
        for file_path in self.data_dir.glob("*.json"):
            file_path.unlink()
        self._index = {}
        self._save_index()
        logger.info("FallbackMemoryClient 已清空")

    def close(self):
        """关闭客户端（保存索引）"""
        self._save_index()
        logger.debug("FallbackMemoryClient 已关闭")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
