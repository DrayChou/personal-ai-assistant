#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agent V2 使用示例

展示如何使用重构后的Agent V2架构。
"""
import asyncio
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agent_v2 import AgentLoop, ContextBuilder, BuildConfig
from src.agent_v2.skills import SkillRegistry, SkillsContextInjector
from src.agent_v2.memory import MemoryContextInjector
from src.agent_v2.personality import PersonalityContextInjector


async def mock_llm_client():
    """模拟LLM客户端"""
    class MockLLM:
        async def chat_completion(self, messages, tools=None):
            # 模拟LLM响应
            last_message = messages[-1]['content'] if messages else ''

            # 简单规则模拟
            if '任务' in last_message or 'todo' in last_message.lower():
                return {
                    'content': '',
                    'tool_calls': [{
                        'id': 'call_1',
                        'function': {
                            'name': 'list_tasks',
                            'arguments': '{}'
                        }
                    }]
                }
            elif '删除' in last_message or '清理' in last_message:
                return {
                    'content': '',
                    'tool_calls': [{
                        'id': 'call_2',
                        'function': {
                            'name': 'delete_task',
                            'arguments': '{"task_id": "task_123"}'
                        }
                    }]
                }
            else:
                return {
                    'content': f'收到您的消息：{last_message}。我是Agent V2，使用新的极简架构。',
                    'tool_calls': None
                }

    return MockLLM()


async def mock_tool_registry():
    """模拟工具注册表"""
    class MockToolRegistry:
        def get_schemas(self):
            return [
                {
                    'name': 'list_tasks',
                    'description': '列出用户的任务'
                },
                {
                    'name': 'create_task',
                    'description': '创建新任务'
                },
                {
                    'name': 'delete_task',
                    'description': '删除任务（需要确认）'
                },
                {
                    'name': 'search_memories',
                    'description': '搜索记忆'
                }
            ]

        async def execute(self, name, **kwargs):
            """模拟工具执行"""
            class MockResult:
                def __init__(self, success, observation, error=None):
                    self.success = success
                    self.observation = observation
                    self.error = error
                    self.metadata = {}

            if name == 'list_tasks':
                return MockResult(True, "找到3个待办任务：\n1. 完成报告\n2. 开会\n3. 回复邮件")
            elif name == 'delete_task':
                if kwargs.get('confirmed'):
                    return MockResult(True, f"已删除任务 {kwargs.get('task_id', '')}")
                else:
                    result = MockResult(False, "需要确认")
                    result.metadata = {'requires_confirmation': True}
                    return result
            elif name == 'create_task':
                return MockResult(True, f"已创建任务：{kwargs.get('title', '')}")
            else:
                return MockResult(False, f"未知工具: {name}")

    return MockToolRegistry()


async def mock_memory_system():
    """模拟记忆系统"""
    class MockMemorySystem:
        async def retrieve_with_intent(self, query, intent, limit=5, min_relevance=0.7):
            # 模拟返回记忆
            if '咖啡' in query:
                return [type('Memory', (), {'content': '用户喜欢在早上喝美式咖啡'})()]
            return []

    return MockMemorySystem()


async def mock_personality_manager():
    """模拟人格管理器"""
    class MockPersonality:
        name = "猫娘助手"
        description = "可爱的猫娘，用喵语回复"
        speech_patterns = ["句尾加喵~", "使用可爱的表情"]
        skills = ["卖萌", "陪伴"]
        response_templates = {}
        behavior_rules = ["保持可爱", "关心主人"]

    class MockPersonalityManager:
        def get_current_personality(self):
            return MockPersonality()

    return MockPersonalityManager()


async def main():
    """主函数"""
    print("=" * 60)
    print("Agent V2 演示")
    print("=" * 60)
    print()

    # 1. 初始化组件
    print("[1/4] 初始化组件...")
    llm_client = await mock_llm_client()
    tool_registry = await mock_tool_registry()
    memory_system = await mock_memory_system()
    personality_manager = await mock_personality_manager()

    # 2. 创建ContextBuilder
    print("[2/4] 配置上下文构建器...")
    context_builder = ContextBuilder()

    # 注册人格注入器 (优先级20)
    context_builder.register_injector(
        PersonalityContextInjector(personality_manager),
        priority=20
    )

    # 注册Skills注入器 (优先级25)
    skills_dir = project_root / "skills"
    if skills_dir.exists():
        skill_registry = SkillRegistry(skills_dir)
        context_builder.register_injector(
            SkillsContextInjector(skill_registry, max_dynamic_skills=3),
            priority=25
        )
        print(f"    - 已加载 {len(skill_registry.list_all())} 个Skills")

    # 注册记忆注入器 (优先级30)
    context_builder.register_injector(
        MemoryContextInjector(memory_system, max_memories=5),
        priority=30
    )

    # 3. 创建Agent
    print("[3/4] 创建AgentLoop...")
    agent = AgentLoop(
        llm_client=llm_client,
        tool_registry=tool_registry,
        context_builder=context_builder,
        max_iterations=5,
    )

    # 4. 运行对话
    print("[4/4] 开始对话 (输入 'exit' 退出)")
    print("-" * 60)

    session_id = "demo_session"
    history = []

    test_inputs = [
        "你好",
        "我有什么任务？",
        "记住我喜欢喝咖啡",
        "删除那个任务",
        "确认",
        "exit"
    ]

    for user_input in test_inputs:
        if user_input == 'exit':
            break

        print(f"\n用户: {user_input}")
        print("助手: ", end="", flush=True)

        response_text = []
        async for response in agent.run(
            session_id=session_id,
            user_input=user_input,
            message_history=history,
        ):
            if response.type.value == 'text':
                print(response.content, end="")
                response_text.append(response.content)
            elif response.type.value == 'tool_call':
                print(f"[调用工具: {', '.join(tc.name for tc in response.tool_calls)}]")
            elif response.type.value == 'confirmation':
                print(f"\n{response.content}")
                response_text.append(response.content)
            elif response.type.value == 'error':
                print(f"[错误: {response.content}]")

        print()  # 换行

        # 更新历史
        if response_text:
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": "".join(response_text)})

    print("-" * 60)
    print("演示结束")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
