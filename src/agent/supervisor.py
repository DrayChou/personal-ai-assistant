# -*- coding: utf-8 -*-
"""
Supervisor Agent

基于 Supervisor 模式的智能体实现
支持三层执行模式：Fast Path / Single Step / Multi Step
"""
import asyncio
import inspect
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import AsyncGenerator, Optional, TYPE_CHECKING

from .tools.base import ToolResult
from .tools.registry import ToolRegistry
from .llm_adapter import create_llm_adapter, LLMAdapter

if TYPE_CHECKING:
    from memory import MemorySystem

logger = logging.getLogger('agent.supervisor')


class MetricsCollector:
    """性能指标收集器"""

    def __init__(self):
        self.metrics = {
            'llm_calls': 0,
            'llm_latency': [],
            'tool_calls': {},
            'tool_latency': {},
            'mode_usage': {
                'fast_path': 0,
                'single_step': 0,
                'multi_step': 0
            },
            'errors': []
        }

    def record_llm_call(self, duration: float):
        """记录 LLM 调用"""
        self.metrics['llm_calls'] += 1
        self.metrics['llm_latency'].append(duration)

    def record_tool_call(self, tool_name: str, duration: float, success: bool):
        """记录工具调用"""
        if tool_name not in self.metrics['tool_calls']:
            self.metrics['tool_calls'][tool_name] = {'success': 0, 'failed': 0}
            self.metrics['tool_latency'][tool_name] = []

        self.metrics['tool_calls'][tool_name]['success' if success else 'failed'] += 1
        self.metrics['tool_latency'][tool_name].append(duration)

    def record_mode(self, mode: str):
        """记录执行模式使用"""
        self.metrics['mode_usage'][mode] = self.metrics['mode_usage'].get(mode, 0) + 1

    def record_error(self, error: str):
        """记录错误"""
        self.metrics['errors'].append({'time': time.time(), 'error': error})

    def get_summary(self) -> dict:
        """获取统计摘要"""
        summary = {
            'llm_calls': self.metrics['llm_calls'],
            'llm_avg_latency': sum(self.metrics['llm_latency']) / len(self.metrics['llm_latency']) if self.metrics['llm_latency'] else 0,
            'tool_usage': self.metrics['tool_calls'],
            'mode_distribution': self.metrics['mode_usage'],
            'error_count': len(self.metrics['errors'])
        }

        # 计算各工具平均延迟
        tool_avg_latency = {}
        for tool_name, latencies in self.metrics['tool_latency'].items():
            if latencies:
                tool_avg_latency[tool_name] = sum(latencies) / len(latencies)
        summary['tool_avg_latency'] = tool_avg_latency

        return summary


