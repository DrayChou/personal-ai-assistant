# -*- coding: utf-8 -*-
"""
工作记忆 (Working Memory)

容量限制 ~2000 tokens，包含最近对话 + 关键事实 + 当前上下文
支持 Token 感知的自动压缩
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .types import WorkingMemorySlot

logger = logging.getLogger('memory.working')


# Token 估算常量
TOKEN_ESTIMATE_RATIO_CN = 0.5  # 中文约 0.5 tokens/char
TOKEN_ESTIMATE_RATIO_EN = 0.25  # 英文约 0.25 tokens/char
SUMMARY_TRIGGER_RATIO = 0.8  # 80% 触发压缩


def estimate_tokens(text: str) -> int:
    """
    估算文本的 Token 数量

    使用启发式方法：
    - 中文约 0.5 tokens/char
    - 英文约 0.25 tokens/char（约 4 chars/token）

    Args:
        text: 输入文本

    Returns:
        估算的 token 数量
    """
    if not text:
        return 0

    char_count = len(text)

    # 计算中文字符数
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    english_chars = char_count - chinese_chars

    # 估算 tokens
    tokens = int(
        chinese_chars * TOKEN_ESTIMATE_RATIO_CN +
        english_chars * TOKEN_ESTIMATE_RATIO_EN
    )

    return max(tokens, 1)


def summarize_messages(messages: list[dict]) -> str:
    """
    对消息进行简单摘要

    Args:
        messages: 消息列表

    Returns:
        摘要文本
    """
    if not messages:
        return ""

    # 提取关键信息
    topics = set()

    for msg in messages:
        content = msg.get('content', '').lower()

        # 简单的关键词提取
        keywords = [
            ("创建", "创建操作"),
            ("搜索", "搜索信息"),
            ("查询", "查询数据"),
            ("计算", "计算"),
            ("分析", "分析"),
            ("天气", "天气查询"),
            ("任务", "任务管理"),
            ("记忆", "记忆操作"),
            ("设置", "设置配置"),
            ("删除", "删除操作"),
        ]

        for keyword, topic in keywords:
            if keyword in content:
                topics.add(topic)

    if topics:
        return f"之前的对话涉及: {', '.join(topics)}"

    return f"之前的对话共 {len(messages)} 条消息"


@dataclass
class WorkingMemoryConfig:
    """工作记忆配置"""
    max_tokens: int = 2000
    max_slots: int = 10             # 最大槽位数
    max_messages: int = 20          # 最大消息数量
    identity_tokens: int = 500      # 身份信息（固定）
    context_tokens: int = 500       # 当前上下文（动态）
    facts_tokens: int = 1000        # 关键事实（动态）
    enable_compression: bool = True # 启用自动压缩


@dataclass
class Message:
    """对话消息"""
    role: str
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp
        }


class WorkingMemory:
    """
    工作记忆管理器

    类比人类的短期记忆，容量有限，快速访问
    支持 Token 感知的自动压缩
    """

    def __init__(self, config: Optional[WorkingMemoryConfig] = None):
        self.config = config or WorkingMemoryConfig()
        self.slots: dict[str, WorkingMemorySlot] = {}
        self.messages: list[Message] = []
        self._summary: str = ""  # 历史对话摘要
        self._init_slots()

    def _init_slots(self):
        """初始化默认槽位"""
        self.slots['identity'] = WorkingMemorySlot(
            name='identity',
            content='',
            max_tokens=self.config.identity_tokens,
            priority=10  # 最高优先级
        )
        self.slots['context'] = WorkingMemorySlot(
            name='context',
            content='',
            max_tokens=self.config.context_tokens,
            priority=5
        )
        self.slots['facts'] = WorkingMemorySlot(
            name='facts',
            content='',
            max_tokens=self.config.facts_tokens,
            priority=3
        )

    def add_message(self, role: str, content: str):
        """
        添加消息到工作记忆

        Args:
            role: 角色 (user/assistant/system)
            content: 消息内容
        """
        self.messages.append(Message(role=role, content=content))
        self._manage_context()

    def _manage_context(self) -> None:
        """
        管理上下文，防止超出 Token 限制

        策略：
        1. 计算当前 Token 总数
        2. 如果超过 80% 阈值，触发压缩
        3. 压缩策略：保留 system 消息 + 最近消息 + 摘要
        """
        if not self.config.enable_compression:
            self._trim_by_count()
            return

        # 计算当前 Token 数
        total_tokens = self._calculate_total_tokens()

        # 检查是否需要压缩
        if total_tokens <= self.config.max_tokens * SUMMARY_TRIGGER_RATIO:
            # 只应用消息数量限制
            if len(self.messages) > self.config.max_messages:
                self._trim_by_count()
            return

        # 需要压缩上下文
        self._compress_context()

    def _calculate_total_tokens(self) -> int:
        """计算消息的总 Token 数"""
        total = 0
        for msg in self.messages:
            total += estimate_tokens(msg.content)
        return total

    def _trim_by_count(self) -> None:
        """按消息数量截断"""
        if len(self.messages) <= self.config.max_messages:
            return

        # 保留 system 消息和最近的消息
        system_msgs = [m for m in self.messages if m.role == "system"]
        other_msgs = [m for m in self.messages if m.role != "system"]

        # 保留最近的非 system 消息
        keep_count = self.config.max_messages - len(system_msgs)
        other_msgs = other_msgs[-keep_count:]

        self.messages = system_msgs + other_msgs

    def _compress_context(self) -> None:
        """
        压缩上下文：对旧消息生成摘要

        保留策略：
        - 所有 system 消息
        - 最近 5 条消息（完整保留）
        - 旧消息生成摘要
        """
        system_msgs = [m for m in self.messages if m.role == "system"]
        other_msgs = [m for m in self.messages if m.role != "system"]

        if len(other_msgs) <= 5:
            # 消息太少，直接截断
            self._trim_by_count()
            return

        # 保留最近 5 条完整消息
        recent_msgs = other_msgs[-5:]
        old_msgs = other_msgs[:-5]

        # 对旧消息生成摘要
        if old_msgs:
            new_summary = summarize_messages([m.to_dict() for m in old_msgs])
            if self._summary:
                self._summary = f"{self._summary}; {new_summary}"
            else:
                self._summary = new_summary

        self.messages = system_msgs + recent_msgs
        logger.debug(f"压缩上下文: 保留 {len(self.messages)} 条消息, 摘要长度 {len(self._summary)}")

    def get_summary(self) -> str:
        """获取历史对话摘要"""
        return self._summary

    def get_messages(self, include_summary: bool = True) -> list[dict]:
        """
        获取消息列表

        Args:
            include_summary: 是否包含历史摘要

        Returns:
            消息字典列表
        """
        messages = [m.to_dict() for m in self.messages]

        # 添加历史摘要
        if include_summary and self._summary:
            summary_msg = {
                "role": "system",
                "content": f"[历史对话摘要] {self._summary}"
            }

            # 插入到第一个 system 消息之后
            system_count = sum(1 for m in messages if m["role"] == "system")
            if system_count > 0:
                last_system_idx = max(
                    i for i, m in enumerate(messages) if m["role"] == "system"
                )
                messages.insert(last_system_idx + 1, summary_msg)
            else:
                messages.insert(0, summary_msg)

        return messages

    def set_identity(self, content: str):
        """设置身份信息（用户偏好、背景等）"""
        self.slots['identity'].content = content
        logger.debug(f"更新身份信息: {len(content)} 字符")

    def set_context(self, content: str):
        """设置当前上下文（最近对话等）"""
        self.slots['context'].content = content
        logger.debug(f"更新上下文: {len(content)} 字符")

    def add_fact(self, fact: str):
        """添加关键事实"""
        current = self.slots['facts'].content
        if current:
            self.slots['facts'].content = current + "\n- " + fact
        else:
            self.slots['facts'].content = "- " + fact
        logger.debug(f"添加事实: {fact[:50]}...")

    def get_full_context(self) -> str:
        """
        获取完整工作记忆上下文

        Returns:
            格式化的上下文字符串
        """
        sections = []

        # Identity（最高优先级，必须保留）
        identity = self.slots['identity'].content
        if identity:
            sections.append(f"【身份/偏好】\n{identity}")

        # 历史摘要
        if self._summary:
            sections.append(f"【历史摘要】\n{self._summary}")

        # Context（当前对话）
        context = self.slots['context'].content
        if context:
            sections.append(f"【当前对话】\n{context}")

        # Facts（关键事实）
        facts = self.slots['facts'].content
        if facts:
            sections.append(f"【关键事实】\n{facts}")

        return "\n\n".join(sections)

    def is_within_limit(self) -> bool:
        """检查是否在工作记忆限制内"""
        total = sum(
            estimate_tokens(slot.content)
            for slot in self.slots.values()
        )
        total += self._calculate_total_tokens()
        return total <= self.config.max_tokens

    def compact(self, llm_client=None):
        """
        智能压缩工作记忆

        策略：
        1. 保留 Identity（不可删除）
        2. Context: 如有LLM则生成摘要，否则保留后半部分
        3. Facts: 按重要性筛选

        Args:
            llm_client: 可选的LLM客户端，用于智能摘要
        """
        for name, slot in self.slots.items():
            if name == 'identity':
                continue  # 身份不裁剪

            tokens = estimate_tokens(slot.content)
            if tokens <= slot.max_tokens:
                continue

            # 智能压缩策略
            if name == 'context' and llm_client:
                # 使用LLM生成对话摘要
                slot.content = self._summarize_with_llm(
                    slot.content, llm_client, slot.max_tokens
                )
                logger.debug(f"LLM智能压缩 {name} 槽位")
            else:
                # 简单策略：保留后半部分（较新的内容）
                ratio = slot.max_tokens / tokens
                keep_chars = int(len(slot.content) * ratio * 0.8)
                slot.content = "..." + slot.content[-keep_chars:]
                logger.debug(f"简单压缩 {name} 槽位")

        # 同时压缩消息
        self._manage_context()

    def _summarize_with_llm(
        self,
        content: str,
        llm_client,
        target_tokens: int
    ) -> str:
        """
        使用LLM生成摘要

        Args:
            content: 原始内容
            llm_client: LLM客户端
            target_tokens: 目标token数

        Returns:
            摘要后的内容
        """
        try:
            max_chars = int(target_tokens * 0.75 * 0.8)  # 目标长度的80%

            prompt = f"""请将以下对话内容总结为简洁的摘要，保留关键信息。

