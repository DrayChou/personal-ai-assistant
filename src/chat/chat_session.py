# -*- coding: utf-8 -*-
"""
对话会话管理

管理单次对话的上下文和记忆捕获
"""
import logging
import re
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from .context_builder import ContextBuilder
from .llm_client import LLMClient
from ..personality import get_personality_manager

if TYPE_CHECKING:
    from ..memory import MemorySystem
    from ..task import TaskManager

logger = logging.getLogger('chat.session')


class ThinkTagFilter:
    """
    用于过滤 <think> 标签内容的流式过滤器

    MiniMax-M2.5 等模型会在 <think>...</think> 标签中返回思考过程，
    这些内容不应该展示给用户。
    """

    def __init__(self):
        self.buffer = ""
        self.in_think_block = False

    def filter(self, chunk: str) -> str:
        """
        过滤单个 chunk 中的 <think> 标签内容

        Args:
            chunk: 输入的文本片段

        Returns:
            过滤后的文本片段
        """
        if not chunk:
            return ""

        self.buffer += chunk
        result = ""

        while self.buffer:
            if self.in_think_block:
                # 在 <think> 块内，寻找 </think>
                end_idx = self.buffer.lower().find('</think>')
                if end_idx != -1:
                    # 找到结束标签，跳过整个块
                    self.buffer = self.buffer[end_idx + 8:]  # len('</think>') = 8
                    self.in_think_block = False
                else:
                    # 还在 think 块内，清空缓冲区
                    self.buffer = ""
                    break
            else:
                # 在 think 块外，寻找 <think>
                start_idx = self.buffer.lower().find('<think>')
                if start_idx != -1:
                    # 找到开始标签，输出之前的内容
                    result += self.buffer[:start_idx]
                    self.buffer = self.buffer[start_idx + 7:]  # len('<think>') = 7
                    self.in_think_block = True
                else:
                    # 没有 <think>，但需要保留可能的部分标签在缓冲区
                    # 检查是否有可能的部分标签在末尾
                    if len(self.buffer) >= 7:
                        # 缓冲区足够长，直接输出（除了最后6个字符，可能是 <think 的开头）
                        result += self.buffer[:-6]
                        self.buffer = self.buffer[-6:]
                    break

        return result

    def flush(self) -> str:
        """刷新缓冲区，返回剩余内容"""
        result = "" if self.in_think_block else self.buffer
        self.buffer = ""
        self.in_think_block = False
        return result

    @staticmethod
    def filter_text(text: str) -> str:
        """
        静态方法：过滤完整文本中的所有 <think> 块

        Args:
            text: 完整文本

        Returns:
            过滤后的文本
        """
        if not text:
            return text

        # 使用正则表达式移除所有 <think>...</think> 块
        # re.DOTALL 让 . 匹配包括换行符在内的所有字符
        filtered = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)

        # 清理可能残留的单个标签
        filtered = re.sub(r'</?think>', '', filtered, flags=re.IGNORECASE)

        return filtered.strip()


