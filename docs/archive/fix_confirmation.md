# 确认流程修复

## 问题
用户输入 "yes" 确认删除时，系统没有正确执行删除，而是让 LLM 去处理，导致 LLM 输出了文本格式的工具调用标记。

## 修复

### 1. 添加确认状态跟踪
**文件**: `src/agent/supervisor.py`

```python
# 在 __init__ 中添加
self._pending_confirmation: Optional[dict] = None
```

### 2. 添加确认检查方法

```python
def _is_confirmation(self, user_input: str) -> bool:
    """检查用户输入是否是确认"""
    confirmation_keywords = ['确认', 'yes', '是', '确定', '好的', '执行', '删除', '清理']
    return user_input.lower().strip() in confirmation_keywords

def _is_cancel(self, user_input: str) -> bool:
    """检查用户输入是否是取消"""
    cancel_keywords = ['取消', 'cancel', 'no', '否', '不', '算了', '不要']
    return user_input.lower().strip() in cancel_keywords
```

### 3. 执行确认操作

```python
async def _execute_confirmation(self, user_input: str) -> AsyncGenerator[str, None]:
    """执行确认的操作"""
    # ... 直接执行之前保存的工具调用
```

### 4. 在 handle 方法中优先检查确认

```python
async def handle(self, user_input: str, ...) -> AsyncGenerator[str | dict, None]:
    # 检查是否有待处理的确认
    if self._pending_confirmation and self._is_confirmation(user_input):
        async for output in self._execute_confirmation(user_input):
            yield output
        return
    # ... 正常流程
```

### 5. 在工具执行后保存确认状态

```python
# 检查是否需要确认
if result.data and result.data.get("needs_confirmation"):
    # 保存确认状态
    self._pending_confirmation = {
        "tool_name": step.tool_name,
        "params": step.parameters.copy()
    }
```

## 现在的工作流程

1. 用户: "清理所有任务"
2. 系统: 调用 `delete_tasks` → 返回需要确认
3. 系统: 保存确认状态，显示确认提示
4. 用户: "yes"
5. 系统: 检测到确认输入，直接执行 `delete_tasks(confirmed=True)`
6. 系统: 显示删除结果

不再依赖 LLM 来处理确认！
