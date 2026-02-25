#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gateway Server 演示脚本

运行方式:
    python examples/gateway_demo.py

测试连接:
    websocat ws://localhost:8080
    > {"jsonrpc": "2.0", "id": "1", "method": "health", "params": {}}
    > {"jsonrpc": "2.0", "id": "2", "method": "chat.send", "params": {"text": "你好"}}
"""
import asyncio
import sys
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from gateway import GatewayServer


class MockAgent:
    """模拟 Agent，用于演示"""

    async def handle(self, text: str, session_id: str):
        """模拟处理消息"""
        # 模拟流式输出
        response = f"收到消息: {text}\n这是来自 MockAgent 的回复。"
        for word in response:
            yield word
            await asyncio.sleep(0.01)  # 模拟延迟


async def main():
    """启动 Gateway 服务器"""
    print("🚀 启动 Gateway Server 演示...")
    print("=" * 50)

    # 创建模拟 Agent
    agent = MockAgent()

    # 创建 Gateway 服务器 (无需认证，方便测试)
    gateway = GatewayServer(
        host="127.0.0.1",
        port=8080,
        auth_token=None,  # 演示模式不启用认证
        agent=agent,
        session_store=None,
    )

    # 启动服务器
    await gateway.start()
    print(f"✅ Gateway 已启动: ws://{gateway.host}:{gateway.port}")
    print("\n测试命令:")
    print("-" * 50)
    print('health 检查:')
    print('  {"jsonrpc": "2.0", "id": "1", "method": "health", "params": {}}')
    print()
    print('发送消息:')
    print('  {"jsonrpc": "2.0", "id": "2", "method": "chat.send", "params": {"text": "你好"}}')
    print()
    print('流式发送:')
    print('  {"jsonrpc": "2.0", "id": "3", "method": "chat.send_stream", "params": {"text": "你好"}}')
    print("-" * 50)
    print("\n按 Ctrl+C 停止服务器\n")

    try:
        # 保持运行
        await asyncio.Future()
    except KeyboardInterrupt:
        print("\n🛑 正在停止...")
    finally:
        await gateway.stop()
        print("✅ 已停止")


if __name__ == "__main__":
    asyncio.run(main())
