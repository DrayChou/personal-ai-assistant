# -*- coding: utf-8 -*-
"""
动作路由器

根据意图执行相应的动作
"""
import json
import logging
from typing import Callable, Optional, Any
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger('chat.action_router')


class IntentType(Enum):
    """意图类型（简化版，仅用于 ActionRouter 内部）"""
    CHAT = "chat"
    CREATE_TASK = "create_task"
    QUERY_TASK = "query_task"
    COMPLETE_TASK = "complete_task"
    DELETE_TASK = "delete_task"
    CREATE_MEMORY = "create_memory"
    QUERY_MEMORY = "query_memory"
    SEARCH = "search"
    WEATHER = "weather"
    TIMER = "timer"
    CALCULATE = "calculate"
    TRANSLATE = "translate"
    UNKNOWN = "unknown"


@dataclass
class Intent:
    """意图数据类"""
    type: IntentType
    confidence: float = 1.0
    entities: dict[str, Any] = None
    original_text: str = ""

    def __post_init__(self):
        if self.entities is None:
            self.entities = {}


class ActionResult:
    """动作执行结果"""
    def __init__(
        self,
        success: bool = False,
        message: str = "",
        data: dict = None,
        need_confirm: bool = False
    ):
        self.success = success
        self.message = message
        self.data = data or {}
        self.need_confirm = need_confirm


