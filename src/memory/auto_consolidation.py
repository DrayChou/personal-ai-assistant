# -*- coding: utf-8 -*-
"""
自动记忆整合调度器

实现 OpenClaw 风格的三层记忆整合:
- Daily Context Sync: 每天整合当日记忆
- Weekly Memory Compound: 每周知识蒸馏
- Hourly Micro-Sync: 白天时段轻量级检查
"""
import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .memory_system import MemorySystem

logger = logging.getLogger('memory.auto_consolidation')


@dataclass
class ConsolidationResult:
    """整合结果"""
    layer: str  # daily/weekly/micro
    success: bool
    items_processed: int = 0
    items_extracted: int = 0
    errors: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


class AutoConsolidationScheduler:
    """
    自动记忆整合调度器

    参考 OpenClaw 的三层记忆架构实现自动化记忆管理。
    无需手动调用 consolidate，系统会自动按调度执行。
    """

    def __init__(
        self,
        memory_system: 'MemorySystem',
        daily_hour: int = 23,
        weekly_day: int = 6,
        weekly_hour: int = 22,
        micro_sync_hours: Optional[list[int]] = None,
        storage_path: str = "./data/consolidation_state.json"
    ):
        """
        初始化调度器

        Args:
            memory_system: 记忆系统实例
            daily_hour: 每日整合时间 (0-23)，默认 23 点
            weekly_day: 每周整合日 (0-6，0=周一)，默认 6=周日
            weekly_hour: 每周整合时间，默认 22 点
            micro_sync_hours: 微同步时间点列表，默认 [10, 13, 16, 19, 22]
            storage_path: 状态存储路径
        """
        self.memory = memory_system
        self.daily_hour = daily_hour
        self.weekly_day = weekly_day
        self.weekly_hour = weekly_hour
        self.micro_sync_hours = micro_sync_hours or [10, 13, 16, 19, 22]
        self.storage_path = Path(storage_path)

        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_results: list[ConsolidationResult] = []

        # 加载上次执行状态
        self._load_state()

    def _load_state(self):
        """加载上次执行状态"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    _state = json.load(f)
                    logger.debug(f"加载整合状态: {self.storage_path}")
            except Exception as e:
                logger.warning(f"加载整合状态失败: {e}")

    def _save_state(self):
        """保存执行状态"""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            state = {
                "last_results": [
                    {
                        "layer": r.layer,
                        "success": r.success,
                        "items_processed": r.items_processed,
                        "items_extracted": r.items_extracted,
                        "timestamp": r.timestamp.isoformat()
                    }
                    for r in self._last_results[-10:]  # 只保留最近10条
                ]
            }
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"保存整合状态失败: {e}")

    async def start(self):
        """启动调度器"""
        if self._running:
            logger.warning("调度器已在运行")
            return

        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info(
            f"自动记忆整合调度器已启动 | "
            f"Daily: {self.daily_hour}:00 | "
            f"Weekly: 周{self.weekly_day} {self.weekly_hour}:00 | "
            f"Micro: {self.micro_sync_hours}"
        )

    async def stop(self):
        """停止调度器"""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("自动记忆整合调度器已停止")

    async def _scheduler_loop(self):
        """主调度循环"""
        while self._running:
            try:
                now = datetime.now()

                # Layer 3: Hourly Micro-Sync (白天时段)
                if now.hour in self.micro_sync_hours and now.minute == 0:
                    result = await self._micro_sync()
                    self._record_result(result)

                # Layer 1: Daily Context Sync (每晚)
                if now.hour == self.daily_hour and now.minute == 0:
                    result = await self._daily_sync()
                    self._record_result(result)

                # Layer 2: Weekly Memory Compound (每周日)
                if (now.weekday() == self.weekly_day and
                    now.hour == self.weekly_hour and
                    now.minute == 0):
                    result = await self._weekly_compound()
                    self._record_result(result)

                await asyncio.sleep(60)  # 每分钟检查一次

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("调度循环异常")
                await asyncio.sleep(60)

    def _record_result(self, result: ConsolidationResult):
        """记录执行结果"""
        self._last_results.append(result)
        if len(self._last_results) > 100:
            self._last_results = self._last_results[-50:]
        self._save_state()

    async def _daily_sync(self) -> ConsolidationResult:
        """
        Layer 1: Daily Context Sync
        每天整合当日新增的记忆
        """
        logger.info("[Layer 1] 执行 Daily Context Sync...")

        try:
            # 获取今日统计（用于日志记录）
            _stats = self._get_today_stats()  # noqa: F841

            # 执行整合
            from ..task.extractor import TaskExtractor

            # 检索今日的相关记忆
            recent_memories = self.memory.recall(
                query="今日活动 对话 决策",
                top_k=20
            )

            # 提取任务和事实
            extractor = TaskExtractor()
            facts = []
            tasks = []

            # 解析 recall 结果文本
            for line in recent_memories.split('\n'):
                if line.strip() and not line.startswith('---'):
                    # 尝试提取任务
                    extracted = extractor.extract_from_single_message(line)
                    tasks.extend(extracted)

                    # 简单事实提取（包含"是""喜欢"等的句子）
                    if any(kw in line for kw in ['是', '喜欢', '需要', '决定', '使用']):
                        facts.append(line.strip())

            # 保存到每日日志（返回值用于日志记录）
            self._save_daily_log(facts, tasks)

            result = ConsolidationResult(
                layer="daily",
                success=True,
                items_processed=len(recent_memories.split('\n')),
                items_extracted=len(facts) + len(tasks),
                errors=[]
            )

            logger.info(
                f"[Layer 1] Daily Sync 完成 | "
                f"处理: {result.items_processed} | "
                f"提取: {result.items_extracted}"
            )

            return result

        except Exception as e:
            logger.exception("[Layer 1] Daily Sync 失败")
            return ConsolidationResult(
                layer="daily",
                success=False,
                errors=[str(e)]
            )

    async def _weekly_compound(self) -> ConsolidationResult:
        """
        Layer 2: Weekly Memory Compound
        每周知识复利 - 蒸馏重要记忆到核心
        """
        logger.info("[Layer 2] 执行 Weekly Memory Compound...")

        try:
            # 获取本周全部记忆
            week_memories = self.memory.recall(
                query="过去一周 重要 决策 偏好",
                top_k=50
            )

            # 生成核心记忆摘要（简化版）
            core_memories = self._generate_core_memories(week_memories)

            # 保存到核心记忆区
            saved_count = 0
            for memory in core_memories:
                self.memory.capture(
                    content=memory,
                    memory_type="summary",
                    confidence="fact",
                    tags=["core", "weekly_compound"]
                )
                saved_count += 1

            result = ConsolidationResult(
                layer="weekly",
                success=True,
                items_processed=len(week_memories.split('\n')),
                items_extracted=saved_count,
                errors=[]
            )

            logger.info(
                f"[Layer 2] Weekly Compound 完成 | "
                f"生成: {saved_count} 条核心记忆"
            )

            return result

        except Exception as e:
            logger.exception("[Layer 2] Weekly Compound 失败")
            return ConsolidationResult(
                layer="weekly",
                success=False,
                errors=[str(e)]
            )

    async def _micro_sync(self) -> ConsolidationResult:
        """
        Layer 3: Hourly Micro-Sync
        微同步 - 轻量级检查最近活动
        """
        logger.info("[Layer 3] 执行 Hourly Micro-Sync...")

        try:
            # 获取工作记忆中的最近活动
            recent_context = self.memory.working_memory.get_context()

            if not recent_context or len(recent_context) < 100:
                # 没有重要活动，静默退出
                return ConsolidationResult(
                    layer="micro",
                    success=True,
                    items_processed=0,
                    items_extracted=0,
                    errors=[]
                )

            # 追加简要摘要到今日日志
            self._append_to_daily_log(f"[Micro-Sync] {recent_context[:200]}...")

            result = ConsolidationResult(
                layer="micro",
                success=True,
                items_processed=1,
                items_extracted=1,
                errors=[]
            )

            logger.info("[Layer 3] Micro-Sync 完成")
            return result

        except Exception as e:
            logger.exception("[Layer 3] Micro-Sync 失败")
            return ConsolidationResult(
                layer="micro",
                success=False,
                errors=[str(e)]
            )

    def _get_today_stats(self) -> dict:
        """获取今日记忆统计"""
        try:
            return self.memory.get_stats()
        except Exception as e:
            logger.warning(f"Failed to get stats: {e}")
            return {}

    def _save_daily_log(self, facts: list[str], tasks: list) -> Path:
        """保存每日日志"""
        today = datetime.now().strftime("%Y-%m-%d")
        log_dir = Path("./data/memory/daily")
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file = log_dir / f"{today}.md"

        content = f"""# {today} Daily Log

