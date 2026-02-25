# -*- coding: utf-8 -*-
"""
配置管理
"""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class MemoryConfig:
    """记忆系统配置"""
    data_dir: str = "./data/memories"
    working_memory_max_tokens: int = 2000
    consolidation_schedule: str = "0 23 * * *"  # 每天23点
    auto_consolidation: bool = True


@dataclass
class EmbeddingConfig:
    """嵌入模型配置"""
    provider: str = "ollama"  # ollama / openai / hash
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "nomic-embed-text"
    openai_api_key: Optional[str] = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "text-embedding-3-small"


@dataclass
class LLMConfig:
    """LLM配置"""
    provider: str = "openai"  # openai / ollama
    api_key: Optional[str] = None
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    max_tokens: int = 2000


@dataclass
class MCPConfig:
    """MCP 工具配置"""
    enabled: bool = False
    amap_api_key: Optional[str] = None
    baidu_map_api_key: Optional[str] = None
    minimax_api_key: Optional[str] = None
    glm_api_key: Optional[str] = None


@dataclass
class ToolConfig:
    """工具配置"""
    use_ai_intent: bool = True  # 使用 AI 意图分类
    auto_tool_select: bool = True  # 自动选择工具
    max_tool_calls: int = 5  # 最大工具调用次数
    use_semantic_router: bool = True  # 使用 Semantic Router
    semantic_router_threshold: float = 0.7  # Semantic Router 置信度阈值


@dataclass
class AppConfig:
    """应用配置"""
    memory: Optional[MemoryConfig] = None
    embedding: Optional[EmbeddingConfig] = None
    llm: Optional[LLMConfig] = None
    mcp: Optional[MCPConfig] = None
    tool: Optional[ToolConfig] = None
    log_level: str = "INFO"

    def __post_init__(self) -> None:
        if self.memory is None:
            self.memory = MemoryConfig()
        if self.embedding is None:
            self.embedding = EmbeddingConfig()
        if self.llm is None:
            self.llm = LLMConfig()
        if self.mcp is None:
            self.mcp = MCPConfig()
        if self.tool is None:
            self.tool = ToolConfig()


def load_config() -> AppConfig:
    """加载配置（从环境变量和默认值）"""
    embedding = EmbeddingConfig(
        ollama_base_url=os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434'),
        openai_api_key=os.environ.get('OPENAI_API_KEY'),
    )

    llm = LLMConfig(
        api_key=os.environ.get('LLM_API_KEY') or os.environ.get('OPENAI_API_KEY'),
        base_url=os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1'),
        model=os.environ.get('LLM_MODEL', 'gpt-4o-mini'),
    )

    mcp = MCPConfig(
        enabled=os.environ.get('MCP_ENABLED', 'false').lower() == 'true',
        amap_api_key=os.environ.get('AMAP_API_KEY'),
        baidu_map_api_key=os.environ.get('BAIDU_MAP_API_KEY'),
        minimax_api_key=os.environ.get('MINIMAX_API_KEY'),
        glm_api_key=os.environ.get('GLM_API_KEY'),
    )

    tool = ToolConfig(
        use_ai_intent=os.environ.get('USE_AI_INTENT', 'true').lower() == 'true',
        auto_tool_select=os.environ.get('AUTO_TOOL_SELECT', 'true').lower() == 'true',
        max_tool_calls=int(os.environ.get('MAX_TOOL_CALLS', '5')),
        use_semantic_router=os.environ.get('USE_SEMANTIC_ROUTER', 'true').lower() == 'true',
        semantic_router_threshold=float(os.environ.get('SEMANTIC_ROUTER_THRESHOLD', '0.7')),
    )

    return AppConfig(
        embedding=embedding,
        llm=llm,
        mcp=mcp,
        tool=tool,
        log_level=os.environ.get('LOG_LEVEL', 'INFO'),
    )


# Settings 类 - 兼容 main.py 的期望接口
class Settings:
    """
    应用设置类

    为 main.py 提供统一的配置接口
    """

    def __init__(
        self,
        data_dir: Optional[str] = None,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
        llm_api_key: Optional[str] = None,
        llm_base_url: Optional[str] = None,
        embedding_provider: Optional[str] = None,
        embedding_model: Optional[str] = None,
        embedding_api_key: Optional[str] = None,
        embedding_base_url: Optional[str] = None,
        session_id: str = "default",
        mcp_enabled: bool = False,
        use_ai_intent: bool = True,
        use_semantic_router: bool = True,
        semantic_router_threshold: float = 0.7,
    ):
        self.data_dir = data_dir or os.environ.get('DATA_DIR', './data')
        self.llm_provider = llm_provider or os.environ.get('LLM_PROVIDER', 'ollama')
        self.llm_model = llm_model or os.environ.get('LLM_MODEL', 'qwen2.5:14b')
        self.llm_api_key = llm_api_key or os.environ.get('LLM_API_KEY') or os.environ.get('OPENAI_API_KEY') or os.environ.get('MINIMAX_API_KEY')
        self.llm_base_url = llm_base_url or os.environ.get('LLM_BASE_URL', 'http://localhost:11434')
        self.embedding_provider = embedding_provider or os.environ.get('EMBEDDING_PROVIDER', 'ollama')
        self.embedding_model = embedding_model or os.environ.get('EMBEDDING_MODEL', 'nomic-embed-text')
        self.embedding_api_key = embedding_api_key or os.environ.get('EMBEDDING_API_KEY')
        self.embedding_base_url = embedding_base_url or os.environ.get('EMBEDDING_BASE_URL', 'http://localhost:11434')
        self.session_id = session_id

        # MCP 配置
        self.mcp_enabled = mcp_enabled or os.environ.get('MCP_ENABLED', 'false').lower() == 'true'
        self.mcp_amap_api_key = os.environ.get('AMAP_API_KEY')
        self.mcp_baidu_map_api_key = os.environ.get('BAIDU_MAP_API_KEY')
        self.mcp_minimax_api_key = os.environ.get('MINIMAX_API_KEY')
        self.mcp_glm_api_key = os.environ.get('GLM_API_KEY')

        # 工具配置
        self.use_ai_intent = use_ai_intent or os.environ.get('USE_AI_INTENT', 'true').lower() == 'true'
        self.auto_tool_select = os.environ.get('AUTO_TOOL_SELECT', 'true').lower() == 'true'

        # Semantic Router 配置
        self.use_semantic_router = use_semantic_router or os.environ.get('USE_SEMANTIC_ROUTER', 'true').lower() == 'true'
        self.semantic_router_threshold = semantic_router_threshold or float(os.environ.get('SEMANTIC_ROUTER_THRESHOLD', '0.7'))