def timed(metric_name: str = None):
    """性能计时装饰器（支持异步函数和异步生成器）"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            name = metric_name or func.__name__

            # 使用 inspect 更可靠地检测异步生成器
            if inspect.isasyncgenfunction(func):
                # 异步生成器
                async def async_gen_wrapper():
                    try:
                        async for item in func(*args, **kwargs):
                            yield item
                    finally:
                        duration = time.time() - start
                        logger.debug(f"[性能] {name}: {duration:.3f}s")
                return async_gen_wrapper()
            else:
                # 普通异步函数
                async def async_wrapper():
                    try:
                        return await func(*args, **kwargs)
                    finally:
                        duration = time.time() - start
                        logger.debug(f"[性能] {name}: {duration:.3f}s")
                return async_wrapper()
        return wrapper
    return decorator


class ExecutionMode(Enum):
    """执行模式"""
    FAST_PATH = "fast_path"      # Tier 2: 快速路径（Semantic Router）
    SINGLE_STEP = "single_step"  # Tier 3: 单步 Function Calling
    MULTI_STEP = "multi_step"    # Tier 4: 多步 Agent 模式


@dataclass
class Step:
    """执行步骤"""
    id: str
    tool_name: str
    parameters: dict
    status: str = "pending"  # pending, running, completed, failed
    result: Optional[ToolResult] = None
    observation: str = ""


@dataclass
class ExecutionPlan:
    """执行计划"""
    mode: ExecutionMode
    goal: str
    steps: list[Step] = field(default_factory=list)
    current_step: int = 0

    @property
    def is_complete(self) -> bool:
        return self.current_step >= len(self.steps)

    @property
    def current(self) -> Optional[Step]:
        if 0 <= self.current_step < len(self.steps):
            return self.steps[self.current_step]
        return None

    def next(self) -> Optional[Step]:
        """移动到下一步"""
        self.current_step += 1
        return self.current


@dataclass
class AgentContext:
    """Agent 上下文"""
    session_id: str
    user_input: str
    plan: Optional[ExecutionPlan] = None
    history: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class SupervisorAgent:
    """
    Supervisor Agent

    职责：
    1. 意图分析 → 选择执行模式
    2. 任务规划 → 生成执行计划
    3. 编排执行 → 协调工具执行
    4. 结果聚合 → 生成最终回复
    """

    def __init__(
        self,
        llm_client,
        tool_registry: ToolRegistry,
        fast_path_classifier=None,
        memory_system: Optional['MemorySystem'] = None,
        max_steps: int = 10,
        retry_attempts: int = 3,
        retry_delay: float = 1.0,
        enable_memory_context: bool = True,
        context_memory_limit: int = 5
    ):
        self.llm: LLMAdapter = create_llm_adapter(llm_client)
        self.tools = tool_registry
        self.fast_path = fast_path_classifier
        self.memory = memory_system
        self.max_steps = max_steps
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.enable_memory_context = enable_memory_context
        self.context_memory_limit = context_memory_limit
        self.schemas = tool_registry.get_schemas()
        self._current_context: Optional[AgentContext] = None
        self.metrics = MetricsCollector()
        self.enable_streaming = True  # 默认启用流式输出

        # 确认状态跟踪
        self._pending_confirmation: Optional[dict] = None  # 等待确认的工具调用

    def _is_confirmation(self, user_input: str) -> bool:
        """检查用户输入是否是确认"""
        confirmation_keywords = ['确认', 'yes', '是', '确定', '好的', '执行', '删除', '清理']
        return user_input.lower().strip() in confirmation_keywords

    def _is_cancel(self, user_input: str) -> bool:
        """检查用户输入是否是取消"""
        cancel_keywords = ['取消', 'cancel', 'no', '否', '不', '算了', '不要']
        return user_input.lower().strip() in cancel_keywords

    async def _execute_confirmation(self, user_input: str) -> AsyncGenerator[str, None]:
        """执行确认的操作"""
        if not self._pending_confirmation:
            yield "没有待确认的操作\n"
            return

        pending = self._pending_confirmation

        # 检查是否是取消
        if self._is_cancel(user_input):
            self._pending_confirmation = None
            yield "已取消操作\n"
            return

        # 执行确认
        tool_name = pending['tool_name']
        params = pending['params'].copy()
        params['confirmed'] = True

        # 对于删除操作，如果没有指定 task_ids，默认删除所有
        if tool_name == "delete_tasks":
            if not params.get('task_ids') and not params.get('delete_all'):
                params['delete_all'] = True

        yield "🤔 "
        result = await self.tools.execute(tool_name, timeout=30.0, **params)

        # 清除确认状态
        self._pending_confirmation = None

        if result.success:
            yield result.observation + "\n"
        else:
            yield f"操作失败: {result.observation}\n"

    async def _generate_response_stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> AsyncGenerator[str, None]:
        """
        流式生成回复

        Args:
            messages: 消息列表
            temperature: 温度
            max_tokens: 最大token数

        Yields:
            文本片段
        """
        try:
            async for chunk in self.llm.stream_generate(messages, temperature, max_tokens):
                yield chunk
        except Exception as e:
            logger.warning(f"流式生成失败: {e}")
            # 降级到批量生成
            response = await self.llm.generate(messages, temperature, max_tokens)
            yield response

    async def handle(
        self,
        user_input: str,
        session_id: str,
        context: Optional[dict] = None
    ) -> AsyncGenerator[str | dict, None]:
        """
        处理用户输入

        Args:
            user_input: 用户输入
            session_id: 会话ID
            context: 额外上下文

        Yields:
            str: 流式输出文本
            dict: 需要用户输入 {"type": "need_input", "prompt": str}
        """
        # 检查是否有待处理的确认
        if self._pending_confirmation and self._is_confirmation(user_input):
            # 执行确认的操作
            async for output in self._execute_confirmation(user_input):
                yield output
            return

        agent_context = AgentContext(
            session_id=session_id,
            user_input=user_input,
            metadata=context or {}
        )
        self._current_context = agent_context

        # Step 1: 意图分析
        mode = await self._analyze_intent(user_input)
        logger.debug(f"执行模式: {mode.value}")

        # Step 2: 规划
        yield "🤔 "
        agent_context.plan = await self._plan(user_input, mode)

        if mode == ExecutionMode.MULTI_STEP:
            yield f"计划 {len(agent_context.plan.steps)} 步\n"

        # Step 3: 执行
        if mode == ExecutionMode.FAST_PATH and self.fast_path:
            async for output in self._execute_fast_path(agent_context):
                yield output
        elif mode == ExecutionMode.SINGLE_STEP:
            async for output in self._execute_single_step(agent_context):
                yield output
        elif mode == ExecutionMode.MULTI_STEP:
            async for output in self._execute_multi_step(agent_context):
                yield output

    def _build_context_messages(self, user_input: str) -> list[dict]:
        """
        构建带记忆上下文的 messages

        如果启用了 memory_context，会搜索相关记忆并注入系统提示
        """
        from datetime import datetime
        messages = []

        # 基础系统提示词（参考 OpenClaw 架构）
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        base_system = f"""你是用户的个人 AI 助手，性格友好、高效、可靠。

