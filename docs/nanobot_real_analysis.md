# Nanobot 真实架构分析（基于源代码）

## 核心发现

**nanobot 只有 4839 行代码（全部）**，但关键区别不是"规则匹配 vs LLM"，而是 **"LLM 主导 vs 系统预设流程主导"**。

---

## Nanobot 架构核心

### 1. AgentLoop (loop.py: 338行) - 极简循环

```python
# 核心处理逻辑 (_process_message 方法第131-224行)
async def _process_message(self, msg):
    # 1. 获取会话历史
    session = self.sessions.get_or_create(msg.session_key)
    messages = self.context.build_messages(
        history=session.get_history(),
        current_message=msg.content,
    )

    # 2. Agent Loop - 让 LLM 决定一切
    while iteration < self.max_iterations:
        # 调用 LLM，传入工具定义
        response = await self.provider.chat(
            messages=messages,
            tools=self.tools.get_definitions(),  # 所有工具定义
            model=self.model
        )

        # 3. 如果 LLM 想要调用工具
        if response.has_tool_calls:
            for tool_call in response.tool_calls:
                result = await self.tools.execute(
                    tool_call.name,
                    tool_call.arguments
                )
                # 把结果返回给 LLM
                messages = self.context.add_tool_result(...)
        else:
            # 4. LLM 直接回复，完成
            final_content = response.content
            break
```

**关键特点**:
- **没有意图分类层**
- **没有 Fast/Single/Multi Step 模式**
- **没有反思机制**
- **直接让 LLM 决定使用什么工具**

---

### 2. 工具系统 - 简单直接

```python
# base.py - Tool 基类
class Tool(ABC):
    @property
    @abstractmethod
    def name(self) -> str: pass

    @property
    @abstractmethod
    def description(self) -> str: pass

    @property
    @abstractmethod
    def parameters(self) -> dict: pass

    @abstractmethod
    async def execute(self, **kwargs) -> str:  # 直接返回字符串！
        pass
```

**与当前系统对比**:

| nanobot | 当前系统 |
|---------|----------|
| `execute() -> str` | `execute() -> ToolResult` |
| 直接返回可读文本 | 返回包装对象 |
| 简单描述 | 超长描述 + 示例 |

**nanobot 的工具描述示例** (filesystem.py 第18行):
```python
@property
def description(self) -> str:
    return "Read the contents of a file at the given path."
# 只有一句话！
```

**当前系统的描述**:
```python
description = "【删除专用】用于清理/删除/移除任务。触发词：'清理'、'删除'..."
# 几百字！
```

---

### 3. MessageBus - 简单事件传递

```python
# events.py - 只有37行！
@dataclass
class InboundMessage:
    channel: str
    sender_id: str
    chat_id: str
    content: str

@dataclass
class OutboundMessage:
    channel: str
    chat_id: str
    content: str
```

---

## 真正的差异对比

### 处理流程对比

**nanobot**:
```
用户: "清理任务"
  ↓
AgentLoop: 把所有工具传给 LLM
  ↓
LLM: "用户要删除，我用 delete_tasks"
  ↓
执行工具
  ↓
返回结果
```

**当前系统**:
```
用户: "清理任务"
  ↓
IntentClassifier: 规则匹配
  ↓
_analyze_intent(): 选择 SINGLE_STEP 模式
  ↓
_plan_single_step(): 构建 messages + 提示词
  ↓
LLM: "用 list_tasks" (可能选错)
  ↓
反思: 检测到错误
  ↓
直接切换到 delete_tasks
  ↓
执行
```

---

## 为什么 nanobot 体验更好

### 1. 让 LLM 做决定，而不是系统预设

**nanobot 的理念**:
- LLM 看到所有工具描述
- LLM 根据上下文决定使用什么
- 不需要系统帮它"预判"

**当前系统的问题**:
- 系统试图在 LLM 之前做意图分析
- 系统预设了执行模式
- 限制了 LLM 的灵活性

### 2. 工具描述简洁

**nanobot**: "Read the contents of a file."
**当前系统**: "【删除专用】用于清理/删除/移除任务。触发词：'清理'..."

