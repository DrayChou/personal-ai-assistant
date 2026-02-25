# 意图识别架构重构方案

## 核心决策

**删除**：
- ❌ `IntentClassifier` (规则匹配，关键词方式)
- ❌ `SemanticIntentRouter` (向量相似度，难以扩展)
- ❌ `AIIntentClassifier` (已弃用)

**采用**：
- ✅ **nanobot 风格**: LLM 自己决定工具选择
- ✅ **OpenClaw 风格**: 简洁的意图映射（如需要）

---

## 为什么关键词/向量方式不好？

### 关键词匹配的问题

```python
# 当前方式 - 难以扩展
DIRECT_PATTERNS = {
    r"(清理|删除|清空).*任务": "delete_tasks",  # 需要维护大量正则
    r"(查看|有什么|列出).*任务": "list_tasks",  # 新场景要加新规则
    r"(完成|做完).*任务": "complete_task",      # 中文变种多
}

# 问题：
# 1. "帮我把任务清了" - 匹配不到
# 2. "把那个任务干掉" - 匹配不到
# 3. "任务都完成了吗" - 可能误匹配 complete_task
```

### 向量相似度的问题

```python
# 需要训练数据
routes = [
    Route("delete_tasks", ["删除任务", "清理任务", "清空任务"]),
    # 新场景需要收集样本、重新训练
]

# 问题：
# 1. 冷启动困难
# 2. 相似意图容易混淆
# 3. 调试困难（黑盒）
```

---

## 新架构: LLM-First Intent Recognition

### 架构图

```
用户输入
    ↓
[可选] 极简预检查（仅确认/取消）
    ↓
ContextBuilder (系统提示 + 所有工具描述)
    ↓
LLM 决策 (工具选择 + 参数提取)
    ↓
执行
```

### 核心代码

```python
class SimpleIntentHandler:
    """
    极简意图处理 - 类似 nanobot
    只处理最基础的确认/取消，其他全部交给 LLM
    """

    # 仅用于处理待确认的交互
    CONFIRMATION_PATTERNS = {
        "yes": ["yes", "是", "确定", "确认", "好的", "执行", "删除"],
        "no": ["no", "否", "取消", "cancel", "算了", "不要"],
    }

    def __init__(self):
        self._pending_confirmation: Optional[PendingAction] = None

    async def handle(self, user_input: str, session: Session) -> HandlerResult:
        # 1. 检查是否有待确认的action
        if self._pending_confirmation:
            intent = self._check_confirmation(user_input)
            if intent == "confirm":
                return await self._execute_confirmed()
            elif intent == "cancel":
                return self._cancel_confirmation()

        # 2. 其他所有情况 → 交给 LLM 决定
        return await self._llm_handle(user_input, session)

    async def _llm_handle(self, user_input: str, session: Session) -> HandlerResult:
        """
        让 LLM 自己决定：
        - 选择什么工具
        - 提取什么参数
        - 是否需要确认
        """
        messages = [
            {"role": "system", "content": self._build_system_prompt()},
            {"role": "user", "content": user_input}
        ]

        response = await self.llm.chat(
            messages=messages,
            tools=self.tools.get_definitions(),  # 所有工具
            tool_choice="auto"  # 让 LLM 自己决定
        )

        if response.tool_calls:
            tool_call = response.tool_calls[0]

            # 检查是否需要确认
            if self._needs_confirmation(tool_call.name):
                self._pending_confirmation = PendingAction(
                    tool_name=tool_call.name,
                    params=tool_call.arguments
                )
                return HandlerResult(
                    type="confirmation_required",
                    message=self._format_confirm_prompt(tool_call)
                )

            # 直接执行
            result = await self.tools.execute(tool_call.name, tool_call.arguments)
            return HandlerResult(type="success", data=result)

        # LLM 直接回复
        return HandlerResult(type="direct_response", message=response.content)

    def _build_system_prompt(self) -> str:
        """
        系统提示 - 清晰描述所有能力和规则
        """
        return """你是一个个人 AI 助理，可以帮助用户管理任务和记忆。

## 可用工具

### 任务管理
- `list_tasks` - 查看任务列表
  使用场景：用户问"有什么任务"、"列出任务"

- `create_task` - 创建新任务
  使用场景：用户说"提醒我..."、"创建一个任务"

- `complete_task` - 标记任务完成
  使用场景：用户说"完成了..."、"任务做完了"

- `delete_tasks` - 删除任务
  使用场景：用户说"删除..."、"清理..."
  ⚠️ 重要：此工具需要用户确认，不要自动执行

### 记忆管理
- `search_memory` - 搜索历史记忆
  使用场景：用户问"之前说过..."、"还记得..."

- `add_memory` - 记录重要信息
  使用场景：用户说"记住..."、"帮我记下..."

## 重要规则

1. **删除操作必须确认**
   - 如果用户说"删除任务"，先调用 delete_tasks 获取待删除列表
   - 然后询问用户确认，等待明确回复后再执行

2. **自然对话优先**
   - 如果用户只是闲聊，不要调用工具，直接回复
   - 如果不确定用户意图，可以询问澄清

3. **中文理解**
   - 理解口语化表达，如"帮我把任务清了" = 删除任务
   - 理解上下文，如用户刚提到一个任务，"完成了"指那个任务
"""
```

---

## 与 nanobot 的对比

| 方面 | nanobot | 我们的方案 |
|------|---------|-----------|
| 意图分类 | ❌ 完全没有 | ✅ 仅确认/取消（极简） |
| 工具选择 | LLM 决定 | LLM 决定 |
| 确认流程 | ❌ 没有 | ✅ 内置确认机制 |
| 中文优化 | 基础 | ✅ 系统提示强化 |
| 扩展性 | 好 | 好（加工具描述即可） |

---

## 扩展方式对比

### 旧方式（关键词/向量）

```python
# 添加新功能 - 复杂
# 1. 添加正则规则
# 2. 收集训练样本
# 3. 重新训练向量模型
# 4. 调试匹配准确率
```

### 新方式（LLM-First）

```python
# 添加新功能 - 简单
# 只需在系统提示中添加工具描述

新工具描述 = """
- `new_feature` - 新功能
  使用场景：用户说"..."、"..."
"""

# 完成！LLM 自动学会使用
```

---

## 风险与应对

| 风险 | 概率 | 应对 |
|------|------|------|
| LLM 选错工具 | 低 | 清晰的系统提示 + 确认机制 |
| 响应延迟 | 低 | 单次 LLM 调用 |
| 成本增加 | 低 | 比多次分类调用更省 |

---

## 实施步骤

1. **删除现有分类器**
   - 删除 `IntentClassifier`
   - 删除 `SemanticIntentRouter`
   - 删除 `AIIntentClassifier`

2. **实现 SimpleIntentHandler**
   - 仅保留确认/取消检查
   - 实现 `_llm_handle` 核心方法

3. **优化系统提示**
   - 清晰的工具描述
   - 使用场景示例
   - 重要规则强调

4. **测试验证**
   - 常见场景准确率
   - 边缘 case 处理
   - 确认流程测试

---

## 代码量对比

| 组件 | 旧方案 | 新方案 |
|------|--------|--------|
| IntentClassifier | ~482 行 | 删除 |
| SemanticIntentRouter | ~660 行 | 删除 |
| AIIntentClassifier | ~361 行 | 删除 |
| SimpleIntentHandler | - | ~150 行 |
| **总计** | **~1,503 行** | **~150 行** |
| **净减少** | | **-1,353 行** |