【当前时间】{current_time}

【核心职责】
1. 准确理解用户意图，选择正确的工具执行任务
2. 当用户说"清理"、"删除"、"移除"时，应该执行删除操作，而不是只查看
3. 当用户说"查看"、"显示"、"有什么"时，才执行查看操作

【工具选择指南】
- 用户说"清理任务/删除任务" → delete_tasks（执行删除）
- 用户说"查看任务/有什么任务" → list_tasks（仅查看）
- 用户说"完成任务" → complete_task
- 用户说"创建任务/提醒我" → create_task"""

        # 如果启用记忆上下文且有记忆系统
        memory_context = ""
        if self.enable_memory_context and self.memory:
            try:
                # 使用 recall 方法检索相关记忆
                raw_memory = self.memory.recall(
                    query=user_input,
                    top_k=min(self.context_memory_limit, 3)  # 限制记忆数量
                )
                # 限制记忆内容长度（最多 1500 字符）
                if raw_memory and raw_memory.strip():
                    memory_context = raw_memory[:1500]
                    if len(raw_memory) > 1500:
                        memory_context += "\n...（记忆内容已截断）"
                    logger.debug(f"已注入相关记忆上下文 ({len(memory_context)} 字符)")
            except Exception as e:
                logger.warning(f"检索记忆失败: {e}")

        # 组合系统提示词
        if memory_context:
            system_prompt = f"""{base_system}

