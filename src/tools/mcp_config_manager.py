# -*- coding: utf-8 -*-
"""
MCP 配置管理器

支持自动发现和加载 MCP 工具配置：
- 从远程 URL 加载 MCP 配置
- 从本地配置文件加载
- 支持 HTTP MCP 和 stdio 模式的在线服务
- 自动检测可用工具
"""
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum
import yaml

logger = logging.getLogger('tools.mcp_config')


class MCPSourceType(Enum):
    """MCP 配置来源类型"""
    HTTP_SSE = "http_sse"      # HTTP + Server-Sent Events
    HTTP_REST = "http_rest"    # HTTP REST API
    STDIO = "stdio"            # 标准输入输出（本地进程）
    WEBSOCKET = "websocket"    # WebSocket


@dataclass
class MCPServiceConfig:
    """单个 MCP 服务配置"""
    name: str
    source_type: MCPSourceType
    # HTTP 相关配置
    endpoint: Optional[str] = None           # HTTP 端点 URL
    api_key: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    # STDIO 相关配置
    command: Optional[str] = None            # 可执行命令
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    # 通用配置
    timeout: int = 30
    enabled: bool = True
    description: str = ""
    auto_discover: bool = True               # 自动发现工具


@dataclass
class MCPRegistry:
    """MCP 服务注册表"""
    services: Dict[str, MCPServiceConfig] = field(default_factory=dict)
    discovered_tools: Dict[str, Any] = field(default_factory=dict)


