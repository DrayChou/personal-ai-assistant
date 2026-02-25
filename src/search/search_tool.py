# -*- coding: utf-8 -*-
"""
搜索工具 - 与AI助手意图系统集成

提供：
- 实时信息查询
- 知识增强
- 事实核查
"""
import logging
from typing import Optional, List, Callable

from .web_search import WebSearchClient, SearchResult

logger = logging.getLogger('search.tool')


class SearchTool:
    """
    搜索工具

    为AI助手提供外部信息获取能力
    """

    def __init__(
        self,
        web_search_client: Optional[WebSearchClient] = None,
        llm_client: Optional[Callable] = None,
        enable_auto_search: bool = False
    ):
        """
        初始化搜索工具

        Args:
            web_search_client: Web搜索客户端
            llm_client: LLM客户端（用于总结）
            enable_auto_search: 是否启用自动搜索（根据意图自动触发）
        """
        self.web_search = web_search_client or WebSearchClient()
        self.llm = llm_client
        self.enable_auto_search = enable_auto_search

    def search(
        self,
        query: str,
        context: str = "",
        num_results: int = 5,
        summarize: bool = True
    ) -> str:
        """
        执行搜索并返回格式化的结果

        Args:
            query: 搜索查询
            context: 上下文信息（用于LLM总结）
            num_results: 结果数量
            summarize: 是否使用LLM总结

        Returns:
            格式化的搜索结果文本
        """
        logger.info(f"执行搜索: {query}")

        results = self.web_search.search(query, num_results=num_results)

        if not results:
            return "抱歉，没有找到相关结果。"

        if summarize and self.llm:
            return self._llm_summarize(results, context)

        return self._format_results(results)

    def should_search(self, text: str, intent_type: str = None) -> bool:
        """
        判断是否应该触发搜索

        Args:
            text: 用户输入
            intent_type: 意图类型

        Returns:
            是否应该搜索
        """
        if not self.enable_auto_search:
            return False

        # 明显的搜索意图关键词
        search_keywords = [
            "搜索", "查找", "查询", "什么是", "谁是", "哪里是",
            "最新", "新闻", "天气", "股价", "价格",
            "怎么", "如何", "为什么", "解释",
            "告诉我关于", "信息", "资料"
        ]

        text_lower = text.lower()
        for keyword in search_keywords:
            if keyword in text_lower:
                return True

        # 某些意图类型应该触发搜索
        search_intents = ["weather", "news", "search", "define"]
        if intent_type and intent_type.lower() in search_intents:
            return True

        return False

    def enhance_prompt(
        self,
        user_message: str,
        search_results: str
    ) -> str:
        """
        使用搜索结果增强提示

        Args:
            user_message: 用户消息
            search_results: 搜索结果

        Returns:
            增强后的提示
        """
        return f"""用户问题: {user_message}

相关搜索结果:
{search_results}

请根据以上信息回答用户的问题。如果搜索结果中没有相关信息，请说明你不知道。"""

    def _format_results(self, results: List[SearchResult]) -> str:
        """格式化搜索结果"""
        lines = [f"找到 {len(results)} 条相关结果：\n"]

        for r in results:
            lines.append(f"[{r.rank}] {r.title}")
            lines.append(f"    {r.snippet}")
            lines.append(f"    来源: {r.url}\n")

        return "\n".join(lines)

    def _llm_summarize(
        self,
        results: List[SearchResult],
        context: str
    ) -> str:
        """使用LLM总结搜索结果"""
        results_text = "\n\n".join([
            f"[{r.rank}] {r.title}\n{r.snippet}"
            for r in results[:5]
        ])

        prompt = f"""基于以下搜索结果，提供一个简洁准确的回答。

用户问题: {context}

搜索结果:
{results_text}

请:
1. 提取关键信息
2. 用简洁的中文回答
3. 如果信息有冲突，优先使用排名靠前的结果
4. 注明信息来源"""

        try:
            return self.llm(prompt)
        except Exception as e:
            logger.error(f"LLM总结失败: {e}")
            return self._format_results(results)

    def quick_answer(self, query: str) -> str:
        """
        快速回答模式

        执行搜索并返回最相关的信息
        """
        results = self.web_search.search(query, num_results=3)

        if not results:
            return "未找到相关信息。"

        # 返回最相关的结果
        best = results[0]
        return f"{best.title}\n\n{best.snippet}\n\n来源: {best.url}"
