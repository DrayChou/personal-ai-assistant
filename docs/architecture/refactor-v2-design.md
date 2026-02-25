# 个人AI助手架构重构方案 V2.0

## 设计理念

**"让LLM做决策，系统做支撑"**

借鉴 nanobot 的极简哲学，同时保留我们的核心优势。新架构的核心转变：
- **从"系统指挥LLM"到"LLM自主决策"**
- **从"预设流程"到"动态上下文"**
- **从"多层分类"到"统一循环"**

---

## 1. 整体架构设计

### 1.1 架构对比

```
【当前架构 - 复杂决策链】
用户输入
  ↓
IntentClassifier (规则/AI分类)
  ↓
_analyze_intent() (选择执行模式)
  ↓
_plan_single_step/multi_step() (LLM选择工具)
  ↓
执行工具
  ↓
反思检查
  ↓
输出结果

【新架构 - 极简循环】
用户输入
  ↓
ContextBuilder构建完整上下文
  ↓
AgentLoop调用LLM (附带所有工具定义)
  ↓
LLM决定使用什么工具/如何回复
  ↓
执行工具 (如有)
  ↓
工具结果返回给LLM
  ↓
LLM决定继续或回复用户
```

### 1.2 新架构模块划分

```
src/agent_v2/
├── core/
│   ├── agent_loop.py      # 核心循环 (类似nanobot loop.py)
│   ├── context_builder.py # 上下文构建 (类似nanobot context.py)
│   └── session.py         # 会话状态管理
├── skills/
│   ├── skill.py           # Skill基类
│   ├── registry.py        # Skill注册表
│   └── loader.py          # Skill加载器
├── tools/
│   ├── tool.py            # Tool基类 (简化版)
│   └── registry.py        # Tool注册表
├── memory/
│   └── context_injector.py # 记忆上下文注入
├── personality/
│   └── context_injector.py # 人格上下文注入
├── safety/
│   ├── confirmation.py    # 确认流程管理
│   └── validator.py       # 安全检查
└── types.py               # 共享类型定义
```

---

## 2. 关键组件设计

### 2.1 AgentLoop - 核心循环

**设计原则**: 极简、无状态、流式