## Facts Extracted
"""
        for fact in facts[:20]:  # 限制数量
            content += f"- {fact}\n"

        content += "\n## Tasks Extracted\n"
        for task in tasks[:10]:
            content += f"- [ ] {task.title}\n"

        content += f"\n---\nGenerated at: {datetime.now().isoformat()}\n"

        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(content)

        return log_file

    def _generate_core_memories(self, week_memories: str) -> list[str]:
        """生成本周核心记忆（简化版）"""
        core_memories = []

        lines = week_memories.split('\n')

        # 简单启发式提取重要记忆
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 偏好类
            if any(kw in line for kw in ['喜欢', '偏好', '习惯', '总是']):
                core_memories.append(f"[Preference] {line}")

            # 决策类
            if any(kw in line for kw in ['决定', '选择', '使用', '采用']):
                core_memories.append(f"[Decision] {line}")

            # 重要事件
            if any(kw in line for kw in ['完成', '发布', '上线', '修复']):
                core_memories.append(f"[Milestone] {line}")

        # 去重
        return list(set(core_memories))[:20]  # 限制数量

    def _append_to_daily_log(self, content: str):
        """追加内容到今日日志"""
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = Path(f"./data/memory/daily/{today}.md")

        if log_file.exists():
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"\n{content}\n")

    def get_status(self) -> dict:
        """获取调度器状态"""
        return {
            "running": self._running,
            "last_results": [
                {
                    "layer": r.layer,
                    "success": r.success,
                    "timestamp": r.timestamp.isoformat()
                }
                for r in self._last_results[-5:]
            ]
        }