**结果**:
- nanobot: LLM 直接理解
- 当前系统: LLM 被复杂描述干扰

### 3. 没有多层决策

| 决策点 | nanobot | 当前系统 |
|--------|---------|----------|
| 意图分析 | ❌ 没有 | ✅ 有 |
| 模式选择 | ❌ 没有 | ✅ 3层模式 |
| 工具选择 | ✅ LLM | ✅ LLM |
| 反思机制 | ❌ 没有 | ✅ 有 |

**关键 insight**: nanobot 相信 LLM 能自己决定，不需要系统预设。

---

## 当前系统的根本问题

### 问题 1: 过度干预 LLM 决策

当前系统试图"帮助"LLM 做决策：
- 意图分类器预选
- 执行模式预选
- 复杂提示词引导

**结果**: 反而限制了 LLM 的能力，让它更容易出错。

### 问题 2: 工具描述过度工程

当前系统的工具描述：
- 几百字长
- 包含示例、规则、触发词
- 试图"教"LLM 怎么用

**nanobot**: 一句话描述，让 LLM 自己理解。

### 问题 3: 预设流程 vs 自然对话

**nanobot**:
- 用户: "先查看任务，然后删除它们"
- LLM: "好，我先 list_tasks，再 delete_tasks"
- 自动处理多步

**当前系统**:
- 必须预设 MULTI_STEP 模式
- 必须显式规划步骤
- 流程僵化

---

## 重构建议

### 方案: 向 nanobot 学习 - 简化架构

```python
class SimpleAgent:
    """简化版 Agent - 像 nanobot 一样让 LLM 主导"""

    async def handle(self, user_input: str):
        # 1. 构建 messages（包含历史）
        messages = self.build_messages(user_input)

        # 2. 直接调用 LLM，传入所有工具
        response = await self.llm.chat(
            messages=messages,
            tools=self.tools.get_definitions()  # 所有工具
        )

        # 3. 如果 LLM 想要调用工具
        if response.has_tool_calls:
            for tool_call in response.tool_calls:
                result = await self.tools.execute(
                    tool_call.name,
                    tool_call.arguments
                )
                # 返回结果给 LLM 继续
                messages.append({
                    "role": "tool",
                    "content": result
                })

            # 让 LLM 基于工具结果回复
            final_response = await self.llm.chat(messages=messages)
            return final_response.content

        # 4. 直接返回 LLM 回复
        return response.content
```

**删除的组件**:
- ❌ IntentClassifier (3个)
- ❌ 三层执行模式
- ❌ 反思机制
- ❌ 复杂提示词
- ❌ 确认状态管理

**保留的组件**:
- ✅ Tool 基类
- ✅ ToolRegistry
- ✅ MessageBus
- ✅ Session 管理

### 工具描述简化

```python
# 之前
class DeleteTasksTool(Tool):
    description = """【删除专用】用于清理/删除/移除任务。
    触发词：'清理'、'删除'、'移除'、'清空'、'不要了'。
    重要：用户说'查看'、'显示'、'有什么'时绝对不要用此工具！
    ...500字..."""

# 之后
class DeleteTasksTool(Tool):
    description = "Delete tasks from the task list."
```

**相信 LLM 能理解**！

---

## 总结

| 方面 | nanobot | 当前系统 | 建议 |
|------|---------|----------|------|
| 架构哲学 | LLM 主导 | 系统主导 | 让 LLM 主导 |
| 意图分类 | ❌ 没有 | ✅ 3个 | ❌ 删除 |
| 执行模式 | ❌ 没有 | ✅ 3层 | ❌ 删除 |
| 工具描述 | 简洁 | 复杂 | 简化 |
| 反思机制 | ❌ 没有 | ✅ 有 | ❌ 删除 |
| 代码行数 | ~4800 | ~10000+ | 简化到 ~6000 |

**核心 insight**: 不是 nanobot 用了规则匹配，而是它**更少干预 LLM，让 LLM 自己决定**。

当前系统的问题不是"不够智能"，而是"过度设计，限制了 LLM 的能力"。
