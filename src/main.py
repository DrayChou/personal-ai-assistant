#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Personal AI Assistant - 主入口

替代 OpenClaw 的个人智能助理 - 完整的集成版本
"""
import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# 添加项目根目录到路径，使 src 作为包可用
sys.path.insert(0, str(Path(__file__).parent.parent))

# 加载 .env 文件
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env')

# 设置 logger
logger = logging.getLogger('pai')

from src.config.settings import Settings
from src.memory import MemorySystem, AutoConsolidationScheduler
from src.memory.embeddings import create_embedding_function, init_config
from src.chat.llm_client import create_llm_client
from src.chat.chat_session import ChatSession
from src.chat.simple_intent_handler import SimpleIntentHandler
from src.chat.action_router import ActionRouter
from src.task.manager import TaskManager
from src.schedule.scheduler import HybridScheduler
from src.search import SearchTool, WebSearchClient
from src.tools import (
    ToolExecutor, MCPClient, FunctionRegistry,
    MCPConfigManager, get_config_manager
)
from src.personality import get_personality_manager
from src.agent import create_agent_system, SupervisorAgent


def setup_logging(level: str = "INFO"):
    """设置日志"""
    Path("data").mkdir(exist_ok=True)

    # 根日志级别
    log_level = getattr(logging, level.upper())

    # 配置根日志
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 清除现有处理器
    root_logger.handlers.clear()

    # 控制台处理器 - 只显示 WARNING 及以上级别
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))

    # 文件处理器 - 记录所有 INFO 及以上级别
    file_handler = logging.FileHandler('data/app.log', encoding='utf-8')
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # 降低第三方库和内部调试模块的日志级别
    noisy_loggers = [
        'agent.tools.base',
        'chat.llm',
        'httpx',
        'httpcore',
        'urllib3',
        'asyncio',
        'memory.working',
        'memory.long_term',
        'memory.retrieval',
    ]
    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


class PersonalAIAssistant:
    """个人AI助手主类"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.memory: MemorySystem | None = None
        self.chat_session: ChatSession | None = None
        self.task_manager: TaskManager | None = None
        self.scheduler: HybridScheduler | None = None
        self.llm = None
        self.search_tool = None
        self.tool_executor: ToolExecutor | None = None
        self.mcp_client: MCPClient | None = None
        self.mcp_config_manager: MCPConfigManager | None = None
        self.function_registry: FunctionRegistry | None = None
        self.personality_manager = None
        self.agent: SupervisorAgent | None = None  # 新增 Agent 系统
        self.auto_consolidation: AutoConsolidationScheduler | None = None  # 自动记忆整合

    async def initialize(self):
        """初始化所有组件"""
        logger = logging.getLogger('pai')
        logger.info("正在初始化个人AI助手...")

        # 创建数据目录
        Path(self.settings.data_dir).mkdir(parents=True, exist_ok=True)

        # 设置嵌入配置环境变量
        import os
        if self.settings.embedding_base_url:
            os.environ['OLLAMA_BASE_URL'] = self.settings.embedding_base_url
        if self.settings.embedding_api_key:
            os.environ['OPENAI_API_KEY'] = self.settings.embedding_api_key

        # 初始化嵌入配置
        init_config()

        # 初始化性格管理器（猫娘为默认性格）
        self.personality_manager = get_personality_manager()
        personality_name = os.environ.get('ASSISTANT_PERSONALITY', 'nekomata_assistant')
        if self.personality_manager.set_personality(personality_name):
            personality = self.personality_manager.get_current()
            logger.info(f"性格已设置为: {personality.name} ({personality.self_reference})")
        else:
            logger.warning(f"性格设置失败: {personality_name}")

        # 初始化嵌入函数
        embedding_func = create_embedding_function()

        # 初始化记忆系统
        self.memory = MemorySystem(
            data_dir=f"{self.settings.data_dir}/memories",
            embedding_func=embedding_func,
            llm_client=None
        )

        # 初始化并启动自动记忆整合调度器 (OpenClaw 风格)
        self.auto_consolidation = AutoConsolidationScheduler(
            memory_system=self.memory,
            daily_hour=23,        # 每晚 11 点
            weekly_day=6,         # 周日
            weekly_hour=22,       # 晚上 10 点
            micro_sync_hours=[10, 13, 16, 19, 22]  # 白天检查点
        )
        await self.auto_consolidation.start()


        # 初始化任务管理器
        self.task_manager = TaskManager(
            storage_path=f"{self.settings.data_dir}/tasks.jsonl"
        )

        # 初始化LLM客户端
        if self.settings.llm_provider == 'openai':
            if not self.settings.llm_api_key:
                raise ValueError("使用 OpenAI 需要提供 API Key (通过 --llm-api-key 或 OPENAI_API_KEY 环境变量)")
            self.llm = create_llm_client(
                provider='openai',
                api_key=self.settings.llm_api_key,
                base_url=self.settings.llm_base_url,
                model=self.settings.llm_model
            )
        elif self.settings.llm_provider == 'minimax':
            if not self.settings.llm_api_key:
                raise ValueError("使用 MiniMax 需要提供 API Key (通过 --llm-api-key 或 MINIMAX_API_KEY 环境变量)")
            self.llm = create_llm_client(
                provider='minimax',
                api_key=self.settings.llm_api_key,
                base_url=self.settings.llm_base_url or 'https://api.minimaxi.com/v1',
                model=self.settings.llm_model or 'MiniMax-M2.5'
            )
            logger.info(f"已连接 MiniMax API: {self.settings.llm_base_url}")
        else:
            # Ollama 不需要 api_key
            self.llm = create_llm_client(
                provider='ollama',
                base_url=self.settings.llm_base_url,
                model=self.settings.llm_model
            )

        # 更新记忆系统的LLM客户端
        self.memory.consolidation.llm_client = self.llm.generate

        # 初始化对话会话（传入性格管理器）
        self.chat_session = ChatSession(
            session_id=self.settings.session_id,
            memory_system=self.memory,
            llm_client=self.llm,
            task_manager=self.task_manager,
            personality_manager=self.personality_manager
        )

        # 初始化调度器
        self.scheduler = HybridScheduler()

        # 初始化搜索工具
        try:
            web_search = WebSearchClient(
                default_engine=os.getenv('SEARCH_ENGINE', 'duckduckgo'),
                api_keys={
                    'bing': os.getenv('BING_API_KEY'),
                    'brave': os.getenv('BRAVE_API_KEY'),
                }
            )
            self.search_tool = SearchTool(
                web_search_client=web_search,
                llm_client=self.llm.generate,
                enable_auto_search=os.getenv('ENABLE_AUTO_SEARCH', 'false').lower() == 'true'
            )
            logger.info("搜索功能已初始化")
        except Exception as e:
            logger.warning(f"搜索功能初始化失败: {e}")
            self.search_tool = None

        # 初始化 MCP 客户端和工具执行器
        if self.settings.mcp_enabled:
            logger.info("正在初始化 MCP 工具...")

            # 使用配置管理器自动发现和加载 MCP 配置
            self.mcp_config_manager = get_config_manager(
                f"{self.settings.data_dir}/mcp_configs"
            )

            # 从环境变量自动发现 MCP 服务
            auto_count = self.mcp_config_manager.auto_discover_from_env()
            if auto_count > 0:
                logger.info(f"  ✓ 从环境变量发现 {auto_count} 个 MCP 服务")

            # 创建 MCP 客户端并从配置管理器加载
            self.mcp_client = MCPClient(config_manager=self.mcp_config_manager)
            self.mcp_client.load_from_config_manager(self.mcp_config_manager)

            # 手动配置（如果环境变量中有但未自动加载）
            if self.settings.mcp_amap_api_key and "amap" not in self.mcp_client.configs:
                self.mcp_client.add_preset("amap", self.settings.mcp_amap_api_key)
                logger.info("  ✓ 高德地图 MCP 已配置")

            if self.settings.mcp_baidu_map_api_key and "baidu_map" not in self.mcp_client.configs:
                self.mcp_client.add_preset("baidu_map", self.settings.mcp_baidu_map_api_key)
                logger.info("  ✓ 百度地图 MCP 已配置")

            if self.settings.mcp_minimax_api_key and "minimax" not in self.mcp_client.configs:
                self.mcp_client.add_preset("minimax", self.settings.mcp_minimax_api_key)
                logger.info("  ✓ MiniMax MCP 已配置")

            if self.settings.mcp_glm_api_key and "glm" not in self.mcp_client.configs:
                self.mcp_client.add_preset("glm", self.settings.mcp_glm_api_key)
                logger.info("  ✓ GLM MCP 已配置")

            # 注册内置工具
            self.function_registry = FunctionRegistry()

            # 创建工具执行器
            self.tool_executor = ToolExecutor(
                mcp_client=self.mcp_client,
                function_registry=self.function_registry
            )

            # 显示可用的工具
            tools = self.tool_executor.get_available_tools()
            logger.info(f"MCP 工具初始化完成，可用工具: {len(tools)} 个")

        # 初始化极简意图处理器（LLM-First 架构）
        logger.info("使用 LLM-First 意图处理")
        self.intent_handler = SimpleIntentHandler(llm_client=self.llm.generate)

        # 初始化动作路由器（旧系统，保留兼容）
        self.action_router = ActionRouter(
            memory_system=self.memory,
            task_manager=self.task_manager,
            llm_client=self.llm.generate,
            search_tool=self.search_tool,
            tool_executor=self.tool_executor
        )

        # 初始化新的 Agent 系统（Supervisor + Function Calling）
        logger.info("正在初始化 Agent 系统...")
        self.agent = create_agent_system(
            llm_client=self.llm,
            memory_system=self.memory,
            task_manager=self.task_manager,
            search_tool=self.search_tool,
            personality_manager=self.personality_manager,
            chat_session=self.chat_session,
            fast_path_classifier=None  # 不再使用旧的意图分类器
        )
        logger.info(f"Agent 系统初始化完成，已注册 {len(self.agent.tools)} 个工具")

        logger.info("初始化完成！")

    def _print_banner(self):
        """打印启动横幅"""
        personality = self.personality_manager.get_current() if self.personality_manager else None
        persona_name = personality.self_reference if personality else "助手"

        print("\n" + "=" * 50)
        print(f"🤖 Personal AI Assistant - {persona_name}")
        print("=" * 50)
        print("命令:")
        print("  /quit, /q          - 退出")
        print("  /tasks, /t         - 查看任务列表")
        print("  /clear, /c         - 清空对话历史")
        print("  /status, /s        - 查看系统状态")
        print("  /personality, /p   - 查看/切换性格")
        print("  /consolidate       - 手动整合记忆")
        print("  /export            - 导出记忆数据")
        print("  /help, /h          - 显示帮助")
        print("=" * 50 + "\n")

    async def interactive_chat(self):
        """交互式对话模式"""
        self._print_banner()

        while True:
            try:
                user_input = input("👤 你: ").strip()

                if not user_input:
                    continue

                # 处理命令
                if user_input.startswith('/'):
                    if await self._handle_command(user_input):
                        break
                    continue

                # 使用新的 Agent 系统处理
                print("🤖 助手: ", end='', flush=True)
                try:
                    async for output in self.agent.handle(user_input, session_id=self.settings.session_id):
                        if isinstance(output, dict) and output.get("type") == "need_input":
                            # 需要用户确认
                            print(f"\n💭 {output.get('prompt', '请确认')}")
                            confirm = input("你的回复: ").strip()
                            # 继续处理确认
                            print("🤖 助手: ", end='', flush=True)
                            async for confirm_output in self.agent.continue_with_input(confirm, self.agent._current_context):
                                print(confirm_output, end='', flush=True)
                        else:
                            print(output, end='', flush=True)
                    print()  # 换行
                    print()
                except Exception as e:
                    logger.error(f"Agent 处理错误: {e}")
                    print(f"\n❌ 错误: {e}")
                    continue

            except KeyboardInterrupt:
                print("\n👋 再见！")
                break
            except Exception as e:
                logging.error(f"对话错误: {e}")
                print(f"❌ 错误: {e}")

    async def _handle_command(self, cmd: str) -> bool:
        """处理命令，返回True表示退出"""
        cmd = cmd.lower()

        if cmd in ['/quit', '/q', 'exit']:
            print("👋 再见！")
            return True

        elif cmd in ['/tasks', '/t']:
            self._show_tasks()

        elif cmd in ['/clear', '/c']:
            self.chat_session.clear_history()
            print("🗑️ 对话历史已清空")

        elif cmd in ['/status', '/s']:
            self._show_status()

        elif cmd in ['/consolidate', '/merge']:
            print("🔄 正在整合记忆...")
            stats = self.memory.consolidate()
            print("✅ 整合完成:")
            print(f"  收集: {stats.get('collected', 0)}")
            print(f"  提取事实: {stats.get('facts_extracted', 0)}")

        elif cmd == '/stats':
            stats = self.memory.get_stats()
            print("\n📊 记忆统计:")
            print(f"  记忆总数: {stats.get('total', 0)}")
            print(f"  新增记忆: {stats.get('memories_added', 0)}")
            print(f"  检索次数: {stats.get('memories_retrieved', 0)}")

        elif cmd in ['/export', '/e']:
            print("📤 正在导出数据...")
            result = self.action_router._handle_export_data(
                type('Intent', (), {'raw_text': ''})(), ''
            )
            if result.success:
                print(f"✅ {result.message}")
            else:
                print(f"❌ 导出失败: {result.message}")

        elif cmd in ['/personality', '/p']:
            """切换性格"""
            personalities = self.personality_manager.list_personalities()
            current = self.personality_manager.get_current()

            print(f"\n🎭 当前性格: {current.name} ({current.self_reference})")
            print("\n可用性格:")
            for i, p in enumerate(personalities, 1):
                marker = " ✓" if p['name'] == current.name else ""
                print(f"  {i}. {p['name']}: {p['description']}{marker}")
            print("\n切换性格: /personality <性格名>")
            print("  例如: /personality ojousama_assistant")

        elif cmd.startswith('/personality '):
            """设置性格"""
            personality_name = cmd[13:].strip()
            if self.personality_manager.set_personality(personality_name):
                new_personality = self.personality_manager.get_current()
                # 重新初始化 ChatSession 以应用新的性格
                self.chat_session = ChatSession(
                    session_id=self.settings.session_id,
                    memory_system=self.memory,
                    llm_client=self.llm,
                    task_manager=self.task_manager,
                    personality_manager=self.personality_manager
                )
                print(f"✅ 性格已切换为: {new_personality.name}")
                print(f"   自称: {new_personality.self_reference}")
                print(f"   对您的称呼: {new_personality.user_reference}")
            else:
                print(f"❌ 无效的性格: {personality_name}")
                print("可用: nekomata_assistant, ojousama_assistant, default_assistant")

        elif cmd in ['/help', '/h']:
            personality = self.personality_manager.get_current()
            print(f"""
🤖 Personal AI Assistant 帮助

当前性格: {personality.name} ({personality.self_reference})

📋 任务管理:
  • 创建任务: "明天下午3点开会"
  • 查看任务: /tasks, /t
  • 设置提醒: "10分钟后提醒我喝水"

🧠 记忆管理:
  • 记录信息: "记住我喜欢Python"
  • 查询记忆: "我之前说过什么"
  • 整合记忆: /consolidate

🎭 性格设置:
  • 查看性格: /personality, /p
  • 切换性格: /personality <性格名>

⚙️  系统命令:
  • 退出: /quit, /q
  • 清空对话: /clear, /c
  • 查看状态: /status, /s
  • 导出数据: /export, /e
  • 帮助: /help, /h
            """)

        else:
            print(f"❓ 未知命令: {cmd}")

        return False

    def _show_tasks(self):
        """显示任务列表"""

        tasks = self.task_manager.list_tasks(status="pending")
        if not tasks:
            print("📋 暂无待办任务")
            return

        print(f"\n📋 待办任务 ({len(tasks)}个):")
        print("-" * 70)

        for task in tasks[:10]:
            # 根据优先级分数选择 emoji
            priority_score = task.priority.calculate()
            if priority_score >= 0.7:
                priority_emoji = "🔴"
            elif priority_score >= 0.4:
                priority_emoji = "🟡"
            else:
                priority_emoji = "🟢"

            # 任务类型标签
            type_emoji = {
                "immediate": "⚡",
                "todo": "📝",
                "scheduled": "📅",
                "recurring": "🔄",
                "triggered": "🔗",
                "delegated": "👤",
            }.get(task.task_type.value, "📌")

            # 第一行：标题 + 执行/截止时间
            exec_time = ""
            if task.scheduled_at:
                exec_time = f"⏰ 执行: {task.scheduled_at.strftime('%m-%d %H:%M')}"
            elif task.due_date:
                exec_time = f"📅 截止: {task.due_date.strftime('%m-%d %H:%M')}"

            if exec_time:
                print(f"{priority_emoji} [{task.id[:8]}] {type_emoji} {task.title}")
                print(f"      {exec_time}")
            else:
                print(f"{priority_emoji} [{task.id[:8]}] {type_emoji} {task.title}")

            # 第二行：描述（如果有）
            if task.description:
                desc = task.description[:45] + "..." if len(task.description) > 45 else task.description
                print(f"      📝 {desc}")

            # 第三行：添加时间 + 标签
            meta_info = []
            if task.created_at:
                meta_info.append(f"📌 添加: {task.created_at.strftime('%m-%d %H:%M')}")
            if task.tags:
                meta_info.append(f"🏷️ {','.join(task.tags[:3])}")
            if task.waiting_for:
                meta_info.append(f"⏳ 等待: {task.waiting_for}")

            if meta_info:
                print(f"      {' | '.join(meta_info)}")

            print()

        if len(tasks) > 10:
            print(f"... 还有 {len(tasks) - 10} 个任务")
        print("-" * 70)

    def _show_status(self):
        """显示系统状态"""
        summary = self.chat_session.get_summary()
        print("\n📊 系统状态:")
        print("-" * 40)
        print(f"会话ID: {summary['session_id']}")
        print(f"运行时长: {summary['duration_seconds']:.0f}秒")
        print(f"对话轮数: {summary['user_message_count']}")

        wm = self.memory.working_memory
        print(f"\n工作记忆槽位: {len(wm.slots)}/10")
        for key in wm.slots:
            print(f"  • {key}")

        all_tasks = self.task_manager.list_tasks()
        pending = len([t for t in all_tasks if t.status.value == "pending"])
        completed = len([t for t in all_tasks if t.status.value == "completed"])
        print(f"\n任务统计: 待办 {pending} | 完成 {completed}")
        print()

    async def run_single(self, command: str):
        """执行单次任务"""
        response = self.chat_session.chat(command)
        print(response)

    async def shutdown(self):
        """关闭所有组件"""
        logger = logging.getLogger('pai')
        logger.info("正在关闭...")
        if self.auto_consolidation:
            await self.auto_consolidation.stop()
        if self.scheduler:
            await self.scheduler.stop_all()
        if self.memory:
            self.memory.close()
        logger.info("已关闭")


