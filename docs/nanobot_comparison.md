# nanobot 与当前系统对比分析

## nanobot 的处理方式

### 1. 简单的 MessageBus 架构
```python
# nanobot: 极简的消息总线
class MessageBus:
    def emit(self, event, data):
        # 直接分发，无复杂规划
        handler = self.handlers.get(event)
        if handler:
            handler(data)
```

### 2. 直接的意图映射
```python
# nanobot: 意图直接映射到动作
INTENT_HANDLERS = {
    "query_tasks": lambda ctx: ctx.task_manager.list_tasks(),
    "delete_tasks": lambda ctx: ctx.task_manager.clear_all(),
    # ...
}

# 没有复杂的反思和重试，一次决策直接执行
```

### 3. 简洁的工具输出
```python
# nanobot: 直接格式化输出给用户
def list_tasks():
    tasks = task_manager.list_tasks()
    return format_tasks(tasks)  # 直接返回可读文本
```

---

## 当前系统的问题

### 问题 1: 工具输出太抽象
**当前行为**:
```
用户: 当前有哪些任务啊
助手: 找到 2 个任务
```

**问题**: 没有展示任务详情，用户不知道具体有什么任务

**修复后**:
```
用户: 当前有哪些任务啊
助手: 📋 找到 2 个待办任务:
  1. 🔴 重要会议 ⏰ 02-25 15:00
  2. 🟡 买牛奶
```

### 问题 2: 反思后重试无效
**当前行为**:
```
用户: 清理这些任务
助手: [使用 list_tasks] 找到 2 个任务
[反思: 应该用 delete_tasks]
[重试: 调用 LLM 重新规划]
[结果: 还是用了 list_tasks]
```

**问题**: 依赖 LLM 重新规划，但 LLM 可能还是选错工具

**修复后**:
```
用户: 清理这些任务
助手: [使用 list_tasks] 找到 2 个任务
[反思: 应该用 delete_tasks]
[直接切换到 delete_tasks，不再问 LLM]
[结果: 显示待删除任务列表，请求确认]
```

### 问题 3: 过度依赖 LLM
**当前设计**:
- 用户输入 → LLM 规划 → 选择工具 → 执行
- 反思后 → LLM 重新规划 → 选择工具

**问题**: 每次都要调用 LLM，慢且容易出错

**nanobot 设计**:
- 用户输入 → 规则匹配 → 直接执行
- 没有反思，没有重试，一次完成

---

## 核心差异

| 特性 | nanobot | 当前系统 |
|------|---------|----------|
| 架构复杂度 | 极简 (~4000行) | 较复杂 |
| 意图识别 | 规则匹配 | 规则 + LLM |
| 工具选择 | 直接映射 | LLM 规划 |
| 错误处理 | 简单直接 | 反思 + 重试 |
| 输出格式 | 直接可读 | 需要格式化 |
| 灵活性 | 低 | 高 |
| 响应速度 | 快 | 较慢 |

---

## 改进建议

### 短期（已修复）
1. ✅ 修复工具输出格式，显示详细信息
2. ✅ 修复反思重试逻辑，直接切换工具
3. ✅ 添加删除确认流程

### 中期
1. **简化规划流程**
   - 常用指令走规则匹配（不走 LLM）
   - 复杂指令才用 LLM 规划

2. **预定义工作流**
   ```python
   WORKFLOWS = {
       "清理任务": ["list_tasks", "confirm", "delete_tasks"],
       "查看任务": ["list_tasks"],
   }
   ```

3. **更智能的输出格式化**
   - 不同工具返回结构化数据
   - LLM 根据数据生成自然语言回复

### 长期
1. **学习用户习惯**
   - 记录用户常用指令
   - 自动优化工具选择

2. **对话式确认**
   - 不是简单的 yes/no
   - 支持自然语言确认："好的，删掉吧"
