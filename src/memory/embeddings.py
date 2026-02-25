# -*- coding: utf-8 -*-
"""
嵌入向量生成模块
支持 Ollama 本地、OpenAI API、哈希回退
"""
import hashlib
import json
import logging
import os
import time
import urllib.error
import urllib.request
from functools import lru_cache
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger('memory.embeddings')

# 全局配置
_config = {
    'provider_priority': ['ollama', 'openai_compatible', 'hash_fallback'],
    'providers': {},
    '_provider_status': {},
}

DEFAULT_CONFIG = {
    'ollama': {
        'enabled': True,
        'base_url': os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434'),
        'model': os.environ.get('EMBEDDING_MODEL', 'nomic-embed-text'),
        'dim': 768,
        'timeout': 10,
    },
    'openai_compatible': {
        'enabled': False,
        'base_url': 'https://api.openai.com/v1',
        'model': 'text-embedding-3-small',
        'api_key': '',
        'dim': 1536,
        'timeout': 30,
    },
    'hash_fallback': {
        'enabled': True,
        'dim': 768,
    },
}


def init_config(config_path: Optional[str] = None):
    """初始化配置"""
    global _config

    if config_path is None:
        config_path = os.environ.get(
            'EMBEDDING_CONFIG',
            './config/embedding_config.json'
        )

    config_file = Path(config_path)
    loaded = {}
    if config_file.exists():
        try:
            with open(config_file, encoding='utf-8') as f:
                loaded = json.load(f)
        except Exception as e:
            logger.warning(f"加载嵌入配置失败: {e}")

    _config['provider_priority'] = loaded.get(
        'provider_priority',
        ['ollama', 'openai_compatible', 'hash_fallback']
    )
    _config['providers'] = loaded.get('providers', DEFAULT_CONFIG)

    # 环境变量覆盖
    if os.environ.get('OLLAMA_BASE_URL'):
        _config['providers']['ollama']['base_url'] = os.environ['OLLAMA_BASE_URL']
    if os.environ.get('OPENAI_API_KEY'):
        _config['providers']['openai_compatible']['api_key'] = os.environ['OPENAI_API_KEY']
        _config['providers']['openai_compatible']['enabled'] = True


def _check_ollama_available(config: dict) -> bool:
    """检查 Ollama 服务是否可用"""
    try:
        url = f"{config['base_url']}/api/tags"
        req = urllib.request.Request(url, method='GET')
        with urllib.request.urlopen(req, timeout=2) as response:
            return response.status == 200
    except Exception as e:
        logger.debug(f"Ollama check failed: {e}")
        return False


def _check_api_available(config: dict) -> bool:
    """检查 OpenAI API 是否可用"""
    if not config.get('api_key'):
        return False
    try:
        url = f"{config['base_url']}/models"
        req = urllib.request.Request(
            url,
            headers={'Authorization': f"Bearer {config['api_key']}"},
            method='GET'
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status == 200
    except Exception as e:
        logger.debug(f"API check failed: {e}")
        return False


def _get_provider_status(provider: str) -> bool:
    """获取提供商可用状态"""
    global _config

    status_key = f'{provider}_available'
    last_check = _config['_provider_status'].get(f'{provider}_last_check', 0)
    cache_ttl = 30  # 30秒缓存

    if time.time() - last_check < cache_ttl:
        return _config['_provider_status'].get(status_key, False)

    config = _config['providers'].get(provider, {})
    if not config.get('enabled', False):
        available = False
    elif provider == 'ollama':
        available = _check_ollama_available(config)
    elif provider == 'openai_compatible':
        available = _check_api_available(config)
    elif provider == 'hash_fallback':
        available = True
    else:
        available = False

    _config['_provider_status'][status_key] = available
    _config['_provider_status'][f'{provider}_last_check'] = time.time()

    return available


def _get_ollama_embeddings(text: str, config: dict) -> Optional[list[float]]:
    """使用 Ollama 生成嵌入"""
    try:
        url = f"{config['base_url']}/api/embeddings"
        data = {"model": config['model'], "prompt": text}

        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )

        with urllib.request.urlopen(req, timeout=config.get('timeout', 10)) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result.get('embedding')
    except Exception as e:
        logger.debug(f"Ollama 嵌入失败: {e}")
    return None


def _get_api_embeddings(text: str, config: dict) -> Optional[list[float]]:
    """使用 OpenAI API 生成嵌入"""
    try:
        url = f"{config['base_url']}/embeddings"
        data = {"model": config['model'], "input": text}

        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers={
                'Content-Type': 'application/json',
                'Authorization': f"Bearer {config['api_key']}"
            },
            method='POST'
        )

        with urllib.request.urlopen(req, timeout=config.get('timeout', 30)) as response:
            result = json.loads(response.read().decode('utf-8'))
            if 'data' in result and len(result['data']) > 0:
                return result['data'][0].get('embedding')
    except Exception as e:
        logger.debug(f"API 嵌入失败: {e}")
    return None


def _hash_embedding(text: str, dim: int = 768) -> list[float]:
    """哈希回退嵌入（仅用于测试）"""
    hash_val = hashlib.md5(text.encode()).hexdigest()
    embedding = []
    hash_len = len(hash_val)

    for i in range(dim):
        idx = (i * 2) % hash_len
        val = int(hash_val[idx:idx+2], 16) / 255.0
        val = (val - 0.5) * 2
        embedding.append(val)

    return embedding


def generate_embedding(text: str) -> list[float]:
    """
    生成嵌入向量

    按优先级尝试：Ollama -> OpenAI API -> 哈希回退
    """
    global _config

    if not _config['providers']:
        init_config()

    for provider in _config['provider_priority']:
        if not _get_provider_status(provider):
            continue

        config = _config['providers'].get(provider, {})

        if provider == 'ollama':
            embedding = _get_ollama_embeddings(text, config)
        elif provider == 'openai_compatible':
            embedding = _get_api_embeddings(text, config)
        elif provider == 'hash_fallback':
            embedding = _hash_embedding(text, config.get('dim', 768))
        else:
            continue

        if embedding:
            logger.debug(f"使用 {provider} 生成嵌入，维度: {len(embedding)}")
            return embedding

    # 最终回退
    logger.warning("所有嵌入提供商都失败，使用哈希回退")
    return _hash_embedding(text, 768)


@lru_cache(maxsize=1000)
def cached_embedding(text: str) -> tuple[float, ...]:
    """缓存的嵌入生成"""
    return tuple(generate_embedding(text))


def get_embedding_dimension() -> int:
    """获取当前嵌入维度"""
    global _config
    if not _config['providers']:
        init_config()

    for provider in _config['provider_priority']:
        if _get_provider_status(provider):
            config = _config['providers'].get(provider, {})
            return config.get('dim', 768)
    return 768


def get_active_provider() -> str:
    """获取当前活动的提供商"""
    global _config
    if not _config['providers']:
        init_config()

    for provider in _config['provider_priority']:
        if _get_provider_status(provider):
            return provider
    return 'hash_fallback'


def create_embedding_function() -> Callable[[str], list[float]]:
    """创建嵌入函数"""
    return generate_embedding
