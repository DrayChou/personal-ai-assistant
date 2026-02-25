# 架构问题综合分析报告

## 核心结论

你的感觉是对的。当前系统相比 nanobot 存在**架构过度设计**问题，导致体验"死板"。

---

## 根本差异

| 维度 | nanobot | 当前系统 |
|------|---------|----------|
| **代码量** | ~4000行全部 | ~3000行仅核心流程 |
| **决策层级** | 2层 (输入→执行) | 5层 (输入→分析→规划→执行→反思) |
| **LLM调用** | 0-1次/请求 | 1-3次/请求 |
| **决策方式** | 规则匹配 (确定性) | LLM选择 (概率性) |
| **响应延迟** | <100ms | 500ms-2s |

---

## 发现的核心问题

### 1. 过度依赖LLM做决策 ❌

**当前系统流程**：
```
用户说"清理任务"
  ↓
_analyze_intent() → 识别为 SINGLE_STEP
  ↓
_plan_single_step() → 调用LLM选择工具
  ↓
LLM: "用 list_tasks 吧" (可能选错)
  ↓
_reflect_on_result() → 检测到错误
  ↓
直接切换到 delete_tasks
```

**问题**：
- 明确的指令还要让LLM选，本身就是问题
- 提示词写了"必须使用 delete_tasks"，但LLM仍可能选错
- 反思机制是**事后补救**，不是正确设计

**nanobot方式**：
```
用户说"清理任务"
  ↓
规则匹配: "清理" in 输入 → delete_tasks
  ↓
直接执行
```

### 2. 三层执行模式实际上退化为单层 ❌

**代码分析** (`supervisor.py`):
- `FAST_PATH`: 只处理"你好"等简单问候
- `SINGLE_STEP`: 90%请求走这里，但仍要LLM选择工具
- `MULTI_STEP`: 极少使用，维护成本高

**结论**：三层模式增加了复杂性，没有带来实际收益。

### 3. 工具注册表过度抽象 ❌

**当前系统**：
```python
class ListTasksTool(Tool):  # 继承基类
    name = "list_tasks"
    description = "..."  # 500字描述
    parameters = [ToolParameter(...), ...]  # 定义参数

    async def execute(self, ...) -> ToolResult:  # 包装结果
        ...
        return ToolResult(success=True, data=..., observation=...)
```

**调用链**：
用户输入 → LLM → 生成JSON → 解析 → Registry查询 → Tool.execute() → 包装结果

**nanobot方式**：
```python
def list_tasks():  # 普通函数
    tasks = db.query(...)
    return format_tasks(tasks)  # 直接返回可读文本

HANDLERS = {
    "query_tasks": list_tasks,  # 直接映射
}
```

### 4. 意图层过度设计 ❌

**当前系统有3个意图分类器**：
1. `IntentClassifier` - 规则分类 (~1200行)
2. `AIIntentClassifier` - LLM分类 (~200行)
3. `SemanticIntentRouter` - 语义向量 (~660行)

**实际使用**：只有规则分类器在工作。

**浪费**：
- `SemanticIntentRouter`: 依赖Ollama，配置复杂，效果提升有限
- `AIIntentClassifier`: 与Supervisor的LLM规划重复

---

## 为什么感觉"死板"

| 体验 | nanobot | 当前系统 |
|------|---------|----------|
| **确定性** | 说"清理"=清理 | 说"清理"→LLM可能理解为查看 |
| **响应速度** | 即时 | 等待LLM调用 |
| **可预测性** | 行为固定 | 每次可能不同 |
| **心智模型** | 简单直接 | 不知道AI会怎么理解 |

**核心问题**：LLM的**概率性**决策 vs 用户期望的**确定性**行为

---

## 重构建议

### 方案A: 规则优先（推荐）

```python
class SimpleAgent:
    # 直接映射表
    ROUTES = [
        (r"(清理|删除|清空).*任务", "delete_tasks"),
        (r"(查看|有什么|列出).*任务", "list_tasks"),
        (r"(完成|做完).*任务", "complete_task"),
        (r"(创建|添加|提醒).*", "create_task"),
    ]

    async def handle(self, text: str):
        # 1. 先尝试规则匹配 (零LLM)
        for pattern, tool_name in self.ROUTES:
            if re.search(pattern, text):
                return await self.tools.execute(tool_name)

        # 2. 复杂指令才用LLM
        return await self.llm.chat(text)
```

**效果**：
- 80%常见指令零LLM调用
- 响应时间 <100ms
- 行为确定可预测

### 方案B: 渐进式简化

**第一阶段**：移除未使用的分类器
- 删除 `SemanticIntentRouter` (~660行)
- 删除 `AIIntentClassifier` (~200行)

**第二阶段**：简化Supervisor
- 移除 `MULTI_STEP` 模式
- 强化规则匹配在 `_analyze_intent`
- 保留反思作为安全网

**第三阶段**：优化工具层
- 工具直接返回格式化文本
- 简化确认流程

---

## 关键文件需要修改

| 文件 | 问题 | 建议 |
|------|------|------|
| `src/agent/supervisor.py` | 过度复杂 | 大幅简化，移除三层模式 |
| `src/chat/semantic_router.py` | 未使用 | 删除 |
| `src/chat/ai_intent_classifier.py` | 重复 | 删除 |
| `src/agent/tools/base.py` | 过度抽象 | 简化Tool基类 |

---

## 预期收益

| 指标 | 当前 | 重构后 |
|------|------|--------|
| 代码行数 | ~3000行 | ~1500行 |
| 响应延迟 | 500ms-2s | <100ms (常见指令) |
| 工具选择准确率 | ~70% | ~95% |
| LLM调用成本 | 高 | 降低70% |

---

## 总结

**当前系统的根本问题**：
1. 用LLM解决应该用规则解决的问题
2. 架构复杂度高但没有对应收益
3. 概率性决策导致行为不可预测

**向nanobot学习的核心**：
- **简单 > 复杂**
- **确定 > 概率**
- **快速 > "智能"**

**建议行动**：
1. 立即删除未使用的意图分类器
2. 强化规则匹配，让80%指令零LLM
3. 简化Supervisor，移除多层模式
4. 工具直接返回可读文本
