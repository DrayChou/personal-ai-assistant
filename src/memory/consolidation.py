# -*- coding: utf-8 -*-
"""
记忆整合 (Consolidation)

类比人类睡眠时的记忆巩固过程：
- 白天的事件 → 晚上整理 → 提取模式 → 长期存储

参考 SimpleMem 的语义结构化压缩 + 在线语义合成
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Callable, Optional

from .types import MemoryEntry, MemoryConfidence, MemoryType
from .long_term_memory import LongTermMemory

logger = logging.getLogger('memory.consolidation')


class MemoryConsolidation:
    """
    记忆整合引擎

    7阶段流程：
    1. 收集 → 2. 筛选 → 3. 提取 → 4. 分类 → 5. 衰减计算 → 6. 归档 → 7. 快照生成
    """

    def __init__(
        self,
        long_term_memory: LongTermMemory,
        llm_client: Optional[Callable] = None
    ):
        self.ltm = long_term_memory
        self.llm_client = llm_client

    def run(
        self,
        days_back: int = 7,
        dry_run: bool = False
    ) -> dict:
        """
        运行完整的 Consolidation 流程

        Args:
            days_back: 处理多少天内的记忆
            dry_run: 仅预览，不实际执行

        Returns:
            处理统计
        """
        stats = {
            "collected": 0,
            "filtered": 0,
            "facts_extracted": 0,
            "beliefs_extracted": 0,
            "summaries_created": 0,
            "archived": 0,
            "dry_run": dry_run,
        }

        logger.info(f"开始记忆整合（过去{days_back}天）")

        # Phase 1: 收集（获取 cutoff 之后到现在的记忆）
        cutoff = datetime.now() - timedelta(days=days_back)
        raw_events = self.ltm.get_after(cutoff)
        stats["collected"] = len(raw_events)
        logger.info(f"收集到 {len(raw_events)} 条原始记忆")

        if not raw_events:
            return stats

        # Phase 2: 筛选（去除低价值事件）
        significant = self._filter_significant(raw_events)
        stats["filtered"] = len(significant)
        logger.info(f"筛选后剩余 {len(significant)} 条重要记忆")

        # Phase 3-4: 提取和分类
        if self.llm_client and len(significant) >= 5:
            facts, beliefs, summaries = self._llm_extract_and_classify(significant)
        else:
            facts, beliefs, summaries = self._rule_based_extract(significant)

        stats["facts_extracted"] = len(facts)
        stats["beliefs_extracted"] = len(beliefs)
        stats["summaries_created"] = len(summaries)

        logger.info(f"提取: {len(facts)} 事实, {len(beliefs)} 信念, {len(summaries)} 摘要")

        if dry_run:
            return stats

        # Phase 5: 衰减计算（已在提取时完成）

        # Phase 6: 归档
        archived = self._archive_forgotten(raw_events)
        stats["archived"] = archived

        # Phase 7: 存储新记忆
        for entry in facts + beliefs + summaries:
            self.ltm.store(entry)

        logger.info(f"记忆整合完成: {stats}")
        return stats

    def _filter_significant(self, events: list[MemoryEntry]) -> list[MemoryEntry]:
        """筛选重要记忆"""
        # 过滤掉：
        # 1. 置信度 < 0.3 的
        # 2. 已访问次数 < 1 且创建时间 > 3天的（从未被检索的冷门记忆）
        significant = []
        for event in events:
            if event.current_confidence < 0.3:
                continue

            days_old = (datetime.now() - event.created_at).days
            if days_old > 3 and event.access_count < 1:
                continue

            significant.append(event)

        return significant

    def _llm_extract_and_classify(
        self,
        events: list[MemoryEntry]
    ) -> tuple[list[MemoryEntry], list[MemoryEntry], list[MemoryEntry]]:
        """使用 LLM 提取和分类"""
        events_text = "\n".join([
            f"[{e.created_at.strftime('%m-%d %H:%M')}] {e.content}"
            for e in events[:50]  # 限制数量
        ])

        prompt = f"""从以下记忆/对话中提取结构化信息：

{events_text}

请提取：
1. 确定的事实（用户明确陈述的，如"我喜欢Python"）
2. 推断的信念（需要推理的，如"用户可能是开发者"）
3. 摘要总结（模式识别，如"用户最近在学AI"）

输出JSON格式：
{{
    "facts": [
        {{"content": "...", "confidence": 0.95}}
    ],
    "beliefs": [
        {{"content": "...", "confidence": 0.6}}
    ],
    "summaries": [
        {{"content": "...", "confidence": 0.8}}
    ]
}}"""

        try:
            response = self.llm_client(prompt)
            data = json.loads(response)

            facts = [
                MemoryEntry(
                    content=f["content"],
                    memory_type=MemoryType.KNOWLEDGE,
                    confidence_level=MemoryConfidence.FACT,
                    initial_confidence=f.get("confidence", 0.9),
                    current_confidence=f.get("confidence", 0.9),
                    tags=["extracted", "fact"]
                )
                for f in data.get("facts", [])
            ]

            beliefs = [
                MemoryEntry(
                    content=b["content"],
                    memory_type=MemoryType.KNOWLEDGE,
                    confidence_level=MemoryConfidence.BELIEF,
                    initial_confidence=b.get("confidence", 0.6),
                    current_confidence=b.get("confidence", 0.6),
                    tags=["extracted", "belief"]
                )
                for b in data.get("beliefs", [])
            ]

            summaries = [
                MemoryEntry(
                    content=s["content"],
                    memory_type=MemoryType.SUMMARY,
                    confidence_level=MemoryConfidence.SUMMARY,
                    initial_confidence=s.get("confidence", 0.8),
                    current_confidence=s.get("confidence", 0.8),
                    tags=["extracted", "summary"]
                )
                for s in data.get("summaries", [])
            ]

            return facts, beliefs, summaries

        except Exception as e:
            logger.warning(f"LLM提取失败: {e}，使用规则方法")
            return self._rule_based_extract(events)

    def _rule_based_extract(
        self,
        events: list[MemoryEntry]
    ) -> tuple[list[MemoryEntry], list[MemoryEntry], list[MemoryEntry]]:
        """基于规则的提取（无需LLM）"""
        facts = []
        beliefs = []
        summaries = []

        # 简单规则：高重要度的转为事实
        for event in events:
            if event.initial_confidence >= 0.9:
                facts.append(MemoryEntry(
                    content=event.content,
                    memory_type=MemoryType.KNOWLEDGE,
                    confidence_level=MemoryConfidence.FACT,
                    tags=["auto_extracted", "fact"]
                ))

        # 生成简单摘要（按天分组）
        from collections import defaultdict
        daily_events = defaultdict(list)
        for e in events:
            day = e.created_at.strftime('%Y-%m-%d')
            daily_events[day].append(e)

        for day, day_events in list(daily_events.items())[-3:]:  # 最近3天
            summary_content = f"{day}有{len(day_events)}条记忆"
            summaries.append(MemoryEntry(
                content=summary_content,
                memory_type=MemoryType.SUMMARY,
                confidence_level=MemoryConfidence.SUMMARY,
                tags=["auto_summary"]
            ))

        return facts, beliefs, summaries

    def _archive_forgotten(self, events: list[MemoryEntry]) -> int:
        """归档应该遗忘的记忆"""
        archived = 0
        for event in events:
            if event.should_forget():
                # 标记为已归档（不删除，保留记录）
                event.tags.append("archived")
                self.ltm.update(event)
                archived += 1
        return archived
