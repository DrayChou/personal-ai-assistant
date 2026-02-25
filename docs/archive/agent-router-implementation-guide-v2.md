# Agent Router 实现方案 v2.0

> 基于《意图识别架构演进报告》和《Agent Router架构设计与识别指南》的务实实施方案

---

## 核心洞察

### 文档关键结论

1. **演进路径**: Tier 2 → Tier 3 → Tier 4（不要跳过 Tier 3）
2. **推荐模式**: 个人助手适合 **Supervisor + Chain-of-Agents 混合**
3. **路由策略**: 渐进式，从 Description-Based 开始，按需引入 LLM Planning
4. **避免陷阱**: 不要过度设计，简单任务用快速路径

### 当前系统诊断

```
你的系统现状：
├── SemanticIntentRouter (Tier 2) ✓ 保留作为快速路径
├── ActionRouter (单步执行) ✗ 需要改造
├── ToolExecutor (MCP) ✓ 保留并扩展
└── 缺失: Planner、Reflection、多步执行

目标架构：
├── Fast Path (Tier 2): 简单任务直接路由
├── Function Calling (Tier 3): 单步工具调用
└── Agent Mode (Tier 4): 复杂任务多步规划
```

---

## 架构设计：Supervisor + Function Calling 混合

### 为什么选 Supervisor 模式？

| 模式 | 适合场景 | 你的系统匹配度 |
|------|----------|----------------|
| **Supervisor** | 任务有明确阶段，需要中央控制 | ✅ 高度匹配 |
| Mesh | Agent 间频繁协作 | ❌ 不需要 |
| Hierarchical | 大规模分布式 | ❌ 过度设计 |
| Chain-of-Agents | 固定流程 | ⚠️ 部分匹配 |

### 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                    Personal AI Assistant                         │
│                     (Supervisor 模式)                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  用户输入 ──→ ┌─────────────────────────────────────────┐      │
│               │      Supervisor Agent (中央协调器)       │      │
│               │                                         │      │
│               │  1. Intent Analysis (意图分析)          │      │
│               │     ├── 简单意图? → Fast Path           │      │
│               │     └── 复杂意图? → Plan & Execute      │      │
│               │                                         │      │
│               │  2. Planning (规划) - 仅复杂任务         │      │
│               │     └── 生成执行计划 (Step序列)          │      │
│               │                                         │      │
│               │  3. Orchestration (编排执行)            │      │
│               │     └── 循环: 执行 → 观察 → 反思        │      │
│               │                                         │      │
│               │  4. Response Generation (生成回复)      │      │
│               └──────────────────┬──────────────────────┘      │
│                                  │                              │
│         ┌────────────────────────┼────────────────────────┐    │
│         ▼                        ▼                        ▼    │
│   ┌────────────┐          ┌────────────┐          ┌──────────┐│
│   │ Memory     │          │ Task       │          │ Search   ││
│   │ Agent      │          │ Agent      │          │ Agent    ││
│   │ (记忆操作)  │          │ (任务管理)  │          │ (搜索)   ││
│   └────────────┘          └────────────┘          └──────────┘│
│                                                                  │
│   其他 Agents: ChatAgent, SchedulerAgent, PersonalityAgent...   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 三阶段实施路线图

### Phase 1: Function Calling 基础（Week 1）

**目标**: 建立 Tier 3 基础，统一工具接口