async def async_main():
    """异步主函数"""
    parser = argparse.ArgumentParser(description='Personal AI Assistant')
    parser.add_argument('-c', '--command', help='执行单次命令后退出')
    parser.add_argument('--data-dir', default=os.getenv('DATA_DIR', './data'), help='数据目录')
    parser.add_argument('--log-level', default=os.getenv('LOG_LEVEL', 'INFO'), help='日志级别')
    parser.add_argument('--llm-provider', default=os.getenv('LLM_PROVIDER', 'ollama'), choices=['openai', 'ollama', 'minimax'])
    parser.add_argument('--llm-model', default=os.getenv('LLM_MODEL', 'qwen2.5:14b'), help='LLM模型')
    parser.add_argument('--llm-api-key', default=os.getenv('LLM_API_KEY'), help='OpenAI API Key (仅OpenAI需要)')
    parser.add_argument('--llm-base-url', default=os.getenv('LLM_BASE_URL'), help='LLM基础URL')
    parser.add_argument('--embedding-provider', default=os.getenv('EMBEDDING_PROVIDER', 'ollama'), choices=['openai', 'ollama'])
    args = parser.parse_args()

    setup_logging(args.log_level)

    # 加载配置（优先级：命令行参数 > 环境变量 > 默认值）
    # 注意：argparse 默认值已从环境变量读取
    settings = Settings(
        data_dir=args.data_dir,
        llm_provider=args.llm_provider,
        llm_model=args.llm_model,
        llm_api_key=args.llm_api_key,
        llm_base_url=args.llm_base_url,
        embedding_provider=args.embedding_provider,
        embedding_model=os.getenv('EMBEDDING_MODEL', 'nomic-embed-text'),
        embedding_base_url=os.getenv('EMBEDDING_BASE_URL', 'http://localhost:11434'),
    )

    assistant = PersonalAIAssistant(settings)

    try:
        await assistant.initialize()

        if args.command:
            await assistant.run_single(args.command)
        else:
            await assistant.interactive_chat()

    finally:
        await assistant.shutdown()


def main():
    """主入口"""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
