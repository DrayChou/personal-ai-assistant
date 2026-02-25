#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agent Router 演示脚本

展示新架构的基本用法
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径，使 src 作为包可用
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env')

from src.chat.llm_client import create_llm_client
from src.memory import MemorySystem
from src.task import TaskManager
from src.agent import create_agent_system


async def main():
    """演示 Agent 系统"""
    print("=" * 60)
    print("🤖 Agent Router 演示")
    print("=" * 60)

    # 初始化组件
    print("\n📦 初始化组件...")

    llm = create_llm_client(
        provider='minimax',
        api_key="YOUR_API_KEY",
        base_url="https://api.minimaxi.com/v1",
        model="MiniMax-M2.5"
    )

    memory = MemorySystem(data_dir="./data/demo_memories")
    tasks = TaskManager(storage_path="./data/demo_tasks.jsonl")

    # 创建 Agent 系统
    print("🤖 创建 Agent 系统...")
    agent = create_agent_system(
        llm_client=llm,
        memory_system=memory,
        task_manager=tasks,
        fast_path_classifier=None  # 暂不配置快速路径
    )

    print(f"   已注册 {len(agent.tools)} 个工具")
    print(f"   工具列表: {agent.tools.get_names()}")

    # 测试用例
    test_inputs = [
        "你好",
        "提醒我明天下午3点开会",
        "我有什么任务",
        "记住我喜欢Python编程",
        "帮我清理任务列表",
    ]

    print("\n" + "=" * 60)
    print("📝 测试用例")
    print("=" * 60)

    for user_input in test_inputs:
        print(f"\n👤 用户: {user_input}")
        print("-" * 40)

        try:
            async for output in agent.handle(user_input, session_id="demo"):
                if isinstance(output, dict):
                    print(f"🤖 需要输入: {output.get('prompt')}")
                else:
                    print(f"🤖 {output}", end='')

        except Exception as e:
            print(f"❌ 错误: {e}")

        print()

    print("\n" + "=" * 60)
    print("✅ 演示完成")
    print("=" * 60)

    # 清理
    memory.close()


if __name__ == "__main__":
    asyncio.run(main())