```python
# src/agent/tools/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Literal

@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    data: Any
    observation: str  # 给 Supervisor 的观察结果
    error: str | None = None

class Tool(ABC):
    """工具基类 - Tier 3 Function Calling 标准"""

    name: str
    description: str

    @abstractmethod
    def get_schema(self) -> dict:
        """OpenAI Function Calling Schema"""
        pass

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        pass

# 记忆工具
class SearchMemoryTool(Tool):
    name = "search_memory"
    description = "搜索用户的长期记忆，当用户询问'我之前说过什么'时使用"

    def get_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "搜索关键词"},
                        "time_range": {"type": "string", "enum": ["today", "week", "month", "all"]}
                    },
                    "required": ["query"]
                }
            }
        }

    async def execute(self, query: str, time_range: str = "all") -> ToolResult:
        results = self.memory.recall(query, top_k=5)
        return ToolResult(
            success=True,
            data={"memories": results},
            observation=f"找到 {len(results)} 条相关记忆"
        )

class AddMemoryTool(Tool):
    name = "add_memory"
    description = "添加新记忆，当用户说'记住我喜欢...'时使用"

    async def execute(self, content: str, importance: int = 5) -> ToolResult:
        memory_id = self.memory.capture(content)
        return ToolResult(
            success=True,
            data={"memory_id": memory_id},
            observation=f"已记住：{content[:50]}..."
        )

# 任务工具
class CreateTaskTool(Tool):
    name = "create_task"
    description = "创建新任务/待办事项，当用户说'提醒我...'、'明天要...'时使用"

    async def execute(self, title: str, due_date: str | None = None) -> ToolResult:
        task = self.task_manager.create(title=title, due_date=due_date)
        return ToolResult(
            success=True,
            data={"task_id": task.id},
            observation=f"已创建任务：{title}"
        )

class ListTasksTool(Tool):
    name = "list_tasks"
    description = "查看任务列表，当用户问'我有什么任务'、'待办有哪些'时使用"

    async def execute(self, status: str = "pending") -> ToolResult:
        tasks = self.task_manager.list_tasks(status=status)
        return ToolResult(
            success=True,
            data={"tasks": tasks, "count": len(tasks)},
            observation=f"找到 {len(tasks)} 个任务"
        )

class DeleteTasksTool(Tool):
    name = "delete_tasks"
    description = "删除任务，当用户说'清理任务'、'删除xxx'、'清空列表'时使用"

    async def execute(self,
                      task_ids: list[str] | None = None,
                      delete_all: bool = False,
                      confirmed: bool = False) -> ToolResult:
        # Agent 模式：先查询，再确认，最后删除
        if not confirmed:
            tasks = self.task_manager.list_tasks(status="pending")
            return ToolResult(
                success=True,
                data={"needs_confirmation": True, "tasks": tasks},
                observation=f"准备删除 {len(tasks)} 个任务，需要用户确认"
            )

        if delete_all:
            count = self.task_manager.delete_all()
        else:
            count = self.task_manager.delete_by_ids(task_ids or [])

        return ToolResult(
            success=True,
            data={"deleted_count": count},
            observation=f"已删除 {count} 个任务"
        )

# 系统工具
class ChatTool(Tool):
    name = "chat"
    description = "闲聊、问候、情感交流。当用户没有明确任务需求，只是打招呼或闲聊时使用"

    async def execute(self, message: str) -> ToolResult:
        return ToolResult(
            success=True,
            data={"type": "direct_response"},
            observation="直接回复用户"
        )
```

**关键改造点**: 所有功能统一为 Tool 接口，支持 Function Calling

---

### Phase 2: Supervisor Agent（Week 2）

**目标**: 实现中央协调器，支持单步和多步模式

