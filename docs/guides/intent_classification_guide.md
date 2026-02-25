# 意图分类系统指南

## 概述

本项目使用 **Semantic Router** 作为主要意图分类方案，相比传统的正则匹配和 LLM 调用，具有以下优势：

- **毫秒级响应**: 使用向量语义相似度，无需调用 LLM，平均延迟约 11ms
- **语义理解**: 比正则匹配更准确，能理解语义相似的表达
- **低成本**: 使用本地 Ollama embedding，无需付费 API
- **智能回退**: 低置信度时自动回退到 LLM 进行更精确分析

## 架构设计

```
用户输入
    |
    v
Semantic Router (向量语义路由)
    |
    +-- 高置信度 (>0.7) --> 直接返回意图
    |
    +-- 中置信度 (0.4-0.7) --> 返回意图（可能触发工具调用）
    |
    +-- 低置信度 (<0.4) --> 回退到 LLM Function Calling
    |
    v
ActionRouter --> 对应 Handler --> 执行操作
```

### 三层分类策略

| 层级 | 方案 | 延迟 | 成本 | 准确率 | 适用场景 |
|------|------|------|------|--------|----------|
| 第一层 | Semantic Router | ~11ms | 低 | 高 | 常见意图快速匹配 |
| 第二层 | LLM Fallback | ~500ms | 高 | 极高 | 复杂/模糊输入 |
| 第三层 | Rule-based | <1ms | 无 | 中 | 简单模式匹配 |

## 使用方法

### 基础用法

```python
from chat.semantic_router import SemanticIntentRouter
from chat.intent_classifier import IntentType

# 创建路由器
router = SemanticIntentRouter(
    encoder_type="ollama",
    ollama_base_url="http://localhost:11434",
    ollama_model="nomic-embed-text"
)

# 分类意图
intent = router.classify("今天天气怎么样")
print(intent.intent_type)  # IntentType.WEATHER
print(intent.confidence)   # 0.85
```

### 带 LLM 回退

```python
from chat.llm_client import LLMClient

# 创建带 LLM 回退的路由器
llm = LLMClient()
router = SemanticIntentRouter(
    encoder_type="ollama",
    llm_fallback=llm.chat,  # 低置信度时回退到 LLM
    threshold=0.7
)

# 自动处理回退
intent = router.classify("那个...帮我查一下...")
# 如果语义路由置信度低，会自动使用 LLM 进行分类
```

### 在 ActionRouter 中使用

```python
from chat.action_router import ActionRouter
from chat.semantic_router import SemanticIntentRouter

# 创建语义路由器
semantic_router = SemanticIntentRouter()

# 创建 Action Router
action_router = ActionRouter(
    intent_classifier=semantic_router  # 使用语义路由器
)

# 处理用户输入
response = action_router.route("添加一个任务：明天开会")
```

## 配置选项

### 环境变量

在 `.env` 文件中配置:

```bash
# Semantic Router 配置（推荐）
USE_SEMANTIC_ROUTER=true

# Ollama Embedding 配置
EMBEDDING_BASE_URL=http://localhost:11434
EMBEDDING_MODEL=nomic-embed-text

# 置信度阈值
SEMANTIC_ROUTER_THRESHOLD=0.7

# LLM 回退（可选）
USE_AI_INTENT=true
```

### 代码配置

```python
router = SemanticIntentRouter(
    # Encoder 类型: "openai", "huggingface", "fastembed", "ollama"
    encoder_type="ollama",

    # Ollama 配置
    ollama_base_url="http://localhost:11434",
    ollama_model="nomic-embed-text",

    # LLM 回退函数
    llm_fallback=my_llm_chat_function,

    # 置信度阈值
    threshold=0.7
)
```

## 支持的意图类型

### 对话交互类
- `CHAT` - 闲聊/问候/寒暄
- `THANKS` - 感谢/反馈
- `GOODBYE` - 结束对话

### 任务管理类
- `CREATE_TASK` - 创建任务/待办
- `QUERY_TASK` - 查询任务列表
- `UPDATE_TASK` - 更新任务状态
- `DELETE_TASK` - 删除任务

### 信息查询类
- `SEARCH` - 搜索信息
- `WEATHER` - 查询天气
- `NEWS` - 查询新闻
- `CALCULATE` - 计算/换算
- `TRANSLATE` - 翻译

### 记忆管理类
- `CREATE_MEMORY` - 记录信息
- `QUERY_MEMORY` - 查询记忆
- `SUMMARIZE` - 总结归纳

### 系统控制类
- `CLEAR_HISTORY` - 清空历史
- `SWITCH_PERSONALITY` - 切换性格

## 扩展意图

### 添加新意图

在 `semantic_router.py` 中添加:

