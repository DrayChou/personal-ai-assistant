# Agent Router 功能清单

## 系统概述

Agent Router 是一个基于 Supervisor 模式的智能体架构，支持三层执行模式（Fast Path / Single Step / Multi Step），兼容 OpenAI、MiniMax、Ollama 等多种 LLM 提供商。

---

## 核心功能

### 1. 三层执行模式

#### Fast Path (快速路径)
- **触发条件**: 简单问候（"你好"、"谢谢"等）
- **执行方式**: 本地语义路由，**无 LLM 调用**
- **延迟**: ~10-50ms
- **成本**: ¥0

#### Single Step (单步执行)
- **触发条件**: 标准工具调用请求
- **执行方式**: Function Calling 选择工具并执行
- **延迟**: ~500-1500ms
- **使用场景**: 创建任务、搜索记忆、网络搜索等

#### Multi Step (多步规划)
- **触发条件**: 复杂指令（包含"并"、"然后"、"先...再"等）
- **执行方式**: Agent 规划 → 多步执行 → 结果聚合
- **延迟**: ~1-5s
- **使用场景**: "清理任务列表并总结"、"搜索并保存"等

---

## 内置工具集 (11个)

### 记忆工具 (3个)

| 工具 | 功能 | 使用场景 |
|------|------|----------|
| `search_memory` | 搜索长期记忆 | "我之前说过什么"、"记得吗" |
| `add_memory` | 添加新记忆 | "记住我喜欢..."、"记录一下..." |
| `summarize_memories` | 总结记忆 | "总结一下关于...的记忆" |

### 任务工具 (4个)

| 工具 | 功能 | 使用场景 |
|------|------|----------|
| `create_task` | 创建任务 | "提醒我明天开会" |
| `list_tasks` | 列出任务 | "我有什么任务" |
| `complete_task` | 完成任务 | "完成任务xxx" |
| `delete_tasks` | 删除任务 | "清理所有任务"（支持确认） |

### 搜索工具 (1个)

| 工具 | 功能 | 使用场景 |
|------|------|----------|
| `web_search` | 网络搜索 | "Python 最新版本"、"今天天气" |

### 系统工具 (3个)

| 工具 | 功能 | 使用场景 |
|------|------|----------|
| `chat` | 闲聊对话 | 问候、感谢、告别 |
| `switch_personality` | 切换人格 | 切换助手性格 |
| `clear_history` | 清空历史 | 清空对话记录 |

---

## LLM 兼容性

| 提供商 | 适配器 | 工具调用方式 | 状态 |
|--------|--------|--------------|------|
| OpenAI | OpenAICompatibleAdapter | 原生 Function Calling | ✅ 完全支持 |
| MiniMax | OpenAICompatibleAdapter | 原生 Function Calling | ✅ 完全支持 |
| Ollama | OllamaAdapter | 提示工程模拟 | ✅ 支持 |

---

## 高级功能

### 记忆上下文注入
- **功能**: 自动搜索与用户输入相关的历史记忆
- **注入位置**: 系统提示
- **配置参数**:
  ```python
  enable_memory_context=True  # 开关
  context_memory_limit=5      # 注入记忆数量
  ```

### 性能监控
- **监控指标**:
  - LLM 调用次数和平均延迟
  - 各工具调用次数和成功率
  - 执行模式分布
  - 错误统计
- **API**:
  ```python
  metrics = agent.get_metrics()
  agent.reset_metrics()
  ```

### 重试机制
- **触发条件**: LLM 调用失败
- **重试策略**: 指数退避
- **配置参数**:
  ```python
  retry_attempts=3    # 最大重试次数
  retry_delay=1.0     # 基础重试间隔（秒）
  ```

### 优雅降级
- **Fast Path 失败**: 自动降级到 Single Step
- **Multi Step 失败**: 自动降级到 Single Step
- **工具调用失败**: 返回错误信息，不中断流程

---

## 配置选项

### SupervisorAgent 完整配置

```python
agent = SupervisorAgent(
    llm_client=llm_client,                  # LLM 客户端（必需）
    tool_registry=registry,                  # 工具注册表（必需）
    memory_system=memory_system,            # 记忆系统（可选）
    fast_path_classifier=classifier,        # 快速路径分类器（可选）
    max_steps=10,                           # 最大执行步数
    retry_attempts=3,                       # 重试次数
    retry_delay=1.0,                        # 重试间隔
    enable_memory_context=True,             # 启用记忆上下文
    context_memory_limit=5                  # 记忆注入数量
)
```

---

## 使用示例

### 基础使用

```python
from agent import create_agent_system

# 创建 Agent
agent = create_agent_system(
    llm_client=llm,
    memory_system=memory,
    task_manager=tasks
)

# 处理用户输入
async for output in agent.handle("提醒我明天下午3点开会", "session_001"):
    print(output, end='')
```

### 处理确认流程

```python
async for output in agent.handle("清理所有任务", "session_001"):
    if isinstance(output, dict) and output.get("type") == "need_input":
        # 需要用户确认
        confirm = input(f"{output['prompt']} ")
        async for confirm_output in agent.continue_with_input(confirm, agent._current_context):
            print(confirm_output, end='')
    else:
        print(output, end='')
```

### 获取性能指标

```python
# 执行一些操作后...
metrics = agent.get_metrics()
print(f"LLM 调用: {metrics['llm_calls']} 次")
print(f"平均延迟: {metrics['llm_avg_latency']:.3f}s")
print(f"工具使用: {metrics['tool_usage']}")
```

---

## 性能指标

### 延迟估算

| 路径 | 延迟 | 成本 |
|------|------|------|
| Fast Path | ~10-50ms | ¥0 |
| Single Step | ~500-1500ms | ~¥0.01 |
| Multi Step | ~1-5s | ~¥0.03/步 |

### 优化建议
1. **启用 Fast Path**: 减少简单查询的 LLM 调用
2. **合理设置 max_steps**: 避免无限循环
3. **调整 context_memory_limit**: 平衡上下文质量和 Token 消耗

---

## 故障排查

### 常见问题

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| LLM 调用失败 | API 密钥错误 | 检查 api_key 配置 |
| 工具选择错误 | 描述不清晰 | 检查工具 description |
| 记忆未注入 | memory_system 未传入 | 检查初始化参数 |
| 确认流程无响应 | 未处理 need_input | 检查 handle() 返回值类型 |

### 调试模式

```python
import logging
logging.getLogger('agent').setLevel(logging.DEBUG)
```

---

## 版本历史

| 版本 | 日期 | 主要更新 |
|------|------|----------|
| v1.0 | 2025-02-24 | 初始版本，基础架构 |
| v1.1 | 2025-02-24 | 添加 LLM 适配器，解决兼容性问题 |
| v1.2 | 2025-02-24 | 添加记忆上下文注入、性能监控、增强工具描述 |

---

*文档版本: v1.2*
*最后更新: 2025-02-24*
