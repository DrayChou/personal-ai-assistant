# -*- coding: utf-8 -*-
"""
SimpleAgent - 简化版 Agent

借鉴 nanobot 的设计理念：
- 信任 LLM 的工具选择能力
- 简单的 Agent Loop：LLM 决策 → 执行 → 回复
- 内置确认机制

参考: docs/plans/optimization-proposal-v2.md
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Optional

from .tools.base import ToolResult
from .tools.registry import ToolRegistry
from .llm_adapter import LLMAdapter, LLMResponse

logger = logging.getLogger('agent.simple')


@dataclass
class AgentContext:
    """Agent 上下文"""
    session_id: str
    user_input: str
    history: list[dict] = field(default_factory=list)
    memory_context: str = ""
    personality: str = ""


@dataclass
class PendingAction:
    """待确认的操作"""
    tool_name: str
    params: dict[str, Any]
    description: str


class SimpleAgent:
    """
    简化版 Agent

    核心理念：
    - 信任 LLM 的工具选择能力
    - 不预设执行模式（Fast/Single/Multi）
    - 让 LLM 自己决定调用什么工具、调用多少次

    工作流程：
    1. 构建系统提示（包含所有工具描述）
    2. 调用 LLM，传入工具定义
    3. 如果 LLM 想要调用工具 → 执行 → 继续循环
    4. 如果 LLM 直接回复 → 结束
    """

    # 需要确认的工具
    CONFIRMATION_TOOLS = {"delete_tasks", "clear_all_tasks"}

    def __init__(
        self,
        llm_adapter: LLMAdapter,
        tool_registry: ToolRegistry,
        memory_system: Optional[Any] = None,
        personality_manager: Optional[Any] = None,
        max_iterations: int = 10
    ):
        self.llm = llm_adapter
        self.tools = tool_registry
        self.memory = memory_system
        self.personality = personality_manager
        self.max_iterations = max_iterations

        # 待确认的操作
        self._pending_action: Optional[PendingAction] = None

        # 统计
        self.stats = {
            "total_requests": 0,
            "tool_calls": 0,
            "llm_calls": 0,
        }

    async def handle(
        self,
        user_input: str,
        session_id: str = "default",
        history: Optional[list[dict]] = None
    ) -> AsyncGenerator[str, None]:
        """
        处理用户输入

        Args:
            user_input: 用户输入
            session_id: 会话 ID
            history: 对话历史

        Yields:
            响应片段（流式输出）
        """
        self.stats["total_requests"] += 1

        # 1. 检查是否有待确认的操作
        if self._pending_action:
            async for chunk in self._handle_confirmation(user_input):
                yield chunk
            return

        # 2. 构建上下文
        context = await self._build_context(user_input, session_id, history or [])

        # 3. Agent Loop
        messages = self._build_messages(context)

        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1
            self.stats["llm_calls"] += 1

            # 调用 LLM
            response = await self._call_llm(messages)

            if response.has_tool_calls:
                # 执行工具调用
                for tool_call in response.tool_calls:
                    # 检查是否需要确认
                    if tool_call.name in self.CONFIRMATION_TOOLS:
                        self._pending_action = PendingAction(
                            tool_name=tool_call.name,
                            params=tool_call.arguments,
                            description=f"执行 {tool_call.name}"
                        )
                        yield self._format_confirmation_prompt()
                        return

                    # 执行工具
                    result = await self._execute_tool(tool_call.name, tool_call.arguments)

                    # 将结果添加到消息历史
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result.content if hasattr(result, 'content') else str(result)
                    })
                    self.stats["tool_calls"] += 1
            else:
                # LLM 直接回复，结束循环
                if response.content:
                    yield response.content
                return

        # 达到最大迭代次数
        yield "抱歉，我无法完成这个请求，请尝试换一种方式表达。"

    async def _handle_confirmation(self, user_input: str) -> AsyncGenerator[str, None]:
        """处理确认/取消"""
        normalized = user_input.lower().strip()

        # 检查确认
        if any(word in normalized for word in ["是", "确认", "确定", "yes", "ok", "好的"]):
            action = self._pending_action
            self._pending_action = None

            result = await self._execute_tool(action.tool_name, action.params)
            self.stats["tool_calls"] += 1

            if result.success:
                yield f"✅ 已执行: {action.description}"
            else:
                yield f"❌ 执行失败: {result.content if hasattr(result, 'content') else str(result)}"
            return

        # 检查取消
        if any(word in normalized for word in ["否", "取消", "no", "cancel", "算了"]):
            self._pending_action = None
            yield "已取消操作。"
            return

        # 其他输入，清除待确认状态
        self._pending_action = None
        yield "操作已取消。"

    async def _build_context(
        self,
        user_input: str,
        session_id: str,
        history: list[dict]
    ) -> AgentContext:
        """构建上下文"""
        context = AgentContext(
            session_id=session_id,
            user_input=user_input,
            history=history[-10:]  # 保留最近 10 轮对话
        )

        # 添加记忆上下文
        if self.memory:
            try:
                context.memory_context = self.memory.recall(user_input, top_k=3)
            except Exception as e:
                logger.warning(f"记忆检索失败: {e}")

        # 添加人格
        if self.personality:
            try:
                personality = self.personality.get_current()
                if personality:
                    context.personality = f"你是{personality.name}，{personality.description}"
            except Exception as e:
                logger.warning(f"获取人格失败: {e}")

        return context

    def _build_messages(self, context: AgentContext) -> list[dict]:
        """构建消息列表"""
        messages = []

        # 系统提示
        system_prompt = self._build_system_prompt(context)
        messages.append({"role": "system", "content": system_prompt})

        # 历史对话
        messages.extend(context.history)

        # 当前输入
        messages.append({"role": "user", "content": context.user_input})

        return messages

    def _build_system_prompt(self, context: AgentContext) -> str:
        """构建系统提示"""
        parts = []

        # 人格
        if context.personality:
            parts.append(context.personality)
        else:
            parts.append("你是一个友好的个人 AI 助手。")

        # 工具描述
        parts.append("\n## 可用工具\n")
        parts.append(self._get_tools_description())

        # 记忆上下文
        if context.memory_context:
            parts.append(f"\n## 相关记忆\n{context.memory_context}")

        # 规则
        parts.append("""
