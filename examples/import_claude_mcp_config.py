#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 Claude Desktop MCP 配置导入示例

演示如何导入 mcpServers 格式的配置
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tools import MCPConfigManager

# 用户的 mcpServers 配置示例
USER_MCP_CONFIG = """{
  "mcpServers": {
    "MiniMax": {
      "args": ["minimax-coding-plan-mcp", "-y"],
      "command": "uvx",
      "env": {
        "MINIMAX_API_HOST": "https://api.minimaxi.com",
        "MINIMAX_API_KEY": "your_api_key_here"
      }
    },
    "context7": {
      "args": ["-y", "@upstash/context7-mcp"],
      "command": "npx",
      "type": "stdio"
    },
    "fetch": {
      "args": ["mcp-server-fetch"],
      "command": "uvx",
      "type": "stdio"
    },
    "mcp-deepwiki": {
      "args": ["-y", "mcp-deepwiki@latest"],
      "command": "npx",
      "env": {},
      "type": "stdio"
    },
    "memory": {
      "args": ["-y", "@modelcontextprotocol/server-memory"],
      "command": "npx",
      "type": "stdio"
    },
    "open-websearch": {
      "args": ["-y", "open-websearch@latest"],
      "command": "npx",
      "env": {
        "ALLOWED_SEARCH_ENGINES": "duckduckgo,bing,brave",
        "DEFAULT_SEARCH_ENGINE": "duckduckgo",
        "MODE": "stdio"
      },
      "type": "stdio"
    },
    "time": {
      "args": ["-y", "@modelcontextprotocol/server-time"],
      "command": "npx",
      "type": "stdio"
    }
  }
}"""


def main():
    print("=" * 60)
    print("🔄 Claude Desktop MCP 配置导入示例")
    print("=" * 60)

    manager = MCPConfigManager()

    # 方法1: 从 JSON 字符串导入
    print("\n📥 方法1: 从 JSON 字符串导入")
    configs = manager.import_from_json(USER_MCP_CONFIG)

    print(f"\n✓ 成功导入 {len(configs)} 个 MCP 服务:")
    for config in configs:
        print(f"  - {config.name} ({config.source_type.value})")
        if config.command:
            print(f"    命令: {config.command} {' '.join(config.args[:2])}...")
        if config.env:
            env_keys = list(config.env.keys())
            print(f"    环境变量: {', '.join(env_keys)}")

    # 方法2: 直接解析 mcpServers 格式
    print("\n📥 方法2: 直接解析 mcpServers 格式")
    data = json.loads(USER_MCP_CONFIG)
    mcp_servers = data.get("mcpServers", {})

    print(f"\n配置详情:")
    for name, server in mcp_servers.items():
        print(f"\n  {name}:")
        print(f"    命令: {server.get('command')}")
        print(f"    参数: {server.get('args', [])}")
        if server.get('env'):
            print(f"    环境变量: {list(server.get('env', {}).keys())}")

    # 保存到本地配置文件
    print("\n💾 保存配置到本地...")
    saved_path = manager.save_to_file()
    print(f"  路径: {saved_path}")

    # 显示建议
    print("\n" + "=" * 60)
    print("💡 建议")
    print("=" * 60)
    print("""
1. 将你的 mcpServers 配置保存到:
   ~/Library/Application Support/Claude/claude_desktop_config.json

2. 或使用环境变量方式（推荐）:
   export MINIMAX_API_KEY="your_key"
   export ENABLE_MCP_FETCH=true
   export ENABLE_MCP_CONTEXT7=true
   ...

3. 在 .env 文件中设置:
   MCP_ENABLED=true
   MINIMAX_API_KEY=your_key
   # 其他 ENABLE_MCP_* 开关

4. 启动助手:
   python -m src.main
""")


if __name__ == "__main__":
    main()