【相关记忆】
{memory_context}"""
        else:
            system_prompt = base_system

        messages.append({"role": "system", "content": system_prompt})

        # 添加用户输入
        messages.append({"role": "user", "content": user_input})
        return messages

    @timed("analyze_intent")
    async def _analyze_intent(self, user_input: str) -> ExecutionMode:
        """
        分析意图，决定执行模式

        启发式判断，避免不必要的 LLM 调用
        """
        user_input_lower = user_input.lower()

        # 简单问候 → Fast Path
        simple_patterns = ["你好", "嗨", "hello", "hi", "谢谢", "再见", "拜拜"]
        if any(p in user_input_lower for p in simple_patterns):
            if len(user_input) < 20:  # 短消息才走 fast path
                return ExecutionMode.FAST_PATH

        # 复杂多步指示 → Multi Step（需要规划和多工具协作）
        complex_multi_indicators = [
            "然后", "先...再", "帮我...然后", "整理并", "总结所有", "分析并"
        ]
        if any(i in user_input for i in complex_multi_indicators):
            return ExecutionMode.MULTI_STEP

        # 任务清理/删除 → Single Step（直接 Function Calling，工具会处理确认流程）
        # 注意：不再走 Multi Step，让 LLM 直接选择 delete_tasks 工具
        delete_keywords = ["清理任务", "删除任务", "清空任务", "移除任务", "删除这些", "清理这些"]
        if any(kw in user_input for kw in delete_keywords):
            return ExecutionMode.SINGLE_STEP

        # 查看/查询 → Single Step
        view_keywords = ["有什么任务", "查看任务", "待办", "显示任务", "列出"]
        if any(kw in user_input for kw in view_keywords):
            return ExecutionMode.SINGLE_STEP

        # 默认 → Single Step (Function Calling)
        return ExecutionMode.SINGLE_STEP

    async def _plan(self, user_input: str, mode: ExecutionMode) -> ExecutionPlan:
        """生成执行计划"""

        if mode == ExecutionMode.FAST_PATH:
            # Fast path 不需要详细规划
            return ExecutionPlan(
                mode=mode,
                goal=user_input,
                steps=[]
            )

        elif mode == ExecutionMode.SINGLE_STEP:
            # 使用 Function Calling 选择工具（带重试）
            return await self._plan_single_step_with_retry(user_input)

        elif mode == ExecutionMode.MULTI_STEP:
            # 使用 LLM 进行多步规划（带重试）
            return await self._plan_multi_step_with_retry(user_input)

        return ExecutionPlan(mode=mode, goal=user_input, steps=[])

    async def _plan_single_step_with_retry(self, user_input: str) -> ExecutionPlan:
        """单步规划（带重试机制）"""
        for attempt in range(self.retry_attempts):
            try:
                return await self._plan_single_step(user_input)
            except Exception as e:
                logger.warning(f"单步规划尝试 {attempt + 1} 失败: {e}")
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                else:
                    logger.error(f"单步规划最终失败: {e}")

        # Fallback: 直接对话
        return ExecutionPlan(
            mode=ExecutionMode.SINGLE_STEP,
            goal=user_input,
            steps=[Step(
                id="step_0",
                tool_name="chat",
                parameters={"message": user_input}
            )]
        )

    @timed("plan_single_step")
    async def _plan_single_step(self, user_input: str) -> ExecutionPlan:
        """单步规划核心逻辑"""
        start_time = time.time()
        messages = self._build_context_messages(user_input)

        # 增强系统提示，强调工具选择规则
        enhanced_system = messages[0].get("content", "") if messages else ""

        # 添加强制性工具选择规则（关键！）
        tool_selection_rules = """

【强制性工具选择规则】
你必须根据用户输入的关键词选择正确的工具：
1. 关键词包含"清理"、"删除"、"移除"、"清空" → 必须使用 delete_tasks
2. 关键词包含"查看"、"显示"、"有什么"、"列出" → 使用 list_tasks
3. 关键词包含"完成"、"做完了" → 使用 complete_task
4. 关键词包含"创建"、"添加"、"提醒我" → 使用 create_task

【Few-shot 示例】
输入: "帮我清理这些任务" → 工具: delete_tasks
输入: "删除无效的任务" → 工具: delete_tasks
输入: "我有什么任务" → 工具: list_tasks
输入: "查看待办列表" → 工具: list_tasks
输入: "完成任务 xxx" → 工具: complete_task
输入: "提醒我明天开会" → 工具: create_task"""

        # 更新系统提示
        for msg in messages:
            if msg.get("role") == "system":
                msg["content"] = enhanced_system + tool_selection_rules
                break

        response = await self.llm.generate_with_tools(
            messages=messages,
            tools=self.schemas,
            tool_choice="auto"
        )

        # 记录性能指标
        self.metrics.record_llm_call(time.time() - start_time)
        self.metrics.record_mode("single_step")

        if response.tool_calls:
            tool_call = response.tool_calls[0]
            return ExecutionPlan(
                mode=ExecutionMode.SINGLE_STEP,
                goal=user_input,
                steps=[Step(
                    id="step_0",
                    tool_name=tool_call.name,
                    parameters=tool_call.arguments
                )]
            )
        else:
            # LLM 认为不需要工具，使用 chat 工具
            return ExecutionPlan(
                mode=ExecutionMode.SINGLE_STEP,
                goal=user_input,
                steps=[Step(
                    id="step_0",
                    tool_name="chat",
                    parameters={"message": user_input}
                )]
            )

    async def _plan_multi_step_with_retry(self, user_input: str) -> ExecutionPlan:
        """多步规划（带重试机制）"""
        for attempt in range(self.retry_attempts):
            try:
                return await self._plan_multi_step(user_input)
            except Exception as e:
                logger.warning(f"多步规划尝试 {attempt + 1} 失败: {e}")
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                else:
                    logger.error(f"多步规划最终失败: {e}")

        # Fallback 到单步
        return await self._plan_single_step_with_retry(user_input)

    @timed("plan_multi_step")
    async def _plan_multi_step(self, user_input: str) -> ExecutionPlan:
        """多步规划核心逻辑"""
        start_time = time.time()
        from datetime import datetime
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 构建带记忆上下文的规划提示
        memory_context = ""
        if self.enable_memory_context and self.memory:
            try:
                relevant_memories = self.memory.recall(
                    query=user_input,
                    top_k=self.context_memory_limit
                )
                if relevant_memories and relevant_memories.strip():
                    memory_context = f"\n【相关记忆】\n{relevant_memories}"
            except Exception as e:
                logger.warning(f"检索记忆失败: {e}")

        # 使用增强的规划提示词（参考 OpenClaw 架构）
        prompt = f"""【当前时间】{current_time}

