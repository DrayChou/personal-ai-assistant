#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP 工具使用示例

演示如何：
1. 配置和加载 MCP 服务
2. 使用 MCP 工具执行查询
3. 结合 AI 意图分类器自动选择工具
"""
import asyncio
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tools import (
    MCPConfigManager,
    MCPClient,
    ToolExecutor,
    get_config_manager,
)
from src.chat.ai_intent_classifier import AIIntentClassifier


def demo_config_manager():
    """演示配置管理器"""
    print("=" * 50)
    print("📦 MCP 配置管理器示例")
    print("=" * 50)

    manager = get_config_manager("./data/demo_mcp_configs")

    # 列出可用预设
    print("\n1. 可用预设服务:")
    for name, desc in manager.list_available_presets().items():
        print(f"   - {name}: {desc}")

    # 从环境变量自动发现
    print("\n2. 从环境变量发现服务:")
    configs = manager.auto_discover_from_env()
    if configs:
        for config in configs:
            print(f"   ✓ 发现: {config.name}")
    else:
        print("   ℹ 未发现环境变量配置（请设置 AMAP_API_KEY 等）")

    return manager


def demo_mcp_client():
    """演示 MCP 客户端"""
    print("\n" + "=" * 50)
    print("🔌 MCP 客户端示例")
    print("=" * 50)

    # 创建客户端
    client = MCPClient()

    # 查看预设工具
    print("\n1. 预设工具:")
    for tool in client.list_tools():
        print(f"   - {tool.name}: {tool.description[:40]}...")

    # 添加服务（如果有 API Key）
    print("\n2. 添加服务:")
    if os.environ.get("AMAP_API_KEY"):
        client.add_preset("amap", os.environ.get("AMAP_API_KEY"))
        print("   ✓ 高德地图服务已添加")
    else:
        print("   ℹ 未设置 AMAP_API_KEY，跳过")

    return client


def demo_tool_executor():
    """演示工具执行器"""
    print("\n" + "=" * 50)
    print("⚙️  工具执行器示例")
    print("=" * 50)

    client = MCPClient()
    executor = ToolExecutor(mcp_client=client)

    # 获取可用工具
    tools = executor.get_available_tools()
    print(f"\n1. 可用工具数量: {len(tools)}")

    # 格式化示例
    print("\n2. 工具格式示例:")
    for tool in tools[:2]:
        print(f"\n   {tool['function']['name']}:")
        print(f"   描述: {tool['function']['description'][:50]}...")

    return executor


def demo_ai_intent_classifier():
    """演示 AI 意图分类器"""
    print("\n" + "=" * 50)
    print("🧠 AI 意图分类器示例")
    print("=" * 50)

    # 创建分类器（无 LLM 客户端时使用规则回退）
    classifier = AIIntentClassifier(llm_client=None)

    # 测试意图识别
    test_inputs = [
        "明天北京天气怎么样？",
        "帮我创建一个任务，下午3点开会",
        "记住我喜欢Python",
        "搜索一下最新的人工智能新闻",
        "你好",
    ]

    print("\n1. 意图识别测试:")
    for text in test_inputs:
        intent = classifier.classify(text)
        print(f"   '{text}'")
        print(f"   → 意图: {intent.type.value}, 置信度: {intent.confidence:.2f}")
        if intent.requires_tool:
            print(f"   → 需要工具: {intent.suggested_tools}")
        print()

    return classifier


async def demo_full_integration():
    """演示完整集成"""
    print("\n" + "=" * 50)
    print("🚀 完整集成示例")
    print("=" * 50)

    # 1. 初始化配置管理器
    config_manager = get_config_manager()

    # 2. 从环境变量加载配置
    config_manager.auto_discover_from_env()

    # 3. 创建 MCP 客户端并加载配置
    client = MCPClient(config_manager=config_manager)
    client.load_from_config_manager(config_manager)

    # 4. 创建工具执行器
    executor = ToolExecutor(mcp_client=client)

    print(f"\n✓ 已加载 {len(client.configs)} 个 MCP 服务")
    print(f"✓ 可用工具: {len(executor.get_available_tools())} 个")

    # 5. 模拟工具调用（如果配置了服务）
    if "amap" in client.configs:
        print("\n6. 模拟天气查询:")
        result = await executor.execute({
            "name": "amap_weather",
            "arguments": {"city": "北京"}
        })
        print(f"   成功: {result.success}")
        if result.error:
            print(f"   错误: {result.error}")
    else:
        print("\n6. 模拟工具调用:")
        print("   ℹ 未配置高德地图 API，跳过实际调用")


def main():
    """主函数"""
    print("\n" + "=" * 50)
    print("🤖 Personal AI Assistant - MCP 演示")
    print("=" * 50)

    # 运行各个演示
    demo_config_manager()
    demo_mcp_client()
    demo_tool_executor()
    demo_ai_intent_classifier()

    # 运行异步演示
    asyncio.run(demo_full_integration())

    print("\n" + "=" * 50)
    print("✅ 演示完成！")
    print("=" * 50)
    print("\n提示:")
    print("  - 设置 AMAP_API_KEY 环境变量以启用地图服务")
    print("  - 查看 .env.example 了解更多配置选项")
    print("  - 阅读 docs/MCP_TOOLS_GUIDE.md 获取完整文档")


if __name__ == "__main__":
    main()
