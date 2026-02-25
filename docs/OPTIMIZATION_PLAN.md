# Personal AI Assistant 优化计划

**版本**: v1.0
**日期**: 2026-02-25
**基于**: demo 目录下 4 个项目的对比分析

---

## 一、优化目标

### 1.1 总体目标

| 维度 | 当前状态 | 目标状态 | 提升 |
|------|---------|---------|------|
| **开发效率** | 工具开发需要样板代码 | 装饰器一键注册 | 80% ↑ |
| **系统稳定性** | 单点故障风险 | 多级 Fallback | 99.9% SLA |
| **Token 效率** | 固定上下文窗口 | 动态压缩 + 分层加载 | 50% ↓ |
| **可扩展性** | 单一 CLI 入口 | 多平台适配器 | +5 平台 |

### 1.2 核心改进方向

1. **简化工具开发** - 引入装饰器注册机制
2. **增强记忆系统** - Token 感知压缩 + Fallback 降级
3. **提升系统稳定性** - LLM/Memory 多级 Fallback
4. **扩展输出渠道** - 多平台适配器架构

---

## 二、Phase 0: 基础增强 (1周)

### P0-1: 装饰器工具注册 🔴 高优先级

**问题**: 当前工具开发需要创建 Tool 子类，样板代码多

**借鉴**: mini-agent-assistant 的 `@tool()` 装饰器

**实现方案**:

```python
# 新文件: src/agent/tools/decorators.py

from functools import wraps
import inspect
from typing import Callable, Any
from .base import Tool, ToolParameter, ToolResult

def tool(
    name: str = None,
    description: str = None,
    timeout: float = 30.0
):
    """装饰器: 将函数转换为工具

    Example:
        @tool(description="搜索网络信息")
        async def web_search(query: str, num_results: int = 5) -> str:
            '''搜索网络

            Args:
                query: 搜索关键词
                num_results: 返回结果数量
            '''
            ...
    """
    def decorator(func: Callable):
        # 自动提取函数签名
        sig = inspect.signature(func)
        params = _extract_parameters(sig)

        # 自动提取描述
        desc = description or _extract_description(func)

        # 创建 Tool 类
        class DecoratedTool(Tool):
            def __init__(self):
                self.name = name or func.__name__
                self.description = desc
                self.parameters = params
                self._func = func
                self._timeout = timeout

            async def execute(self, **kwargs) -> ToolResult:
                try:
                    result = await self._func(**kwargs)
                    return ToolResult(
                        success=True,
                        data={"result": result},
                        observation=str(result)
                    )
                except Exception as e:
                    return ToolResult(
                        success=False,
                        observation=f"执行失败: {e}",
                        error=str(e)
                    )

        DecoratedTool.__name__ = func.__name__
        return DecoratedTool()

    return decorator

def _extract_parameters(sig: inspect.Signature) -> list[ToolParameter]:
    """从函数签名提取参数定义"""
    params = []
    for name, param in sig.parameters.items():
        param_type = _python_type_to_json(param.annotation)
        required = param.default == inspect.Parameter.empty

        params.append(ToolParameter(
            name=name,
            type=param_type,
            description=f"参数 {name}",
            required=required,
            default=param.default if not required else None
        ))
    return params

def _extract_description(func: Callable) -> str:
    """从 docstring 提取描述"""
    doc = func.__doc__ or ""
    # 取第一行作为描述
    return doc.strip().split('\n')[0]
```

**文件变更**:
- 新增: `src/agent/tools/decorators.py`
- 修改: `src/agent/tools/__init__.py` (导出装饰器)
- 新增: `tests/test_tool_decorators.py`

**验收标准**:
- [ ] `@tool()` 装饰器可正常工作
- [ ] 自动从函数签名生成参数 schema
- [ ] 支持 async 和 sync 函数
- [ ] 测试覆盖率 > 90%

---

### P0-2: Token 感知上下文压缩 🔴 高优先级

**问题**: 当前 WorkingMemory 缺少 Token 感知，可能导致上下文溢出

**借鉴**: mini-agent-assistant 的 Memory 类

**实现方案**:

