# -*- coding: utf-8 -*-
"""
SimpleIntentHandler - 极简意图处理

借鉴 nanobot 的设计理念：
- 不做复杂的意图分类
- 让 LLM 自己决定使用什么工具
- 仅保留确认/取消的简单检查

参考: docs/plans/intent-recognition-redesign.md
"""
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger('chat.simple_intent')


class IntentType(Enum):
    """简化版意图类型 - 仅用于内部判断"""
    CHAT = "chat"              # 普通对话
    CONFIRM = "confirm"        # 确认操作
    CANCEL = "cancel"          # 取消操作
    TOOL_NEEDED = "tool_needed"  # 需要工具


@dataclass
class IntentResult:
    """意图识别结果"""
    intent_type: IntentType
    confidence: float = 1.0
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PendingAction:
    """待确认的操作"""
    tool_name: str
    params: dict[str, Any]
    description: str = ""


class SimpleIntentHandler:
    """
    极简意图处理器

    核心理念：
    - 信任 LLM 的判断能力
    - 不预设复杂的意图分类规则
    - 仅处理确认/取消交互

    工作流程：
    1. 检查是否有待确认的操作
    2. 如果有，判断用户回复是确认还是取消
    3. 如果没有，返回 CHAT 意图，让 Agent 自行处理
    """

    # 确认词模式（中英文）
    CONFIRM_PATTERNS = [
        "yes", "是", "确定", "确认", "好的", "执行", "删除",
        "ok", "okay", "sure", "do it", "go ahead", "没问题",
        "可以", "行", "对", "没错", "正确"
    ]

    # 取消词模式（中英文）
    CANCEL_PATTERNS = [
        "no", "否", "取消", "cancel", "算了", "不要", "不行",
        "不", "停止", "abort", "don't", "dont", "暂停"
    ]

    def __init__(
        self,
        llm_client: Optional[Callable] = None
    ):
        """
        初始化

        Args:
            llm_client: LLM 客户端（可选，用于复杂场景）
        """
        self.llm_client = llm_client
        self._pending_action: Optional[PendingAction] = None

    def analyze(self, user_input: str) -> IntentResult:
        """
        分析用户输入

        Args:
            user_input: 用户输入

        Returns:
            意图识别结果
        """
        # 1. 检查是否有待确认的操作
        if self._pending_action:
            return self._check_confirmation(user_input)

        # 2. 默认返回 CHAT，让 Agent 自己处理
        return IntentResult(
            intent_type=IntentType.CHAT,
            confidence=1.0,
            content=user_input
        )

    def _check_confirmation(self, user_input: str) -> IntentResult:
        """检查是否是确认/取消"""
        normalized_input = user_input.lower().strip()

        # 检查确认
        for pattern in self.CONFIRM_PATTERNS:
            if pattern in normalized_input:
                return IntentResult(
                    intent_type=IntentType.CONFIRM,
                    confidence=0.9,
                    content=user_input,
                    metadata={"pending_action": self._pending_action}
                )

        # 检查取消
        for pattern in self.CANCEL_PATTERNS:
            if pattern in normalized_input:
                return IntentResult(
                    intent_type=IntentType.CANCEL,
                    confidence=0.9,
                    content=user_input,
                    metadata={"pending_action": self._pending_action}
                )

        # 其他输入可能是新的问题，清除待确认状态
        logger.info("用户输入不是确认/取消，清除待确认状态")
        self._pending_action = None

        return IntentResult(
            intent_type=IntentType.CHAT,
            confidence=1.0,
            content=user_input
        )

    def set_pending_action(
        self,
        tool_name: str,
        params: dict[str, Any],
        description: str = ""
    ) -> None:
        """
        设置待确认的操作

        Args:
            tool_name: 工具名称
            params: 工具参数
            description: 操作描述（用于显示给用户）
        """
        self._pending_action = PendingAction(
            tool_name=tool_name,
            params=params,
            description=description
        )
        logger.info(f"设置待确认操作: {tool_name}")

    def get_pending_action(self) -> Optional[PendingAction]:
        """获取当前待确认的操作"""
        return self._pending_action

    def clear_pending_action(self) -> None:
        """清除待确认的操作"""
        self._pending_action = None
        logger.info("清除待确认操作")

    def has_pending_action(self) -> bool:
        """是否有待确认的操作"""
        return self._pending_action is not None

    def format_confirmation_prompt(self, action: PendingAction) -> str:
        """
        格式化确认提示

        Args:
            action: 待确认的操作

        Returns:
            格式化的确认提示
        """
        return f"""⚠️ 需要确认

即将执行: {action.description or action.tool_name}

请回复「是」确认执行，或「否」取消操作。"""
