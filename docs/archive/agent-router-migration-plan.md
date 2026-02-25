# Agent Router 改造计划

## 一、当前架构分析

### 1.1 现有架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                     当前架构（三层混杂）                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  用户输入                                                        │
│     │                                                           │
│     ▼                                                           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  意图识别层（三层二选一）                                  │   │
│  │  ├─ SemanticIntentRouter (向量相似度)                     │   │
│  │  ├─ AIIntentClassifier (LLM分类)                         │   │
│  │  └─ IntentClassifier (关键词正则)                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│     │                                                           │
│     ▼                                                           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  动作路由层（一次性执行）                                  │   │
│  │  ActionRouter.route(intent) → 直接执行                    │   │
│  │  - _handle_chat                                           │   │
│  │  - _handle_create_task                                    │   │
│  │  - _handle_delete_task  （无法实现"先查询再确认再删除"）     │   │
│  └─────────────────────────────────────────────────────────┘   │
│     │                                                           │
│     ▼                                                           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  工具层（分散实现）                                        │   │
│  │  - TaskManager （直接调用）                                │   │
│  │  - MemorySystem （直接调用）                               │   │
│  │  - SearchTool （通过 action_router 调用）                  │   │
│  │  - ToolExecutor （MCP，通过 action_router 调用）           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 当前架构问题

| 问题 | 说明 | 影响 |
|------|------|------|
| **意图层冗余** | 3套意图识别系统并存 | 维护困难，行为不一致 |
| **无状态执行** | ActionRouter 一次性执行 | 无法实现多步交互 |
| **工具接口不统一** | 有的直接调用，有的通过 MCP | 难以扩展和管理 |
| **无反思机制** | 执行完即结束 | 无法自我纠错 |
| **记忆集成浅层** | 只用于检索，不参与决策 | Agent 无法利用历史经验 |

---

## 二、目标架构设计

### 2.1 Agent Router 架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Agent Router 架构                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                      Agent Runtime                           │   │
│  │  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐  │   │
│  │  │ Planner │ → │ Router  │ → │Executor │ → │Reflection│  │   │
│  │  │  规划   │    │  路由   │    │  执行   │    │  反思    │  │   │
│  │  └────┬────┘    └────┬────┘    └────┬────┘    └────┬────┘  │   │
│  │       └────────────────────────────────────────────────┘     │   │
│  │                        ↑            │                        │   │
│  │                        └────────────┘                        │   │
│  │                           循环执行                            │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│         ┌────────────────────┼────────────────────┐                │
│         ▼                    ▼                    ▼                │
│  ┌─────────────┐      ┌─────────────┐      ┌─────────────┐        │
│  │ Working Mem │      │  Tool Registry │   │ Long-term   │        │
│  │  (上下文)   │      │  (工具集合)    │    │ Memory      │        │
│  └─────────────┘      └─────────────┘      └─────────────┘        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 核心组件说明

| 组件 | 职责 | 对应现有代码 |
|------|------|-------------|
| **AgentRuntime** | 管理整个执行生命周期 | 替代 `main.py` 中的交互逻辑 |
| **Planner** | 将目标拆解为执行步骤 | 新增，替代简单意图分类 |
| **Router** | 每步选择合适的工具 | 替代 `ActionRouter` |
| **Executor** | 调用工具并获取结果 | 替代分散的工具调用 |
| **Reflection** | 评估结果，决定下一步 | 新增 |
| **AgentState** | 维护跨步骤的状态 | 新增 |
| **ToolRegistry** | 统一管理所有工具 | 整合 `ToolExecutor` + `FunctionRegistry` |

---

## 三、改造工作量评估

### 3.1 文件变更矩阵

