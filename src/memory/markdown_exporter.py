# -*- coding: utf-8 -*-
"""
Markdown 记忆导出器

将记忆导出为 MemSearch 兼容的 Markdown 格式
支持 YAML frontmatter，便于版本控制和人类阅读
"""
import logging
from datetime import datetime
from pathlib import Path

import yaml

from .types import MemoryEntry, MemoryType

logger = logging.getLogger('memory.exporter')


class MarkdownExporter:
    """
    Markdown 记忆导出器

    特性:
    - YAML frontmatter 元数据
    - 按时间/类型组织目录
    - 兼容 MemSearch 格式
    - Git 友好
    """

    def __init__(self, base_path: str = "~/ai_workspace/memories"):
        self.base_path = Path(base_path).expanduser()
        self.base_path.mkdir(parents=True, exist_ok=True)

        # 创建子目录
        for subdir in ['episodic', 'semantic', 'procedural', 'emotional', 'general']:
            (self.base_path / subdir).mkdir(exist_ok=True)

    def export_memory(self, entry: MemoryEntry) -> str:
        """
        将单条记忆转为 Markdown 格式

        Args:
            entry: 记忆条目

        Returns:
            Markdown 格式字符串
        """
        # 构建 frontmatter
        fm = {
            "id": entry.id,
            "type": entry.memory_type.value,
            "type_category": self._get_type_category(entry.memory_type),
            "confidence_level": entry.confidence_level.name,
            "initial_confidence": entry.initial_confidence,
            "current_confidence": entry.current_confidence,
            "created_at": entry.created_at.isoformat(),
            "last_accessed": entry.last_accessed.isoformat(),
            "access_count": entry.access_count,
            "tags": entry.tags,
            "source": entry.source,
        }

        # 构建内容
        lines = [
            "---",
            yaml.dump(fm, allow_unicode=True, sort_keys=False),
            "---",
            "",
            f"# {self._get_title(entry)}",
            "",
            entry.content,
            "",
        ]

        # 添加元数据段落
        if entry.metadata:
            lines.extend([
                "## 元数据",
                "",
                "```json",
                str(entry.metadata),
                "```",
                "",
            ])

        return "\n".join(lines)

    def save_memory(self, entry: MemoryEntry) -> Path:
        """
        保存记忆到文件系统

        Args:
            entry: 记忆条目

        Returns:
            保存的文件路径
        """
        # 确定目录
        category = self._get_type_category(entry.memory_type)
        date_str = entry.created_at.strftime("%Y-%m-%d")

        dir_path = self.base_path / category / date_str
        dir_path.mkdir(parents=True, exist_ok=True)

        # 生成文件名
        safe_content = entry.content[:30].replace("/", "_").replace("\\", "_")
        filename = f"{entry.id}_{safe_content}.md"

        file_path = dir_path / filename

        # 写入文件
        markdown = self.export_memory(entry)
        file_path.write_text(markdown, encoding='utf-8')

        logger.debug(f"记忆已导出: {file_path}")
        return file_path

    def batch_export(self, entries: list[MemoryEntry]) -> list[Path]:
        """
        批量导出记忆

        Args:
            entries: 记忆条目列表

        Returns:
            导出的文件路径列表
        """
        paths = []
        for entry in entries:
            try:
                path = self.save_memory(entry)
                paths.append(path)
            except Exception as e:
                logger.error(f"导出记忆失败 {entry.id}: {e}")

        logger.info(f"批量导出完成: {len(paths)}/{len(entries)} 条")
        return paths

    def _get_type_category(self, memory_type: MemoryType) -> str:
        """获取记忆类型分类目录"""
        episodic_types = [
            MemoryType.EPISODIC, MemoryType.CONVERSATION,
            MemoryType.EVENT, MemoryType.EXPERIENCE
        ]
        semantic_types = [
            MemoryType.SEMANTIC, MemoryType.FACT,
            MemoryType.CONCEPT, MemoryType.SOLUTION,
            MemoryType.KNOWLEDGE, MemoryType.INSIGHT
        ]
        procedural_types = [
            MemoryType.PROCEDURAL, MemoryType.WORKFLOW,
            MemoryType.PATTERN, MemoryType.SKILL
        ]
        emotional_types = [
            MemoryType.EMOTIONAL, MemoryType.ATTITUDE,
            MemoryType.SENTIMENT
        ]

        if memory_type in episodic_types:
            return "episodic"
        elif memory_type in semantic_types:
            return "semantic"
        elif memory_type in procedural_types:
            return "procedural"
        elif memory_type in emotional_types:
            return "emotional"
        else:
            return "general"

    def _get_title(self, entry: MemoryEntry) -> str:
        """生成记忆标题"""
        content = entry.content.strip()

        # 如果内容较短，直接使用
        if len(content) <= 50:
            return content

        # 否则取前50字符
        return content[:50] + "..."

    def generate_index(self) -> Path:
        """
        生成索引文件

        Returns:
            索引文件路径
        """
        index_path = self.base_path / "README.md"

        lines = [
            "# 记忆库索引",
            "",
            f"生成时间: {datetime.now().isoformat()}",
            "",
            "## 目录结构",
            "",
            "```",
            "episodic/    - 情节记忆 (事件、对话、经历)",
            "semantic/    - 语义记忆 (知识、事实、概念)",
            "procedural/  - 程序记忆 (流程、技能、模式)",
            "emotional/   - 情感记忆 (情绪、态度)",
            "general/     - 其他记忆",
            "```",
            "",
            "## 统计",
            "",
        ]

        # 统计各目录文件数
        for category in ['episodic', 'semantic', 'procedural', 'emotional', 'general']:
            dir_path = self.base_path / category
            if dir_path.exists():
                count = len(list(dir_path.rglob("*.md")))
                lines.append(f"- {category}: {count} 条")

        lines.append("")

        index_path.write_text("\n".join(lines), encoding='utf-8')
        logger.info(f"索引已生成: {index_path}")

        return index_path