```python
class SemanticIntentRouter:
    INTENT_ROUTES = {
        # 添加新意图
        IntentType.NEW_INTENT: [
            "示例语句1",
            "示例语句2",
            "示例语句3",
        ],
        # ...
    }

    TOOL_REQUIRED_INTENTS = {
        # 如果需要工具
        IntentType.NEW_INTENT,
    }

    INTENT_TO_TOOLS = {
        # 映射到工具
        IntentType.NEW_INTENT: ["new_intent_tool"],
    }
```

### 最佳实践

1. **示例语句质量**: 每个意图至少 5-10 个多样化示例
2. **语义覆盖**: 示例应覆盖不同表达方式
3. **避免重叠**: 不同意图的示例应有明显语义差异
4. **定期更新**: 根据用户反馈持续优化示例

## 性能指标

### 响应时间

| 方案 | P50 | P95 | P99 |
|------|-----|-----|-----|
| Semantic Router | 11ms | 15ms | 25ms |
| AI Intent Classifier | 500ms | 800ms | 1200ms |
| Rule-based | <1ms | <1ms | <1ms |

### 准确率

- **常见意图 (>90%)**: CHAT, CREATE_TASK, SEARCH, WEATHER
- **中等意图 (80-90%)**: QUERY_TASK, TRANSLATE, CALCULATE
- **复杂意图 (<80%)**: 需要上下文的意图，自动回退到 LLM

### 成本

- **Semantic Router**: 本地 Ollama，几乎零成本
- **LLM Fallback**: 约 10-20% 的请求需要回退
- **总体节省**: 相比纯 LLM 方案节省 80%+ API 成本

## 与旧方案对比

### AIIntentClassifier (已弃用)

```python
# 旧方案 - 不推荐
from chat.ai_intent_classifier import AIIntentClassifier

classifier = AIIntentClassifier(llm_client=llm.chat)
intent = classifier.classify("今天天气怎么样")
# 延迟: ~500ms，每次调用都消耗 API
```

**弃用原因**:
- 延迟高 (~500ms vs ~11ms)
- 成本高 (每次调用 LLM API)
- 无语义理解 (依赖 LLM 解释)

**保留用途**:
- Semantic Router 置信度 < 0.4 时的回退
- 复杂多意图检测
- 需要深度上下文分析的场景

### 迁移指南

```python
# Before (旧代码)
from chat.ai_intent_classifier import AIIntentClassifier
from chat.llm_client import LLMClient

llm = LLMClient()
classifier = AIIntentClassifier(llm_client=llm.chat)
intent = classifier.classify(text)

# After (新代码)
from chat.semantic_router import SemanticIntentRouter
from chat.llm_client import LLMClient

llm = LLMClient()
router = SemanticIntentRouter(llm_fallback=llm.chat)
intent = router.classify(text)
```

## 故障排查

### Semantic Router 返回 UNKNOWN

**原因**: 置信度低于阈值

**解决**:
1. 检查示例语句是否覆盖该表达
2. 降低 `threshold` 参数
3. 启用 LLM 回退

### Ollama 连接失败

**错误**: `Ollama embedding 失败`

**解决**:
1. 确认 Ollama 服务运行: `ollama serve`
2. 下载 embedding 模型: `ollama pull nomic-embed-text`
3. 检查 `EMBEDDING_BASE_URL` 配置

### 置信度异常低

**原因**: 示例语句不足或质量差

**解决**:
1. 增加 `INTENT_ROUTES` 中的示例
2. 确保示例语义多样化
3. 检查 embedding 模型是否正常

## 附录

### 意图优先级设计

```python
INTENT_PRIORITY = {
    # 高优先级：系统级操作
    'CLEAR_HISTORY': 10,
    'SWITCH_PERSONALITY': 9,

    # 中高优先级：时间敏感
    'SET_REMINDER': 8,
    'TIMER': 8,

    # 中优先级：任务相关
    'CREATE_TASK': 6,
    'UPDATE_TASK': 6,
    'QUERY_TASK': 5,

    # 普通优先级：信息查询
    'SEARCH': 4,
    'WEATHER': 4,

    # 低优先级：闲聊
    'CHAT': 1,
}
```

### 意图与实体关系

| 意图类型 | 关键实体 | 示例 |
|---------|---------|------|
| CREATE_TASK | content, due_date, priority | "明天下午3点完成报告" |
| SET_REMINDER | trigger_time, content | "10分钟后提醒我" |
| WEATHER | location, date | "北京明天天气怎么样" |
| TRANSLATE | source_text, target_language | "把这句话翻译成英文" |

### 参考资料

- [Semantic Router 官方文档](https://github.com/aurelio-labs/semantic-router)
- [Ollama Embedding 模型](https://ollama.ai/library/nomic-embed-text)
- [意图分类最佳实践](./agent-router-implementation-guide-v2.md)