| 类型 | 文件/目录 | 工作量 | 说明 |
|------|----------|--------|------|
| **新增** | `src/agent/` 目录 | 5天 | 核心 Agent 框架 |
| **新增** | `src/agent/core.py` | 2天 | AgentRuntime, AgentState |
| **新增** | `src/agent/planner.py` | 1.5天 | Planner 实现 |
| **新增** | `src/agent/executor.py` | 1天 | Executor 实现 |
| **新增** | `src/agent/reflection.py` | 1天 | Reflection 机制 |
| **新增** | `src/tools/registry.py` | 1天 | 统一 ToolRegistry |
| **新增** | `src/tools/base.py` | 0.5天 | Tool 基类定义 |
| **重构** | `src/chat/` 目录 | 2天 | 删除旧意图分类器 |
| **重构** | `src/main.py` | 1天 | 接入 AgentRuntime |
| **重构** | `src/personality/skills/` | 1天 | 改造为 Agent Tools |
| **重构** | `src/task/manager.py` | 0.5天 | 封装为 Tool |
| **重构** | `src/memory/system.py` | 0.5天 | 增强 Agent 集成 |
| **测试** | `tests/agent/` | 2天 | 单元测试 + 集成测试 |
| **文档** | `docs/` | 1天 | 架构文档 + 迁移指南 |
| **总计** | - | **约 20 天** | 全职开发 |

### 3.2 关键重构点

```
删除/废弃的代码:
├── src/chat/intent_classifier.py      (关键词分类器 - 废弃)
├── src/chat/ai_intent_classifier.py   (AI分类器 - 废弃)
├── src/chat/semantic_router.py        (语义路由 - 可保留为辅助)
├── src/chat/action_router.py          (动作路由 - 废弃)
└── src/chat/context_builder.py        (上下文构建 - 整合到 AgentState)

新增的代码:
├── src/agent/
│   ├── __init__.py
│   ├── core.py              (AgentRuntime, AgentState, AgentConfig)
│   ├── planner.py           (Planner, Plan, Step)
│   ├── executor.py          (ToolExecutor)
│   ├── reflection.py        (Reflection, Observation)
│   └── memory_integration.py (Agent 与记忆系统交互)
├── src/tools/
│   ├── base.py              (Tool, ToolResult 基类)
│   ├── registry.py          (ToolRegistry)
│   └── builtin/             (内置工具)
│       ├── task_tools.py    (任务相关)
│       ├── memory_tools.py  (记忆相关)
│       ├── search_tools.py  (搜索相关)
│       └── system_tools.py  (系统控制)
└── tests/agent/
    ├── test_core.py
    ├── test_planner.py
    └── test_integration.py
```

---

## 四、详细实现方案

### 4.1 Phase 1: 工具标准化（Week 1）

**目标**: 统一所有工具接口

```python
# src/tools/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable

@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    data: Any
    observation: str          # 执行观察，用于反思
    error: str | None = None

@dataclass
class ToolParameter:
    """工具参数定义"""
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None

class Tool(ABC):
    """工具基类"""

    name: str
    description: str
    parameters: list[ToolParameter]

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """执行工具"""
        pass

    def to_function_schema(self) -> dict:
        """转换为 OpenAI Function Calling 格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        p.name: {
                            "type": p.type,
                            "description": p.description
                        } for p in self.parameters
                    },
                    "required": [p.name for p in self.parameters if p.required]
                }
            }
        }

# src/tools/builtin/task_tools.py
class CreateTaskTool(Tool):
    name = "create_task"
    description = "创建新任务或待办事项"
    parameters = [
        ToolParameter("title", "string", "任务标题", True),
        ToolParameter("description", "string", "任务描述", False),
        ToolParameter("due_date", "string", "截止时间(ISO格式)", False),
    ]

    def __init__(self, task_manager: TaskManager):
        self.task_manager = task_manager

    async def execute(self, **kwargs) -> ToolResult:
        try:
            task = self.task_manager.create(**kwargs)
            return ToolResult(
                success=True,
                data={"task_id": task.id},
                observation=f"成功创建任务: {task.title}"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                observation="创建任务失败",
                error=str(e)
            )

class ListTasksTool(Tool):
    name = "list_tasks"
    description = "查看任务列表"
    parameters = [
        ToolParameter("status", "string", "任务状态过滤", False),
    ]

    async def execute(self, **kwargs) -> ToolResult:
        tasks = self.task_manager.list_tasks(**kwargs)
        return ToolResult(
            success=True,
            data={"tasks": tasks, "count": len(tasks)},
            observation=f"找到 {len(tasks)} 个任务"
        )

class DeleteTasksTool(Tool):
    name = "delete_tasks"
    description = "删除任务，支持删除单个或批量清理"
    parameters = [
        ToolParameter("task_ids", "array", "要删除的任务ID列表", False),
        ToolParameter("delete_all", "boolean", "是否删除所有任务", False),
        ToolParameter("confirm", "boolean", "用户已确认删除", False),
    ]

    async def execute(self, **kwargs) -> ToolResult:
        if not kwargs.get("confirm"):
            # 需要确认，返回任务列表供确认
            tasks = self.task_manager.list_tasks(status="pending")
            return ToolResult(
                success=True,
                data={"needs_confirmation": True, "tasks": tasks},
                observation=f"准备删除 {len(tasks)} 个任务，需要用户确认"
            )

        # 执行删除
        if kwargs.get("delete_all"):
            count = self.task_manager.delete_all()
        else:
            count = self.task_manager.delete_by_ids(kwargs.get("task_ids", []))

        return ToolResult(
            success=True,
            data={"deleted_count": count},
            observation=f"成功删除 {count} 个任务"
        )
```

