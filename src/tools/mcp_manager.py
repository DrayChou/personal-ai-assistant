# -*- coding: utf-8 -*-
"""
统一 MCP 管理器

集中管理所有 MCP 服务器连接和工具调用
"""
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from .mcp_client import MCPClient, MCPConfig, MCPTool, MCPTransport

logger = logging.getLogger('tools.mcp.manager')


@dataclass
class MCPManagerConfig:
    """MCP 管理器配置"""
    config_path: Optional[str] = None
    presets: list[str] = field(default_factory=list)
    auto_discover: bool = True
    timeout: int = 30
    fallback_enabled: bool = True
    max_retries: int = 3


@dataclass
class MCPConnection:
    """MCP 服务器连接"""
    name: str
    config: MCPConfig
    client: MCPClient
    status: str = "disconnected"
    tools: list[MCPTool] = field(default_factory=list)
    last_error: Optional[str] = None
    connected_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "tool_count": len(self.tools),
            "connected_at": self.connected_at.isoformat() if self.connected_at else None,
            "last_error": self.last_error,
        }


class MCPManager:
    """
    统一 MCP 管理器

    集中管理所有 MCP 服务器连接和工具调用
    提供统一的工具发现和执行接口
    """

    PRESET_SERVERS = {
        "brave-search": {
            "command": "npx",
            "args": ["-y", "@anthropic-ai/mcp-server-brave-search"],
            "env": {"BRAVE_API_KEY": "${BRAVE_API_KEY}"}
        },
        "filesystem": {
            "command": "npx",
            "args": ["-y", "@anthropic-ai/mcp-server-filesystem", "/workspace"],
            "env": {}
        },
        "github": {
            "command": "npx",
            "args": ["-y", "@anthropic-ai/mcp-server-github"],
            "env": {"GITHUB_TOKEN": "${GITHUB_TOKEN}"}
        },
        "memory": {
            "command": "npx",
            "args": ["-y", "@anthropic-ai/mcp-server-memory"],
            "env": {}
        },
    }

    def __init__(self, config: Optional[MCPManagerConfig] = None):
        self.config = config or MCPManagerConfig()
        self.connections: dict[str, MCPConnection] = {}
        self._tools_index: dict[str, dict] = {}  # 工具名称到连接的映射

        logger.info(f"MCP 管理器初始化，预设服务器: {len(self.PRESET_SERVERS)}")

    def load_from_config(self, config_path: str) -> int:
        """
        从配置文件加载 MCP 服务器

        Args:
            config_path: 配置文件路径 (JSON 格式)

        Returns:
            加载的服务数量
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

            servers = config_data.get("mcpServers", {})
            loaded = 0

            for name, server_config in servers.items():
                try:
                    self._load_server(name, server_config)
                    loaded += 1
                except Exception as e:
                    logger.warning(f"加载 MCP 服务器 {name} 失败: {e}")

            return loaded
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return 0

    def load_presets(self, presets: list[str]) -> int:
        """
        加载预设服务器

        Args:
            presets: 预设服务器名称列表

        Returns:
            加载的服务数量
        """
        loaded = 0

        for name in presets:
            if name not in self.PRESET_SERVERS:
                logger.warning(f"未知预设服务器: {name}")
                continue

            preset = self.PRESET_SERVERS[name].copy()
            try:
                # 解析环境变量
                resolved_env = {}
                for key, value in preset.get("env", {}).items():
                    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                        env_key = key[2:-1]  # 提取 ${KEY}
                        actual_value = os.environ.get(env_key, value)
                        resolved_env[key] = actual_value
                    else:
                        resolved_env[key] = value

                preset["env"] = resolved_env

                self._load_server(name, preset)
                loaded += 1
            except Exception as e:
                logger.warning(f"加载预设服务器 {name} 失败: {e}")

        return loaded

    def _load_server(self, name: str, config: dict) -> None:
        """
        加载单个服务器

        Args:
            name: 服务器名称
            config: 服务器配置
        """
        if name in self.connections:
            logger.warning(f"MCP 服务器 {name} 已存在，将被覆盖")

        # 创建配置
        mcp_config = MCPConfig(
            name=name,
            transport=MCPTransport(config.get("transport", "http")),
            endpoint=config.get("endpoint", config.get("command", "")),
            api_key=config.get("api_key"),
            headers=config.get("headers", {}),
            timeout=config.get("timeout", 30)
        )

        # 创建客户端并添加配置
        client = MCPClient()
        client.configs[name] = mcp_config

        # 存储连接
        self.connections[name] = MCPConnection(
            name=name,
            config=mcp_config,
            client=client,
            status="disconnected"
        )

        logger.info(f"已加载 MCP 服务器: {name}")

    async def connect_all(self) -> dict[str, Any]:
        """
        连接所有服务器

        Returns:
            连接结果 {服务名: 状态}
        """
        results = {}
        for name, conn in self.connections.items():
            try:
                await self.connect(name)
                results[name] = "connected"
            except Exception as e:
                results[name] = f"failed: {e}"
                logger.error(f"连接 MCP 服务器 {name} 失败: {e}")

        return results

    async def connect(self, name: str) -> bool:
        """
        连接指定服务器

        Args:
            name: 服务器名称

        Returns:
            是否成功
        """
        if name not in self.connections:
            raise ValueError(f"MCP 服务器 {name} 不存在")

        conn = self.connections[name]
        if conn.status == "connected":
            logger.info(f"MCP 服务器 {name} 已连接")
            return True

        try:
            # 获取工具列表
            tools = conn.client.list_tools()
            conn.tools = tools
            conn.status = "connected"
            conn.connected_at = datetime.now()

            # 更新工具索引
            for tool in tools:
                self._tools_index[tool.name] = {
                    "server": name,
                    "tool": tool
                }

            logger.info(f"MCP 服务器 {name} 已连接，工具数: {len(tools)}")
            return True
        except Exception as e:
            conn.status = "error"
            conn.last_error = str(e)
            logger.error(f"连接 MCP 服务器 {name} 失败: {e}")
            return False

    async def disconnect(self, name: str) -> bool:
        """
        断开服务器连接

        Args:
            name: 服务器名称

        Returns:
            是否成功
        """
        if name not in self.connections:
            return False

        conn = self.connections[name]
        try:
            # 清理工具索引
            for tool in conn.tools:
                if tool.name in self._tools_index:
                    del self._tools_index[tool.name]

            conn.status = "disconnected"
            conn.tools = []
            logger.info(f"已断开 MCP 服务器: {name}")
            return True
        except Exception as e:
            logger.error(f"断开 MCP 服务器 {name} 失败: {e}")
            return False

    def get_all_tools(self) -> list[MCPTool]:
        """获取所有可用工具"""
        return [
            info["tool"]
            for info in self._tools_index.values()
        ]

    def get_tool(self, tool_name: str) -> Optional[MCPTool]:
        """
        获取指定工具

        Args:
            tool_name: 工具名称

        Returns:
            工具对象，不存在返回 None
        """
        if tool_name not in self._tools_index:
            return None

        return self._tools_index[tool_name]["tool"]

    def get_openai_schemas(self) -> list[dict]:
        """
        获取所有工具的 OpenAI Function Schema

        Returns:
            Schema 列表
        """
        schemas = []
        for tool in self.get_all_tools():
            schemas.append(tool.to_openai_function())
        return schemas

    def get_anthropic_schemas(self) -> list[dict]:
        """
        获取所有工具的 Anthropic Tool Schema

        Returns:
            Schema 列表
        """
        schemas = []
        for tool in self.get_all_tools():
            schemas.append(tool.to_anthropic_tool())
        return schemas

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any]
    ) -> Any:
        """
        执行 MCP 工具

        Args:
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            执行结果

        Raises:
            ValueError: 工具不存在
            RuntimeError: 服务器未连接
        """
        if tool_name not in self._tools_index:
            raise ValueError(f"MCP 工具 {tool_name} 不存在")

        tool_info = self._tools_index[tool_name]
        server_name = tool_info["server"]

        conn = self.connections.get(server_name)
        if not conn or conn.status != "connected":
            raise RuntimeError(f"MCP 服务器 {server_name} 未连接")

        try:
            result = await conn.client.call_tool(tool_name, arguments)
            return result
        except Exception as e:
            logger.error(f"执行 MCP 工具 {tool_name} 失败: {e}")
            raise

    def get_stats(self) -> dict:
        """
        获取管理器统计信息

        Returns:
            统计信息字典
        """
        return {
            "total_servers": len(self.connections),
            "connected_servers": sum(1 for c in self.connections.values() if c.status == "connected"),
            "total_tools": len(self._tools_index),
            "servers": {
                name: conn.to_dict()
                for name, conn in self.connections.items()
            }
        }

    async def close(self):
        """关闭管理器，断开所有连接"""
        for name in list(self.connections.keys()):
            try:
                await self.disconnect(name)
            except Exception as e:
                logger.error(f"断开 MCP 服务器 {name} 失败: {e}")

        logger.info("MCP 管理器已关闭")