```python
# 修改文件: src/memory/working_memory.py

# 新增常量
DEFAULT_MAX_TOKENS = 8000
TOKEN_ESTIMATE_RATIO = 0.5  # 中文约 0.5 tokens/char
SUMMARY_TRIGGER_RATIO = 0.8  # 80% 触发压缩

def estimate_tokens(text: str) -> int:
    """估算文本 Token 数量"""
    if not text:
        return 0
    # 中文约 0.5 tokens/char，英文约 0.25 tokens/char
    char_count = len(text)
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    english_chars = char_count - chinese_chars
    return int(chinese_chars * 0.5 + english_chars * 0.25)

class WorkingMemory:
    def __init__(
        self,
        max_messages: int = 50,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        enable_compression: bool = True
    ):
        self.max_messages = max_messages
        self.max_tokens = max_tokens
        self.enable_compression = enable_compression
        self._summary: str = ""  # 历史对话摘要

    def add(self, role: str, content: str):
        """添加消息（带 Token 感知）"""
        super().add(role, content)
        self._manage_context()

    def _manage_context(self) -> None:
        """管理上下文，防止超出 Token 限制"""
        total_tokens = self._calculate_total_tokens()

        if total_tokens <= self.max_tokens * SUMMARY_TRIGGER_RATIO:
            # 只应用消息数量限制
            self._trim_by_count()
            return

        # 需要压缩上下文
        if self.enable_compression:
            self._compress_context()
        else:
            self._trim_by_count()

    def _compress_context(self) -> None:
        """压缩上下文：对旧消息生成摘要"""
        system_msgs = [m for m in self.messages if m.role == "system"]
        other_msgs = [m for m in self.messages if m.role != "system"]

        if len(other_msgs) <= 5:
            return

        # 保留最近 5 条完整消息
        recent_msgs = other_msgs[-5:]
        old_msgs = other_msgs[:-5]

        # 对旧消息生成摘要（简单关键词提取）
        topics = self._extract_topics(old_msgs)
        if topics:
            new_summary = f"之前的对话涉及: {', '.join(topics)}"
            self._summary = f"{self._summary}; {new_summary}" if self._summary else new_summary

        self.messages = system_msgs + recent_msgs

    def get_context_with_summary(self) -> list[dict]:
        """获取带摘要的上下文"""
        messages = [m.to_dict() for m in self.messages]

        if self._summary:
            # 插入摘要
            summary_msg = {
                "role": "system",
                "content": f"[历史对话摘要] {self._summary}"
            }
            # 插入到第一个 system 消息之后
            for i, m in enumerate(messages):
                if m["role"] == "system":
                    messages.insert(i + 1, summary_msg)
                    break

        return messages
```

**文件变更**:
- 修改: `src/memory/working_memory.py`
- 新增: `tests/test_token_compression.py`

**验收标准**:
- [ ] Token 估算准确率 > 80%
- [ ] 80% 阈值触发压缩
- [ ] 摘要保留关键信息
- [ ] 测试覆盖率 > 90%

---

### P0-3: 记忆系统 Fallback 机制 🔴 高优先级

**问题**: 当主存储不可用时，系统可能崩溃

**借鉴**: viking-assistant 的 FallbackMemoryClient

**实现方案**:

```python
# 修改文件: src/memory/memory_system.py

class MemorySystem:
    """增强版记忆系统，支持 Fallback"""

    def __init__(self, config: MemoryConfig = None):
        self.config = config or MemoryConfig()
        self._primary_client = None
        self._fallback_client = None
        self._using_fallback = False

    def _ensure_client(self):
        """确保有可用的存储客户端"""
        if self._primary_client is not None:
            return

        try:
            # 尝试主存储
            self._primary_client = self._create_primary_client()
            logger.info("使用主存储: SQLite + sqlite-vec")
        except Exception as e:
            logger.warning(f"主存储初始化失败: {e}，启用 Fallback")
            self._fallback_client = self._create_fallback_client()
            self._using_fallback = True

    def _create_fallback_client(self):
        """创建降级客户端（简单文件存储）"""
        return FallbackMemoryClient(self.config.data_dir / "fallback")

    def recall(self, query: str, top_k: int = 5) -> str:
        """搜索记忆（带 Fallback）"""
        self._ensure_client()

        if self._using_fallback:
            return self._fallback_client.search(query, top_k)

        try:
            return self._primary_client.search(query, top_k)
        except Exception as e:
            logger.warning(f"主存储查询失败: {e}，临时使用 Fallback")
            return self._fallback_client.search(query, top_k)


class FallbackMemoryClient:
    """降级记忆客户端 - 简单文件存储"""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def add(self, content: str, metadata: dict = None) -> str:
        """添加记忆"""
        memory_id = str(uuid.uuid4())[:8]
        file_path = self.data_dir / f"{memory_id}.json"

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump({
                "id": memory_id,
                "content": content,
                "metadata": metadata or {},
                "created_at": datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)

        return memory_id

    def search(self, query: str, top_k: int = 5) -> str:
        """简单搜索（关键词匹配）"""
        results = []
        query_lower = query.lower()

        for file_path in self.data_dir.glob("*.json"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                content = data.get("content", "")
                if query_lower in content.lower():
                    results.append(content)
                    if len(results) >= top_k:
                        break
            except Exception:
                continue

        return "\n---\n".join(results) if results else ""
```