【任务分析】
分析用户需求，选择正确的工具执行任务。

【用户输入】
{user_input}{memory_context}

【可用工具】
{self._format_tools()}

【工具选择规则】（非常重要！）
1. "清理任务"、"删除任务"、"清空列表" → 必须使用 delete_tasks
2. "查看任务"、"有什么任务"、"显示列表" → 使用 list_tasks
3. "完成任务"、"做完了" → 使用 complete_task
4. "创建任务"、"提醒我" → 使用 create_task

【正确示例】
示例1:
输入: "帮我清理这些任务"
输出: {{"goal": "清理用户的任务列表", "steps": [{{"tool": "delete_tasks", "params": {{"delete_all": true, "confirmed": false}}, "reason": "用户说清理任务，需要执行删除操作"}}]}}

示例2:
输入: "删除无效的任务"
输出: {{"goal": "删除无效任务", "steps": [{{"tool": "delete_tasks", "params": {{"confirmed": false}}, "reason": "用户要删除任务，使用 delete_tasks"}}]}}

示例3:
输入: "我有什么待办事项"
输出: {{"goal": "查看任务列表", "steps": [{{"tool": "list_tasks", "params": {{}}, "reason": "用户只是想查看，不是删除"}}]}}

【错误示例】❌
输入: "帮我清理这些任务"
错误输出: {{"goal": "查看任务", "steps": [{{"tool": "list_tasks", ...}}]}}  // 错误！用户说"清理"应该用 delete_tasks