class MCPConfigManager:
    """
    MCP 配置管理器

    功能：
    1. 从远程 URL 加载 MCP 配置
    2. 从本地配置文件加载
    3. 自动发现和注册工具
    4. 支持 HTTP/SSE/STDIO 多种模式
    """

    # 预设的 MCP 服务配置模板
    PRESET_TEMPLATES = {
        # ===== HTTP 在线服务 =====
        "amap": {
            "name": "amap",
            "source_type": "http_sse",
            "endpoint": "https://mcp.amap.com/sse",
            "description": "高德地图 MCP - 地理编码、天气、路径规划",
            "requires_key": True,
        },
        "baidu_map": {
            "name": "baidu_map",
            "source_type": "http_sse",
            "endpoint": "https://lbsyun.baidu.com/faq/api?title=mcpserver/base",
            "description": "百度地图 MCP - 地图服务",
            "requires_key": True,
        },
        "minimax": {
            "name": "minimax",
            "source_type": "http_rest",
            "endpoint": "https://api.minimaxi.com/v1",
            "description": "MiniMax MCP (HTTP) - 文本生成、语音合成",
            "requires_key": True,
        },
        "glm": {
            "name": "glm",
            "source_type": "http_rest",
            "endpoint": "https://open.bigmodel.cn/api/paas/v4",
            "description": "GLM MCP - 代码生成、对话",
            "requires_key": True,
        },
        "github": {
            "name": "github",
            "source_type": "http_rest",
            "endpoint": "https://api.github.com",
            "description": "GitHub API - 代码仓库操作",
            "requires_key": True,
        },
        # ===== STDIO 本地服务 (uvx) =====
        "fetch": {
            "name": "fetch",
            "source_type": "stdio",
            "command": "uvx",
            "args": ["mcp-server-fetch"],
            "description": "网页内容获取 MCP - 获取任意 URL 内容",
            "requires_key": False,
        },
        "minimax_search": {
            "name": "minimax_search",
            "source_type": "stdio",
            "command": "uvx",
            "args": ["minimax-coding-plan-mcp", "-y"],
            "description": "MiniMax 搜索 MCP - 网页搜索和图片分析",
            "requires_key": True,
            "env_vars": ["MINIMAX_API_KEY", "MINIMAX_API_HOST"],
        },
        # ===== STDIO 本地服务 (npx) =====
        "context7": {
            "name": "context7",
            "source_type": "stdio",
            "command": "npx",
            "args": ["-y", "@upstash/context7-mcp"],
            "description": "Context7 MCP - 文档查询与知识检索",
            "requires_key": False,
        },
        "deepwiki": {
            "name": "deepwiki",
            "source_type": "stdio",
            "command": "npx",
            "args": ["-y", "mcp-deepwiki@latest"],
            "description": "DeepWiki MCP - Wiki 知识查询",
            "requires_key": False,
        },
        "memory_mcp": {
            "name": "memory_mcp",
            "source_type": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-memory"],
            "description": "MCP Memory Server - 知识图谱记忆（独立于项目记忆系统）",
            "requires_key": False,
        },
        "open_websearch": {
            "name": "open_websearch",
            "source_type": "stdio",
            "command": "npx",
            "args": ["-y", "open-websearch@latest"],
            "description": "Open WebSearch MCP - 多引擎网页搜索",
            "requires_key": False,
            "env_vars": ["DEFAULT_SEARCH_ENGINE", "ALLOWED_SEARCH_ENGINES"],
        },
        "time": {
            "name": "time",
            "source_type": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-time"],
            "description": "Time MCP - 时间查询与时区转换",
            "requires_key": False,
        },
    }

    # 已知的 MCP 配置源 URL
    KNOWN_MCP_SOURCES = [
        "https://mcp.amap.com/sse",
        "https://api.minimaxi.com/v1/mcp",
        "https://open.bigmodel.cn/api/paas/v4/mcp",
    ]

    def __init__(self, config_dir: str = "./data/mcp_configs"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.registry = MCPRegistry()
        self._loaded_configs: Dict[str, Dict] = {}

    def load_from_url(self, url: str, name: Optional[str] = None) -> Optional[MCPServiceConfig]:
        """
        从远程 URL 加载 MCP 配置

        Args:
            url: 配置 URL
            name: 服务名称（可选）

        Returns:
            MCPServiceConfig 或 None
        """
        import requests

        try:
            logger.info(f"正在从 URL 加载 MCP 配置: {url}")
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            config_data = response.json()
            service_name = name or config_data.get("name", "unknown")

            # 解析配置
            source_type = self._detect_source_type(url, config_data)

            config = MCPServiceConfig(
                name=service_name,
                source_type=source_type,
                endpoint=url if source_type in [MCPSourceType.HTTP_SSE, MCPSourceType.HTTP_REST] else None,
                description=config_data.get("description", ""),
                auto_discover=config_data.get("auto_discover", True),
            )

            self.registry.services[service_name] = config
            self._loaded_configs[service_name] = config_data

            logger.info(f"✓ 已加载 MCP 配置: {service_name}")
            return config

        except Exception as e:
            logger.error(f"从 URL 加载 MCP 配置失败: {e}")
            return None

    def load_from_file(self, file_path: str) -> List[MCPServiceConfig]:
        """
        从本地文件加载 MCP 配置

        Args:
            file_path: 配置文件路径

        Returns:
            加载的服务配置列表
        """
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"配置文件不存在: {file_path}")
            return []

        try:
            content = path.read_text(encoding='utf-8')

            if path.suffix in ['.yaml', '.yml']:
                config_data = yaml.safe_load(content)
            else:
                config_data = json.loads(content)

            configs = []

            # 支持单服务或多服务配置
            if isinstance(config_data, list):
                for item in config_data:
                    config = self._parse_config_item(item)
                    if config:
                        self.registry.services[config.name] = config
                        configs.append(config)
            else:
                config = self._parse_config_item(config_data)
                if config:
                    self.registry.services[config.name] = config
                    configs.append(config)

            logger.info(f"✓ 从 {file_path} 加载了 {len(configs)} 个 MCP 配置")
            return configs

        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return []

    def add_preset(self, name: str, api_key: Optional[str] = None, **kwargs) -> Optional[MCPServiceConfig]:
        """
        添加预设 MCP 服务

        Args:
            name: 预设名称
            api_key: API 密钥
            **kwargs: 额外配置参数

        Returns:
            MCPServiceConfig 或 None
        """
        if name not in self.PRESET_TEMPLATES:
            logger.error(f"未知的 MCP 预设: {name}")
            return None

        template = self.PRESET_TEMPLATES[name].copy()
        template.update(kwargs)

        config = self._parse_config_item(template)
        if config:
            config.api_key = api_key
            self.registry.services[name] = config
            logger.info(f"✓ 已添加 MCP 预设: {name}")
            return config

        return None

    def add_custom_http(
        self,
        name: str,
        endpoint: str,
        api_key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        use_sse: bool = False,
    ) -> MCPServiceConfig:
        """
        添加自定义 HTTP MCP 服务

        Args:
            name: 服务名称
            endpoint: HTTP 端点
            api_key: API 密钥
            headers: 自定义请求头
            use_sse: 是否使用 SSE 模式

        Returns:
            MCPServiceConfig
        """
        config = MCPServiceConfig(
            name=name,
            source_type=MCPSourceType.HTTP_SSE if use_sse else MCPSourceType.HTTP_REST,
            endpoint=endpoint,
            api_key=api_key,
            headers=headers or {},
        )

        self.registry.services[name] = config
        logger.info(f"✓ 已添加自定义 HTTP MCP: {name}")
        return config

    def add_custom_stdio(
        self,
        name: str,
        command: str,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> MCPServiceConfig:
        """
        添加自定义 STDIO MCP 服务（本地进程）

        Args:
            name: 服务名称
            command: 可执行命令
            args: 命令参数
            env: 环境变量

        Returns:
            MCPServiceConfig
        """
        config = MCPServiceConfig(
            name=name,
            source_type=MCPSourceType.STDIO,
            command=command,
            args=args or [],
            env=env or {},
        )

        self.registry.services[name] = config
        logger.info(f"✓ 已添加自定义 STDIO MCP: {name}")
        return config

    def auto_discover_from_env(self) -> List[MCPServiceConfig]:
        """
        从环境变量自动发现并配置 MCP 服务

        Returns:
            配置列表
        """
        configs = []

        # ===== HTTP 服务（需要 API Key）=====
        http_env_mappings = {
            "AMAP_API_KEY": "amap",
            "BAIDU_MAP_API_KEY": "baidu_map",
            "MINIMAX_API_KEY": "minimax",
            "GLM_API_KEY": "glm",
            "GITHUB_TOKEN": "github",
        }

        for env_var, preset_name in http_env_mappings.items():
            api_key = os.environ.get(env_var)
            if api_key:
                config = self.add_preset(preset_name, api_key)
                if config:
                    configs.append(config)

        # ===== STDIO 服务（检查命令可用性和环境变量开关）=====
        stdio_presets = {
            "fetch": self._check_command_available("uvx") and os.environ.get("ENABLE_MCP_FETCH", "true").lower() == "true",
            "minimax_search": os.environ.get("MINIMAX_API_KEY") and self._check_command_available("uvx") and os.environ.get("ENABLE_MCP_MINIMAX_SEARCH", "true").lower() == "true",
            "context7": self._check_command_available("npx") and os.environ.get("ENABLE_MCP_CONTEXT7", "true").lower() == "true",
            "deepwiki": self._check_command_available("npx") and os.environ.get("ENABLE_MCP_DEEPWIKI", "true").lower() == "true",
            "memory_mcp": self._check_command_available("npx") and os.environ.get("ENABLE_MCP_MEMORY_SERVER", "false").lower() == "true",
            "open_websearch": self._check_command_available("npx") and os.environ.get("ENABLE_MCP_OPEN_WEBSEARCH", "true").lower() == "true",
            "time": self._check_command_available("npx") and os.environ.get("ENABLE_MCP_TIME", "true").lower() == "true",
        }

        for preset_name, available in stdio_presets.items():
            if available:
                config = self.add_preset(preset_name)
                if config:
                    configs.append(config)

        # 检查自定义 MCP 配置
        custom_mcp_urls = os.environ.get('MCP_CUSTOM_URLS', '')
        if custom_mcp_urls:
            for url in custom_mcp_urls.split(','):
                url = url.strip()
                if url:
                    config = self.load_from_url(url)
                    if config:
                        configs.append(config)

        return configs

    def _check_command_available(self, command: str) -> bool:
        """检查命令是否可用"""
        import shutil
        return shutil.which(command) is not None

    def get_enabled_services(self) -> Dict[str, MCPServiceConfig]:
        """获取所有启用的服务配置"""
        return {
            name: config
            for name, config in self.registry.services.items()
            if config.enabled
        }

    def get_service(self, name: str) -> Optional[MCPServiceConfig]:
        """获取指定服务配置"""
        return self.registry.services.get(name)

    def load_from_claude_desktop_config(self, config_path: Optional[str] = None) -> List[MCPServiceConfig]:
        """
        从 Claude Desktop 的 mcpServers 配置加载

        支持格式：
        {
            "mcpServers": {
                "server_name": {
                    "command": "npx",
                    "args": ["-y", "@scope/package"],
                    "env": {"KEY": "value"},
                    "type": "stdio"
                }
            }
        }

        Args:
            config_path: Claude Desktop 配置文件路径
                        macOS: ~/Library/Application Support/Claude/claude_desktop_config.json

        Returns:
            加载的服务配置列表
        """
        if config_path is None:
            # 默认 macOS 路径
            home = Path.home()
            config_path = home / "Library/Application Support/Claude/claude_desktop_config.json"

        path = Path(config_path)
        if not path.exists():
            logger.warning(f"Claude Desktop 配置文件不存在: {config_path}")
            return []

        try:
            content = path.read_text(encoding='utf-8')
            data = json.loads(content)

            mcp_servers = data.get("mcpServers", {})
            configs = []

            for name, server_config in mcp_servers.items():
                # 转换为目标格式
                source_type_str = server_config.get("type", "stdio")
                source_type = MCPSourceType(source_type_str)

                # 提取环境变量中的 API Key
                api_key = None
                env_vars = server_config.get("env", {})
                for key in ["MINIMAX_API_KEY", "AMAP_API_KEY", "GLM_API_KEY", "GITHUB_TOKEN"]:
                    if key in env_vars:
                        api_key = env_vars[key]
                        break

                config = MCPServiceConfig(
                    name=name,
                    source_type=source_type,
                    endpoint=server_config.get("endpoint"),
                    api_key=api_key,
                    command=server_config.get("command"),
                    args=server_config.get("args", []),
                    env=env_vars,
                    description=f"从 Claude Desktop 导入的 {name} 服务",
                )

                self.registry.services[name] = config
                configs.append(config)
                logger.info(f"✓ 从 Claude Desktop 配置导入: {name}")

            logger.info(f"✓ 从 Claude Desktop 配置加载了 {len(configs)} 个 MCP 服务")
            return configs

        except Exception as e:
            logger.error(f"加载 Claude Desktop 配置失败: {e}")
            return []

    def import_from_json(self, json_content: str) -> List[MCPServiceConfig]:
        """
        从 JSON 字符串导入 MCP 配置

        支持格式：
        - Claude Desktop 格式: {"mcpServers": {...}}
        - 标准格式: [{"name": "...", "source_type": "...", ...}]

        Args:
            json_content: JSON 字符串

        Returns:
            加载的服务配置列表
        """
        try:
            data = json.loads(json_content)

            # 检测 Claude Desktop 格式
            if "mcpServers" in data:
                return self._parse_mcp_servers_format(data["mcpServers"])

            # 标准格式
            if isinstance(data, list):
                configs = []
                for item in data:
                    config = self._parse_config_item(item)
                    if config:
                        self.registry.services[config.name] = config
                        configs.append(config)
                return configs

            # 单服务格式
            config = self._parse_config_item(data)
            if config:
                self.registry.services[config.name] = config
                return [config]

            return []

        except Exception as e:
            logger.error(f"导入 JSON 配置失败: {e}")
            return []

    def _parse_mcp_servers_format(self, mcp_servers: Dict) -> List[MCPServiceConfig]:
        """解析 mcpServers 格式"""
        configs = []

        for name, server_config in mcp_servers.items():
            try:
                source_type_str = server_config.get("type", "stdio")
                source_type = MCPSourceType(source_type_str)

                # 提取 API Key（从环境变量中）
                api_key = None
                env_vars = server_config.get("env", {})
                for key, value in env_vars.items():
                    if "API_KEY" in key or "TOKEN" in key:
                        api_key = value
                        break

                config = MCPServiceConfig(
                    name=name,
                    source_type=source_type,
                    command=server_config.get("command"),
                    args=server_config.get("args", []),
                    env=env_vars,
                    api_key=api_key,
                    description=f"导入的 {name} 服务",
                )

                self.registry.services[name] = config
                configs.append(config)
                logger.info(f"✓ 导入 MCP 服务: {name}")

            except Exception as e:
                logger.warning(f"解析 MCP 服务 {name} 失败: {e}")

        return configs

    def save_to_file(self, file_path: Optional[str] = None) -> str:
        """
        保存配置到文件

        Args:
            file_path: 文件路径（默认使用 config_dir）

        Returns:
            保存的文件路径
        """
        path = Path(file_path) if file_path else self.config_dir / "mcp_configs.json"

        configs = []
        for config in self.registry.services.values():
            configs.append({
                "name": config.name,
                "source_type": config.source_type.value,
                "endpoint": config.endpoint,
                "api_key": "***" if config.api_key else None,  # 不保存真实密钥
                "headers": config.headers,
                "command": config.command,
                "args": config.args,
                "env": config.env,
                "timeout": config.timeout,
                "enabled": config.enabled,
                "description": config.description,
            })

        path.write_text(json.dumps(configs, indent=2, ensure_ascii=False), encoding='utf-8')
        logger.info(f"✓ MCP 配置已保存到: {path}")
        return str(path)

    def _detect_source_type(self, url: str, config_data: Dict) -> MCPSourceType:
        """检测 MCP 源类型"""
        # 从 URL 检测
        if '/sse' in url or config_data.get('transport') == 'sse':
            return MCPSourceType.HTTP_SSE
        elif config_data.get('transport') == 'stdio' or 'command' in config_data:
            return MCPSourceType.STDIO
        elif config_data.get('transport') == 'websocket':
            return MCPSourceType.WEBSOCKET
        else:
            return MCPSourceType.HTTP_REST

    def _parse_config_item(self, item: Dict) -> Optional[MCPServiceConfig]:
        """解析配置项"""
        try:
            source_type_str = item.get('source_type', item.get('transport', 'http_rest'))
            source_type = MCPSourceType(source_type_str)

            return MCPServiceConfig(
                name=item['name'],
                source_type=source_type,
                endpoint=item.get('endpoint'),
                api_key=item.get('api_key'),
                headers=item.get('headers', {}),
                command=item.get('command'),
                args=item.get('args', []),
                env=item.get('env', {}),
                timeout=item.get('timeout', 30),
                enabled=item.get('enabled', True),
                description=item.get('description', ''),
                auto_discover=item.get('auto_discover', True),
            )
        except Exception as e:
            logger.warning(f"解析 MCP 配置项失败: {e}")
            return None

    def list_available_presets(self) -> Dict[str, str]:
        """列出所有可用的预设"""
        return {
            name: template.get("description", "")
            for name, template in self.PRESET_TEMPLATES.items()
        }


# 全局配置管理器实例
_global_config_manager: Optional[MCPConfigManager] = None


def get_config_manager(config_dir: str = "./data/mcp_configs") -> MCPConfigManager:
    """获取全局配置管理器实例"""
    global _global_config_manager
    if _global_config_manager is None:
        _global_config_manager = MCPConfigManager(config_dir)
    return _global_config_manager
