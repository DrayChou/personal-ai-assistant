# -*- coding: utf-8 -*-
"""
控制台适配器

提供命令行交互能力，用于开发和测试
"""
import asyncio
import logging
import sys
from typing import Any, Optional

from .base import ChannelAdapter, ChatMessage, ChatResponse

logger = logging.getLogger('channels.console')


class ConsoleAdapter(ChannelAdapter):
    """
    控制台适配器

    提供简单的命令行交互界面，适合开发和测试使用

    Example:
        async def main():
            adapter = ConsoleAdapter({"user_id": "console_user"})

            async def handle(msg: ChatMessage):
                return f"收到: {msg.content}"

            adapter.on_message(handle)
            await adapter.start()

        asyncio.run(main())
    """

    def __init__(self, config: dict):
        """
        初始化控制台适配器

        Args:
            config: 配置字典
                - user_id: 用户ID (默认: "console_user")
                - chat_id: 会话ID (默认: "console_chat")
                - prompt: 输入提示符 (默认: "> ")
                - welcome: 欢迎消息 (默认: "Console Adapter Ready")
        """
        super().__init__(config)
        self.user_id = config.get("user_id", "console_user")
        self.chat_id = config.get("chat_id", "console_chat")
        self.prompt = config.get("prompt", "> ")
        self.welcome = config.get("welcome", "Console Adapter Ready. Type 'exit' to quit.")
        self._input_queue: asyncio.Queue = asyncio.Queue()
        self._output_queue: asyncio.Queue = asyncio.Queue()
        self._reader_task: Optional[asyncio.Task] = None

    async def start(self):
        """启动控制台适配器"""
        if self._running:
            logger.warning("控制台适配器已在运行")
            return

        self._running = True

        # 打印欢迎消息
        print(f"\n{self.welcome}\n")

        # 启动输入读取任务
        self._reader_task = asyncio.create_task(self._read_input_loop())

        # 启动消息处理循环
        asyncio.create_task(self._process_loop())

        logger.info("控制台适配器已启动")

    async def stop(self):
        """停止控制台适配器"""
        self._running = False

        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass

        print("\n控制台适配器已停止")
        logger.info("控制台适配器已停止")

    async def send_message(self, chat_id: str, content: str, **kwargs) -> ChatResponse:
        """
        发送消息到控制台

        Args:
            chat_id: 会话ID (控制台模式下忽略)
            content: 消息内容
            **kwargs: 额外参数

        Returns:
            ChatResponse 响应对象
        """
        if not self._running:
            return ChatResponse(
                content="",
                success=False,
                error="适配器未运行"
            )

        try:
            # 输出到控制台
            print(content)
            return ChatResponse(
                content=content,
                success=True,
                message_id=f"console_{id(content)}"
            )
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return ChatResponse(
                content="",
                success=False,
                error=str(e)
            )

    async def _read_input_loop(self):
        """读取用户输入循环"""
        loop = asyncio.get_event_loop()

        while self._running:
            try:
                # 在线程中读取输入，避免阻塞
                line = await loop.run_in_executor(None, self._read_line)

                if line is None:
                    continue

                line = line.strip()

                # 处理退出命令
                if line.lower() in ('exit', 'quit', 'q'):
                    await self.stop()
                    break

                if not line:
                    continue

                # 创建消息并放入队列
                message = ChatMessage(
                    chat_id=self.chat_id,
                    user_id=self.user_id,
                    content=line
                )
                await self._input_queue.put(message)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"读取输入失败: {e}")
                await asyncio.sleep(0.1)

    def _read_line(self) -> Optional[str]:
        """同步读取一行输入"""
        try:
            print(self.prompt, end='', flush=True)
            return sys.stdin.readline()
        except EOFError:
            return None
        except Exception:
            return None

    async def _process_loop(self):
        """消息处理循环"""
        while self._running:
            try:
                # 等待输入消息
                message = await asyncio.wait_for(
                    self._input_queue.get(),
                    timeout=0.5
                )

                # 分发消息到处理器
                responses = await self._dispatch_message(message)

                # 输出响应
                for response in responses:
                    if response.content:
                        print(response.content)

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"处理消息失败: {e}")
                await asyncio.sleep(0.1)

    async def send_typing(self, chat_id: str):
        """
        发送正在输入状态

        Args:
            chat_id: 会话ID
        """
        # 控制台模式下打印提示
        print("...", end='\r', flush=True)

    async def send_reaction(self, chat_id: str, message_id: str, reaction: str):
        """
        发送表情反应

        Args:
            chat_id: 会话ID
            message_id: 消息ID
            reaction: 表情
        """
        # 控制台模式下打印表情
        print(f"[{reaction}]")

    def get_stats(self) -> dict:
        """获取统计信息"""
        stats = super().get_stats()
        stats.update({
            "user_id": self.user_id,
            "chat_id": self.chat_id,
            "input_queue_size": self._input_queue.qsize(),
        })
        return stats


class AsyncConsoleAdapter(ConsoleAdapter):
    """
    异步控制台适配器

    支持流式输出，适合与流式 LLM 响应配合使用
    """

    async def send_stream(self, chat_id: str, stream: Any):
        """
        发送流式消息

        Args:
            chat_id: 会话ID
            stream: 异步生成器，产生消息片段
        """
        full_content = []
        try:
            async for chunk in stream:
                if isinstance(chunk, str):
                    print(chunk, end='', flush=True)
                    full_content.append(chunk)
                elif hasattr(chunk, 'content'):
                    print(chunk.content, end='', flush=True)
                    full_content.append(chunk.content)

            print()  # 换行
            return ChatResponse(
                content=''.join(full_content),
                success=True
            )
        except Exception as e:
            logger.error(f"流式输出失败: {e}")
            return ChatResponse(
                content=''.join(full_content),
                success=False,
                error=str(e)
            )