原始内容:
{content}

要求:
1. 字数控制在 {max_chars} 字符以内
2. 保留关键事实、决策和待办事项
3. 去除寒暄和冗余表达
4. 使用简洁的要点形式

摘要:"""

            summary = llm_client.generate(prompt)
            return f"[摘要] {summary.strip()}"

        except Exception as e:
            logger.warning(f"LLM摘要失败: {e}，回退到简单压缩")
            # 回退到简单策略
            ratio = 0.5
            keep_chars = int(len(content) * ratio)
            return "..." + content[-keep_chars:]

    def clear_context(self):
        """清空上下文（会话结束时调用）"""
        self.slots['context'].content = ''
        self.messages = []
        self._summary = ''
        logger.debug("清空工作记忆上下文")

    def clear_all(self):
        """清空所有工作记忆"""
        for slot in self.slots.values():
            slot.content = ''
        self.messages = []
        self._summary = ''
        logger.debug("清空所有工作记忆")

    def write_slot(self, name: str, content: str, priority: float = 1.0):
        """
        写入槽位（通用接口）

        Args:
            name: 槽位名称
            content: 内容
            priority: 优先级 (0-1)，高优先级优先保留
        """
        # 如果槽位已存在，更新内容
        if name in self.slots:
            self.slots[name].content = content
            self.slots[name].priority = int(priority * 10)
            return

        # 如果达到槽位上限，淘汰优先级最低的
        if len(self.slots) >= self.config.max_slots:
            # 找到优先级最低的槽位（排除 identity）
            lowest_slot = min(
                (s for s in self.slots.values() if s.name != 'identity'),
                key=lambda s: s.priority,
                default=None
            )
            if lowest_slot and lowest_slot.priority < priority * 10:
                del self.slots[lowest_slot.name]
                logger.debug(f"淘汰槽位: {lowest_slot.name}")
            else:
                logger.warning(f"槽位已满，无法添加: {name}")
                return

        # 创建新槽位
        self.slots[name] = WorkingMemorySlot(
            name=name,
            content=content,
            max_tokens=500,
            priority=int(priority * 10)
        )
        logger.debug(f"创建槽位: {name}")

    def read_slot(self, name: str) -> Optional[WorkingMemorySlot]:
        """
        读取槽位

        Args:
            name: 槽位名称

        Returns:
            槽位对象，不存在返回 None
        """
        return self.slots.get(name)

    def get_context(self) -> str:
        """获取当前上下文"""
        slot = self.slots.get('context')
        return slot.content if slot else ""

    def get_stats(self) -> dict:
        """
        获取工作记忆统计信息

        Returns:
            统计信息字典
        """
        message_tokens = self._calculate_total_tokens()
        slot_tokens = sum(
            estimate_tokens(slot.content)
            for slot in self.slots.values()
        )

        return {
            "message_count": len(self.messages),
            "message_tokens": message_tokens,
            "slot_count": len(self.slots),
            "slot_tokens": slot_tokens,
            "total_tokens": message_tokens + slot_tokens,
            "max_tokens": self.config.max_tokens,
            "usage_ratio": (message_tokens + slot_tokens) / self.config.max_tokens,
            "has_summary": bool(self._summary),
            "within_limit": self.is_within_limit()
        }
