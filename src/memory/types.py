# -*- coding: utf-8 -*-
"""
记忆类型定义
三层记忆架构：工作记忆、结构化长期记忆、原始事件流
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
import uuid


class MemoryConfidence(Enum):
    """
    记忆置信度等级
    衰减公式: current = initial × (1 - decay_rate) ^ days
    """
    FACT = (0.9, 1.0, 0.008, "事实")       # 半衰期87天
    SUMMARY = (0.7, 0.9, 0.025, "摘要")    # 半衰期28天
    BELIEF = (0.3, 0.8, 0.07, "信念")      # 半衰期10天
    EVENT = (0.0, 1.0, 0.15, "事件")       # 半衰期5天
    GOSSIP = (0.1, 0.5, 0.20, "传闻")      # 半衰期3天

    def __init__(self, min_conf: float, max_conf: float, decay_rate: float, label: str):
        self.min_conf = min_conf
        self.max_conf = max_conf
        self.decay_rate = decay_rate
        self.label = label
        self.half_life = int(0.693 / decay_rate) if decay_rate > 0 else float('inf')

    def get_decayed_confidence(self, days: int, initial: float = 1.0) -> float:
        """
        获取衰减后的置信度

        Args:
            days: 经过的天数
            initial: 初始置信度

        Returns:
            衰减后的置信度
        """
        if self.decay_rate == 0:
            return initial
        decay_factor = (1 - self.decay_rate) ** days
        return initial * decay_factor


class MemoryType(Enum):
    """
    记忆类型 - 基于认知心理学分类

    人类记忆三类型映射:
    - 情节记忆 (Episodic): 具体事件和经历
    - 语义记忆 (Semantic): 事实和概念知识
    - 程序记忆 (Procedural): 技能和操作流程
    """
    # 基础类型
    DIALOGUE = "对话"
    OBSERVATION = "观察"
    RELATIONSHIP = "关系"
    KNOWLEDGE = "知识"
    PREFERENCE = "偏好"
    TASK = "任务"
    INSIGHT = "洞察"
    SUMMARY = "摘要"

    # 情节记忆 - Episodic (个人经历)
    EPISODIC = "情节"           # 具体事件 (如: "昨天去了图书馆")
    CONVERSATION = "对话片段"    # 重要对话记录
    EVENT = "事件"              # 重大事件
    EXPERIENCE = "经历"         # 个人体验

    # 语义记忆 - Semantic (事实知识)
    SEMANTIC = "语义"           # 概念知识 (如: "巴黎是法国首都")
    FACT = "事实"               # 客观事实
    CONCEPT = "概念"            # 抽象概念
    SOLUTION = "解决方案"        # 问题解决方法

    # 程序记忆 - Procedural (如何做事)
    PROCEDURAL = "程序"         # 操作流程 (如: "如何骑自行车")
    WORKFLOW = "工作流"          # 工作流程
    PATTERN = "模式"            # 代码/行为模式
    SKILL = "技能"              # 技能记录

    # 情感记忆 - Emotional
    EMOTIONAL = "情感"          # 情绪体验
    ATTITUDE = "态度"           # 对事物的态度
    SENTIMENT = " sentiment"    # 情感倾向

    # 实用分类
    BUGFIX = "Bug修复"          # 问题修复记录
    DECISION = "决策"           # 重要决策
    REFERENCE = "参考"          # 参考资料


@dataclass
class MemoryEntry:
    """记忆条目 - 统一存储格式"""
    content: str
    memory_type: MemoryType = MemoryType.OBSERVATION
    confidence_level: MemoryConfidence = MemoryConfidence.EVENT

    # 标识
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])

    # 时间信息
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)

    # 置信度
    initial_confidence: float = 1.0
    current_confidence: float = 1.0

    # 访问统计
    access_count: int = 0

    # 元数据
    source: Optional[str] = None          # 来源（会话ID等）
    tags: list[str] = field(default_factory=list)
    embedding: Optional[list[float]] = None
    metadata: dict = field(default_factory=dict)

    def calculate_current_confidence(self) -> float:
        """计算当前置信度（含时间衰减）"""
        days_passed = (datetime.now() - self.created_at).days
        decay_factor = (1 - self.confidence_level.decay_rate) ** days_passed
        # 访问频率增强
        freq_boost = min(0.1, self.access_count * 0.01)
        self.current_confidence = min(1.0, self.initial_confidence * decay_factor + freq_boost)
        return self.current_confidence

    def should_forget(self, threshold: float = 0.3) -> bool:
        """是否应该遗忘"""
        return self.calculate_current_confidence() < threshold

    def access(self):
        """访问记忆，更新统计"""
        self.last_accessed = datetime.now()
        self.access_count += 1

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type.value,
            "confidence_level": self.confidence_level.name,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "initial_confidence": self.initial_confidence,
            "current_confidence": self.current_confidence,
            "access_count": self.access_count,
            "source": self.source,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryEntry":
        """从字典反序列化"""
        return cls(
            id=data.get("id", str(uuid.uuid4())[:12]),
            content=data["content"],
            memory_type=MemoryType(data.get("memory_type", "观察")),
            confidence_level=MemoryConfidence[data.get("confidence_level", "EVENT")],
            created_at=datetime.fromisoformat(data.get("created_at", datetime.now().isoformat())),
            last_accessed=datetime.fromisoformat(data.get("last_accessed", datetime.now().isoformat())),
            initial_confidence=data.get("initial_confidence", 1.0),
            current_confidence=data.get("current_confidence", 1.0),
            access_count=data.get("access_count", 0),
            source=data.get("source"),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class WorkingMemorySlot:
    """工作记忆槽位"""
    name: str           # 槽位名称（如 identity, context, facts）
    content: str        # 内容
    max_tokens: int     # 最大Token数
    priority: int = 0   # 优先级（越高越优先保留）
