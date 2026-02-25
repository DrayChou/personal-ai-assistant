# 重新思考：nanobot vs 我们的系统

## 我之前犯的错误

**错误1**: 我声称 nanobot "没有意图分类"
**事实**: nanobot 通过 **ContextBuilder + Skills** 让 LLM 具备完整上下文，由 LLM 自己判断

**错误2**: 我主张"删除意图分类层，完全让 LLM 主导"
**问题**: 忽略了我们系统与 nanobot 的本质区别

---

## 核心发现：nanobot 的 Skills 系统

### nanobot 架构（仔细看 context.py + skills.py）

```
System Prompt 构建（ContextBuilder.build_system_prompt()）:
├── Identity (核心身份)
├── Bootstrap Files (AGENTS.md, TOOLS.md, IDENTITY.md, SOUL.md, USER.md)
├── Memory Context
├── Always-loaded Skills (完整内容)
└── Available Skills Summary (列表，LLM 可用 read_file 加载)
```

**关键洞察**:
- nanobot 不是"没有意图分类"，而是"**意图分类在 LLM 内部完成**"
- 通过 **丰富的 system prompt** 让 LLM 理解自己的能力和上下文
- Skills 是**动态加载的能力定义**，不是静态规则

### Skills 如何工作

**Skill 文件示例** (`skills/github/SKILL.md`):
```markdown
---
name: github
description: Interact with GitHub using gh CLI
---

# GitHub Skill

You can use the `gh` command to interact with GitHub.

Common workflows:
- `gh repo view` - View repository information
- `gh pr list` - List pull requests
- `gh issue create` - Create an issue
```

**使用方式**:
1. **Always skills**: 直接加载到 system prompt
2. **Available skills**: LLM 看到列表，需要时用 `read_file` 加载具体内容
3. **Progressive loading**: 避免 context window 过载

---

## 本质区别：使用场景

| 维度 | nanobot | 我们的系统 |
|------|---------|------------|
| **目标用户** | 开发者/程序员 | 普通用户 |
| **核心功能** | 文件操作、Shell、代码编辑 | 任务管理、记忆、对话 |
| **工具类型** | 通用计算机操作 | 特定业务逻辑 |
| **决策复杂度** | 低（读文件 vs 执行命令） | 高（查看 vs 删除 vs 完成） |
| **错误成本** | 低（可撤销） | 高（误删任务不可恢复） |

### 为什么 nanobot 可以"让 LLM 主导"

**场景1**: 用户说"看看这个文件"
- LLM: 调用 `read_file`
- 结果: 显示文件内容
- 确定性: 高

**场景2**: 用户说"运行测试"
- LLM: 调用 `exec` 执行测试命令
- 结果: 显示测试输出
- 确定性: 高

### 为什么我们的系统需要更明确的控制

**场景1**: 用户说"看看我的任务"
- 可能是 `list_tasks`
- 可能是 `search_memory`（之前讨论过的任务）
- 可能是直接聊天（想了解任务概念）
- **歧义性高**

**场景2**: 用户说"清理任务"
- 必须是 `delete_tasks`，不能是 `list_tasks`
- 但 LLM 可能理解错
- **需要确认流程**
- **错误成本高**

---

## 我们的优势在哪里？

### 1. 三层记忆系统（vs nanobot 的简单 MemoryStore）

**nanobot**: 简单的 markdown 文件存储
**我们的系统**:
- L0: Working Memory（槽位机制）
- L1: Short-term Memory（向量检索）
- L2: Long-term Memory（SQLite + ChromaDB）
- **优势**: 自动捕获、智能检索、定期整合

### 2. 人格/性格系统（nanobot 没有）

- 猫娘、大小姐、战斗修女等多种性格
- 动态切换
- 个性化回复风格

### 3. 任务状态机（vs nanobot 的简单命令执行）

**nanobot**: 执行命令 → 返回结果（一次性）
**我们的系统**:
- PENDING → IN_PROGRESS → COMPLETED
- 阻塞、等待、逾期处理
- 依赖管理
- **优势**: 支持复杂工作流

### 4. 确认流程和反思机制（nanobot 没有）

- 删除前的确认
- 工具选择错误的自动纠正
- **优势**: 更可靠，适合生产环境

---

## 正确的改进方向

### 不是"删除意图分类"，而是"优化决策链"

**当前问题**:
```
用户输入 → IntentClassifier（规则）→ _analyze_intent（启发式）→ _plan_single_step（LLM）→ 可能反思
```
**链条过长，层层损耗**

**改进方向**: 借鉴 nanobot 的 Skills 思想

```
用户输入 → System Prompt（包含 Skills）→ LLM 决策 → 执行
```

### 具体改进

