# -*- coding: utf-8 -*-
"""
MCP 管理器测试
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from src.tools.mcp_manager import (
    MCPManager,
    MCPManagerConfig,
    MCPConnection,
)
from src.tools.mcp_client import MCPTool, MCPConfig, MCPTransport


class TestMCPManagerConfig:
    """测试 MCP 管理器配置"""

    def test_default_config(self):
        """测试默认配置"""
        config = MCPManagerConfig()

        assert config.config_path is None
        assert config.auto_discover is True
        assert config.timeout == 30

    def test_custom_config(self):
        """测试自定义配置"""
        config = MCPManagerConfig(
            config_path="/path/to/config.json",
            presets=["brave-search", "filesystem"],
            timeout=60
        )

        assert config.config_path == "/path/to/config.json"
        assert "brave-search" in config.presets


class TestMCPConnection:
    """测试 MCP 连接"""

    def test_connection_creation(self):
        """测试连接创建"""
        config = MCPConfig(
            name="test",
            transport=MCPTransport.HTTP,
            endpoint="http://localhost:8080"
        )
        client = MagicMock()

        conn = MCPConnection(
            name="test",
            config=config,
            client=client
        )

        assert conn.name == "test"
        assert conn.status == "disconnected"
        assert len(conn.tools) == 0

    def test_connection_to_dict(self):
        """测试连接转字典"""
        config = MCPConfig(
            name="test",
            transport=MCPTransport.HTTP,
            endpoint="http://localhost:8080"
        )
        client = MagicMock()

        conn = MCPConnection(
            name="test",
            config=config,
            client=client,
            status="connected",
            connected_at=datetime.now()
        )

        d = conn.to_dict()

        assert d["name"] == "test"
        assert d["status"] == "connected"
        assert d["tool_count"] == 0


class TestMCPManager:
    """测试 MCP 管理器"""

    @pytest.fixture
    def manager(self):
        """创建管理器实例"""
        return MCPManager()

    def test_manager_initialization(self, manager):
        """测试管理器初始化"""
        assert len(manager.connections) == 0
        assert len(manager._tools_index) == 0

    def test_preset_servers(self, manager):
        """测试预设服务器"""
        assert "brave-search" in manager.PRESET_SERVERS
        assert "filesystem" in manager.PRESET_SERVERS
        assert "github" in manager.PRESET_SERVERS

    def test_load_server(self, manager):
        """测试加载服务器"""
        config = {
            "endpoint": "http://localhost:8080",
            "transport": "http"
        }

        manager._load_server("test", config)

        assert "test" in manager.connections
        assert manager.connections["test"].status == "disconnected"

    def test_load_duplicate_server(self, manager):
        """测试加载重复服务器"""
        config = {"endpoint": "http://localhost:8080"}

        manager._load_server("test", config)
        manager._load_server("test", config)  # 应该覆盖

        assert len(manager.connections) == 1

    def test_get_all_tools_empty(self, manager):
        """测试获取空工具列表"""
        tools = manager.get_all_tools()
        assert len(tools) == 0

    def test_get_tool_not_found(self, manager):
        """测试获取不存在的工具"""
        tool = manager.get_tool("nonexistent")
        assert tool is None

    def test_get_stats(self, manager):
        """测试获取统计信息"""
        stats = manager.get_stats()

        assert "total_servers" in stats
        assert "connected_servers" in stats
        assert "total_tools" in stats
        assert stats["total_servers"] == 0

    @patch('src.tools.mcp_manager.MCPClient')
    def test_connect_success(self, mock_client_class, manager):
        """测试连接成功"""
        # Mock 客户端和工具
        mock_client = MagicMock()
        mock_tool = MCPTool(
            name="test_tool",
            description="Test tool",
            parameters={"type": "object"}
        )
        mock_client.list_tools.return_value = [mock_tool]

        mock_client_class.return_value = mock_client

        # 加载服务器
        manager._load_server("test", {"endpoint": "http://localhost:8080"})
        manager.connections["test"].client = mock_client

        # 连接
        import asyncio
        result = asyncio.run(manager.connect("test"))

        assert result is True
        assert manager.connections["test"].status == "connected"
        assert "test_tool" in manager._tools_index

    def test_disconnect(self, manager):
        """测试断开连接"""
        # 先加载并连接
        manager._load_server("test", {"endpoint": "http://localhost:8080"})
        manager.connections["test"].status = "connected"
        manager.connections["test"].tools = [
            MCPTool(name="tool1", description="Tool 1", parameters={})
        ]
        manager._tools_index["tool1"] = {"server": "test", "tool": MagicMock()}

        import asyncio
        result = asyncio.run(manager.disconnect("test"))

        assert result is True
        assert manager.connections["test"].status == "disconnected"
        assert "tool1" not in manager._tools_index

    def test_get_all_tools(self, manager):
        """测试获取所有工具"""
        # 添加模拟工具
        tool1 = MCPTool(name="tool1", description="Tool 1", parameters={})
        tool2 = MCPTool(name="tool2", description="Tool 2", parameters={})

        manager._tools_index["tool1"] = {"server": "s1", "tool": tool1}
        manager._tools_index["tool2"] = {"server": "s2", "tool": tool2}

        tools = manager.get_all_tools()

        assert len(tools) == 2

    def test_get_openai_schemas(self, manager):
        """测试获取 OpenAI Schema"""
        tool = MCPTool(
            name="test_tool",
            description="Test",
            parameters={"type": "object", "properties": {}}
        )
        manager._tools_index["test_tool"] = {"server": "test", "tool": tool}

        schemas = manager.get_openai_schemas()

        assert len(schemas) == 1
        assert schemas[0]["type"] == "function"

    def test_get_anthropic_schemas(self, manager):
        """测试获取 Anthropic Schema"""
        tool = MCPTool(
            name="test_tool",
            description="Test",
            parameters={"type": "object", "properties": {}}
        )
        manager._tools_index["test_tool"] = {"server": "test", "tool": tool}

        schemas = manager.get_anthropic_schemas()

        assert len(schemas) == 1
        assert "name" in schemas[0]


class TestMCPManagerIntegration:
    """MCP 管理器集成测试"""

    def test_load_presets(self):
        """测试加载预设服务器"""
        with patch.dict('os.environ', {'BRAVE_API_KEY': 'test_key'}):
            manager = MCPManager()
            # 加载预设（但不会真正连接）
            # 这里只测试配置解析
            assert "brave-search" in manager.PRESET_SERVERS

    def test_full_lifecycle(self):
        """测试完整生命周期"""
        manager = MCPManager()

        # 加载服务器
        manager._load_server("test", {
            "endpoint": "http://localhost:8080",
            "timeout": 60
        })

        assert "test" in manager.connections

        # 获取统计
        stats = manager.get_stats()
        assert stats["total_servers"] == 1

        # 关闭
        import asyncio
        asyncio.run(manager.close())