class ChatSession:
    """
    对话会话

    管理单次完整的对话：
    - 维护对话历史
    - 调用 LLM 生成回复
    - 捕获记忆到长期记忆
    - 提取任务
    """

    def __init__(
        self,
        session_id: str,
        memory_system: "MemorySystem",
        llm_client: LLMClient,
        task_manager: Optional["TaskManager"] = None,
        personality_manager=None,
        history: Optional[list[dict]] = None
    ):
        self.session_id = session_id
        self.memory = memory_system
        self.llm = llm_client
        self.task_manager = task_manager
        self.personality = personality_manager or get_personality_manager()

        self.context_builder = ContextBuilder(memory_system, self.personality)
        self.history: list[dict] = history or []  # 支持传入初始历史记录
        self.started_at = datetime.now()

    def chat(self, user_message: str) -> str:
        """
        发送消息并获取回复

        Args:
            user_message: 用户消息

        Returns:
            助手回复
        """
        # 1. 构建上下文
        messages = self.context_builder.build(
            user_message=user_message,
            conversation_history=self.history
        )

        # 2. 调用 LLM
        try:
            response = self.llm.generate(messages)
            # 过滤掉 <think> 标签内容
            response = ThinkTagFilter.filter_text(response)
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            return f"抱歉，我遇到了一些问题：{e}"

        # 3. 记录对话
        self.history.append({"role": "user", "content": user_message})
        self.history.append({"role": "assistant", "content": response})

        # 4. 捕获记忆
        self._capture_memory(user_message, response)

        # 5. 提取任务（如果有任务管理器）
        if self.task_manager:
            self._extract_tasks(user_message)

        return response

    def chat_stream(self, user_message: str):
        """
        发送消息并获取流式回复

        Args:
            user_message: 用户消息

        Yields:
            助手回复的每个片段

        Returns:
            完整的助手回复
        """
        # 1. 构建上下文
        messages = self.context_builder.build(
            user_message=user_message,
            conversation_history=self.history
        )

        # 2. 调用 LLM 流式生成
        full_response = ""
        think_filter = ThinkTagFilter()

        try:
            # 检查 LLM 客户端是否支持流式生成
            if hasattr(self.llm, 'stream_generate'):
                for chunk in self.llm.stream_generate(messages):
                    # 过滤 think 标签
                    filtered_chunk = think_filter.filter(chunk)
                    if filtered_chunk:
                        full_response += filtered_chunk
                        yield filtered_chunk

                # 刷新缓冲区，获取剩余内容
                remaining = think_filter.flush()
                if remaining:
                    full_response += remaining
                    yield remaining
            else:
                # 回退到非流式
                response = self.llm.generate(messages)
                # 过滤 think 标签
                filtered_response = ThinkTagFilter.filter_text(response)
                full_response = filtered_response
                yield filtered_response
        except Exception as e:
            logger.error(f"LLM 流式调用失败: {e}")
            error_str = str(e)

            # 提供更友好的错误信息
            if "400" in error_str:
                error_msg = "抱歉，请求格式有误。让我重新尝试..."
                # 尝试使用非流式作为回退
                try:
                    response = self.llm.generate(messages)
                    filtered_response = ThinkTagFilter.filter_text(response)
                    full_response = filtered_response
                    yield filtered_response
                    return
                except Exception as e2:
                    logger.error(f"回退到非流式也失败: {e2}")
                    error_msg = "抱歉，服务暂时不可用，请稍后再试。"
            elif "401" in error_str:
                error_msg = "抱歉，API 认证失败，请检查 API Key 设置。"
            elif "429" in error_str:
                error_msg = "抱歉，请求太频繁了，请稍后再试。"
            else:
                error_msg = f"抱歉，我遇到了一些问题：{e}"

            yield error_msg
            full_response = error_msg

        # 3. 记录对话
        self.history.append({"role": "user", "content": user_message})
        self.history.append({"role": "assistant", "content": full_response})

        # 4. 捕获记忆
        self._capture_memory(user_message, full_response)

        # 5. 提取任务（如果有任务管理器）
        if self.task_manager:
            self._extract_tasks(user_message)

        return full_response

    def _capture_memory(self, user_message: str, assistant_response: str):
        """捕获对话到记忆系统"""
        # 捕获用户消息
        self.memory.capture(
            content=f"用户: {user_message}",
            source=self.session_id,
            tags=["conversation", "user"]
        )

        # 捕获助手回复
        self.memory.capture(
            content=f"助手: {assistant_response}",
            source=self.session_id,
            tags=["conversation", "assistant"]
        )

        # 更新工作记忆上下文
        recent_turns = self.history[-6:]  # 最近3轮
        context_text = "\n".join([
            f"{msg['role']}: {msg['content'][:100]}"
            for msg in recent_turns
        ])
        self.memory.working_memory.set_context(context_text)

        logger.debug(f"对话已捕获到记忆: {self.session_id}")

    def _extract_tasks(self, user_message: str):
        """从用户消息中提取任务"""
        if not self.task_manager:
            return

        # 检查是否包含任务关键词（更广泛的匹配）
        task_keywords = [
            "TODO", "任务", "记得", "别忘了", "需要", "要", "帮",
            "记录", "提醒", "叫", "闹钟", "明天", "后天", "周末"
        ]
        if not any(kw in user_message for kw in task_keywords):
            return

        try:
            from src.task.extractor import TaskExtractor
            extractor = TaskExtractor()

            tasks = extractor.extract_from_single_message(user_message)
            for task in tasks:
                # 使用任务管理器创建任务
                created = self.task_manager.create(
                    title=task.title,
                    description=task.description,
                    task_type=task.task_type,
                    due_date=task.due_date,
                    priority=task.priority,
                    source_conversation=self.session_id
                )
                logger.info(f"从对话提取任务: {created.id} - {created.title}")

        except Exception as e:
            logger.error(f"任务提取失败: {e}")

    def get_summary(self) -> dict:
        """获取会话摘要"""
        duration = datetime.now() - self.started_at
        return {
            "session_id": self.session_id,
            "started_at": self.started_at.isoformat(),
            "duration_seconds": duration.total_seconds(),
            "message_count": len(self.history),
            "user_message_count": len([m for m in self.history if m["role"] == "user"]),
        }

    def clear_history(self):
        """清空对话历史"""
        self.history.clear()
        logger.info(f"会话 {self.session_id} 历史已清空")
