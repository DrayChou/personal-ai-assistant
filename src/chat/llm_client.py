# -*- coding: utf-8 -*-
"""
LLM 客户端

支持 OpenAI API、MiniMax API 和 Ollama 本地模型
"""
import json
import logging
import urllib.request
from abc import ABC, abstractmethod
from typing import Generator, Optional

try:
    from json_repair import repair_json
    HAS_JSON_REPAIR = True
except ImportError:
    HAS_JSON_REPAIR = False
    repair_json = None

from .exceptions import LLMClientError, ModelNotSupportedError

logger = logging.getLogger('chat.llm')


def safe_json_loads(text: str) -> Optional[dict]:
    """安全地解析 JSON，使用 json_repair 处理不合法的 JSON"""
    if not text or not text.strip():
        return None

    text = text.strip()

    # 首先尝试标准 json 解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试使用 json_repair
    if HAS_JSON_REPAIR and repair_json:
        try:
            repaired = repair_json(text)
            if isinstance(repaired, dict):
                return repaired
            if isinstance(repaired, str):
                return json.loads(repaired)
        except Exception as e:
            logger.debug(f"json_repair 解析失败: {e}")

    # 尝试处理常见的格式问题
    # 1. 处理单引号
    try:
        return json.loads(text.replace("'", '"'))
    except json.JSONDecodeError:
        pass

    # 2. 尝试提取 JSON 对象
    if '{' in text and '}' in text:
        try:
            start = text.find('{')
            end = text.rfind('}') + 1
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass

    logger.warning(f"无法解析 JSON: {text[:200]}")
    return None