现在请分析用户输入并生成执行计划，返回 JSON 格式：
{{
    "goal": "任务目标",
    "steps": [
        {{"tool": "工具名", "params": {{"参数名": "值"}}, "reason": "选择此工具的理由"}}
    ]
}}"""

        response = await self.llm.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1  # 使用低温度确保稳定的工具选择和 JSON 输出
        )

        # 记录性能指标
        self.metrics.record_llm_call(time.time() - start_time)
        self.metrics.record_mode("multi_step")

        # 检查空响应
        if not response or not response.strip():
            raise ValueError("LLM 返回空响应")

        # 尝试解析 JSON，失败时尝试提取 JSON 片段
        try:
            plan_data = json.loads(response.strip())
        except json.JSONDecodeError as e:
            # 尝试从响应中提取 JSON 对象
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                try:
                    plan_data = json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    raise ValueError(f"无法解析 JSON 响应: {response[:200]}") from e
            else:
                raise ValueError(f"响应中未找到 JSON: {response[:200]}") from e

        return ExecutionPlan(
            mode=ExecutionMode.MULTI_STEP,
            goal=plan_data.get("goal", user_input),
            steps=[
                Step(
                    id=f"step_{i}",
                    tool_name=s["tool"],
                    parameters=s.get("params", {})
                )
                for i, s in enumerate(plan_data.get("steps", []))
            ]
        )

    # Intent 到工具名的映射表
    INTENT_TO_TOOL_MAP = {
        'chat': 'chat',
        'thanks': 'chat',
        'goodbye': 'chat',
        'help': 'chat',
        'create_task': 'create_task',
        'query_task': 'list_tasks',
        'update_task': 'complete_task',
        'delete_task': 'delete_tasks',
        'set_reminder': 'create_task',
        'create_memory': 'add_memory',
        'query_memory': 'search_memory',
        'summarize': 'summarize_memories',
        'search': 'web_search',
        'clear_history': 'clear_history',
        'switch_personality': 'switch_personality',
    }

    @timed("execute_fast_path")
    async def _execute_fast_path(self, context: AgentContext) -> AsyncGenerator[str, None]:
        """执行 Fast Path"""
        self.metrics.record_mode("fast_path")

        if not self.fast_path:
            yield "快速路径未配置\n"
            return

        start_time = time.time()
        try:
            intent = self.fast_path.classify(context.user_input)
            intent_value = intent.type.value if hasattr(intent.type, 'value') else str(intent.type)

            # 使用映射表获取工具名
            tool_name = self.INTENT_TO_TOOL_MAP.get(intent_value, 'chat')

            # 检查工具是否存在
            if not self.tools.has(tool_name):
                logger.warning(f"Fast path: 工具 {tool_name} 不存在，降级到 chat")
                tool_name = 'chat'

            # 根据工具类型传递正确参数
            if tool_name == "chat":
                result = await self.tools.execute(tool_name, timeout=10.0, message=context.user_input)
            else:
                result = await self.tools.execute(tool_name, timeout=30.0, **{})

            # 记录性能指标
            self.metrics.record_tool_call(tool_name, time.time() - start_time, result.success)

            # 对于 chat 工具，使用流式生成回复
            if tool_name == "chat" and self.enable_streaming:
                async for chunk in self._generate_chat_response_stream(context):
                    yield chunk
                yield "\n"
            else:
                yield result.observation + "\n"

        except Exception as e:
            logger.warning(f"Fast path 失败: {e}")
            self.metrics.record_error(f"fast_path: {str(e)}")
            # Fallback
            async for output in self._execute_single_step(context):
                yield output

    @timed("execute_single_step")
    async def _execute_single_step(self, context: AgentContext) -> AsyncGenerator[str, None]:
        """执行单步（支持流式输出 + 执行反思）"""
        step = context.plan.steps[0] if context.plan.steps else None
        if not step:
            yield "没有可执行的步骤\n"
            return

        step.status = "running"
        start_time = time.time()

        result = await self.tools.execute(step.tool_name, timeout=30.0, **step.parameters)

        # 记录性能指标
        self.metrics.record_tool_call(step.tool_name, time.time() - start_time, result.success)

        step.result = result
        step.status = "completed" if result.success else "failed"

        if result.success:
            # 执行反思：验证结果是否符合用户意图
            retry_tool = await self._reflect_on_result(context.user_input, step.tool_name, result)
            if retry_tool:
                logger.info(f"反思检测到需要重试，原工具: {step.tool_name} -> 新工具: {retry_tool}")
                # 直接切换到正确工具，不再依赖LLM重新规划
                yield f"⚠️ 重新调整策略，使用 {retry_tool}...\n"
                new_result = await self.tools.execute(retry_tool, timeout=30.0)
                self.metrics.record_tool_call(retry_tool, time.time() - start_time, new_result.success)
                if new_result.success:
                    result = new_result
                    step.tool_name = retry_tool
                    step.result = new_result

            # 检查是否需要确认
            if result.data and result.data.get("needs_confirmation"):
                # 保存确认状态
                self._pending_confirmation = {
                    "tool_name": step.tool_name,
                    "params": step.parameters.copy()
                }
                yield result.observation + "\n"
            else:
                # 对于 chat 工具，使用流式生成回复
                if step.tool_name == "chat" and self.enable_streaming:
                    async for chunk in self._generate_chat_response_stream(context):
                        yield chunk
                    yield "\n"
                else:
                    yield result.observation + "\n"
        else:
            yield f"操作失败: {result.observation}\n"

    async def _reflect_on_result(self, user_input: str, tool_name: str, result: ToolResult) -> str | None:
        """
        执行反思：验证结果是否符合用户意图

        Returns:
            应该使用的工具名，或 None 表示不需要重试
        """
        user_input_lower = user_input.lower()

        # 反思规则：用户说"清理/删除"但使用了 list_tasks
        if tool_name == "list_tasks":
            delete_keywords = ["清理", "删除", "移除", "清空", "不要", "去掉", "删掉"]
            if any(kw in user_input_lower for kw in delete_keywords):
                logger.warning(f"反思: 用户说'{user_input}'但使用了 list_tasks，应使用 delete_tasks")
                return "delete_tasks"

        # 反思规则：用户说"查看/显示"但使用了 delete_tasks
        if tool_name == "delete_tasks":
            view_keywords = ["查看", "显示", "有什么", "列出", "看看"]
            if any(kw in user_input_lower for kw in view_keywords):
                # 但如果有"清理"关键词，则删除是正确的
                if not any(kw in user_input_lower for kw in ["清理", "删除", "移除"]):
                    logger.warning(f"反思: 用户说'{user_input}'但使用了 delete_tasks，应使用 list_tasks")
                    return "list_tasks"

        return None

    async def _generate_chat_response_stream(self, context: AgentContext) -> AsyncGenerator[str, None]:
        """流式生成聊天回复"""
        messages = self._build_context_messages(context.user_input)

        # 流式生成回复
        async for chunk in self._generate_response_stream(messages, temperature=0.7, max_tokens=800):
            yield chunk

    @timed("execute_multi_step")
    async def _execute_multi_step(self, context: AgentContext) -> AsyncGenerator[str, None]:
        """执行多步"""
        plan = context.plan
        step_count = 0

        while not plan.is_complete and step_count < self.max_steps:
            step = plan.current
            if not step:
                break

            step.status = "running"
            yield f"  [{plan.current_step + 1}/{len(plan.steps)}] {step.tool_name}... "

            start_time = time.time()
            result = await self.tools.execute(step.tool_name, timeout=30.0, **step.parameters)

            # 记录性能指标
            self.metrics.record_tool_call(step.tool_name, time.time() - start_time, result.success)

            step.result = result

            # 检查是否需要确认
            if result.data.get("needs_confirmation"):
                step.status = "needs_clarification"
                yield f"\n💭 {result.observation}\n"
                yield {
                    "type": "need_input",
                    "prompt": "确认执行吗？(yes/no/show)",
                    "context": {"step_id": step.id, "data": result.data}
                }
                return

            if result.success:
                step.status = "completed"
                yield "✓\n"
                if result.observation:
                    yield f"    {result.observation}\n"
            else:
                step.status = "failed"
                yield "✗\n"
                yield f"    错误: {result.observation}\n"
                self.metrics.record_error(f"{step.tool_name}: {result.observation}")

            plan.next()
            step_count += 1

    def _format_tools(self) -> str:
        """格式化工具列表"""
        lines = []
        for name in self.tools.get_names():
            tool = self.tools.get(name)
            if tool:
                lines.append(f"- {name}: {tool.description}")
        return "\n".join(lines)

    def get_metrics(self) -> dict:
        """获取性能指标摘要"""
        return self.metrics.get_summary()

    def reset_metrics(self):
        """重置性能指标"""
        self.metrics = MetricsCollector()

    async def continue_with_input(
        self,
        user_input: str,
        context: AgentContext
    ) -> AsyncGenerator[str, None]:
        """
        继续执行（用户输入确认后）

        Args:
            user_input: 用户输入（如 "yes"）
            context: 当前上下文
        """
        plan = context.plan
        step = plan.current if plan else None

        if not step:
            yield "没有待执行的步骤\n"
            return

        if user_input.lower() in ["yes", "y", "确认", "是"]:
            # 继续执行
            step.parameters["confirmed"] = True
            result = await self.tools.execute(step.tool_name, timeout=30.0, **step.parameters)

            if result.success:
                yield f"✅ {result.observation}\n"
                plan.next()

                # 继续后续步骤
                if not plan.is_complete:
                    async for output in self._execute_multi_step(context):
                        yield output
            else:
                yield f"❌ {result.observation}\n"

        elif user_input.lower() in ["no", "n", "取消", "否"]:
            yield "已取消操作\n"
            step.status = "cancelled"
            plan.next()

        else:
            yield "请输入 yes 确认或 no 取消\n"
