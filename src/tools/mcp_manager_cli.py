#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP 配置管理命令行工具

用法:
    python -m src.tools.mcp_manager_cli list
    python -m src.tools.mcp_manager_cli add amap --api-key YOUR_KEY
    python -m src.tools.mcp_manager_cli remove amap
    python -m src.tools.mcp_manager_cli discover
"""
import argparse
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.tools.mcp_config_manager import get_config_manager


def cmd_list(args):
    """列出所有 MCP 配置"""
    manager = get_config_manager()

    # 自动发现环境变量中的配置
    manager.auto_discover_from_env()

    services = manager.get_enabled_services()

    if not services:
        print("❌ 没有启用的 MCP 服务")
        print("\n提示: 使用 'discover' 命令从环境变量发现服务")
        print("      或使用 'add' 命令手动添加")
        return

    print(f"\n📦 已配置的 MCP 服务 ({len(services)}个):\n")
    print(f"{'名称':<15} {'类型':<12} {'状态':<8} {'描述'}")
    print("-" * 60)

    for name, config in services.items():
        status = "✅ 启用" if config.enabled else "❌ 禁用"
        print(f"{name:<15} {config.source_type.value:<12} {status:<8} {config.description[:30]}")

    print()


def cmd_discover(args):
    """从环境变量发现 MCP 服务"""
    print("\n🔍 正在从环境变量发现 MCP 服务...\n")

    manager = get_config_manager()
    configs = manager.auto_discover_from_env()

    if not configs:
        print("❌ 未发现任何 MCP 配置")
        print("\n请确保以下环境变量已设置:")
        print("  - AMAP_API_KEY")
        print("  - BAIDU_MAP_API_KEY")
        print("  - MINIMAX_API_KEY")
        print("  - GLM_API_KEY")
        print("  - MCP_CUSTOM_URLS")
        return

    print(f"✅ 发现 {len(configs)} 个 MCP 服务:\n")
    for config in configs:
        print(f"  ✓ {config.name}: {config.description}")

    # 保存配置
    saved_path = manager.save_to_file()
    print(f"\n💾 配置已保存到: {saved_path}")


def cmd_add(args):
    """添加 MCP 预设"""
    manager = get_config_manager()

    if args.preset:
        if args.preset not in manager.PRESET_TEMPLATES:
            print(f"❌ 未知的预设: {args.preset}")
            print("\n可用的预设:")
            for name, desc in manager.list_available_presets().items():
                print(f"  - {name}: {desc}")
            return

        api_key = args.api_key or os.environ.get(f"{args.preset.upper()}_API_KEY")
        if not api_key:
            print(f"❌ 添加 {args.preset} 需要提供 API Key")
            print(f"  使用 --api-key 参数或设置 {args.preset.upper()}_API_KEY 环境变量")
            return

        config = manager.add_preset(args.preset, api_key)
        if config:
            print(f"✅ 已添加 MCP 预设: {args.preset}")
            manager.save_to_file()
        else:
            print("❌ 添加失败")

    elif args.custom:
        # 添加自定义 HTTP MCP
        if not args.endpoint:
            print("❌ 自定义 MCP 需要提供 --endpoint")
            return

        config = manager.add_custom_http(
            name=args.name,
            endpoint=args.endpoint,
            api_key=args.api_key,
            use_sse=args.sse
        )
        print(f"✅ 已添加自定义 MCP: {args.name}")
        manager.save_to_file()


def cmd_remove(args):
    """移除 MCP 配置"""
    manager = get_config_manager()

    if args.name not in manager.registry.services:
        print(f"❌ 未找到 MCP 服务: {args.name}")
        return

    del manager.registry.services[args.name]
    manager.save_to_file()
    print(f"✅ 已移除 MCP 服务: {args.name}")


def cmd_presets(args):
    """列出可用的预设"""
    manager = get_config_manager()

    print("\n📋 可用的 MCP 预设:\n")
    for name, desc in manager.list_available_presets().items():
        template = manager.PRESET_TEMPLATES[name]
        requires = "需要 API Key" if template.get("requires_key") else "无需认证"
        print(f"  {name}")
        print(f"    描述: {desc}")
        print(f"    认证: {requires}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="MCP 配置管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 列出所有配置
  python mcp_manager_cli.py list

  # 从环境变量发现服务
  python mcp_manager_cli.py discover

  # 添加高德地图 MCP
  python mcp_manager_cli.py add amap --api-key YOUR_AMAP_KEY

  # 添加自定义 HTTP MCP
  python mcp_manager_cli.py add custom_name --custom --endpoint https://api.example.com/mcp

  # 查看可用预设
  python mcp_manager_cli.py presets
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # list 命令
    list_parser = subparsers.add_parser("list", help="列出所有 MCP 配置")
    list_parser.set_defaults(func=cmd_list)

    # discover 命令
    discover_parser = subparsers.add_parser("discover", help="从环境变量发现 MCP 服务")
    discover_parser.set_defaults(func=cmd_discover)

    # add 命令
    add_parser = subparsers.add_parser("add", help="添加 MCP 服务")
    add_parser.add_argument("name", help="服务名称")
    add_parser.add_argument("--preset", action="store_true", help="使用预设配置")
    add_parser.add_argument("--custom", action="store_true", help="添加自定义配置")
    add_parser.add_argument("--api-key", help="API 密钥")
    add_parser.add_argument("--endpoint", help="HTTP 端点 (自定义模式)")
    add_parser.add_argument("--sse", action="store_true", help="使用 SSE 模式")
    add_parser.set_defaults(func=cmd_add)

    # remove 命令
    remove_parser = subparsers.add_parser("remove", help="移除 MCP 服务")
    remove_parser.add_argument("name", help="服务名称")
    remove_parser.set_defaults(func=cmd_remove)

    # presets 命令
    presets_parser = subparsers.add_parser("presets", help="列出可用预设")
    presets_parser.set_defaults(func=cmd_presets)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