class LLMClient(ABC):
    """LLM 客户端基类"""

    @abstractmethod
    def generate(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        response_format: Optional[dict] = None
    ) -> str:
        """生成回复

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            response_format: 响应格式，如 {"type": "json_object"}
        """
        raise NotImplementedError("Subclasses must implement generate()")

    @abstractmethod
    def stream_generate(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Generator[str, None, None]:
        """流式生成回复"""
        raise NotImplementedError("Subclasses must implement stream_generate()")


class OpenAIClient(LLMClient):
    """OpenAI API 客户端"""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini"
    ):
        self.api_key = api_key
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip('/')
        self.model = model

    def generate(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        response_format: Optional[dict] = None
    ) -> str:
        """生成回复"""
        url = f"{self.base_url}/chat/completions"
        data = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # 添加响应格式参数（如需要JSON输出）
        if response_format:
            data["response_format"] = response_format

        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            },
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"OpenAI API 错误: {e}")
            raise

    def stream_generate(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Generator[str, None, None]:
        """流式生成（简化实现，实际应使用 SSE）"""
        # 简化版：直接返回完整回复
        yield self.generate(messages, temperature, max_tokens)


class MiniMaxClient(LLMClient):
    """MiniMax API 客户端 (OpenAI 兼容格式)"""

    # MiniMax 支持的模型列表
    SUPPORTED_MODELS = [
        "MiniMax-M1",
        "MiniMax-M2.5",
        "MiniMax-Text-01",
        "abab6.5s-chat",
        "abab6.5-chat",
    ]

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.minimaxi.com/v1",
        model: str = "MiniMax-M2.5"
    ):
        self.api_key = api_key
        self.base_url = (base_url or "https://api.minimaxi.com/v1").rstrip('/')
        self.model = model

    def generate(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        response_format: Optional[dict] = None
    ) -> str:
        """生成回复"""
        # 使用 OpenAI 兼容的 /chat/completions 端点
        url = f"{self.base_url}/chat/completions"

        data = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # 添加响应格式参数（如需要JSON输出）
        if response_format:
            data["response_format"] = response_format

        # 记录请求体（用于调试）
        logger.info(f"MiniMax 请求体: {json.dumps(data)}")

        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json"
            },
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            try:
                error_body = e.read().decode('utf-8')
            except (UnicodeDecodeError, OSError):
                error_body = "No error body"
            logger.error(f"MiniMax HTTP 错误 {e.code}: {error_body}")
            raise Exception(f"MiniMax API 错误 ({e.code}): {error_body}")
        except Exception as e:
            logger.error(f"MiniMax API 错误: {e}")
            raise

    def stream_generate(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Generator[str, None, None]:
        """流式生成 (OpenAI 兼容格式)"""
        import urllib.error

        url = f"{self.base_url}/chat/completions"

        # 过滤掉 content 为空的消息，避免 API 错误
        filtered_messages = []
        for msg in messages:
            if msg.get("content") or msg.get("role") == "system":
                filtered_messages.append(msg)

        # 确保至少有一条消息
        if not filtered_messages:
            yield "抱歉，没有有效的输入消息。"
            return

        data = {
            "model": self.model,
            "messages": filtered_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }

        # 记录请求信息（用于调试）
        logger.info(f"MiniMax 流式请求: model={self.model}, messages_count={len(filtered_messages)}")
        logger.info(f"MiniMax 请求体: {json.dumps(data, ensure_ascii=False)}")

        req = urllib.request.Request(
            url,
            data=json.dumps(data, ensure_ascii=False).encode('utf-8'),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json"
            },
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                for line in response:
                    line = line.decode('utf-8').strip()
                    logger.debug(f"MiniMax 流式响应行: {line[:100]}...")

                    if not line or line.startswith(':'):
                        continue
                    if line.startswith('data: '):
                        line = line[6:]  # 移除 'data: ' 前缀
                    if line == '[DONE]':
                        break

                    try:
                        chunk = json.loads(line)
                        choices = chunk.get("choices")
                        if choices and isinstance(choices, list) and len(choices) > 0:
                            delta = choices[0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]
                    except json.JSONDecodeError:
                        continue
                    except Exception as e:
                        logger.error(f"处理流式响应出错: {e}, line: {line[:200]}")
                        raise
        except urllib.error.HTTPError as e:
            try:
                error_body = e.read().decode('utf-8')
            except (UnicodeDecodeError, OSError):
                error_body = "No error body"
            logger.error(f"MiniMax HTTP 错误 {e.code}: {error_body}")
            # 提供更有用的错误信息
            if e.code == 400:
                error_msg = "MiniMax 请求格式错误 (400)。可能原因：\n"
                error_msg += f"1. 模型名称 '{self.model}' 不受支持。支持的模型: {', '.join(self.SUPPORTED_MODELS)}\n"
                error_msg += "2. 请求参数格式错误\n"
                error_msg += "3. API Key 无效\n"
                error_msg += f"详细错误: {error_body}"
                raise ModelNotSupportedError(error_msg, status_code=400, response_body=error_body)
            raise LLMClientError(f"MiniMax API 错误 ({e.code}): {error_body}", status_code=e.code, response_body=error_body)
        except Exception as e:
            logger.error(f"MiniMax 流式错误: {e}")
            raise


class OllamaClient(LLMClient):
    """Ollama 本地客户端"""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5:14b"
    ):
        self.base_url = (base_url or "http://localhost:11434").rstrip('/')
        self.model = model

    def generate(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        response_format: Optional[dict] = None
    ) -> str:
        """生成回复"""
        url = f"{self.base_url}/api/chat"
        data = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }
        # Ollama 支持 format 参数用于 JSON 输出
        if response_format and response_format.get("type") == "json_object":
            data["format"] = "json"

        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=300) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result["message"]["content"]
        except Exception as e:
            logger.error(f"Ollama 错误: {e}")
            raise

    def stream_generate(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Generator[str, None, None]:
        """流式生成"""
        url = f"{self.base_url}/api/chat"
        data = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=300) as response:
                for line in response:
                    line = line.decode('utf-8').strip()
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                        if "message" in chunk and "content" in chunk["message"]:
                            yield chunk["message"]["content"]
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"Ollama 流式错误: {e}")
            raise


def create_llm_client(
    provider: str = "openai",
    **kwargs
) -> LLMClient:
    """
    创建 LLM 客户端

    Args:
        provider: "openai"、"minimax" 或 "ollama"
        **kwargs: 配置参数

    Returns:
        LLMClient 实例
    """
    if provider == "openai":
        return OpenAIClient(**kwargs)
    elif provider == "minimax":
        return MiniMaxClient(**kwargs)
    elif provider == "ollama":
        return OllamaClient(**kwargs)
    else:
        raise ValueError(f"不支持的 LLM 提供商: {provider}")