```python
# src/agent/supervisor.py
from dataclasses import dataclass, field
from typing import AsyncGenerator
from enum import Enum

class ExecutionMode(Enum):
    """执行模式"""
    FAST_PATH = "fast_path"      # 简单意图，直接路由
    SINGLE_STEP = "single_step"  # 单步工具调用
    MULTI_STEP = "multi_step"    # 多步 Agent 模式

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
    def current(self) -> Step | None:
        if 0 <= self.current_step < len(self.steps):
            return self.steps[self.current_step]
        return None

class SupervisorAgent:
    """
    Supervisor 模式实现

    职责：
    1. 意图分析 → 选择执行模式
    2. 任务规划 → 生成执行计划
    3. 编排执行 → 协调 Agents/Tools
    4. 结果聚合 → 生成最终回复
    """

    def __init__(
        self,
        llm_client,
        tools: list[Tool],
        memory_system,
        fast_path_router: SemanticIntentRouter | None = None
    ):
        self.llm = llm_client
        self.tools = {t.name: t for t in tools}
        self.memory = memory_system
        self.fast_path = fast_path_router  # 保留 Tier 2 作为快速路径
        self.tool_schemas = [t.get_schema() for t in tools]

    async def handle(
        self,
        user_input: str,
        session_id: str
    ) -> AsyncGenerator[str | dict, None]:
        """
        处理用户输入的主入口

        Yields:
            - str: 流式输出文本
            - dict: 需要用户输入 {"type": "need_input", "prompt": str}
        """

        # === Step 1: Intent Analysis ===
        mode = await self._analyze_intent(user_input)

        if mode == ExecutionMode.FAST_PATH and self.fast_path:
            # 使用 Tier 2 快速路径
            yield "⚡ 快速处理...\n"
            intent = self.fast_path.classify(user_input)
            result = await self._execute_single_tool(intent.type.value, {})
            yield result.observation
            return

        # === Step 2: Planning ===
        yield "🤔 正在规划...\n"
        plan = await self._plan(user_input, mode)

        if mode == ExecutionMode.SINGLE_STEP:
            # 单步执行
            yield f"⚡ 执行: {plan.steps[0].tool_name}\n"
            result = await self._execute_step(plan.steps[0])
            yield f"✅ {result.observation}\n"

        elif mode == ExecutionMode.MULTI_STEP:
            # 多步 Agent 模式
            yield f"📋 计划: {plan.goal}（共{len(plan.steps)}步）\n"

            async for output in self._execute_multi_step(plan):
                if isinstance(output, dict) and output.get("type") == "need_input":
                    yield output  # 需要用户确认
                    return
                yield output

        # === Step 3: Response Generation ===
        final_response = await self._generate_response(plan)
        yield final_response

    async def _analyze_intent(self, user_input: str) -> ExecutionMode:
        """
        意图分析，决定执行模式

        策略：
        - 简单/高频意图 → FAST_PATH
        - 单工具可完成 → SINGLE_STEP
        - 需要多步/确认 → MULTI_STEP
        """
        # 简单意图关键词（快速路径）
        simple_patterns = ["你好", "嗨", "hello", "谢谢", "再见"]
        if any(p in user_input.lower() for p in simple_patterns):
            return ExecutionMode.FAST_PATH

        # 检查是否需要多步（基于关键词启发式）
        multi_step_indicators = [
            "并", "然后", "再", "先...再", "帮我...然后",
            "清理", "整理", "总结", "分析"
        ]
        needs_multi_step = any(i in user_input for i in multi_step_indicators)

        if needs_multi_step:
            return ExecutionMode.MULTI_STEP

        return ExecutionMode.SINGLE_STEP

    async def _plan(self, user_input: str, mode: ExecutionMode) -> ExecutionPlan:
        """生成执行计划"""

        if mode == ExecutionMode.SINGLE_STEP:
            # 单步：使用 Function Calling 选择工具
            response = await self.llm.generate(
                messages=[{"role": "user", "content": user_input}],
                tools=self.tool_schemas,
                tool_choice="auto"
            )

            if response.tool_calls:
                tool_call = response.tool_calls[0]
                return ExecutionPlan(
                    mode=mode,
                    goal=user_input,
                    steps=[Step(
                        id="step_0",
                        tool_name=tool_call.function.name,
                        parameters=json.loads(tool_call.function.arguments)
                    )]
                )

        elif mode == ExecutionMode.MULTI_STEP:
            # 多步：使用 LLM 进行规划
            prompt = f"""分析用户需求，制定执行计划。

用户输入：{user_input}

可用工具：
{self._format_tools()}

请生成执行计划，返回 JSON：
{{
    "goal": "任务目标",
    "steps": [
        {{"tool": "工具名", "params": {{}}, "reason": "理由"}}
    ]
}}"""

            response = await self.llm.generate([{"role": "user", "content": prompt}])
            plan_data = json.loads(response)

            return ExecutionPlan(
                mode=mode,
                goal=plan_data["goal"],
                steps=[
                    Step(id=f"step_{i}", tool_name=s["tool"], parameters=s["params"])
                    for i, s in enumerate(plan_data["steps"])
                ]
            )

        # 默认：直接对话
        return ExecutionPlan(
            mode=mode,
            goal=user_input,
            steps=[Step(id="step_0", tool_name="chat", parameters={"message": user_input})]
        )

    async def _execute_multi_step(
        self,
        plan: ExecutionPlan
    ) -> AsyncGenerator[str | dict, None]:
        """执行多步计划"""

        while not plan.is_complete:
            step = plan.current

            yield f"  [{plan.current_step + 1}/{len(plan.steps)}] {step.tool_name}\n"

            result = await self._execute_step(step)

            # 检查是否需要用户确认
            if result.data.get("needs_confirmation"):
                yield {
                    "type": "need_input",
                    "prompt": f"{result.observation}\n确认执行吗？(yes/no)"
                }
                return

            if result.success:
                yield f"  ✅ {result.observation}\n"
            else:
                yield f"  ❌ {result.observation}\n"
                # 可以在这里添加重试逻辑

            plan.current_step += 1

    async def _execute_step(self, step: Step) -> ToolResult:
        """执行单个步骤"""
        tool = self.tools.get(step.tool_name)
        if not tool:
            return ToolResult(
                success=False,
                data=None,
                observation=f"工具 {step.tool_name} 不存在",
                error="Tool not found"
            )

        try:
            return await tool.execute(**step.parameters)
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                observation=f"执行失败: {str(e)}",
                error=str(e)
            )
```