### 4.2 Phase 2: Agent 核心框架（Week 2）

**目标**: 实现 Agent Runtime 和状态管理

```python
# src/agent/core.py
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator
from enum import Enum

class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_CLARIFICATION = "needs_clarification"

@dataclass
class Step:
    """执行步骤"""
    id: str
    tool_name: str
    parameters: dict
    status: StepStatus = StepStatus.PENDING
    result: ToolResult | None = None
    observation: str = ""
    retry_count: int = 0

@dataclass
class Plan:
    """执行计划"""
    goal: str
    steps: list[Step] = field(default_factory=list)
    current_step_index: int = 0

    @property
    def current_step(self) -> Step | None:
        if 0 <= self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None

    @property
    def is_complete(self) -> bool:
        return self.current_step_index >= len(self.steps)

@dataclass
class AgentState:
    """Agent 状态"""
    session_id: str
    user_input: str
    plan: Plan | None = None
    context: dict = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)
    working_memory: dict = field(default_factory=dict)

    def add_observation(self, step_id: str, observation: str):
        """添加观察结果到历史"""
        self.history.append({
            "step_id": step_id,
            "observation": observation,
            "timestamp": datetime.now().isoformat()
        })

class AgentRuntime:
    """Agent 运行时"""

    def __init__(
        self,
        llm_client,
        tool_registry: ToolRegistry,
        memory_system: MemorySystem,
        planner: Planner | None = None,
        reflection_engine: ReflectionEngine | None = None,
        max_steps: int = 10
    ):
        self.llm = llm_client
        self.tools = tool_registry
        self.memory = memory_system
        self.planner = planner or DefaultPlanner(llm_client)
        self.reflection = reflection_engine or DefaultReflectionEngine(llm_client)
        self.max_steps = max_steps

    async def run(self, user_input: str, session_id: str) -> AsyncGenerator[str, None]:
        """
        运行 Agent 直到完成任务

        Yields:
            流式输出：思考过程、工具调用、结果等
        """
        # 初始化状态
        state = AgentState(
            session_id=session_id,
            user_input=user_input
        )

        # 检索相关记忆
        relevant_memories = self.memory.recall(user_input, top_k=5)
        state.working_memory["relevant_memories"] = relevant_memories

        # Step 1: 规划
        yield "🤔 正在思考...\n"
        state.plan = await self.planner.create_plan(user_input, state)
        yield f"📋 计划: {state.plan.goal}\n"

        step_count = 0
        while step_count < self.max_steps:
            step = state.plan.current_step
            if not step:
                break

            # Step 2: 执行
            yield f"⚡ 执行: {step.tool_name}\n"
            step.status = StepStatus.RUNNING

            tool = self.tools.get(step.tool_name)
            if not tool:
                step.status = StepStatus.FAILED
                step.observation = f"工具 {step.tool_name} 不存在"
                break

            try:
                result = await tool.execute(**step.parameters)
                step.result = result
                step.observation = result.observation

                if result.success:
                    step.status = StepStatus.COMPLETED
                    yield f"✅ {result.observation}\n"
                else:
                    step.status = StepStatus.FAILED
                    yield f"❌ {result.observation}\n"

                state.add_observation(step.id, result.observation)

            except Exception as e:
                step.status = StepStatus.FAILED
                step.observation = f"执行异常: {str(e)}"
                yield f"❌ {step.observation}\n"

            # Step 3: 反思
            reflection = await self.reflection.evaluate(state)

            if reflection.needs_clarification:
                yield f"💭 {reflection.question}\n"
                # 等待用户输入...
                # 这里需要处理交互
                break

            if reflection.should_retry and step.retry_count < 3:
                step.retry_count += 1
                step.status = StepStatus.PENDING
                # 调整参数重试
                step.parameters.update(reflection.suggested_parameter_changes)
                yield f"🔄 重试 (第{step.retry_count}次)...\n"
                continue

            if reflection.should_replan:
                yield "📝 重新规划...\n"
                state.plan = await self.planner.replan(state)
                continue

            # 移动到下一步
            state.plan.current_step_index += 1
            step_count += 1

        # 生成最终回复
        yield "💬 生成回复...\n"
        final_response = await self._generate_response(state)
        yield final_response

    async def _generate_response(self, state: AgentState) -> str:
        """基于执行历史生成自然语言回复"""
        # 使用 LLM 生成友好回复
        context = {
            "goal": state.plan.goal if state.plan else state.user_input,
            "history": state.history,
            "personality": self._get_personality_prompt()
        }

        prompt = f"""基于以下执行历史，生成友好的回复：

目标: {context['goal']}

执行步骤:
{self._format_history(context['history'])}

请以助手的身份回复用户，总结执行结果。语气要{context['personality']}。
"""

        return await self.llm.generate([{"role": "user", "content": prompt}])
```