```python
# src/agent_v2/core/agent_loop.py
"""
AgentLoop - 核心执行循环

借鉴nanobot的极简设计，一个循环处理所有交互。
"""
from typing import AsyncGenerator, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger('agent_v2.loop')


@dataclass
class LoopContext:
    """单次循环的上下文"""
    session_id: str
    user_input: str
    message_history: list[dict]  # 历史消息
    system_prompt: str          # 完整的system prompt
    available_tools: list[dict] # 可用工具定义
    iteration: int = 0          # 当前迭代次数
    max_iterations: int = 10    # 最大迭代次数


class AgentLoop:
    """
    Agent执行循环

    核心职责：
    1. 接收用户输入
    2. 构建完整上下文
    3. 调用LLM
    4. 执行工具调用
    5. 返回结果

    不负责的：
    - 意图分类 (由LLM自己决定)
    - 模式选择 (没有模式)
    - 任务规划 (LLM动态规划)
    """

    def __init__(
        self,
        llm_client,
        tool_registry,
        context_builder,
        max_iterations: int = 10,
        confirmation_handler=None,
    ):
        self.llm = llm_client
        self.tools = tool_registry
        self.context_builder = context_builder
        self.max_iterations = max_iterations
        self.confirmation = confirmation_handler
        self._pending_confirmation: Optional[dict] = None

    async def run(
        self,
        session_id: str,
        user_input: str,
        message_history: list[dict] = None,
    ) -> AsyncGenerator[str, None]:
        """
        执行一次完整的交互循环

        Args:
            session_id: 会话ID
            user_input: 用户输入
            message_history: 历史消息

        Yields:
            流式输出文本
        """
        # 检查是否有待确认的操作
        if self._pending_confirmation:
            async for chunk in self._handle_confirmation(user_input):
                yield chunk
            return

        # 构建完整上下文
        context = await self.context_builder.build(
            session_id=session_id,
            user_input=user_input,
            message_history=message_history or [],
            tools=self.tools.get_schemas(),
        )

        # 核心循环
        current_input = user_input
        for iteration in range(self.max_iterations):
            context.iteration = iteration

            # 调用LLM
            response = await self.llm.chat_completion(
                messages=self._build_messages(context, current_input),
                tools=context.available_tools,
                stream=True,
            )

            # 处理响应
            async for chunk in self._process_response(response, context):
                yield chunk

            # 检查是否需要继续迭代
            if not context.has_tool_calls:
                break

            # 执行工具调用
            tool_results = await self._execute_tools(context.tool_calls)

            # 检查是否需要确认
            if self._needs_confirmation(tool_results):
                self._pending_confirmation = {
                    'tool_results': tool_results,
                    'context': context,
                }
                yield self._format_confirmation_request(tool_results)
                return

            # 工具结果作为下一次迭代的输入
            current_input = self._format_tool_results(tool_results)

    def _build_messages(self, context: LoopContext, user_input: str) -> list[dict]:
        """构建消息列表"""
        messages = [
            {"role": "system", "content": context.system_prompt},
            *context.message_history,
        ]

        # 只在第一次迭代添加用户输入
        if context.iteration == 0:
            messages.append({"role": "user", "content": user_input})
        else:
            messages.append({"role": "user", "content": user_input})

        return messages

    async def _execute_tools(self, tool_calls: list[dict]) -> list[dict]:
        """执行工具调用"""
        results = []
        for call in tool_calls:
            try:
                result = await self.tools.execute(
                    name=call['name'],
                    arguments=call['arguments'],
                )
                results.append({
                    'tool': call['name'],
                    'success': result.success,
                    'output': result.output if result.success else result.error,
                })
            except Exception as e:
                results.append({
                    'tool': call['name'],
                    'success': False,
                    'output': f"执行失败: {str(e)}",
                })
        return results

    def _needs_confirmation(self, tool_results: list[dict]) -> bool:
        """检查是否需要用户确认"""
        for result in tool_results:
            tool_name = result['tool']
            # 高风险操作需要确认
            if any(keyword in tool_name for keyword in ['delete', 'remove', 'clean', 'drop']):
                return True
            # 检查工具返回的元数据
            if result.get('metadata', {}).get('requires_confirmation'):
                return True
        return False
```

### 2.2 ContextBuilder - 上下文构建器

**设计原则**: 模块化组装、渐进式加载