---

### Phase 3: 与记忆系统深度整合（Week 3）

```python
# src/agent/memory_integration.py

class IntentMemoryIntegration:
    """意图识别与记忆系统整合"""

    def __init__(self, memory_system):
        self.memory = memory_system

    def enrich_context(self, user_input: str) -> dict:
        """
        用记忆上下文丰富用户输入

        检索：
        1. 工作记忆（当前对话上下文）
        2. 短期记忆（最近活跃记忆）
        3. 长期记忆（语义相关）
        """
        context = {
            "user_input": user_input,
            "working_memory": self._get_working_memory(),
            "recent_memories": self._get_recent_memories(),
            "relevant_memories": self._get_relevant_memories(user_input)
        }
        return context

    def record_execution(self, user_input: str, plan: ExecutionPlan, success: bool):
        """记录执行历史到记忆"""
        self.memory.capture(
            content=f"用户'{user_input}' → 执行'{plan.goal}'（成功：{success}）",
            memory_type="execution_pattern",
            tags=["agent", "execution"],
            metadata={
                "user_input": user_input,
                "goal": plan.goal,
                "steps_count": len(plan.steps),
                "success": success
            }
        )

    def get_suggested_plan(self, user_input: str) -> ExecutionPlan | None:
        """
        基于历史执行模式推荐计划

        如果用户经常做类似的事情，直接推荐之前的成功计划
        """
        similar = self.memory.recall(
            query=f"执行模式 {user_input}",
            filters={"memory_type": "execution_pattern", "success": True},
            top_k=3
        )

        if similar and similar[0].score > 0.9:
            # 复用历史计划
            metadata = similar[0].metadata
            return ExecutionPlan(
                mode=ExecutionMode.MULTI_STEP,
                goal=metadata.get("goal"),
                steps=[]  # 可以从 metadata 恢复
            )

        return None
```

---

## 与现有代码的整合

### 最小化改造策略

```
保留（无需改动）：
├── src/memory/           # 记忆系统完整保留
├── src/task/             # 任务管理完整保留
├── src/personality/      # 性格系统完整保留
├── src/chat/llm_client.py # LLM客户端保留
└── src/tools/mcp_*.py    # MCP工具保留

改造（需要调整）：
├── src/chat/
│   ├── intent_classifier.py      # 废弃，保留为Fallback
│   ├── ai_intent_classifier.py   # 废弃
│   ├── semantic_router.py        # 保留为Fast Path
│   ├── action_router.py          # 改造为Tool基类
│   └── chat_session.py           # 简化，接入Supervisor
└── src/main.py                   # 接入SupervisorAgent

新增：
├── src/agent/
│   ├── __init__.py
│   ├── supervisor.py      # Supervisor Agent核心
│   ├── tools/
│   │   ├── base.py        # Tool基类
│   │   ├── registry.py    # Tool注册表
│   │   └── builtin/       # 内置Tools
│   └── memory_integration.py  # 记忆整合
```

### main.py 改造示例