## 重要规则

1. **自然对话优先**
   - 如果用户只是闲聊，直接回复，不要调用工具
   - 如果不确定用户意图，可以询问澄清

2. **工具使用**
   - 根据用户需求选择合适的工具
   - 如果需要多个工具，可以连续调用

3. **确认机制**
   - 删除操作会自动要求确认
   - 等待用户明确回复后再执行
""")

        return "\n".join(parts)

    def _get_tools_description(self) -> str:
        """获取工具描述"""
        descriptions = []
        for tool in self.tools.get_all_tools():
            desc = f"- `{tool.name}`: {tool.description}"
            if hasattr(tool, 'parameters') and tool.parameters:
                params = ", ".join(tool.parameters.get('properties', {}).keys())
                if params:
                    desc += f"\n  参数: {params}"
            descriptions.append(desc)
        return "\n".join(descriptions)

    async def _call_llm(self, messages: list[dict]) -> LLMResponse:
        """调用 LLM"""
        tools = self.tools.get_tool_definitions()
        return await self.llm.chat(messages=messages, tools=tools)

    async def _execute_tool(self, name: str, params: dict) -> ToolResult:
        """执行工具"""
        start_time = time.time()
        try:
            result = await self.tools.execute(name, params)
            duration = time.time() - start_time
            logger.info(f"工具执行完成: {name}, 耗时: {duration:.2f}s")
            return result
        except Exception as e:
            logger.error(f"工具执行失败: {name}, 错误: {e}")
            return ToolResult(success=False, content=f"执行失败: {str(e)}")

    def _format_confirmation_prompt(self) -> str:
        """格式化确认提示"""
        if self._pending_action:
            return f"""⚠️ 需要确认

即将执行: {self._pending_action.description}

请回复「是」确认执行，或「否」取消操作。"""
        return ""

    def has_pending_action(self) -> bool:
        """是否有待确认的操作"""
        return self._pending_action is not None

    def get_stats(self) -> dict:
        """获取统计信息"""
        return self.stats.copy()