```python
# src/agent_v2/core/context_builder.py
"""
ContextBuilder - 构建完整的System Prompt

借鉴nanobot的context.py设计，模块化组装上下文。
"""
from typing import Protocol
from dataclasses import dataclass
import logging

logger = logging.getLogger('agent_v2.context')


class ContextInjector(Protocol):
    """上下文注入器协议"""

    async def inject(self, context: dict) -> str:
        """
        注入上下文片段

        Args:
            context: 构建上下文

        Returns:
            要添加到system prompt的文本
        """
        ...


@dataclass
class BuildConfig:
    """构建设置"""
    include_identity: bool = True
    include_personality: bool = True
    include_memory: bool = True
    include_skills: bool = True
    memory_limit: int = 5           # 记忆条目数限制
    skill_limit: int = 10           # 技能数限制


class ContextBuilder:
    """
    上下文构建器

    职责：
    1. 组装完整的System Prompt
    2. 管理上下文组件的加载顺序
    3. 控制上下文长度

    组件加载顺序 (按优先级)：
    1. Identity (身份定义)
    2. Personality (人格设定)
    3. Skills (技能说明)
    4. Memory (相关记忆)
    5. Tools (工具定义)
    """

    def __init__(self):
        self._injectors: list[tuple[int, ContextInjector]] = []

    def register_injector(self, injector: ContextInjector, priority: int = 50):
        """
        注册上下文注入器

        Args:
            injector: 注入器实例
            priority: 优先级 (数字越小越先加载)
        """
        self._injectors.append((priority, injector))
        self._injectors.sort(key=lambda x: x[0])

    async def build(
        self,
        session_id: str,
        user_input: str,
        message_history: list[dict],
        tools: list[dict],
        config: BuildConfig = None,
    ) -> 'LoopContext':
        """
        构建完整上下文

        Args:
            session_id: 会话ID
            user_input: 用户输入
            message_history: 历史消息
            tools: 可用工具定义
            config: 构建设置

        Returns:
            LoopContext实例
        """
        config = config or BuildConfig()

        context = {
            'session_id': session_id,
            'user_input': user_input,
            'message_history': message_history,
            'tools': tools,
            'config': config,
        }

        # 收集所有注入器的输出
        sections = []
        for priority, injector in self._injectors:
            try:
                section = await injector.inject(context)
                if section:
                    sections.append(section)
            except Exception as e:
                logger.warning(f"注入器 {injector.__class__.__name__} 失败: {e}")

        # 组装System Prompt
        system_prompt = self._assemble_prompt(sections, tools)

        from .agent_loop import LoopContext
        return LoopContext(
            session_id=session_id,
            user_input=user_input,
            message_history=message_history,
            system_prompt=system_prompt,
            available_tools=tools,
        )

    def _assemble_prompt(self, sections: list[str], tools: list[dict]) -> str:
        """组装最终的System Prompt"""
        parts = []

        # 基础身份
        parts.append("你是用户的个人AI助手，性格友好、高效、可靠。")

        # 各组件内容
        for section in sections:
            parts.append(section)

        # 工具使用说明 (简化版)
        if tools:
            parts.append("\n【可用工具】")
            parts.append("你可以使用以下工具来完成用户请求：")
            for tool in tools:
                parts.append(f"- {tool['name']}: {tool['description']}")
            parts.append("\n需要时直接调用工具，不要询问用户是否需要。")

        return "\n\n".join(parts)
```

### 2.3 Skills系统

**设计原则**: Markdown定义、渐进加载、自描述

```python
# src/agent_v2/skills/skill.py
"""
Skill系统 - 借鉴nanobot的skills.py设计

Skill = Markdown文件 + YAML frontmatter + 可选代码
"""
from dataclasses import dataclass
from typing import Optional, Callable
from pathlib import Path
import re
import yaml
import logging

logger = logging.getLogger('agent_v2.skills')


@dataclass
class SkillManifest:
    """Skill元数据"""
    name: str
    description: str
    version: str = "1.0"
    author: str = ""
    tags: list[str] = None
    always_load: bool = False  # 是否总是加载到上下文
    triggers: list[str] = None  # 触发关键词


class Skill:
    """
    Skill封装

    一个Skill包含：
    1. SKILL.md - 技能说明文档 (Markdown格式)
    2. manifest - YAML frontmatter定义的元数据
    3. 可选的代码实现

    示例SKILL.md结构：
    ```markdown
    ---
    name: task_management
    description: 管理用户的任务和待办事项
    always_load: false
    triggers: ["任务", "待办", "todo", "提醒"]
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
    """

    def __init__(self, skill_path: Path):
        self.path = skill_path
        self.manifest: Optional[SkillManifest] = None
        self.content: str = ""  # Markdown内容 (不含frontmatter)
        self._load()

    def _load(self):
        """加载Skill文件"""
        skill_file = self.path / "SKILL.md"
        if not skill_file.exists():
            raise ValueError(f"Skill文件不存在: {skill_file}")

        text = skill_file.read_text(encoding='utf-8')

        # 解析YAML frontmatter
        if text.startswith('---'):
            parts = text.split('---', 2)
            if len(parts) >= 3:
                manifest_data = yaml.safe_load(parts[1])
                self.manifest = SkillManifest(**manifest_data)
                self.content = parts[2].strip()

        if not self.manifest:
            raise ValueError(f"Skill {self.path} 缺少有效的manifest")

    def should_load(self, user_input: str) -> bool:
        """
        判断是否应该加载此Skill到上下文

        Args:
            user_input: 用户输入

        Returns:
            是否应该加载
        """
        # 总是加载的Skill
        if self.manifest.always_load:
            return True

        # 检查触发词
        if self.manifest.triggers:
            input_lower = user_input.lower()
            for trigger in self.manifest.triggers:
                if trigger.lower() in input_lower:
                    return True

        return False

    def to_context(self) -> str:
        """转换为上下文文本"""
        return f"""
