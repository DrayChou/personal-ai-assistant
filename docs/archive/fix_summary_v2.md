# 底层问题修复总结

## 根本原因

### 1. 循环导入问题
**文件**: `src/agent/factory.py:9`

```python
# 错误
from agent import SupervisorAgent, ToolRegistry  # 绝对导入导致循环导入

# 修复
from . import SupervisorAgent, ToolRegistry  # 相对导入
```

### 2. 提示词不够明确
当 MiniMax 不支持 `tools` 参数时，系统回退到提示工程模式，但原提示词缺少：
- 强制性工具选择规则
- 明确的触发关键词列表
- Few-shot 示例

### 3. 工具描述不够清晰
原工具描述没有明确区分：
- 什么时候必须用 `delete_tasks`
- 什么时候必须用 `list_tasks`
- 关键词冲突时的优先级

---

## 修复内容

### 1. LLM Adapter 增强
**文件**: `src/agent/llm_adapter.py:188-220`

添加了强制性规则和清晰的示例：
```python
【强制性工具选择规则】
1. 用户说"清理任务"、"删除任务" → 必须使用 delete_tasks
2. 用户说"查看任务"、"有什么任务" → 使用 list_tasks
...

【示例】
用户：查看我的任务
助手：<tool_call>{"name": "list_tasks"...}

用户：清理这些任务
助手：<tool_call>{"name": "delete_tasks"...}
```

### 2. 规划提示词增强
**文件**: `src/agent/supervisor.py:430-445`

添加了强制规则和 Few-shot：
```python
【强制性工具选择规则】
- 关键词包含"清理"、"删除" → 必须使用 delete_tasks
- 关键词包含"查看"、"显示" → 使用 list_tasks
...
```

### 3. 工具描述增强
**文件**: `src/agent/tools/builtin/task_tools.py`

- `ListTasksTool`: 明确禁止在"清理/删除"时使用
- `DeleteTasksTool`: 明确禁止在"查看/显示"时使用

---

## 为什么 nanobot 更"灵活"

### nanobot 的做法
1. **预定义工作流** - 某些指令直接映射到工具，不走 LLM
2. **简单直接** - 规则匹配 → 直接执行，没有复杂的反思重试
3. **输出即结果** - 工具直接返回格式化文本

### 当前系统的问题
1. **过度依赖 LLM** - 即使是简单的"清理任务"也要 LLM 决策
2. **反思机制低效** - 发现错误后重新问 LLM，可能还是错
3. **提示词不够强** - 没有强制约束 LLM 的选择

---

## 测试建议

```bash
uv run python src/main.py
```

测试用例：
1. "查看任务" → 应该调用 list_tasks，显示格式化列表
2. "清理任务" → 应该调用 delete_tasks，显示确认提示
3. "删除这些任务" → 反思后应该直接切换到 delete_tasks

如果还有问题，可能是 MiniMax 的 function calling 支持不完善，需要完全依赖提示工程模式。
