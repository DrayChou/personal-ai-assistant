# -*- coding: utf-8 -*-
"""
LLM 适配器

提供统一的工具调用接口，适配不同 LLM 提供商
"""
import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncGenerator, Optional

logger = logging.getLogger('agent.llm_adapter')


@dataclass
class ToolCall:
    """工具调用"""
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    """LLM 响应"""
    content: Optional[str] = None
    tool_calls: list[ToolCall] = None
    finish_reason: str = "stop"

    def __post_init__(self):
        if self.tool_calls is None:
            self.tool_calls = []


class LLMAdapter(ABC):
    """LLM 适配器基类"""

    @abstractmethod
    async def generate_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        tool_choice: str = "auto",
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> LLMResponse:
        """
        使用工具调用生成响应

        Args:
            messages: 消息列表
            tools: 工具定义列表 (Function Calling schema)
            tool_choice: 工具选择策略 ("auto", "none", "required")
            temperature: 温度参数
            max_tokens: 最大token数

        Returns:
            LLMResponse
        """
        pass

    @abstractmethod
    async def generate(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        response_format: Optional[dict] = None
    ) -> str:
        """普通文本生成"""
        pass

    @abstractmethod
    async def stream_generate(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> AsyncGenerator[str, None]:
        """流式文本生成"""
        pass


class OpenAICompatibleAdapter(LLMAdapter):
    """
    OpenAI 兼容适配器

    适用于 OpenAI、MiniMax 等兼容 OpenAI API 的提供商
    """

    def __init__(self, llm_client):
        self.client = llm_client
        self.provider = getattr(llm_client, '__class__.__name__', 'unknown')

    async def generate_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        tool_choice: str = "auto",
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> LLMResponse:
        """
        使用工具调用生成响应

        通过直接调用 HTTP API 支持 tools 参数
        """
        import urllib.request
        import urllib.error

        url = f"{self.client.base_url}/chat/completions"

        data = {
            "model": self.client.model,
            "messages": messages,
            "tools": tools,
            "tool_choice": tool_choice,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.client.api_key}"
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers=headers,
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode('utf-8'))
                message = result["choices"][0]["message"]

                # 解析工具调用
                tool_calls = []
                if "tool_calls" in message:
                    for tc in message["tool_calls"]:
                        if tc.get("type") == "function":
                            tool_calls.append(ToolCall(
                                id=tc.get("id", ""),
                                name=tc["function"]["name"],
                                arguments=json.loads(tc["function"]["arguments"])
                            ))

                return LLMResponse(
                    content=message.get("content"),
                    tool_calls=tool_calls,
                    finish_reason=result["choices"][0].get("finish_reason", "stop")
                )

        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if hasattr(e, 'read') else "Unknown error"
            logger.error(f"LLM API HTTP 错误 {e.code}: {error_body}")

            # 如果是 400 错误，可能是 provider 不支持 tools 参数
            if e.code == 400:
                logger.warning(f"{self.provider} 可能不支持 tools 参数，回退到提示工程模式")
                return await self._fallback_with_prompt(messages, tools, temperature, max_tokens)

            raise Exception(f"LLM API 错误 ({e.code}): {error_body}")

        except Exception as e:
            logger.error(f"LLM API 错误: {e}")
            raise

    async def _fallback_with_prompt(
        self,
        messages: list[dict],
        tools: list[dict],
        temperature: float,
        max_tokens: int
    ) -> LLMResponse:
        """
        回退到提示工程模式

        当 API 不支持 tools 参数时，通过精心设计的提示来模拟工具选择
        """
        # 构建工具描述
        tools_desc = self._format_tools_for_prompt(tools)

        system_prompt = f"""你是一个智能助手，必须使用以下工具来帮助用户完成任务：

{tools_desc}

【关键规则 - 必须遵守】
1. 用户说"清理任务"、"删除任务"、"清空任务" → 必须使用 delete_tasks
2. 用户说"查看任务"、"有什么任务"、"显示任务" → 使用 list_tasks
3. 用户说"完成任务"、"做完了" → 使用 complete_task
4. 用户说"创建任务"、"提醒我" → 使用 create_task

【回复格式】
如果需要使用工具，必须严格按照以下格式回复（不要添加其他内容）：
<tool_call>
{{"name": "工具名", "arguments": {{"参数名": "值"}}}}
</tool_call>

如果不需要工具，直接回复用户。

【示例】
用户：查看我的任务
助手：<tool_call>
{{"name": "list_tasks", "arguments": {{}}}}
</tool_call>

用户：清理这些任务
助手：<tool_call>
{{"name": "delete_tasks", "arguments": {{"delete_all": true, "confirmed": false}}}}
</tool_call>"""

        # 添加系统提示
        enhanced_messages = [{"role": "system", "content": system_prompt}] + messages

        # 调用普通生成
        content = await self.generate(enhanced_messages, temperature, max_tokens)

        # 解析工具调用
        tool_calls = []
        if "<tool_call>" in content:
            try:
                import re
                match = re.search(r'<tool_call>\s*(\{.*?\})\s*</tool_call>', content, re.DOTALL)
                if match:
                    tool_data = json.loads(match.group(1))
                    tool_calls.append(ToolCall(
                        id="call_0",
                        name=tool_data["name"],
                        arguments=tool_data.get("arguments", {})
                    ))
                    # 移除工具调用标记，保留其他内容
                    content = re.sub(r'<tool_call>.*?</tool_call>', '', content, flags=re.DOTALL).strip()
            except Exception as e:
                logger.warning(f"解析工具调用失败: {e}")

        return LLMResponse(content=content, tool_calls=tool_calls)

    def _format_tools_for_prompt(self, tools: list[dict]) -> str:
        """将工具格式化为提示文本"""
        lines = []
        for tool in tools:
            func = tool.get("function", {})
            name = func.get("name", "")
            desc = func.get("description", "")
            params = func.get("parameters", {})

            lines.append(f"工具名: {name}")
            lines.append(f"描述: {desc}")

            if "properties" in params:
                lines.append("参数:")
                for param_name, param_info in params["properties"].items():
                    required = " (必需)" if param_name in params.get("required", []) else ""
                    lines.append(f"  - {param_name}: {param_info.get('description', '')}{required}")

            lines.append("")

        return "\n".join(lines)

    async def generate(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        response_format: Optional[dict] = None
    ) -> str:
        """普通文本生成"""
        # 使用底层客户端的 generate 方法
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.client.generate(messages, temperature, max_tokens, response_format)
        )

    async def stream_generate(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> AsyncGenerator[str, None]:
        """流式文本生成 - 真正的异步流式"""
        import threading
        import queue as thread_queue

        _loop = asyncio.get_event_loop()  # noqa: F841 - reserved for future async operations
        chunk_queue: thread_queue.Queue = thread_queue.Queue()
        done_event = threading.Event()
        exception_holder = [None]

        def run_stream():
            """在后台线程运行同步生成器"""
            try:
                for chunk in self.client.stream_generate(messages, temperature, max_tokens):
                    chunk_queue.put(chunk)
            except Exception as e:
                exception_holder[0] = e
            finally:
                done_event.set()

        # 启动后台线程
        thread = threading.Thread(target=run_stream, daemon=True)
        thread.start()

        # 异步 yield chunks
        while not done_event.is_set() or not chunk_queue.empty():
            try:
                chunk = chunk_queue.get(timeout=0.01)
                yield chunk
            except thread_queue.Empty:
                await asyncio.sleep(0.001)  # 短暂让出控制权

        # 检查是否有异常
        if exception_holder[0]:
            raise exception_holder[0]


class OllamaAdapter(LLMAdapter):
    """
    Ollama 适配器

    Ollama 不支持标准的 tools 参数，使用提示工程模拟
    """

    def __init__(self, llm_client):
        self.client = llm_client

    async def generate_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        tool_choice: str = "auto",
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> LLMResponse:
        """使用提示工程模拟工具调用"""

        # 构建工具描述
        tools_desc = self._format_tools_for_prompt(tools)

        system_prompt = f"""你是一个智能助手，可以使用以下工具来帮助用户：

{tools_desc}

重要规则：
1. 如果需要使用工具，请严格按照以下 JSON 格式回复，不要添加其他内容：
   {{"tool": "工具名", "params": {{"参数名": "值"}}}}

2. 如果不需要工具，直接回复用户。

3. 只能使用上面列出的工具。"""

        # 添加系统提示
        enhanced_messages = [{"role": "system", "content": system_prompt}] + messages

        # 调用生成
        content = await self.generate(enhanced_messages, temperature, max_tokens)

        # 尝试解析为工具调用
        tool_calls = []
        try:
            # 尝试解析 JSON
            data = json.loads(content.strip())
            if "tool" in data:
                tool_calls.append(ToolCall(
                    id="call_0",
                    name=data["tool"],
                    arguments=data.get("params", {})
                ))
                content = None  # 工具调用时没有文本内容
        except json.JSONDecodeError:
            # 不是 JSON，当作普通文本回复
            pass
        except Exception as e:
            logger.warning(f"解析工具调用失败: {e}")

        return LLMResponse(content=content, tool_calls=tool_calls)

    def _format_tools_for_prompt(self, tools: list[dict]) -> str:
        """将工具格式化为提示文本"""
        lines = []
        for tool in tools:
            func = tool.get("function", {})
            name = func.get("name", "")
            desc = func.get("description", "")
            params = func.get("parameters", {})

            lines.append(f"- {name}: {desc}")
            if "properties" in params:
                for param_name, param_info in params["properties"].items():
                    required = " (必需)" if param_name in params.get("required", []) else ""
                    lines.append(f"    {param_name}: {param_info.get('description', '')}{required}")

        return "\n".join(lines)

    async def generate(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        response_format: Optional[dict] = None
    ) -> str:
        """普通文本生成"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.client.generate(messages, temperature, max_tokens, response_format)
        )

    async def stream_generate(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> AsyncGenerator[str, None]:
        """流式文本生成 - 真正的异步流式"""
        import threading
        import queue as thread_queue

        _loop = asyncio.get_event_loop()  # noqa: F841 - reserved for future async operations
        chunk_queue: thread_queue.Queue = thread_queue.Queue()
        done_event = threading.Event()
        exception_holder = [None]

        def run_stream():
            """在后台线程运行同步生成器"""
            try:
                for chunk in self.client.stream_generate(messages, temperature, max_tokens):
                    chunk_queue.put(chunk)
            except Exception as e:
                exception_holder[0] = e
            finally:
                done_event.set()

        # 启动后台线程
        thread = threading.Thread(target=run_stream, daemon=True)
        thread.start()

        # 异步 yield chunks
        while not done_event.is_set() or not chunk_queue.empty():
            try:
                chunk = chunk_queue.get(timeout=0.01)
                yield chunk
            except thread_queue.Empty:
                await asyncio.sleep(0.001)  # 短暂让出控制权

        # 检查是否有异常
        if exception_holder[0]:
            raise exception_holder[0]


def create_llm_adapter(llm_client) -> LLMAdapter:
    """
    创建合适的 LLM 适配器

    Args:
        llm_client: LLM 客户端实例

    Returns:
        LLMAdapter 实例
    """
    class_name = llm_client.__class__.__name__

    if class_name in ["OpenAIClient", "MiniMaxClient"]:
        return OpenAICompatibleAdapter(llm_client)
    elif class_name == "OllamaClient":
        return OllamaAdapter(llm_client)
    else:
        # 默认使用 OpenAI 兼容适配器
        logger.warning(f"未知的 LLM 客户端类型: {class_name}，尝试使用 OpenAI 兼容适配器")
        return OpenAICompatibleAdapter(llm_client)