## {self.manifest.name}
{self.manifest.description}

{self.content}
"""


class SkillRegistry:
    """Skill注册表"""

    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self._skills: dict[str, Skill] = {}
        self._load_all()

    def _load_all(self):
        """加载所有Skill"""
        if not self.skills_dir.exists():
            return

        for skill_dir in self.skills_dir.iterdir():
            if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                try:
                    skill = Skill(skill_dir)
                    self._skills[skill.manifest.name] = skill
                    logger.info(f"加载Skill: {skill.manifest.name}")
                except Exception as e:
                    logger.warning(f"加载Skill失败 {skill_dir}: {e}")

    def get_relevant_skills(self, user_input: str) -> list[Skill]:
        """
        获取与用户输入相关的Skills

        Args:
            user_input: 用户输入

        Returns:
            相关Skill列表
        """
        relevant = []
        for skill in self._skills.values():
            if skill.should_load(user_input):
                relevant.append(skill)
        return relevant

    def get_always_loaded(self) -> list[Skill]:
        """获取总是加载的Skills"""
        return [s for s in self._skills.values() if s.manifest.always_load]
```

### 2.4 记忆上下文注入器

```python
# src/agent_v2/memory/context_injector.py
"""
记忆上下文注入器

将三层记忆系统整合到上下文构建流程中。
"""
from typing import Optional
import logging

from ..core.context_builder import ContextInjector
from memory import MemorySystem, QueryIntent

logger = logging.getLogger('agent_v2.memory')


class MemoryContextInjector(ContextInjector):
    """
    记忆上下文注入器

    职责：
    1. 根据用户输入检索相关记忆
    2. 将记忆格式化为上下文
    3. 控制记忆长度避免溢出
    """

    def __init__(
        self,
        memory_system: MemorySystem,
        max_memories: int = 5,
        min_relevance: float = 0.7,
    ):
        self.memory = memory_system
        self.max_memories = max_memories
        self.min_relevance = min_relevance

    async def inject(self, context: dict) -> str:
        """
        注入记忆上下文

        Args:
            context: 构建上下文

        Returns:
            格式化的记忆文本
        """
        user_input = context.get('user_input', '')
        config = context.get('config', {})

        if not config.get('include_memory', True):
            return ""

        try:
            # 使用意图感知检索
            memories = await self.memory.retrieve_with_intent(
                query=user_input,
                intent=QueryIntent.FACTUAL,
                limit=self.max_memories,
                min_relevance=self.min_relevance,
            )

            if not memories:
                return ""

            # 格式化记忆
            parts = ["\n【相关记忆】"]
            for memory in memories:
                parts.append(f"- {memory.content}")

            return "\n".join(parts)

        except Exception as e:
            logger.warning(f"检索记忆失败: {e}")
            return ""
```

### 2.5 人格上下文注入器

```python
# src/agent_v2/personality/context_injector.py
"""
人格上下文注入器