### 4.3 Phase 3: Planner 实现（Week 2-3）

```python
# src/agent/planner.py
class Planner(ABC):
    """规划器基类"""

    @abstractmethod
    async def create_plan(self, goal: str, state: AgentState) -> Plan:
        """根据目标创建执行计划"""
        pass

    @abstractmethod
    async def replan(self, state: AgentState) -> Plan:
        """根据当前状态重新规划"""
        pass

class LLMPlanner(Planner):
    """基于 LLM 的规划器"""

    def __init__(self, llm_client, tool_registry: ToolRegistry):
        self.llm = llm_client
        self.tools = tool_registry

    async def create_plan(self, goal: str, state: AgentState) -> Plan:
        """使用 LLM 创建执行计划"""

        # 获取可用工具列表
        available_tools = self.tools.list_tools()
        tool_descriptions = "\n".join([
            f"- {t.name}: {t.description}"
            for t in available_tools
        ])

        prompt = f"""你是一个任务规划专家。请将用户目标拆解为可执行步骤。

用户目标: {goal}

可用工具:
{tool_descriptions}

请输出 JSON 格式的执行计划:
{{
    "goal": "计划目标",
    "steps": [
        {{
            "tool_name": "工具名称",
            "parameters": {{"参数名": "参数值"}},
            "reasoning": "为什么使用这个工具"
        }}
    ]
}}

规划规则:
1. 步骤要具体、可执行
2. 参数值如果未知，使用 null 或占位符
3. 需要用户确认的步骤，添加 "needs_confirmation": true
4. 优先使用最匹配的工具
"""

        response = await self.llm.generate([{"role": "user", "content": prompt}])
        plan_data = json.loads(response)

        steps = [
            Step(
                id=f"step_{i}",
                tool_name=s["tool_name"],
                parameters=s["parameters"],
                status=StepStatus.PENDING
            )
            for i, s in enumerate(plan_data["steps"])
        ]

        return Plan(goal=plan_data["goal"], steps=steps)
```

### 4.4 Phase 4: Reflection 实现（Week 3）

