# -*- coding: utf-8 -*-
"""
记忆检索 Pipeline
多路召回 + Reranking 架构
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional

import numpy as np

from .types import MemoryEntry
from .long_term_memory import LongTermMemory

logger = logging.getLogger('memory.retrieval')


@dataclass
class RetrievalResult:
    """检索结果 - RIF评分模型"""
    memory: MemoryEntry
    semantic_score: float      # 语义相似度 (0-1)
    recency_score: float       # Recency: 时间相关度 (0-1)
    importance_score: float    # Importance: 初始重要性 (0-1)
    frequency_score: float     # Frequency: 访问频率 (0-1)
    final_score: float         # 综合分数 (0-1)


class MemoryRetrieval:
    """
    记忆检索器

    实现 SimpleMem 的意图感知检索规划
    """

    def __init__(
        self,
        long_term_memory: LongTermMemory,
        embedding_func: Optional[Callable[[str], list[float]]] = None
    ):
        self.ltm = long_term_memory
        self.embedding_func = embedding_func

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        min_confidence: float = 0.3,
        time_decay_hours: Optional[int] = None
    ) -> list[RetrievalResult]:
        """
        检索记忆

        步骤:
        1. 向量相似度检索 (召回)
        2. 关键词补充检索 (容错)
        3. 时间衰减加权
        4. 置信度加权
        5. Reranking

        Args:
            query: 查询文本
            top_k: 返回数量
            min_confidence: 最小置信度
            time_decay_hours: 时间衰减窗口（小时），None表示不考虑时间

        Returns:
            检索结果列表（按分数排序）
        """
        candidates: dict[str, tuple[MemoryEntry, float]] = {}

        # Step 1: 向量检索
        if self.embedding_func:
            try:
                query_emb = self.embedding_func(query)
                vec_results = self.ltm.search_by_vector(
                    query_emb, top_k * 2, min_confidence
                )
                for entry, score in vec_results:
                    candidates[entry.id] = (entry, score)
                logger.debug(f"向量检索: {len(vec_results)} 条")
            except Exception as e:
                logger.warning(f"向量检索失败: {e}")

        # Step 2: 关键词检索（补充）
        # 提取查询中的关键词
        keywords = self._extract_keywords(query)
        for keyword in keywords:
            keyword_results = self.ltm.search_by_keyword(keyword, top_k)
            for entry in keyword_results:
                if entry.id not in candidates:
                    candidates[entry.id] = (entry, 0.5)  # 默认分数
                else:
                    # 提升已有候选的分数
                    entry, score = candidates[entry.id]
                    candidates[entry.id] = (entry, min(1.0, score + 0.1))

        logger.debug(f"关键词检索后: {len(candidates)} 条候选")

        # Step 3: RIF 多维度打分
        results = []
        for entry, semantic_score in candidates.values():
            # R: Recency - 时间相关度
            recency_score = self._calculate_recency(
                entry, time_decay_hours
            )

            # I: Importance - 初始重要性
            importance_score = self._calculate_importance(entry)

            # F: Frequency - 访问频率
            frequency_score = self._calculate_frequency(entry)

            # RIF 综合分数（加权）
            # 权重配置: R=0.3, I=0.3, F=0.1, Semantic=0.3
            final_score = (
                semantic_score * 0.3 +      # 语义相似度
                recency_score * 0.3 +       # 时间相关
                importance_score * 0.3 +    # 重要性
                frequency_score * 0.1       # 频率加成
            )

            # 过滤低分
            if final_score < min_confidence:
                continue

            results.append(RetrievalResult(
                memory=entry,
                semantic_score=semantic_score,
                recency_score=recency_score,
                importance_score=importance_score,
                frequency_score=frequency_score,
                final_score=final_score
            ))

        # Step 4: 排序返回
        results.sort(key=lambda x: x.final_score, reverse=True)
        return results[:top_k]

    def retrieve_for_context(
        self,
        query: str,
        max_tokens: int = 1500,
        max_memories: int = 10
    ) -> str:
        """
        检索并格式化为上下文字符串

        Args:
            query: 查询
            max_tokens: 最大Token数
            max_memories: 最大记忆数

        Returns:
            格式化的上下文字符串
        """
        results = self.retrieve(query, top_k=max_memories)

        if not results:
            return ""

        lines = ["【相关记忆】"]
        current_tokens = 0

        for result in results:
            entry = result.memory
            line = f"- {entry.content}"

            # 粗略估算token
            line_tokens = int(len(line) / 0.75)

            if current_tokens + line_tokens > max_tokens:
                break

            lines.append(line)
            current_tokens += line_tokens

            # 更新访问统计
            entry.access()
            self.ltm.update(entry)

        return "\n".join(lines)

    def _extract_keywords(self, text: str) -> list[str]:
        """提取关键词"""
        # 简单实现：提取长度>2的词
        import re
        words = re.findall(r'\b\w{2,}\b', text)
        # 去重并限制数量
        seen = set()
        keywords = []
        for w in words:
            if w.lower() not in seen and len(keywords) < 3:
                seen.add(w.lower())
                keywords.append(w)
        return keywords

    def _calculate_recency(
        self,
        entry: MemoryEntry,
        decay_hours: Optional[int]
    ) -> float:
        """计算时间相关度分数 (Recency)"""
        if decay_hours is None:
            # 默认7天衰减
            decay_hours = 7 * 24

        hours_ago = (datetime.now() - entry.created_at).total_seconds() / 3600

        # 指数衰减
        score = np.exp(-hours_ago / decay_hours)
        return float(score)

    def _calculate_importance(self, entry: MemoryEntry) -> float:
        """计算重要性分数 (Importance)

        基于:
        - 初始置信度 (0.5)
        - 置信度等级 (0.3)
        - 记忆类型 (0.2)
        """
        # 基础: 初始置信度
        base_score = entry.initial_confidence

        # 置信度等级加成
        confidence_bonus = {
            'FACT': 0.3,
            'SUMMARY': 0.2,
            'BELIEF': 0.1,
            'EVENT': 0.0,
            'GOSSIP': -0.1
        }.get(entry.confidence_level.name, 0.0)

        # 记忆类型加成 (重要类型)
        type_bonus = {
            'SOLUTION': 0.2,
            'FACT': 0.15,
            'KNOWLEDGE': 0.1,
            'DECISION': 0.1,
            'BUGFIX': 0.1,
            'PROCEDURAL': 0.05,
            'PATTERN': 0.05,
        }.get(entry.memory_type.name, 0.0)

        score = base_score * 0.5 + confidence_bonus + type_bonus
        return max(0.0, min(1.0, score))

    def _calculate_frequency(self, entry: MemoryEntry) -> float:
        """计算频率分数 (Frequency)

        访问次数归一化，封顶10次
        """
        if entry.access_count == 0:
            return 0.0

        # 对数缩放: 前几次访问影响大，后续递减
        import math
        score = min(1.0, math.log1p(entry.access_count) / math.log1p(10))
        return float(score)