将人格系统整合到上下文构建流程中。
"""
import logging

from ..core.context_builder import ContextInjector
from personality import PersonalityManager

logger = logging.getLogger('agent_v2.personality')


class PersonalityContextInjector(ContextInjector):
    """
    人格上下文注入器

    职责：
    1. 获取当前激活的人格配置
    2. 将人格设定注入上下文
    3. 整合人格专属技能
    """

    def __init__(
        self,
        personality_manager: PersonalityManager,
    ):
        self.pm = personality_manager

    async def inject(self, context: dict) -> str:
        """
        注入人格上下文

        Args:
            context: 构建上下文

        Returns:
            格式化的人格设定文本
        """
        config = context.get('config', {})
        if not config.get('include_personality', True):
            return ""

        try:
            personality = self.pm.get_current_personality()

            parts = ["\n【人格设定】"]
            parts.append(f"你正在扮演: {personality.name}")
            parts.append(f"性格特点: {personality.description}")

            # 语言风格
            if personality.speech_patterns:
                parts.append("\n语言风格:")
                for pattern in personality.speech_patterns:
                    parts.append(f"- {pattern}")

            # 专属技能
            if personality.skills:
                parts.append("\n你擅长的领域:")
                for skill in personality.skills:
                    parts.append(f"- {skill}")

            return "\n".join(parts)

        except Exception as e:
            logger.warning(f"加载人格失败: {e}")
            return ""
```

### 2.6 Skills上下文注入器

```python
# src/agent_v2/skills/context_injector.py
"""
Skills上下文注入器

