# -*- coding: utf-8 -*-
"""
记忆系统主类
整合工作记忆、长期记忆、检索和整合
支持 Fallback 降级机制
"""
import logging
from pathlib import Path
from typing import Callable, Optional

from .types import MemoryEntry, MemoryConfidence, MemoryType
from .working_memory import WorkingMemory, WorkingMemoryConfig
from .long_term_memory import LongTermMemory
from .retrieval import MemoryRetrieval
from .consolidation import MemoryConsolidation
from .markdown_exporter import MarkdownExporter
from .fallback_client import FallbackMemoryClient

logger = logging.getLogger('memory.system')


class MemorySystem:
    """
    记忆系统主类

    两层架构：
    - L0: 工作记忆（2000 tokens，当前会话）
    - L1: 长期记忆（SQLite-Vec，全部历史）

    特性：
    - 自动记忆捕获
    - 语义检索
    - 定期整合
    - Markdown 导出（兼容 MemSearch）
    - Fallback 降级机制
    """

    def __init__(
        self,
        data_dir: str = "./data/memories",
        embedding_func: Optional[Callable[[str], list[float]]] = None,
        llm_client: Optional[Callable] = None,
        enable_markdown_export: bool = False,
        markdown_path: str = "~/ai_workspace/memories"
    ):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Fallback 状态
        self._using_fallback = False
        self._fallback_client: Optional[FallbackMemoryClient] = None

        # L0: 工作记忆
        self.working_memory = WorkingMemory(WorkingMemoryConfig())

        # L1: 长期记忆（带 Fallback）
        db_path = self.data_dir / "long_term.db"
        self.long_term_memory = self._init_long_term_memory(db_path)

        # 检索器
        self.retrieval = MemoryRetrieval(
            self.long_term_memory,
            embedding_func
        )

        # 整合器
        self.consolidation = MemoryConsolidation(
            self.long_term_memory,
            llm_client
        )

        # Markdown 导出器
        self.markdown_exporter: Optional[MarkdownExporter] = None
        if enable_markdown_export:
            self.markdown_exporter = MarkdownExporter(markdown_path)

        # 统计
        self.stats = {
            "memories_added": 0,
            "memories_retrieved": 0,
            "last_consolidation": None,
            "fallback_mode": self._using_fallback,
        }

        logger.info(f"记忆系统初始化完成（{'Fallback 模式' if self._using_fallback else '正常模式'}）")

    def _init_long_term_memory(self, db_path: Path) -> LongTermMemory:
        """
        初始化长期记忆，支持 Fallback

        Args:
            db_path: 数据库路径

        Returns:
            LongTermMemory 实例
        """
        try:
            ltm = LongTermMemory(str(db_path))
            logger.info("长期记忆初始化成功: SQLite-Vec")
            return ltm
        except Exception as e:
            logger.warning(f"长期记忆初始化失败: {e}，启用 Fallback 模式")
            self._using_fallback = True
            self._fallback_client = FallbackMemoryClient(
                self.data_dir / "fallback"
            )
            # 返回一个 None 占位符，实际使用 fallback_client
            return None  # type: ignore

    def _get_storage(self):
        """获取当前使用的存储"""
        if self._using_fallback and self._fallback_client:
            return self._fallback_client
        return self.long_term_memory

    def capture(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.OBSERVATION,
        confidence: MemoryConfidence = MemoryConfidence.EVENT,
        source: Optional[str] = None,
        tags: Optional[list] = None
    ) -> str:
        """
        捕获记忆

        步骤：
        1. 存入长期记忆
        2. 更新工作记忆（如果是重要信息）

        Args:
            content: 记忆内容
            memory_type: 记忆类型
            confidence: 置信度等级
            source: 来源（会话ID等）
            tags: 标签

        Returns:
            记忆ID
        """
        entry = MemoryEntry(
            content=content,
            memory_type=memory_type,
            confidence_level=confidence,
            source=source,
            tags=tags or []
        )

        # 生成嵌入（如果有嵌入函数）
        embedding = None
        if self.retrieval.embedding_func:
            try:
                embedding = self.retrieval.embedding_func(content)
            except Exception as e:
                logger.debug(f"嵌入生成失败: {e}")

        # 存入长期记忆（带 Fallback）
        success = self._store_with_fallback(entry, embedding)

        if success:
            self.stats["memories_added"] += 1

            # L0: 如果是高置信度事实，加入工作记忆
            if confidence == MemoryConfidence.FACT:
                self.working_memory.add_fact(content)

            # Markdown 导出（如果启用）
            if self.markdown_exporter:
                try:
                    self.markdown_exporter.save_memory(entry)
                except Exception as e:
                    logger.warning(f"Markdown 导出失败: {e}")

            logger.debug(f"记忆已捕获: {entry.id}")
            return entry.id

        return ""

    def _store_with_fallback(self, entry: MemoryEntry, embedding: Optional[list[float]] = None) -> bool:
        """
        存储记忆（带 Fallback 机制）

        Args:
            entry: 记忆条目
            embedding: 嵌入向量

        Returns:
            是否成功
        """
        # 如果已经在 Fallback 模式
        if self._using_fallback and self._fallback_client:
            return self._fallback_client.store(entry, embedding)

        # 尝试主存储
        try:
            success = self.long_term_memory.store(entry, embedding)
            if success:
                return True

            # 主存储返回失败，尝试 Fallback
            logger.warning("主存储失败，尝试 Fallback")
            return self._try_fallback_store(entry, embedding)

        except Exception as e:
            logger.warning(f"主存储异常: {e}，切换到 Fallback")
            return self._try_fallback_store(entry, embedding)

    def _try_fallback_store(self, entry: MemoryEntry, embedding: Optional[list[float]] = None) -> bool:
        """
        尝试使用 Fallback 存储

        Args:
            entry: 记忆条目
            embedding: 嵌入向量

        Returns:
            是否成功
        """
        if self._fallback_client is None:
            self._fallback_client = FallbackMemoryClient(
                self.data_dir / "fallback"
            )

        self._using_fallback = True
        self.stats["fallback_mode"] = True
        return self._fallback_client.store(entry, embedding)

    def recall(
        self,
        query: str,
        top_k: int = 5,
        include_working_memory: bool = True
    ) -> str:
        """
        回忆记忆（两层检索）

        步骤：
        1. L0: 检查工作记忆
        2. L1: 检索长期记忆
        3. 合并返回

        Args:
            query: 查询
            top_k: 返回数量
            include_working_memory: 是否包含工作记忆

        Returns:
            格式化的上下文字符串
        """
        contexts = []

        # L0: 工作记忆（最高优先级）
        if include_working_memory:
            wm_context = self.working_memory.get_full_context()
            if wm_context:
                contexts.append(wm_context)

        # L1: 长期记忆检索（带 Fallback）
        ltm_context = self._retrieve_with_fallback(query, top_k)

        if ltm_context:
            contexts.append(ltm_context)
            self.stats["memories_retrieved"] += top_k

        return "\n\n".join(contexts)

    def _retrieve_with_fallback(self, query: str, top_k: int) -> str:
        """
        检索记忆（带 Fallback 机制）

        Args:
            query: 查询字符串
            top_k: 返回数量

        Returns:
            格式化的上下文字符串
        """
        # 如果已经在 Fallback 模式
        if self._using_fallback and self._fallback_client:
            return self._fallback_search(query, top_k)

        # 尝试主存储
        try:
            context = self.retrieval.retrieve_for_context(
                query, max_memories=top_k
            )
            return context
        except Exception as e:
            logger.warning(f"主存储检索失败: {e}，使用 Fallback")
            return self._fallback_search(query, top_k)

    def _fallback_search(self, query: str, top_k: int) -> str:
        """
        Fallback 模式下的搜索

        Args:
            query: 查询字符串
            top_k: 返回数量

        Returns:
            格式化的上下文字符串
        """
        if not self._fallback_client:
            return ""

        results = self._fallback_client.search(query, top_k=top_k)
        if not results:
            return ""

        # 格式化结果
        formatted = []
        for entry, score in results:
            formatted.append(f"- [{entry.memory_type.value}] {entry.content}")

        return "【相关记忆 (Fallback)】\n" + "\n".join(formatted)

    def consolidate(self, dry_run: bool = False) -> dict:
        """
        运行记忆整合

        Args:
            dry_run: 仅预览

        Returns:
            处理统计
        """
        stats = self.consolidation.run(days_back=7, dry_run=dry_run)
        self.stats["last_consolidation"] = stats
        return stats

    def export(self, output_path: Optional[str] = None) -> str:
        """
        导出记忆为 JSONL

        Args:
            output_path: 输出路径，None则使用默认路径

        Returns:
            输出文件路径
        """
        if output_path is None:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = str(self.data_dir / f"memories_export_{timestamp}.jsonl")

        self.long_term_memory.export_to_jsonl(output_path)
        return output_path

    def export_markdown(self, generate_index: bool = True) -> str:
        """
        导出所有记忆为 Markdown

        Args:
            generate_index: 是否生成索引文件

        Returns:
            导出目录路径
        """
        if not self.markdown_exporter:
            raise ValueError("Markdown 导出未启用，请在初始化时设置 enable_markdown_export=True")

        # 导出所有记忆
        recent = self.long_term_memory.get_recent(limit=10000)
        self.markdown_exporter.batch_export(recent)

        # 生成索引
        if generate_index:
            self.markdown_exporter.generate_index()

        return str(self.markdown_exporter.base_path)

    def get_stats(self) -> dict:
        """获取系统统计（两层架构）"""
        # 获取存储统计
        if self._using_fallback and self._fallback_client:
            storage_stats = self._fallback_client.get_stats()
        elif self.long_term_memory:
            storage_stats = self.long_term_memory.get_stats()
        else:
            storage_stats = {"total": 0}

        return {
            **self.stats,
            **storage_stats,
            "working_memory_slots": list(self.working_memory.slots.keys()),
            "markdown_export_enabled": self.markdown_exporter is not None,
            "using_fallback": self._using_fallback,
        }

    def close(self):
        """关闭资源"""
        if self.long_term_memory:
            self.long_term_memory.close()
        if self._fallback_client:
            self._fallback_client.close()
        logger.info("记忆系统已关闭")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
