# -*- coding: utf-8 -*-
"""
MCP (Model Context Protocol) 客户端

支持连接到各种MCP服务：
- 高德地图MCP
- 百度地图MCP
- MiniMax MCP
- GLM MCP
- 自定义MCP服务
"""
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum

logger = logging.getLogger('tools.mcp')


class MCPTransport(Enum):
    """MCP传输协议"""
    STDIO = "stdio"      # 标准输入输出
    SSE = "sse"          # Server-Sent Events
    HTTP = "http"        # HTTP/REST
    WEBSOCKET = "ws"     # WebSocket


@dataclass
class MCPTool:
    """MCP工具定义"""
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema
    required_params: List[str] = field(default_factory=list)
    examples: List[Dict] = field(default_factory=list)

    def to_openai_function(self) -> Dict:
        """转换为OpenAI Function格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }

    def to_anthropic_tool(self) -> Dict:
        """转换为Anthropic Tool格式"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters
        }


@dataclass
class MCPConfig:
    """MCP服务配置"""
    name: str
    transport: MCPTransport
    endpoint: str              # URL或命令
    api_key: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: int = 30


class MCPClient:
    """
    MCP客户端

    支持连接和管理多个MCP服务
    """

    # 预定义的MCP服务配置
    PRESETS = {
        "amap": MCPConfig(
            name="amap",
            transport=MCPTransport.SSE,
            endpoint="https://mcp.amap.com/sse",
            api_key=None  # 需要用户配置
        ),
        "baidu_map": MCPConfig(
            name="baidu_map",
            transport=MCPTransport.SSE,
            endpoint="https://lbsyun.baidu.com/faq/api?title=mcpserver/base",
            api_key=None
        ),
        "minimax": MCPConfig(
            name="minimax",
            transport=MCPTransport.HTTP,
            endpoint="https://api.minimaxi.com/v1",
            api_key=None
        ),
        "glm": MCPConfig(
            name="glm",
            transport=MCPTransport.HTTP,
            endpoint="https://open.bigmodel.cn/api/paas/v4",
            api_key=None
        ),
    }

    def __init__(self, config_manager=None):
        self.configs: Dict[str, MCPConfig] = {}
        self.tools: Dict[str, MCPTool] = {}
        self._http_client = None
        self._config_manager = config_manager

        # 注册预设工具
        self._register_preset_tools()

    def _register_preset_tools(self) -> None:
        """注册预设工具定义"""
        for tool in AMAP_TOOLS:
            self.register_tool(tool)
        for tool in MINIMAX_TOOLS:
            self.register_tool(tool)
        for tool in GLM_TOOLS:
            self.register_tool(tool)

    def load_from_config_manager(self, config_manager) -> int:
        """
        从配置管理器加载 MCP 配置

        Args:
            config_manager: MCPConfigManager 实例

        Returns:
            加载的服务数量
        """
        from .mcp_config_manager import MCPSourceType

        self._config_manager = config_manager
        count = 0

        for name, service_config in config_manager.get_enabled_services().items():
            # 转换配置格式
            transport_map = {
                MCPSourceType.HTTP_SSE: MCPTransport.SSE,
                MCPSourceType.HTTP_REST: MCPTransport.HTTP,
                MCPSourceType.STDIO: MCPTransport.STDIO,
                MCPSourceType.WEBSOCKET: MCPTransport.WEBSOCKET,
            }

            transport = transport_map.get(service_config.source_type, MCPTransport.HTTP)

            self.configs[name] = MCPConfig(
                name=service_config.name,
                transport=transport,
                endpoint=service_config.endpoint or "",
                api_key=service_config.api_key,
                headers=service_config.headers,
                timeout=service_config.timeout,
            )
            count += 1
            logger.info(f"从配置管理器加载 MCP 服务: {name}")

        return count

    def auto_configure_from_env(self) -> int:
        """
        从环境变量自动配置 MCP 服务

        Returns:
            配置的服务数量
        """
        from .mcp_config_manager import MCPConfigManager

        config_manager = MCPConfigManager()
        configs = config_manager.auto_discover_from_env()

        for config in configs:
            # 转换 source_type 到 transport
            transport = MCPTransport.HTTP
            if config.source_type.value == "http_sse":
                transport = MCPTransport.SSE
            elif config.source_type.value == "stdio":
                transport = MCPTransport.STDIO

            self.configs[config.name] = MCPConfig(
                name=config.name,
                transport=transport,
                endpoint=config.endpoint or "",
                api_key=config.api_key,
                headers=config.headers,
            )

        return len(configs)

    def add_preset(self, name: str, api_key: Optional[str] = None) -> bool:
        """
        添加预设MCP服务

        Args:
            name: 预设名称 (amap, baidu_map, minimax, glm)
            api_key: API密钥

        Returns:
            是否成功
        """
        if name not in self.PRESETS:
            logger.error(f"未知的MCP预设: {name}")
            return False

        config = self.PRESETS[name]
        if api_key:
            config.api_key = api_key

        self.configs[name] = config
        logger.info(f"已添加MCP服务: {name}")
        return True

    def add_custom(
        self,
        name: str,
        transport: str,
        endpoint: str,
        api_key: Optional[str] = None,
        headers: Optional[Dict] = None
    ) -> bool:
        """
        添加自定义MCP服务

        Args:
            name: 服务名称
            transport: 传输协议 (stdio, sse, http, ws)
            endpoint: 端点URL或命令
            api_key: API密钥
            headers: 自定义请求头

        Returns:
            是否成功
        """
        try:
            transport_enum = MCPTransport(transport)
        except ValueError:
            logger.error(f"不支持的传输协议: {transport}")
            return False

        self.configs[name] = MCPConfig(
            name=name,
            transport=transport_enum,
            endpoint=endpoint,
            api_key=api_key,
            headers=headers or {}
        )

        logger.info(f"已添加自定义MCP服务: {name}")
        return True

    def register_tool(self, tool: MCPTool) -> None:
        """注册工具"""
        self.tools[tool.name] = tool
        logger.debug(f"已注册工具: {tool.name}")

    def list_tools(self) -> List[MCPTool]:
        """列出所有可用工具"""
        return list(self.tools.values())

    def get_tool(self, name: str) -> Optional[MCPTool]:
        """获取工具定义"""
        return self.tools.get(name)

    async def call_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        调用MCP工具

        Args:
            tool_name: 工具名称
            parameters: 工具参数

        Returns:
            工具执行结果
        """
        tool = self.tools.get(tool_name)
        if not tool:
            return {"error": f"未知工具: {tool_name}"}

        # 查找对应的服务配置
        service_name = tool_name.split("_")[0] if "_" in tool_name else "default"
        config = self.configs.get(service_name)

        if not config:
            return {"error": f"未配置MCP服务: {service_name}"}

        try:
            if config.transport == MCPTransport.HTTP:
                return await self._call_http(config, tool_name, parameters)
            elif config.transport == MCPTransport.SSE:
                return await self._call_sse(config, tool_name, parameters)
            else:
                return {"error": f"不支持的传输协议: {config.transport}"}
        except Exception as e:
            logger.error(f"调用工具失败: {e}")
            return {"error": str(e)}

    async def _call_http(
        self,
        config: MCPConfig,
        tool_name: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """HTTP调用"""
        import aiohttp

        headers = {
            "Content-Type": "application/json",
            **config.headers
        }

        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"

        url = f"{config.endpoint}/{tool_name}"

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers=headers,
                json=parameters,
                timeout=aiohttp.ClientTimeout(total=config.timeout)
            ) as response:
                return await response.json()

    async def _call_sse(
        self,
        config: MCPConfig,
        tool_name: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """SSE调用（简化实现）"""
        # 实际实现需要SSE客户端
        logger.warning("SSE调用暂未完全实现")
        return {"error": "SSE transport not fully implemented"}

    def get_available_functions(self) -> List[Dict]:
        """获取所有可用函数的OpenAI格式定义"""
        return [tool.to_openai_function() for tool in self.tools.values()]

    def get_available_tools_anthropic(self) -> List[Dict]:
        """获取所有可用工具的Anthropic格式定义"""
        return [tool.to_anthropic_tool() for tool in self.tools.values()]


# 预定义的工具
AMAP_TOOLS = [
    MCPTool(
        name="amap_geocode",
        description="将地址转换为经纬度坐标",
        parameters={
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "description": "要转换的地址"
                }
            },
            "required": ["address"]
        }
    ),
    MCPTool(
        name="amap_weather",
        description="查询指定城市的天气",
        parameters={
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "城市名称或城市编码"
                }
            },
            "required": ["city"]
        }
    ),
    MCPTool(
        name="amap_direction",
        description="路径规划",
        parameters={
            "type": "object",
            "properties": {
                "origin": {"type": "string", "description": "起点"},
                "destination": {"type": "string", "description": "终点"},
                "mode": {"type": "string", "enum": ["driving", "walking", "transit", "riding"], "description": "出行方式"}
            },
            "required": ["origin", "destination"]
        }
    ),
]

MINIMAX_TOOLS = [
    MCPTool(
        name="minimax_chat",
        description="使用MiniMax模型进行对话",
        parameters={
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "用户消息"},
                "model": {"type": "string", "default": "MiniMax-M1"}
            },
            "required": ["message"]
        }
    ),
    MCPTool(
        name="minimax_tts",
        description="文本转语音",
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "要转换的文本"},
                "voice_id": {"type": "string", "description": "音色ID"}
            },
            "required": ["text"]
        }
    ),
]

GLM_TOOLS = [
    MCPTool(
        name="glm_chat",
        description="使用GLM模型进行对话",
        parameters={
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "用户消息"},
                "model": {"type": "string", "default": "glm-4"}
            },
            "required": ["message"]
        }
    ),
    MCPTool(
        name="glm_code",
        description="代码生成与解释",
        parameters={
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "代码需求描述"},
                "language": {"type": "string", "description": "编程语言"}
            },
            "required": ["prompt"]
        }
    ),
]