**文件变更**:
- 修改: `src/memory/memory_system.py`
- 新增: `src/memory/fallback_client.py`
- 新增: `tests/test_memory_fallback.py`

**验收标准**:
- [ ] 主存储失败时自动切换 Fallback
- [ ] Fallback 支持基本的 CRUD
- [ ] 日志记录切换事件
- [ ] 测试覆盖率 > 90%

---

## 三、Phase 1: 架构增强 (2周)

### P1-1: 统一 MCP 管理 🟡 中优先级

**问题**: 当前 MCP 集成分散，缺少统一管理

**借鉴**: mini-agent-assistant 的 MCPManager

**实现方案**:

```python
# 新文件: src/tools/mcp_manager.py

class MCPToolManager:
    """统一 MCP 工具管理器"""

    PRESET_SERVERS = {
        "brave-search": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-brave-search"],
            "env": {"BRAVE_API_KEY": "${BRAVE_API_KEY}"}
        },
        "github": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": {"GITHUB_TOKEN": "${GITHUB_TOKEN}"}
        },
        "filesystem": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "${WORKSPACE}"]
        }
    }

    def __init__(self):
        self.clients: dict[str, MCPClient] = {}
        self.all_tools: list[MCPTool] = []

    def load_from_config(self, config_path: str) -> int:
        """从配置文件加载 MCP 服务器"""
        with open(config_path) as f:
            config = json.load(f)

        loaded = 0
        for name, server_config in config.get("mcpServers", {}).items():
            try:
                client = MCPClient(server_config)
                self.clients[name] = client
                self.all_tools.extend(client.list_tools())
                loaded += 1
            except Exception as e:
                logger.warning(f"加载 MCP 服务器 {name} 失败: {e}")

        return loaded

    def load_presets(self, presets: list[str]) -> int:
        """加载预设服务器"""
        loaded = 0
        for name in presets:
            if name in self.PRESET_SERVERS:
                config = self._resolve_env_vars(self.PRESET_SERVERS[name])
                try:
                    client = MCPClient(config)
                    self.clients[name] = client
                    self.all_tools.extend(client.list_tools())
                    loaded += 1
                except Exception as e:
                    logger.warning(f"加载预设 {name} 失败: {e}")
        return loaded

    def to_openai_schemas(self) -> list[dict]:
        """转换为 OpenAI Function Schema"""
        return [tool.to_schema() for tool in self.all_tools]

    def execute(self, name: str, arguments: dict) -> str:
        """执行 MCP 工具"""
        for client in self.clients.values():
            if client.has_tool(name):
                return client.call_tool(name, arguments)
        raise ValueError(f"MCP 工具未找到: {name}")
```

**文件变更**:
- 新增: `src/tools/mcp_manager.py`
- 修改: `src/agent/supervisor.py` (集成 MCPManager)
- 新增: `config/mcp_presets.json`

**验收标准**:
- [ ] 支持 JSON 配置加载
- [ ] 支持预设服务器快速启用
- [ ] 统一的 OpenAI Schema 输出
- [ ] 测试覆盖率 > 80%

---

### P1-2: 多平台适配器架构 🟡 中优先级

**问题**: 当前只有 CLI 入口，缺少多平台支持

**借鉴**: dev-assistant-demo 的适配器架构

**实现方案**:

```
src/channels/
├── __init__.py          # 工厂函数
├── base.py              # 基类定义
├── console.py           # 控制台适配器
├── telegram.py          # Telegram 适配器
├── discord.py           # Discord 适配器
└── feishu.py            # 飞书适配器
```