```python
# src/main.py 关键改造

class PersonalAIAssistant:
    async def initialize(self):
        # ... 现有初始化代码 ...

        # 初始化 Tools
        self.tools = [
            SearchMemoryTool(self.memory),
            AddMemoryTool(self.memory),
            CreateTaskTool(self.task_manager),
            ListTasksTool(self.task_manager),
            DeleteTasksTool(self.task_manager),
            ChatTool(),
            # ... 其他 tools
        ]

        # 初始化 Supervisor Agent（替代旧的意图分类器）
        self.supervisor = SupervisorAgent(
            llm_client=self.llm,
            tools=self.tools,
            memory_system=self.memory,
            fast_path_router=self.semantic_router  # 保留快速路径
        )

    async def interactive_chat(self):
        """新的交互循环"""
        while True:
            user_input = input("👤 你: ").strip()

            # 使用 Supervisor 处理
            async for output in self.supervisor.handle(user_input, self.session_id):
                if isinstance(output, dict) and output.get("type") == "need_input":
                    # 需要用户确认
                    confirm = input(f"🤖 {output['prompt']} ")
                    # 继续执行...
                else:
                    print(output, end='')
            print()
```

---

## 渐进式迁移策略

### 双模式运行（推荐）

```python
# 配置切换
class PersonalAIAssistant:
    def __init__(self, settings: Settings, use_agent: bool = False):
        self.use_agent = use_agent

    async def handle_input(self, user_input: str):
        if self.use_agent:
            return await self._agent_mode(user_input)
        else:
            return await self._legacy_mode(user_input)  # 保留旧模式
```

### 迁移时间线

```
Week 1: Function Calling 基础
        - 创建 Tool 基类
        - 迁移核心功能为 Tools
        - 测试单步工具调用

Week 2: Supervisor Agent
        - 实现 SupervisorAgent
        - 支持 SINGLE_STEP 和 MULTI_STEP
        - 测试"清理任务"等多步场景

Week 3: 记忆整合与优化
        - 实现 IntentMemoryIntegration
        - 添加执行历史记录
        - 性能优化

Week 4: 双模式并行测试
        - 对比新旧模式效果
        - 调优 Agent 参数
        - 修复边界 case

Week 5: 默认切换
        - 默认启用 Agent 模式
        - 保留 --legacy-mode 选项
        - 收集用户反馈

Week 6: 清理与文档
        - 废弃旧代码
        - 完善文档
        - 发布新版本
```

---

## 关键设计决策

### 1. 为什么保留 Semantic Router？

| 策略 | 优点 | 缺点 |
|------|------|------|
| 完全废弃 | 架构简洁 | 简单任务也有 LLM 延迟 |
| 保留为 Fast Path | 简单任务快速响应 | 需要维护两套系统（暂时） |
| **推荐：保留** | 兼顾性能和复杂度 | 迁移期结束后可移除 |

### 2. 为什么选 Supervisor 模式？

- 个人助手场景任务边界清晰
- 不需要 Agent 间频繁协作（Mesh 过度）
- 中央控制便于调试和监控
- 与现有代码结构兼容性好

### 3. 多步执行的触发条件？

```python
# 启发式判断，避免 LLM 调用开销
def needs_multi_step(user_input: str) -> bool:
    indicators = [
        # 显式多步关键词
        "并", "然后", "再", "先...再",
        # 隐式多步场景
        "清理", "整理", "总结", "分析",
        # 需要确认的场景
        "删除", "清空", "修改"
    ]
    return any(i in user_input for i in indicators)
```

---

## 预期效果

| 指标 | 当前 | 改造后 |
|------|------|--------|
| 架构复杂度 | 高（多套系统） | 中（统一 Supervisor） |
| 简单任务延迟 | 50-100ms | 10-50ms（Fast Path） |
| 复杂任务支持 | ❌ | ✅（多步规划） |
| 代码可维护性 | 低 | 高 |
| 扩展性 | 难 | 易（新增 Tool 即可） |

---

## 下一步行动

1. **确认方案**: 是否采纳 Supervisor + Function Calling 混合架构？
2. **确定范围**: 是否需要保留 Fast Path，还是直接全面 Function Calling？
3. **开始实施**: 从 Phase 1（Tool 基类）开始逐步实现

要我立即开始 Phase 1 的实现吗？
