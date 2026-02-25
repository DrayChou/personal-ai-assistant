# Agent V2 架构迁移指南

## 概述

本文档指导如何从当前的 SupervisorAgent 架构迁移到新的 Agent V2 架构。

## 架构对比

### 当前架构 (SupervisorAgent)

```
用户输入
  ↓
IntentClassifier (规则分类)
  ↓
AIIntentClassifier (AI分类)
  ↓
_analyze_intent() (模式选择: Fast/Single/Multi)
  ↓
_plan() (任务规划)
  ↓
执行工具
  ↓
_reflect_on_result() (反思)
  ↓
输出结果
```

**问题：**
- 决策链条过长
- 多次LLM调用
- 过度干预LLM决策

### 新架构 (Agent V2)

```
用户输入
  ↓
ContextBuilder (构建完整上下文)
  ↓
AgentLoop (单次/多次LLM调用)
  ↓
LLM自主决策
  ↓
输出结果
```

**优势：**
- 极简循环
- LLM自主决策
- 渐进式上下文加载

## 迁移步骤

### 步骤1: 安装新组件

```python
# 新架构入口
from src.agent_v2 import AgentLoop, ContextBuilder, BuildConfig

# Skills系统
from src.agent_v2.skills import SkillRegistry, SkillsContextInjector

# 记忆集成
from src.agent_v2.memory import MemoryContextInjector

# 人格集成
from src.agent_v2.personality import PersonalityContextInjector
```

### 步骤2: 初始化 Agent V2

```python
async def create_agent_v2(llm_client, tool_registry, memory_system, personality_manager):
    """创建 Agent V2 实例"""

    # 1. 创建 ContextBuilder
    context_builder = ContextBuilder()

    # 2. 注册上下文注入器 (按优先级)
    # 优先级20: 人格
    context_builder.register_injector(
        PersonalityContextInjector(personality_manager),
        priority=20
    )

    # 优先级25: Skills
    skills_dir = Path("./skills")
    skill_registry = SkillRegistry(skills_dir)
    context_builder.register_injector(
        SkillsContextInjector(skill_registry, max_dynamic_skills=3),
        priority=25
    )

    # 优先级30: 记忆
    context_builder.register_injector(
        MemoryContextInjector(memory_system, max_memories=5),
        priority=30
    )

    # 3. 创建 AgentLoop
    agent = AgentLoop(
        llm_client=llm_client,
        tool_registry=tool_registry,
        context_builder=context_builder,
        max_iterations=10,
        tool_timeout=30.0,
    )

    return agent
```

### 步骤3: 替换调用代码

**旧代码：**
```python
# 旧架构
from src.agent.supervisor import SupervisorAgent

agent = SupervisorAgent(
    llm_client=llm,
    tool_registry=tools,
    memory_system=memory,
)

async for chunk in agent.handle(user_input, session_id):
    print(chunk)
```

**新代码：**
```python
# 新架构
from src.agent_v2 import AgentLoop, ContextBuilder

agent = await create_agent_v2(llm, tools, memory, personality)

async for response in agent.run(
    session_id=session_id,
    user_input=user_input,
    message_history=history,
):
    if response.type.value == 'text':
        print(response.content)
    elif response.type.value == 'confirmation':
        print(f"需要确认: {response.confirmation_prompt}")
```

### 步骤4: 创建 Skills

将原有的意图分类逻辑转换为 Skills。

**示例：任务管理 Skill**

创建 `skills/task_management/SKILL.md`:

```markdown
---
name: task_management
description: 管理用户的任务和待办事项
always_load: false
triggers:
  - 任务
  - 待办
  - todo
  - 提醒
---

# 任务管理技能

## 功能
- 创建新任务
- 查询现有任务
- 更新任务状态
- 删除已完成任务

## 使用场景
当用户提到"创建任务"、"查看待办"等时，使用相关工具。

## 注意事项
- 删除任务前需要用户确认
- 任务优先级分为: 高、中、低
```

### 步骤5: 适配工具返回格式

**旧格式：**
```python
@dataclass
class ToolResult:
    success: bool
    data: Any
    observation: str  # 给Agent反思用
    error: Optional[str]
    metadata: dict
```

**新格式：**
```python
# 工具直接返回字符串
# 特殊标记：
# - [PENDING_CONFIRMATION] 需要确认
# - [ERROR] 执行错误

async def execute(self, task_id: str) -> str:
    if not self._is_confirmed():
        return "[PENDING_CONFIRMATION] 确认删除任务?"
    await self._delete(task_id)
    return f"已删除任务: {task_id}"
```

## 配置切换

使用环境变量控制使用哪个版本：

```python
import os

USE_V2_AGENT = os.getenv('USE_V2_AGENT', 'false').lower() == 'true'

if USE_V2_AGENT:
    agent = await create_agent_v2(...)
    async for response in agent.run(...):
        ...
else:
    agent = SupervisorAgent(...)
    async for chunk in agent.handle(...):
        ...
```

## 功能对照表

| 功能 | 旧架构 | 新架构 |
|------|--------|--------|
| 意图分类 | IntentClassifier + AIIntentClassifier | Skills系统 |
| 执行模式 | Fast/Single/Multi | LLM自主决策 |
| 任务规划 | _plan() 方法 | LLM动态规划 |
| 反思机制 | _reflect_on_result() | 移除 (LLM自行判断) |
| 记忆集成 | 直接调用 | MemoryContextInjector |
| 人格集成 | 直接调用 | PersonalityContextInjector |
| 确认流程 | 内置 | 保留 (AgentLoop处理) |

## 性能预期

| 指标 | 旧架构 | 新架构 | 优化 |
|------|--------|--------|------|
| 简单查询 | 2-3s | 1-2s | 减少1次LLM调用 |
| 单工具调用 | 3-4s | 2-3s | 减少2次LLM调用 |
| 多步任务 | 5-8s | 3-5s | 移除强制反思 |

## 回滚方案

如果新架构出现问题：

1. 设置环境变量 `USE_V2_AGENT=false`
2. 重启服务
3. 检查日志定位问题
4. 修复后重新启用

## 常见问题

### Q: LLM决策不稳定怎么办？

A: 保留确认流程，高风险操作必须用户确认。同时可以通过优化Skills的描述来提高稳定性。

### Q: 上下文过长怎么办？

A: Skills系统支持渐进加载，只加载相关的Skills。可以调整 `max_dynamic_skills` 参数。

### Q: 如何调试新架构？

A: 启用debug日志：
```python
logging.getLogger('agent_v2').setLevel(logging.DEBUG)
```

## 迁移检查清单

- [ ] 创建Skills目录和基础Skills
- [ ] 实现Agent V2初始化函数
- [ ] 添加配置切换开关
- [ ] 测试简单对话
- [ ] 测试工具调用
- [ ] 测试确认流程
- [ ] 测试记忆集成
- [ ] 测试人格集成
- [ ] 性能对比测试
- [ ] 文档更新

## 参考文档

- [架构设计文档](./refactor-v2-design.md)
- [API参考](./api-reference.md)
- [Skills开发指南](./skills-development.md)