```python
# src/channels/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, AsyncGenerator

@dataclass
class ChatMessage:
    """统一消息格式"""
    chat_id: str
    user_id: str
    content: str
    metadata: dict = None

@dataclass
class ChatResponse:
    """统一响应格式"""
    content: str
    success: bool = True
    metadata: dict = None

class ChannelAdapter(ABC):
    """渠道适配器基类"""

    def __init__(self, config: dict):
        self.config = config
        self._message_handlers: list[Callable] = []

    @abstractmethod
    async def start(self):
        """启动适配器"""
        pass

    @abstractmethod
    async def stop(self):
        """停止适配器"""
        pass

    @abstractmethod
    async def send_message(self, chat_id: str, content: str):
        """发送消息"""
        pass

    def on_message(self, handler: Callable[[ChatMessage], AsyncGenerator[str, None]]):
        """注册消息处理器"""
        self._message_handlers.append(handler)

    async def _dispatch_message(self, message: ChatMessage):
        """分发消息到处理器"""
        for handler in self._message_handlers:
            async for chunk in handler(message):
                await self.send_message(message.chat_id, chunk)


# src/channels/__init__.py

def get_channel(name: str, config: dict) -> ChannelAdapter:
    """工厂函数: 获取渠道适配器"""
    channels = {
        "console": ConsoleAdapter,
        "telegram": TelegramAdapter,
        "discord": DiscordAdapter,
        "feishu": FeishuAdapter,
    }

    adapter_class = channels.get(name)
    if adapter_class is None:
        raise ValueError(f"不支持的渠道: {name}")

    return adapter_class(config)
```

**文件变更**:
- 新增: `src/channels/` 目录
- 新增: `src/channels/base.py`
- 新增: `src/channels/console.py`
- 新增: `src/channels/telegram.py` (骨架)
- 修改: `src/main.py` (支持渠道选择)

**验收标准**:
- [ ] ConsoleAdapter 完整实现
- [ ] TelegramAdapter 基本功能
- [ ] 统一消息格式
- [ ] 测试覆盖率 > 70%

---

### P1-3: LLM Provider Fallback 🟡 中优先级

**问题**: 当前 LLM Adapter 缺少 Fallback 机制

**借鉴**: dev-assistant-demo 的 AIEngine

**实现方案**:

```python
# 修改文件: src/agent/llm_adapter.py

@dataclass
class LLMConfig:
    """LLM 配置"""
    provider: str = "openai"
    api_key: str = None
    base_url: str = None
    model: str = "gpt-4o-mini"

    # Fallback 配置
    fallback_enabled: bool = False
    fallback_provider: str = "ollama"
    fallback_base_url: str = "http://localhost:11434"
    fallback_model: str = "qwen2.5:14b"


class LLMAdapter:
    """增强版 LLM 适配器，支持 Fallback"""

    def __init__(self, config: LLMConfig):
        self.config = config
        self._primary = self._create_provider(
            config.provider,
            config.api_key,
            config.base_url,
            config.model
        )

        self._fallback = None
        if config.fallback_enabled:
            self._fallback = self._create_provider(
                config.fallback_provider,
                None,  # 本地模型无需 API Key
                config.fallback_base_url,
                config.fallback_model
            )

    async def generate(
        self,
        messages: list[dict],
        stream: bool = False,
        **kwargs
    ) -> str | AsyncGenerator:
        """生成响应（带 Fallback）"""
        try:
            return await self._call_primary(messages, stream, **kwargs)
        except Exception as e:
            logger.warning(f"主 LLM 调用失败: {e}")
            if self._fallback:
                logger.info("切换到 Fallback LLM")
                return await self._call_fallback(messages, stream, **kwargs)
            raise

    async def _call_primary(self, messages, stream, **kwargs):
        """调用主 LLM"""
        if stream:
            return self._primary.stream_chat(messages, **kwargs)
        return await self._primary.chat(messages, **kwargs)

    async def _call_fallback(self, messages, stream, **kwargs):
        """调用 Fallback LLM"""
        if stream:
            return self._fallback.stream_chat(messages, **kwargs)
        return await self._fallback.chat(messages, **kwargs)
```

**文件变更**:
- 修改: `src/agent/llm_adapter.py`
- 修改: `src/config/settings.py` (添加 Fallback 配置)
- 新增: `tests/test_llm_fallback.py`

**验收标准**:
- [ ] 主 LLM 失败时自动切换 Fallback
- [ ] 支持 OpenAI → Ollama 切换
- [ ] 日志记录切换事件
- [ ] 测试覆盖率 > 80%