将相关Skills注入到上下文中。
"""
import logging

from ..core.context_builder import ContextInjector
from .registry import SkillRegistry

logger = logging.getLogger('agent_v2.skills.injector')


class SkillsContextInjector(ContextInjector):
    """
    Skills上下文注入器

    职责：
    1. 根据用户输入选择相关Skills
    2. 总是加载的Skills优先
    3. 动态加载触发的Skills
    """

    def __init__(
        self,
        skill_registry: SkillRegistry,
        max_dynamic_skills: int = 3,
    ):
        self.registry = skill_registry
        self.max_dynamic_skills = max_dynamic_skills

    async def inject(self, context: dict) -> str:
        """
        注入Skills上下文

        Args:
            context: 构建上下文

        Returns:
            格式化的Skills文本
        """
        user_input = context.get('user_input', '')
        config = context.get('config', {})

        if not config.get('include_skills', True):
            return ""

        try:
            # 获取总是加载的Skills
            always_loaded = self.registry.get_always_loaded()

            # 获取动态触发的Skills
            relevant = self.registry.get_relevant_skills(user_input)

            # 合并并去重
            all_skills = always_loaded.copy()
            for skill in relevant:
                if skill not in all_skills:
                    all_skills.append(skill)

            # 限制数量
            all_skills = all_skills[:self.max_dynamic_skills + len(always_loaded)]

            if not all_skills:
                return ""

            # 格式化
            parts = ["\n【技能说明】"]
            for skill in all_skills:
                parts.append(skill.to_context())

            return "\n".join(parts)

        except Exception as e:
            logger.warning(f"加载Skills失败: {e}")
            return ""
```

---

## 3. 决策流程设计

### 3.1 流程对比

```
【当前流程 - 多层决策】
1. IntentClassifier (规则匹配)
   - 正则匹配 → 意图类型
   - 置信度计算

2. AIIntentClassifier (AI辅助)
   - LLM分析意图
   - 建议工具

3. _analyze_intent() (模式选择)
   - 根据意图选择 Fast/Single/Multi
   - 预设执行策略

4. _plan() (任务规划)
   - 生成执行步骤
   - 选择具体工具

5. 执行 + 反思
   - 执行工具
   - _reflect_on_result()

【新流程 - LLM自主决策】
1. ContextBuilder构建上下文
   - 整合Identity + Personality + Skills + Memory + Tools
   - 一次性构建完整System Prompt

2. AgentLoop调用LLM
   - LLM看到完整上下文
   - LLM自己决定：直接回复 / 调用工具 / 多步规划

3. 执行工具 (如有)
   - 返回结果给LLM
   - LLM决定继续或回复

4. 确认流程 (高风险操作)
   - 系统拦截高风险操作
   - 等待用户确认
```

### 3.2 为什么LLM自主决策更好

| 场景 | 当前系统 | 新架构 |
|------|----------|--------|
| "帮我查下明天的天气，如果下雨就提醒我带伞" | 意图分类→天气查询→需要二次理解条件 | LLM直接理解条件逻辑，一步完成 |
| "把昨天的任务都完成了，然后告诉我今天有什么安排" | 多步模式→先更新任务→再查询日程 | LLM自动规划两步，无需预设 |
| "这个任务不急，下周再提醒我" | 意图分类→创建任务→需要理解"不急" | LLM理解优先级，直接设置低优先级 |

### 3.3 保留的干预点

虽然让LLM自主决策，但在以下场景保留系统干预：

1. **高风险操作确认**
   - 删除、清理、修改敏感数据
   - 系统拦截，等待用户确认

2. **工具执行超时**
   - 长时间运行的工具
   - 系统提供取消选项

3. **循环检测**
   - 防止LLM陷入无限循环
   - 超过max_iterations自动停止

4. **安全过滤**
   - 输入/输出安全检查
   - 敏感信息过滤

---

## 4. 工具系统简化

### 4.1 当前工具定义 (复杂)

```python
# 当前 - 过度工程
class DeleteTaskTool(Tool):
    name = "delete_task"
    description = """
    删除指定的任务。

    使用场景：
    - 用户明确说"删除任务"
    - 用户说"清理已完成的任务"
    - 用户说"把这个任务移除"

    参数说明：
    - task_id: 要删除的任务ID
    - confirmed: 是否已确认 (高风险操作需要二次确认)

    注意事项：
    - 删除操作不可恢复
    - 如果confirmed为false，系统会请求用户确认
    - 支持批量删除，传入task_ids数组

    示例：
    {"task_id": "task_123", "confirmed": true}
    """
    parameters = [
        ToolParameter(name="task_id", type="string", description="任务ID", required=True),
        ToolParameter(name="confirmed", type="boolean", description="是否已确认", required=False, default=False),
    ]
```

### 4.2 新工具定义 (简洁)

```python
# 新架构 - 简洁自描述
class DeleteTaskTool(Tool):
    name = "delete_task"
    description = "删除指定的任务，删除前需要用户确认"
    parameters = [
        ToolParameter(name="task_id", type="string", description="要删除的任务ID"),
    ]

    async def execute(self, task_id: str) -> str:
        """
        执行删除

        Returns:
            执行结果字符串 (直接返回给LLM)
        """
        task = await self._get_task(task_id)
        if not task:
            return f"任务 {task_id} 不存在"

        # 标记需要确认
        if not self._is_confirmed():
            return f"[PENDING_CONFIRMATION] 确认删除任务 '{task.title}'?"

        await self._delete(task_id)
        return f"已删除任务: {task.title}"
```

### 4.3 工具返回简化

```python
# 当前 - 包装对象
@dataclass
class ToolResult:
    success: bool
    data: Any
    observation: str  # 给Agent反思用
    error: Optional[str]
    metadata: dict

# 新架构 - 直接字符串
# 工具直接返回字符串，LLM自己理解结果
# 特殊标记：
# - [PENDING_CONFIRMATION] 需要确认
# - [ERROR] 执行错误
# - [NEED_MORE_INFO] 需要更多信息
```

---

## 5. 实施路径

### 5.1 阶段划分

```
Phase 1: 基础设施 (1-2周)
├── 创建 agent_v2/ 目录结构
├── 实现 ContextBuilder 框架
├── 实现 Skill 系统
└── 编写迁移测试

Phase 2: 核心循环 (2周)
├── 实现 AgentLoop
├── 集成 LLM 调用
├── 实现工具执行
└── 基础确认流程

Phase 3: 系统集成 (2周)
├── 记忆系统集成
├── 人格系统集成
├── 工具迁移
└── 端到端测试

Phase 4: 灰度切换 (1周)
├── 配置开关
├── A/B测试
├── 问题修复
└── 全量切换

Phase 5: 旧系统清理 (1周)
├── 废弃旧代码
├── 文档更新
└── 监控告警
```

### 5.2 风险缓解

| 风险 | 缓解措施 |
|------|----------|
| LLM决策不稳定 | 保留确认流程，高风险操作必须确认 |
| 上下文过长 | Skills渐进加载，记忆数量限制 |
| 工具调用错误 | 完善的错误提示，LLM可重试 |
| 性能下降 | 流式输出，异步工具执行 |

### 5.3 回滚方案

```python
# 配置开关
USE_V2_AGENT = os.getenv('USE_V2_AGENT', 'false').lower() == 'true'

# 在 main.py 中
if USE_V2_AGENT:
    agent = AgentLoop(...)
else:
    agent = SupervisorAgent(...)  # 旧系统
```

---

## 6. 代码示例

### 6.1 完整使用示例

```python
# examples/v2_agent_demo.py
"""
Agent V2 使用示例
"""
import asyncio
from pathlib import Path

from src.agent_v2.core.agent_loop import AgentLoop
from src.agent_v2.core.context_builder import ContextBuilder
from src.agent_v2.skills.registry import SkillRegistry
from src.agent_v2.skills.context_injector import SkillsContextInjector
from src.agent_v2.memory.context_injector import MemoryContextInjector
from src.agent_v2.personality.context_injector import PersonalityContextInjector
from src.agent_v2.tools.registry import ToolRegistry
from memory import MemorySystem
from personality import PersonalityManager


async def main():
    # 1. 初始化组件
    llm_client = create_llm_client()

    # 2. 创建ContextBuilder
    context_builder = ContextBuilder()

    # 注册记忆注入器
    memory = MemorySystem()
    context_builder.register_injector(
        MemoryContextInjector(memory),
        priority=30
    )

    # 注册人格注入器
    personality = PersonalityManager()
    context_builder.register_injector(
        PersonalityContextInjector(personality),
        priority=20
    )

    # 注册Skills注入器
    skills = SkillRegistry(Path("./skills"))
    context_builder.register_injector(
        SkillsContextInjector(skills),
        priority=25
    )

    # 3. 创建工具注册表
    tools = ToolRegistry()
    tools.register(TaskTools())
    tools.register(MemoryTools())
    tools.register(SearchTools())

    # 4. 创建Agent
    agent = AgentLoop(
        llm_client=llm_client,
        tool_registry=tools,
        context_builder=context_builder,
        max_iterations=10,
    )

    # 5. 运行对话
    session_id = "demo_session"
    history = []

    while True:
        user_input = input("\n用户: ")
        if user_input in ['exit', 'quit']:
            break

        print("助手: ", end="", flush=True)
        response_chunks = []

        async for chunk in agent.run(
            session_id=session_id,
            user_input=user_input,
            message_history=history,
        ):
            print(chunk, end="", flush=True)
            response_chunks.append(chunk)

        # 更新历史
        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": "".join(response_chunks)})


if __name__ == "__main__":
    asyncio.run(main())
```

### 6.2 Skill定义示例

```markdown
<!-- skills/task_management/SKILL.md -->
---
name: task_management
description: 管理用户的任务和待办事项
version: "1.0"
always_load: false
triggers:
  - 任务
  - 待办
  - todo
  - 提醒
  - 计划
---

# 任务管理技能

## 功能概述
帮助用户管理日常任务和待办事项，包括创建、查询、更新和删除任务。

## 使用场景

### 创建任务
当用户说：
- "帮我创建一个任务"
- "提醒我明天开会"
- "把XXX加入待办"

使用 `create_task` 工具。

### 查询任务
当用户说：
- "我有什么任务"
- "查看待办列表"
- "今天有什么安排"

使用 `list_tasks` 工具。

### 更新任务
当用户说：
- "完成任务"
- "标记为已完成"
- "推迟到明天"

使用 `update_task` 工具。

### 删除任务
当用户说：
- "删除任务"
- "清理已完成的"
- "移除这个任务"

使用 `delete_task` 工具。
**注意：删除前必须获得用户确认。**

## 任务属性
- **title**: 任务标题 (必填)
- **description**: 详细描述 (可选)
- **due_date**: 截止日期 (可选)
- **priority**: 优先级 - high/medium/low (默认medium)
- **tags**: 标签列表 (可选)

## 最佳实践
1. 创建任务时，如果用户没有指定优先级，根据描述判断
   - "紧急"、"马上"、"今天" → high
   - "不急"、"下周"、"有空" → low
2. 查询时优先显示高优先级和即将到期的任务
3. 删除操作必须确认，告知用户删除后不可恢复
```

---

## 7. 性能预期

### 7.1 延迟优化

| 指标 | 当前系统 | 新架构 | 优化 |
|------|----------|--------|------|
| 简单查询 | 2-3s (多层分类) | 1-2s | 减少1次LLM调用 |
| 单工具调用 | 3-4s (分类+规划+执行) | 2-3s | 减少2次LLM调用 |
| 多步任务 | 5-8s (每步都有反思) | 3-5s | 移除强制反思 |

### 7.2 Token使用

| 场景 | 当前系统 | 新架构 | 说明 |
|------|----------|--------|------|
| 简单对话 | 低 | 略高 | 需要加载更多上下文 |
| 工具调用 | 高 | 中 | 减少规划阶段的LLM调用 |
| 复杂任务 | 很高 | 中 | 无强制反思，LLM自主决定 |

---

## 8. 总结

### 8.1 核心改变

1. **从预设流程到动态决策**
   - 移除三层意图分类
   - 移除 Fast/Single/Multi 模式
   - LLM根据完整上下文自主决策

2. **从系统指挥到系统支撑**
   - 系统负责构建高质量上下文
   - 系统提供工具和安全保障
   - LLM负责决策和规划

3. **从复杂定义到自描述**
   - Skills使用Markdown自描述
   - 工具定义简化
   - 渐进式上下文加载

### 8.2 保留的优势

1. **三层记忆系统** - 完整保留，更好的上下文注入
2. **人格系统** - 完整保留，通过注入器集成
3. **确认流程** - 完整保留，作为安全保障
4. **任务状态机** - 在Skill层实现，不侵入核心循环

### 8.3 预期收益

1. **响应更快** - 减少LLM调用次数
2. **更灵活** - LLM可以创造性地组合工具
3. **更易维护** - 减少决策层的复杂代码
4. **更易扩展** - 添加新Skill只需写Markdown

---

## 附录：与nanobot的对比

| 特性 | nanobot | 新架构 | 说明 |
|------|---------|--------|------|
| 核心循环 | AgentLoop | AgentLoop | 相同设计理念 |
| 上下文构建 | ContextBuilder | ContextBuilder | 相同设计理念 |
| Skills系统 | Markdown + YAML | Markdown + YAML | 相同设计理念 |
| 记忆系统 | 无 | 三层记忆 | 我们的优势 |
| 人格系统 | 无 | 完整支持 | 我们的优势 |
| 确认流程 | 无 | 高风险操作确认 | 我们的优势 |
| 中文优化 | 一般 | 专门优化 | 我们的优势 |
| 工具返回 | 字符串 | 字符串 | 相同 |
| 渐进加载 | 支持 | 支持 | 相同 |