class ActionRouter:
    """
    动作路由器

    根据意图调用相应的功能模块
    """

    def __init__(
        self,
        memory_system=None,
        task_manager=None,
        llm_client: Optional[Callable] = None,
        search_tool=None,
        tool_executor=None
    ):
        self.memory = memory_system
        self.tasks = task_manager
        self.llm = llm_client
        self.search = search_tool
        self.tool_executor = tool_executor

    async def route(self, intent: Intent, conversation_context: str = "") -> ActionResult:
        """
        路由并执行动作

        Args:
            intent: 意图识别结果
            conversation_context: 对话上下文

        Returns:
            ActionResult 执行结果
        """
        handlers = {
            # 对话交互类
            IntentType.CHAT: self._handle_chat,
            IntentType.THANKS: self._handle_thanks,
            IntentType.GOODBYE: self._handle_goodbye,
            IntentType.HELP: self._handle_help,
            # 任务管理类
            IntentType.CREATE_TASK: self._handle_create_task,
            IntentType.QUERY_TASK: self._handle_query_task,
            IntentType.UPDATE_TASK: self._handle_update_task,
            IntentType.DELETE_TASK: self._handle_delete_task,
            # 时间管理类
            IntentType.SET_REMINDER: self._handle_set_reminder,
            IntentType.TIMER: self._handle_timer,
            IntentType.QUERY_TIME: self._handle_query_time,
            # 记忆管理类
            IntentType.CREATE_MEMORY: self._handle_create_memory,
            IntentType.QUERY_MEMORY: self._handle_query_memory,
            IntentType.SUMMARIZE: self._handle_summarize,
            # 信息查询类
            IntentType.SEARCH: self._handle_search,
            IntentType.NEWS: self._handle_news,
            IntentType.STOCK: self._handle_stock,
            IntentType.CALCULATE: self._handle_calculate,
            IntentType.TRANSLATE: self._handle_translate,
            IntentType.DEFINE: self._handle_define,
            IntentType.WEATHER: self._handle_weather,
            # 内容生成类
            IntentType.WRITE: self._handle_write,
            IntentType.REWRITE: self._handle_rewrite,
            IntentType.BRAINSTORM: self._handle_brainstorm,
            # 系统控制类
            IntentType.SETTINGS: self._handle_settings,
            IntentType.CLEAR_HISTORY: self._handle_clear_history,
            IntentType.EXPORT_DATA: self._handle_export_data,
            IntentType.SWITCH_PERSONALITY: self._handle_switch_personality,
            # 决策辅助类
            IntentType.DECISION_HELP: self._handle_decision_help,
            IntentType.RECOMMEND: self._handle_recommend,
            # 工具发现类
            IntentType.API_SEARCH: self._handle_api_search,
        }

        handler = handlers.get(intent.type, self._handle_unknown)

        # 处理异步处理器
        import inspect
        if inspect.iscoroutinefunction(handler):
            return await handler(intent, conversation_context)
        return handler(intent, conversation_context)

    def _handle_chat(self, intent: Intent, context: str) -> ActionResult:
        """处理闲聊 - 交给 LLM 流式输出"""
        return ActionResult(
            success=True,
            message="chat",
            data={"type": "stream_chat"}
        )

    def _handle_create_task(self, intent: Intent, context: str) -> ActionResult:
        """处理创建任务"""
        if not self.tasks:
            return ActionResult(
                success=False,
                message="任务管理器未初始化"
            )

        # 使用 LLM 提取结构化信息
        task_info = self._extract_task_info(intent.raw_text)

        if not task_info.get('title'):
            return ActionResult(
                success=False,
                message="无法提取任务内容"
            )

        # 创建任务
        try:
            from src.task.types import TaskPriority

            priority = TaskPriority.from_string(
                task_info.get('priority', 'medium')
            )

            # 判断任务类型：有 scheduled_at 的是定时任务，否则是普通待办
            task_type = 'scheduled' if task_info.get('scheduled_at') else 'todo'

            task = self.tasks.create(
                title=task_info['title'],
                description=task_info.get('description', ''),
                task_type=task_type,
                scheduled_at=task_info.get('scheduled_at'),
                due_date=task_info.get('due_date'),
                priority=priority,
                tags=['auto_extracted']
            )

            return ActionResult(
                success=True,
                message=f"已创建任务：{task.title}",
                data={"task_id": task.id, "task": task},
                need_confirm=False
            )

        except Exception as e:
            logger.error(f"创建任务失败: {e}")
            return ActionResult(
                success=False,
                message=f"创建任务失败: {e}"
            )

    def _handle_query_task(self, intent: Intent, context: str) -> ActionResult:
        """处理查询任务"""
        if not self.tasks:
            return ActionResult(success=False, message="任务管理器未初始化")

        pending = self.tasks.list_tasks(status='pending')

        # 使用 LLM 生成自然回复
        if self.llm and pending:
            task_list = []
            for i, t in enumerate(pending[:10], 1):
                time_info = ""
                if t.scheduled_at:
                    time_info = f" (执行时间: {t.scheduled_at.strftime('%m月%d日 %H:%M')})"
                elif t.due_date:
                    time_info = f" (截止时间: {t.due_date.strftime('%m月%d日 %H:%M')})"
                task_list.append(f"{i}. {t.title}{time_info}")

            tasks_text = "\n".join(task_list)

            prompt = f"""用户询问当前有什么任务。以下是待办任务列表：

{tasks_text}

请用自然、友好的语气回复用户，总结这些任务。如果任务有执行时间或截止时间，请提及。
任务数量：{len(pending)}个

要求：
1. 语气友好自然，像朋友对话
2. 简要总结任务内容
3. 提醒即将到期或需要关注的任务
4. 控制在100字以内"""

            try:
                messages = [{"role": "user", "content": prompt}]
                natural_response = self.llm(messages)
                return ActionResult(
                    success=True,
                    message=natural_response.strip(),
                    data={"tasks": pending, "count": len(pending), "natural": True}
                )
            except Exception as e:
                logger.warning(f"LLM 生成自然回复失败: {e}")

        # 回退到简单回复
        if not pending:
            return ActionResult(
                success=True,
                message="你目前没有待办任务，可以好好休息或者安排新的事情哦~",
                data={"tasks": [], "count": 0}
            )

        # 简单列表回复
        task_lines = []
        for i, t in enumerate(pending[:10], 1):
            time_info = ""
            if t.scheduled_at:
                time_info = f" [{t.scheduled_at.strftime('%m-%d %H:%M')}执行]"
            elif t.due_date:
                time_info = f" [{t.due_date.strftime('%m-%d %H:%M')}截止]"
            task_lines.append(f"{i}. {t.title}{time_info}")

        return ActionResult(
            success=True,
            message=f"你有 {len(pending)} 个待办任务：\n" + "\n".join(task_lines),
            data={"tasks": pending, "count": len(pending)}
        )

    def _handle_update_task(self, intent: Intent, context: str) -> ActionResult:
        """处理更新任务"""
        return ActionResult(
            success=True,
            message="请指定要操作的任务ID",
            need_confirm=True
        )

    def _handle_create_memory(self, intent: Intent, context: str) -> ActionResult:
        """处理创建记忆"""
        if not self.memory:
            return ActionResult(success=False, message="记忆系统未初始化")

        content = intent.entities.get('content', intent.raw_text)

        self.memory.capture(
            content=content,
            tags=['user_preference', 'auto_extracted']
        )

        return ActionResult(
            success=True,
            message="已记录到记忆中",
            data={"content": content}
        )

    def _handle_query_memory(self, intent: Intent, context: str) -> ActionResult:
        """处理查询记忆"""
        if not self.memory:
            return ActionResult(success=False, message="记忆系统未初始化")

        query = intent.entities.get('content', intent.raw_text)
        results = self.memory.recall(query, top_k=5)

        return ActionResult(
            success=True,
            message=f"找到 {len(results)} 条相关记忆",
            data={"memories": results}
        )

    def _handle_delete_task(self, intent: Intent, context: str) -> ActionResult:
        """处理删除/清理任务"""
        if not self.tasks:
            return ActionResult(success=False, message="任务管理器未初始化")

        text = intent.raw_text.lower()

        # 判断是否是要清理所有任务
        clear_all_keywords = ['清理', '清空', '清除', '全部删除', '删掉所有', '全部清除']
        is_clear_all = any(kw in text for kw in clear_all_keywords)

        if is_clear_all:
            # 获取所有待办任务
            pending = self.tasks.list_tasks(status='pending')
            if not pending:
                return ActionResult(
                    success=True,
                    message="任务列表已经是空的了，没有需要清理的任务~",
                    data={"count": 0}
                )

            # 批量删除
            deleted_count = 0
            for task in pending:
                if self.tasks.delete(task.id):
                    deleted_count += 1

            return ActionResult(
                success=True,
                message=f"已清理 {deleted_count} 个任务，列表已清空~",
                data={"count": deleted_count},
                need_confirm=False
            )

        # 单个任务删除（需要更具体的识别，暂时提示用户）
        pending = self.tasks.list_tasks(status='pending')
        if not pending:
            return ActionResult(
                success=True,
                message="当前没有待办任务",
                data={"count": 0}
            )

        return ActionResult(
            success=True,
            message=f"你有 {len(pending)} 个待办任务。要删除特定任务，请告诉我任务名称或编号。",
            data={"count": len(pending), "tasks": pending},
            need_confirm=True
        )

    def _handle_thanks(self, intent: Intent, context: str) -> ActionResult:
        """处理感谢"""
        return ActionResult(
            success=True,
            message="不客气！很高兴能帮到你。",
            data={"type": "chat_response"}
        )

    def _handle_goodbye(self, intent: Intent, context: str) -> ActionResult:
        """处理告别"""
        return ActionResult(
            success=True,
            message="再见！有需要随时找我。",
            data={"type": "chat_response", "action": "exit"}
        )

    def _handle_help(self, intent: Intent, context: str) -> ActionResult:
        """处理帮助请求"""
        help_text = """我可以帮你：

📋 任务管理
  • 创建任务："明天下午3点开会"
  • 查看任务："我有什么任务"
  • 完成任务："标记任务完成"

🧠 记忆管理
  • 记录信息："记住我喜欢Python"
  • 查询记忆："我之前说过什么"

⏰ 时间管理
  • 设置提醒："10分钟后提醒我"
  • 计时器："计时5分钟"

💬 其他
  • 计算："100加200等于多少"
  • 翻译："翻译成英文"
  • 总结："总结一下以上内容"

命令：
  /tasks - 查看任务
  /clear - 清空对话
  /status - 系统状态"""

        return ActionResult(
            success=True,
            message=help_text,
            data={"type": "chat_response"}
        )

    def _handle_set_reminder(self, intent: Intent, context: str) -> ActionResult:
        """处理设置提醒"""
        if not self.tasks:
            return ActionResult(success=False, message="任务管理器未初始化")

        # 提取时间信息
        duration = intent.entities.get('duration', '')
        content = intent.entities.get('content', intent.raw_text)

        # 尝试解析相对时间
        due_date = None
        if duration:
            import re
            match = re.search(r'(\d+)\s*(分钟|分|小时|时)', duration)
            if match:
                value = int(match.group(1))
                unit = match.group(2)
                from datetime import timedelta
                if unit in ['小时', '时']:
                    due_date = datetime.now() + timedelta(hours=value)
                else:
                    due_date = datetime.now() + timedelta(minutes=value)

        try:
            from src.task.types import TaskPriority
            task = self.tasks.create(
                title=f"提醒: {content[:30]}",
                description=content,
                due_date=due_date,
                priority=TaskPriority.from_string('medium'),
                tags=['reminder', 'auto_extracted']
            )

            time_str = due_date.strftime("%H:%M") if due_date else "稍后"
            return ActionResult(
                success=True,
                message=f"已设置提醒：{content[:30]} ({time_str})",
                data={"task_id": task.id, "due_date": due_date}
            )
        except Exception as e:
            logger.error(f"设置提醒失败: {e}")
            return ActionResult(success=False, message=f"设置提醒失败: {e}")

    def _handle_timer(self, intent: Intent, context: str) -> ActionResult:
        """处理计时器"""
        import re
        text = intent.raw_text

        # 提取时间
        minutes = 0
        match = re.search(r'(\d+)\s*分钟', text)
        if match:
            minutes = int(match.group(1))
        else:
            match = re.search(r'计时\s*(\d+)', text)
            if match:
                minutes = int(match.group(1))

        if minutes <= 0:
            minutes = 5  # 默认5分钟

        # 创建定时任务
        if self.tasks:
            try:
                from src.task.types import TaskPriority
                from datetime import timedelta

                due_date = datetime.now() + timedelta(minutes=minutes)
                task = self.tasks.create(
                    title=f"计时器: {minutes}分钟",
                    description=f"倒计时 {minutes} 分钟",
                    due_date=due_date,
                    priority=TaskPriority.from_string('high'),
                    tags=['timer']
                )

                return ActionResult(
                    success=True,
                    message=f"⏱️ 已启动 {minutes} 分钟计时器",
                    data={"minutes": minutes, "task_id": task.id}
                )
            except Exception as e:
                logger.error(f"创建计时器失败: {e}")

        return ActionResult(
            success=True,
            message=f"⏱️ 计时器功能（{minutes}分钟）- 请在调度器中实现触发",
            data={"minutes": minutes, "type": "timer"}
        )

    def _handle_query_time(self, intent: Intent, context: str) -> ActionResult:
        """处理查询时间"""
        now = datetime.now()
        weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
        weekday = weekdays[now.weekday()]

        time_str = now.strftime(f"%Y年%m月%d日 {weekday} %H:%M")
        return ActionResult(
            success=True,
            message=f"现在是 {time_str}",
            data={"datetime": now.isoformat()}
        )

    def _handle_summarize(self, intent: Intent, context: str) -> ActionResult:
        """处理总结请求"""
        if not self.llm:
            return ActionResult(
                success=True,
                message="总结功能需要LLM支持，已回退到流式输出模式",
                data={"type": "stream_chat"}
            )

        return ActionResult(
            success=True,
            message="summarize",
            data={"type": "stream_chat", "context": context}
        )

    def _handle_calculate(self, intent: Intent, context: str) -> ActionResult:
        """处理计算请求"""
        import re
        text = intent.raw_text

        # 尝试提取数学表达式
        result = None
        expression = None

        # 匹配数字运算
        patterns = [
            r'(\d+)\s*加\s*(\d+)',
            r'(\d+)\s*减\s*(\d+)',
            r'(\d+)\s*乘\s*(\d+)',
            r'(\d+)\s*除\s*(\d+)',
            r'(\d+)\s*\+\s*(\d+)',
            r'(\d+)\s*-\s*(\d+)',
            r'(\d+)\s*\*\s*(\d+)',
            r'(\d+)\s*/\s*(\d+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                a, b = int(match.group(1)), int(match.group(2))
                if '加' in text or '+' in text:
                    result = a + b
                    expression = f"{a} + {b}"
                elif '减' in text or '-' in text:
                    result = a - b
                    expression = f"{a} - {b}"
                elif '乘' in text or '*' in text:
                    result = a * b
                    expression = f"{a} * {b}"
                elif '除' in text or '/' in text:
                    if b != 0:
                        result = a / b
                        expression = f"{a} / {b}"
                break

        if result is not None:
            return ActionResult(
                success=True,
                message=f"{expression} = {result}",
                data={"expression": expression, "result": result}
            )

        return ActionResult(
            success=True,
            message="calculate",
            data={"type": "stream_chat"}
        )

    def _handle_translate(self, intent: Intent, context: str) -> ActionResult:
        """处理翻译请求"""
        return ActionResult(
            success=True,
            message="translate",
            data={"type": "stream_chat"}
        )

    def _handle_define(self, intent: Intent, context: str) -> ActionResult:
        """处理定义查询"""
        return ActionResult(
            success=True,
            message="define",
            data={"type": "stream_chat"}
        )

    async def _handle_weather(self, intent: Intent, context: str) -> ActionResult:
        """处理天气查询"""
        # 尝试提取城市名
        import re
        text = intent.raw_text
        city_match = re.search(r'(.+?)(的|天气|气温|怎么样)', text)
        city = city_match.group(1) if city_match else None

        # 优先使用 MCP 工具
        if self.tool_executor and city:
            try:
                result = await self.tool_executor.execute({
                    "name": "amap_weather",
                    "arguments": {"city": city}
                })
                if result.success:
                    return ActionResult(
                        success=True,
                        message=f"{city}天气信息：\n{result.result}",
                        data={"type": "tool_result", "tool": "amap_weather"}
                    )
            except Exception as e:
                logger.warning(f"MCP天气查询失败: {e}")

        # 回退到搜索
        if self.search:
            query = f"{city}天气" if city else "天气"
            result = self.search.search(query, num_results=3, summarize=True)
            return ActionResult(
                success=True,
                message=result,
                data={"type": "search_result", "query": query}
            )

        return ActionResult(
            success=True,
            message="天气查询功能需要接入天气API或启用搜索功能。",
            data={"type": "needs_api", "api": "weather"}
        )

    def _handle_search(self, intent: Intent, context: str) -> ActionResult:
        """处理搜索请求"""
        if not self.search:
            return ActionResult(
                success=True,
                message="搜索功能未启用。请安装 duckduckgo-search 库。",
                data={"type": "needs_config"}
            )

        query = intent.entities.get('content', intent.raw_text)
        # 去除常见的搜索前缀
        import re
        query = re.sub(r'^(搜索|查找|查询)\s*', '', query)

        result = self.search.search(query, context=intent.raw_text, num_results=5)

        return ActionResult(
            success=True,
            message=result,
            data={"type": "search_result", "query": query}
        )

    def _handle_news(self, intent: Intent, context: str) -> ActionResult:
        """处理新闻查询"""
        if not self.search:
            return ActionResult(
                success=True,
                message="新闻查询需要启用搜索功能。",
                data={"type": "stream_chat"}
            )

        query = "最新新闻"
        # 尝试提取新闻类型
        text = intent.raw_text
        import re
        category_match = re.search(r'(科技|财经|体育|娱乐|国际|国内).{0,3}(新闻|消息)', text)
        if category_match:
            query = f"{category_match.group(1)}最新新闻"

        result = self.search.search(query, context=intent.raw_text, num_results=5)

        return ActionResult(
            success=True,
            message=result,
            data={"type": "search_result", "query": query}
        )

    def _handle_stock(self, intent: Intent, context: str) -> ActionResult:
        """处理股价查询"""
        if not self.search:
            return ActionResult(
                success=True,
                message="股价查询需要启用搜索功能。",
                data={"type": "stream_chat"}
            )

        # 尝试提取股票名称/代码
        import re
        text = intent.raw_text
        stock_match = re.search(r'(.+?)(股价|股票|行情|涨|跌)', text)

        if stock_match:
            stock_name = stock_match.group(1).strip()
            query = f"{stock_name}股价"
        else:
            query = "股市行情"

        result = self.search.search(query, context=intent.raw_text, num_results=3)

        return ActionResult(
            success=True,
            message=result,
            data={"type": "search_result", "query": query}
        )

    def _handle_write(self, intent: Intent, context: str) -> ActionResult:
        """处理写作请求"""
        return ActionResult(
            success=True,
            message="write",
            data={"type": "stream_chat"}
        )

    def _handle_rewrite(self, intent: Intent, context: str) -> ActionResult:
        """处理改写请求"""
        return ActionResult(
            success=True,
            message="rewrite",
            data={"type": "stream_chat"}
        )

    def _handle_brainstorm(self, intent: Intent, context: str) -> ActionResult:
        """处理头脑风暴"""
        return ActionResult(
            success=True,
            message="brainstorm",
            data={"type": "stream_chat"}
        )

    def _handle_settings(self, intent: Intent, context: str) -> ActionResult:
        """处理设置请求"""
        return ActionResult(
            success=True,
            message="设置功能尚未完全实现。请直接编辑 .env 文件或配置文件。",
            data={"type": "settings"}
        )

    def _handle_clear_history(self, intent: Intent, context: str) -> ActionResult:
        """处理清空历史"""
        return ActionResult(
            success=True,
            message="clear_history",
            data={"type": "clear_history"}
        )

    def _handle_export_data(self, intent: Intent, context: str) -> ActionResult:
        """处理导出数据"""
        if not self.memory:
            return ActionResult(success=False, message="记忆系统未初始化")

        try:
            from pathlib import Path
            export_dir = Path("data/exports")
            export_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_path = export_dir / f"memories_{timestamp}.jsonl"

            # 调用长期记忆的导出功能
            if hasattr(self.memory, 'long_term_memory'):
                self.memory.long_term_memory.export_to_jsonl(str(export_path))
                return ActionResult(
                    success=True,
                    message=f"数据已导出到: {export_path}",
                    data={"export_path": str(export_path)}
                )
            else:
                return ActionResult(
                    success=False,
                    message="导出功能不可用"
                )
        except Exception as e:
            logger.error(f"导出失败: {e}")
            return ActionResult(success=False, message=f"导出失败: {e}")

    def _handle_switch_personality(self, intent: Intent, context: str) -> ActionResult:
        """处理切换性格请求"""
        text = intent.raw_text.lower()

        # 性格关键词映射
        personality_keywords = {
            '猫娘': 'nekomata_assistant',
            'maid': 'nekomata_assistant',
            '浮浮': 'nekomata_assistant',
            '大小姐': 'ojousama_assistant',
            'ojousama': 'ojousama_assistant',
            '傲娇': 'ojousama_assistant',
            '本小姐': 'ojousama_assistant',
            '战斗修女': 'battle_sister_assistant',
            'aleta': 'battle_sister_assistant',
            '修女': 'battle_sister_assistant',
            '40k': 'battle_sister_assistant',
            '文言文': 'classical_assistant',
            '古文': 'classical_assistant',
            'classical': 'classical_assistant',
            '占卜家': 'seer_assistant',
            'seer': 'seer_assistant',
            'lotm': 'seer_assistant',
            '慵懒猫': 'lazy_cat_assistant',
            '橘猫': 'lazy_cat_assistant',
            '懒猫': 'lazy_cat_assistant',
            'sleepy': 'lazy_cat_assistant',
            '大福': 'lazy_cat_assistant',
            '默认': 'default_assistant',
            'default': 'default_assistant',
            '专业': 'default_assistant',
        }

        # 查找匹配的性格
        target_personality = None
        for keyword, personality_name in personality_keywords.items():
            if keyword in text:
                target_personality = personality_name
                break

        if target_personality:
            return ActionResult(
                success=True,
                message=f"SWITCH_PERSONALITY:{target_personality}",
                data={"personality": target_personality, "type": "switch_personality"}
            )
        else:
            return ActionResult(
                success=True,
                message="请告诉我你想切换到什么性格：猫娘、大小姐、战斗修女、文言文、占卜家、慵懒猫、默认",
                data={"type": "switch_personality", "needs_clarification": True}
            )

    def _handle_decision_help(self, intent: Intent, context: str) -> ActionResult:
        """处理决策辅助"""
        return ActionResult(
            success=True,
            message="decision_help",
            data={"type": "stream_chat"}
        )

    def _handle_recommend(self, intent: Intent, context: str) -> ActionResult:
        """处理推荐请求"""
        return ActionResult(
            success=True,
            message="recommend",
            data={"type": "stream_chat"}
        )

    def _handle_api_search(self, intent: Intent, context: str) -> ActionResult:
        """处理 API 搜索请求"""
        try:
            from ..tools.public_api_search import PublicAPISearch

            searcher = PublicAPISearch()
            text = intent.raw_text.lower()

            # 根据关键词推断搜索意图
            keyword = ""
            category = None

            # 提取关键词
            if "天气" in text or "weather" in text:
                keyword = "weather"
            elif "汇率" in text or "currency" in text or "exchange" in text:
                keyword = "currency"
            elif "加密货币" in text or "crypto" in text or "比特币" in text:
                keyword = "crypto"
            elif "翻译" in text or "translate" in text:
                keyword = "translate"
            elif "新闻" in text or "news" in text:
                keyword = "news"
            elif "笑话" in text or "joke" in text:
                keyword = "joke"
            elif "名言" in text or "quote" in text:
                keyword = "quote"
            elif "ip" in text:
                keyword = "ip"
            elif "图片" in text or "image" in text or "photo" in text:
                keyword = "image"
            else:
                # 提取最可能的关键词
                import re
                # 尝试提取 "XX API" 或 "XX api" 中的 XX
                match = re.search(r'(\w+)\s*(?:API|api)', text)
                if match:
                    keyword = match.group(1)
                else:
                    # 使用通用搜索
                    keyword = "api"

            # 搜索 API
            results = searcher.search(keyword, category=category)

            if results:
                message = searcher.format_result(results)
            else:
                message = f"未找到与 '{keyword}' 相关的 API。试试其他关键词，如：weather, currency, crypto, news, translate"

            return ActionResult(
                success=True,
                message=message,
                data={"keyword": keyword, "count": len(results)}
            )

        except Exception as e:
            logger.error(f"API 搜索失败: {e}")
            return ActionResult(
                success=False,
                message=f"API 搜索功能暂时不可用: {e}",
                data={"type": "stream_chat"}
            )

    def _handle_unknown(self, intent: Intent, context: str) -> ActionResult:
        """处理未知意图"""
        return ActionResult(
            success=True,
            message="unknown",
            data={"type": "stream_chat"}
        )

    def _extract_task_info(self, text: str) -> dict:
        """使用 LLM 提取任务信息"""
        if not self.llm:
            return {"title": text[:50], "description": text, "scheduled_at": None, "due_date": None}

        prompt = f"""从以下文本中提取任务信息，输出 JSON：

文本："{text}"

当前时间：{datetime.now().isoformat()}

输出格式：
{{
    "title": "简洁的任务标题（10字以内）",
    "description": "详细描述",
    "scheduled_at": "ISO格式时间或null（任务执行时间）",
    "due_date": "ISO格式时间或null（任务截止时间）",
    "priority": "high/medium/low"
}}

注意：
- 如果提到"明天早上8点叫我起床"，这是定时执行，设置 scheduled_at
- 如果提到"周五前完成报告"，这是截止时间，设置 due_date
- 标题要简洁，描述要完整
- 时间必须是有效的 ISO 格式"""

        try:
            messages = [{"role": "user", "content": prompt}]
            response = self.llm(messages)
            result = json.loads(response)

            # 解析 scheduled_at
            scheduled_at = None
            if result.get('scheduled_at'):
                try:
                    scheduled_at = datetime.fromisoformat(result['scheduled_at'].replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    pass

            # 解析 due_date
            due_date = None
            if result.get('due_date'):
                try:
                    due_date = datetime.fromisoformat(result['due_date'].replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    pass

            return {
                "title": result.get('title', text[:50]),
                "description": result.get('description', text),
                "scheduled_at": scheduled_at,
                "due_date": due_date,
                "priority": result.get('priority', 'medium')
            }

        except Exception as e:
            logger.warning(f"LLM 提取任务信息失败: {e}")
            return {"title": text[:50], "description": text, "scheduled_at": None, "due_date": None}