```python
# src/agent/reflection.py
@dataclass
class Reflection:
    """反思结果"""
    should_continue: bool
    should_retry: bool
    should_replan: bool
    needs_clarification: bool
    question: str = ""
    suggested_parameter_changes: dict = field(default_factory=dict)
    observation: str = ""

class ReflectionEngine(ABC):
    """反思引擎基类"""

    @abstractmethod
    async def evaluate(self, state: AgentState) -> Reflection:
        """评估当前状态，决定下一步"""
        pass

class LLMReflectionEngine(ReflectionEngine):
    """基于 LLM 的反思引擎"""

    async def evaluate(self, state: AgentState) -> Reflection:
        step = state.plan.current_step if state.plan else None
        if not step or not step.result:
            return Reflection(should_continue=True, should_retry=False, should_replan=False, needs_clarification=False)

        prompt = f"""评估刚刚执行的工具调用结果，决定下一步行动。

当前步骤: {step.tool_name}
执行结果: {step.result.observation}
成功状态: {"成功" if step.result.success else "失败"}

历史记录:
{self._format_history(state.history)}

请输出 JSON:
{{
    "assessment": "评估说明",
    "should_continue": true/false,
    "should_retry": true/false,
    "should_replan": true/false,
    "needs_clarification": true/false,
    "question": "如果需要用户澄清，问什么问题",
    "suggested_changes": {{"参数名": "新值"}}
}}
"""

        response = await self.llm.generate([{"role": "user", "content": prompt}])
        result = json.loads(response)

        return Reflection(
            should_continue=result.get("should_continue", True),
            should_retry=result.get("should_retry", False),
            should_replan=result.get("should_replan", False),
            needs_clarification=result.get("needs_clarification", False),
            question=result.get("question", ""),
            suggested_parameter_changes=result.get("suggested_changes", {}),
            observation=result.get("assessment", "")
        )
```

---

## 五、迁移策略

### 5.1 渐进式迁移方案

推荐 **Side-by-Side** 迁移，而非大爆炸式重构：

```
Week 1-2: 搭建 Agent 框架（并行开发）
    - 新增 src/agent/ 目录
    - 保持现有代码不变
    - 编写 Agent 核心代码

Week 3: 工具迁移
    - 逐个将功能封装为 Tool
    - 每个 Tool 独立测试
    - 验证与旧系统输出一致

Week 4: 双模式运行
    - main.py 支持 --agent-mode 参数
    - 默认保持旧模式
    - Agent 模式可选启用

Week 5-6: 逐步切换
    - 内部测试 Agent 模式
    - 修复边界 case
    - 性能优化

Week 7: 全面切换
    - 默认启用 Agent 模式
    - 保留旧模式作为 --legacy-mode

Week 8: 清理
    - 删除旧代码
    - 完善文档
```

### 5.2 兼容性处理

```python
# src/main.py 改造
class PersonalAIAssistant:
    def __init__(self, settings: Settings, use_agent: bool = False):
        self.use_agent = use_agent
        self.agent_runtime: AgentRuntime | None = None
        # ... 其他初始化

    async def interactive_chat(self):
        if self.use_agent:
            await self._agent_chat()
        else:
            await self._legacy_chat()  # 保持原有逻辑

    async def _agent_chat(self):
        """新的 Agent 交互模式"""
        while True:
            user_input = input("👤 你: ").strip()

            # 使用 AgentRuntime 处理
            async for output in self.agent_runtime.run(user_input, self.session_id):
                print(output, end='', flush=True)
            print()
```

---

## 六、风险与应对

| 风险 | 影响 | 应对策略 |
|------|------|----------|
| **开发周期超预期** | 高 | 采用渐进式迁移，确保每阶段可交付 |
| **LLM 调用成本增加** | 中 | 实现本地缓存，优化 Prompt 长度 |
| **延迟增加** | 中 | 多步执行确实更慢，优化为可配置的最大步数 |
| **Bug 引入** | 中 | 完整的测试覆盖，保留旧模式回退 |
| **维护两套系统** | 低 | 限定并行期为 1 个月，到期强制切换 |

---

## 七、总结

### 改造收益

| 维度 | 当前 | Agent Router |
|------|------|--------------|
| **多步交互** | ❌ 不支持 | ✅ 原生支持 |
| **错误恢复** | ❌ 需手动处理 | ✅ 自动重试/重规划 |
| **扩展性** | ⚠️ 需改多处 | ✅ 新增 Tool 即可 |
| **维护成本** | ⚠️ 三套意图系统 | ✅ 统一架构 |
| **用户体验** | ⚠️ 单轮执行 | ✅ 复杂任务自动分解 |

### 工作量总结

- **总工期**: 约 8 周（含测试和迁移）
- **核心开发**: 4 周
- **测试验证**: 2 周
- **渐进迁移**: 2 周
- **建议**: 先实现简化版（支持 3-5 步规划），再逐步增强

### 下一步建议

1. **先实现简化 Agent**：只支持 Chain 模式（线性步骤）
2. **验证可行性**：用一个功能（如任务管理）试点
3. **再全面推广**：验证成功后迁移其他功能

要我帮你开始实现 Phase 1 的工具标准化吗？