#### 1. 简化意图层（不是删除）

**保留**:
- `IntentClassifier`（规则匹配常见指令）

**删除**:
- `SemanticIntentRouter`（依赖外部服务，效果不佳）
- `AIIntentClassifier`（与 Supervisor 重复）

**新增**:
- Skills 系统（类似 nanobot）

#### 2. 引入 Skills 系统

```python
# skills/task_management/SKILL.md
---
name: task_management
description: Manage user tasks and todos
always: true
---

# Task Management Skill

You can help users manage their tasks.

## Available Tools

- `list_tasks` - View all tasks. Use when user asks "what tasks do I have"
- `create_task` - Create a new task. Use when user says "remind me to..."
- `complete_task` - Mark a task as done. Use when user says "I finished..."
- `delete_tasks` - Delete tasks. **IMPORTANT**: Only use when user explicitly says "delete" or "clean up"

## Confirmation Required

Always ask for confirmation before deleting tasks.
```

#### 3. 简化工具描述

**当前**:
```python
description = """【删除专用】用于清理/删除/移除任务。
触发词：'清理'、'删除'、'移除'、'清空'、'不要了'。
重要：用户说'查看'、'显示'、'有什么'时绝对不要用此工具，应该用 list_tasks！"""
```

**改进**:
```python
description = "Delete tasks. Requires user confirmation."
# 详细规则放到 Skill 文件中
```

#### 4. 优化 Agent Loop（学习 nanobot）

**保留核心逻辑**:
- 支持多步工具调用（LLM 看到工具结果后继续决策）
- 工具结果直接返回给 LLM

**删除**:
- 复杂的 `_analyze_intent` 分层
- Fast/Single/Multi 模式区分
- 反思机制（如果意图分类准确，就不需要反思）

---

## 重构后的架构对比

### nanobot
```
Message → ContextBuilder (System Prompt + Skills) → Agent Loop (LLM decides tools) → Execute → Response
```

### 我们的系统（改进后）
```
Message → IntentClassifier (rule-based) → ContextBuilder (System Prompt + Skills + Memory) → Agent Loop (LLM decides tools) → Execute → Response
```

**关键区别**: 我们保留了：
1. **IntentClassifier** - 处理中文语境下的歧义
2. **三层记忆** - 更智能的上下文管理
3. **人格系统** - 个性化体验
4. **确认流程** - 高可靠性

---

## 结论

### 我之前的错误

我主张"完全让 LLM 主导，删除意图分类"是**错误**的，因为：

1. **忽略了使用场景差异**: nanobot 面向开发者（通用操作），我们面向普通用户（特定业务逻辑）
2. **忽略了错误成本**: 文件操作可撤销，任务删除不可恢复
3. **忽略了语言差异**: 中文语境下歧义更多

### 正确的策略

**不是模仿 nanobot，而是借鉴其优点，保留我们的优势**:

| nanobot 优点 | 如何借鉴 |
|-------------|---------|
| Skills 系统 | 引入 Skills，将工具描述从代码移到可配置的文件 |
| ContextBuilder | 优化我们的系统提示构建，更清晰地描述能力 |
| 简洁的 Agent Loop | 简化我们的三层模式，但保留必要的确认流程 |

| 我们的优势 | 如何保留 |
|-----------|---------|
| 三层记忆 | 保持，这是核心差异化 |
| 人格系统 | 保持，作为 Skill 实现 |
| 任务状态机 | 保持，通过 TaskManagement Skill 描述 |
| 确认流程 | 保持，在 Skill 中标注需要确认的工具 |

### 最终架构

```python
class ImprovedAgent:
    async def handle(self, user_input: str):
        # 1. 快速规则匹配（常见指令）
        intent = self.intent_classifier.classify(user_input)

        # 2. 构建上下文（借鉴 nanobot）
        system_prompt = self.context_builder.build(
            identity="personal_assistant",
            skills=["task_management", "memory", "personality"],
            memory_context=self.memory.recall(user_input),
            personality=self.personality.get_current()
        )

        # 3. Agent Loop（简化版）
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ]

        while True:
            response = await self.llm.chat(
                messages=messages,
                tools=self.tools.get_definitions()
            )

            if response.has_tool_calls:
                for tool_call in response.tool_calls:
                    # 检查是否需要确认
                    if self.tools.needs_confirmation(tool_call.name):
                        yield "需要确认..."
                        # 处理确认...

                    result = await self.tools.execute(
                        tool_call.name,
                        tool_call.arguments
                    )
                    messages.append({
                        "role": "tool",
                        "content": result
                    })
            else:
                yield response.content
                break
```

**保留核心优势，借鉴优秀设计，而不是简单模仿。**