---

## 四、Phase 2: 功能增强 (1-2周)

### P2-1: Session Notes 功能 🟢 低优先级

**借鉴**: mini-agent-assistant 的 SessionNotes

**实现方案**:

```python
# 新文件: src/notes/manager.py

@dataclass
class Note:
    id: str
    title: str
    content: str
    created_at: str
    updated_at: str

class SessionNotes:
    """跨会话笔记管理器"""

    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path or str(
            Path.home() / ".personal-assistant" / "notes.json"
        )
        self.notes: dict[str, Note] = {}
        self._load()

    def create(self, title: str, content: str) -> Note:
        """创建笔记"""
        note_id = str(uuid.uuid4())[:8]
        note = Note(
            id=note_id,
            title=title,
            content=content,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        self.notes[note_id] = note
        self._save()
        return note

    def search(self, keyword: str) -> list[Note]:
        """搜索笔记"""
        keyword = keyword.lower()
        return [
            note for note in self.notes.values()
            if keyword in note.title.lower() or keyword in note.content.lower()
        ]
```

**工具集成**:

```python
@tool(description="创建跨会话笔记")
def create_note(title: str, content: str) -> str:
    """创建一条笔记，在后续会话中可用"""
    ...

@tool(description="搜索笔记")
def search_notes(keyword: str) -> str:
    """搜索之前创建的笔记"""
    ...
```

---

### P2-2: 记忆生命周期管理 🟢 低优先级

**借鉴**: dev-assistant-demo 的 P0/P1/P2 优先级

**实现方案**:

```python
@dataclass
class MemoryEntry:
    content: str
    priority: str = "P1"  # P0=永久, P1=90天, P2=30天
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)

    def decay_weight(self) -> float:
        """基于艾宾浩斯遗忘曲线计算权重衰减"""
        days = (datetime.now() - self.last_accessed).days

        if self.priority == "P0":
            return 1.0  # 永不衰减
        elif self.priority == "P1":
            return max(0.1, 2 ** (-days / 30))  # 30天半衰
        else:  # P2
            return max(0.05, 2 ** (-days / 7))  # 7天半衰

    def should_archive(self) -> bool:
        """是否应该归档"""
        return self.decay_weight() < 0.1
```

---

## 五、实施计划

### 5.1 时间线

```
Week 1: P0-1 装饰器工具注册 + P0-2 Token 压缩
Week 2: P0-3 记忆 Fallback + P1-1 MCP 管理
Week 3: P1-2 多平台适配器 + P1-3 LLM Fallback
Week 4: P2-1 Session Notes + 测试完善
```

### 5.2 里程碑

| 里程碑 | 时间 | 交付物 |
|--------|------|--------|
| **M1** | Week 1 结束 | 装饰器工具 + Token 压缩 |
| **M2** | Week 2 结束 | Fallback 机制 + MCP 管理 |
| **M3** | Week 3 结束 | 多平台适配器 + LLM Fallback |
| **M4** | Week 4 结束 | Session Notes + 全部测试 |

### 5.3 资源需求

| 资源 | 用途 |
|------|------|
| 开发时间 | 约 4 周 |
| API Key | Brave Search, GitHub Token (可选) |
| 服务器 | Telegram/Discord Bot 托管 (可选) |

---

## 六、风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| LLM API 变更 | 高 | 抽象层隔离，快速适配 |
| 第三方库依赖 | 中 | 版本锁定，备用方案 |
| Token 估算不准 | 中 | 多种估算算法，动态调整 |
| 多平台适配复杂 | 中 | 优先实现核心平台 |

---

## 七、验收标准

### 7.1 功能验收

- [ ] 所有 P0 功能完成并测试通过
- [ ] 所有 P1 功能完成并测试通过
- [ ] 测试覆盖率 > 80%
- [ ] 文档更新完成

### 7.2 性能验收

- [ ] 工具注册时间 < 100ms
- [ ] Token 压缩准确率 > 80%
- [ ] Fallback 切换时间 < 1s
- [ ] 内存使用 < 200MB

### 7.3 质量验收

- [ ] Ruff 检查全部通过
- [ ] Mypy 类型检查通过
- [ ] 无高危安全问题
- [ ] 代码评审通过

---

*计划创建时间: 2026-02-25*
*计划负责人: AI Assistant*
