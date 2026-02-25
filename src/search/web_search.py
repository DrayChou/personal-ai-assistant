# -*- coding: utf-8 -*-
"""
Web搜索客户端

集成多个搜索引擎：
- DuckDuckGo（默认，无需API Key）
- Bing（需要API Key）
- Brave（需要API Key）
"""
import logging
import urllib.request
import urllib.parse
import json
from dataclasses import dataclass
from typing import Optional, List, Callable

logger = logging.getLogger('search.web')


@dataclass
class SearchResult:
    """搜索结果"""
    title: str
    url: str
    snippet: str
    source: str = "unknown"  # 搜索引擎来源
    date: Optional[str] = None
    rank: int = 0  # 排名位置

    def to_text(self) -> str:
        """转换为文本格式"""
        return f"[{self.rank}] {self.title}\n{self.snippet}\n来源: {self.url}"


class WebSearchClient:
    """
    Web搜索客户端

    提供统一的搜索接口，支持多个搜索引擎
    """

    def __init__(
        self,
        default_engine: str = "duckduckgo",
        api_keys: dict = None,
        timeout: int = 10
    ):
        """
        初始化搜索客户端

        Args:
            default_engine: 默认搜索引擎
            api_keys: API密钥字典 {engine: key}
            timeout: 请求超时时间
        """
        self.default_engine = default_engine
        self.api_keys = api_keys or {}
        self.timeout = timeout

        # 搜索引擎配置
        self.engines = {
            "duckduckgo": self._search_duckduckgo,
            "bing": self._search_bing,
            "brave": self._search_brave,
        }

    def search(
        self,
        query: str,
        engine: str = None,
        num_results: int = 5
    ) -> List[SearchResult]:
        """
        执行搜索

        Args:
            query: 搜索查询
            engine: 搜索引擎（默认使用初始化时设置的）
            num_results: 返回结果数量

        Returns:
            搜索结果列表
        """
        engine = engine or self.default_engine

        if engine not in self.engines:
            logger.warning(f"未知的搜索引擎: {engine}，使用默认")
            engine = "duckduckgo"

        try:
            results = self.engines[engine](query, num_results)
            logger.info(f"搜索 '{query}' 返回 {len(results)} 条结果")
            return results
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return []

    def search_multi_engine(
        self,
        query: str,
        engines: List[str] = None,
        num_results_per_engine: int = 3
    ) -> List[SearchResult]:
        """
        多引擎搜索并合并结果

        Args:
            query: 搜索查询
            engines: 搜索引擎列表
            num_results_per_engine: 每个引擎的结果数

        Returns:
            合并后的搜索结果
        """
        engines = engines or ["duckduckgo"]
        all_results = []

        for engine in engines:
            results = self.search(query, engine, num_results_per_engine)
            all_results.extend(results)

        # 去重（基于URL）
        seen_urls = set()
        unique_results = []
        for r in all_results:
            if r.url not in seen_urls:
                seen_urls.add(r.url)
                unique_results.append(r)

        # 重新排名
        for i, r in enumerate(unique_results, 1):
            r.rank = i

        return unique_results[:10]  # 最多返回10条

    def _search_duckduckgo(self, query: str, num_results: int) -> List[SearchResult]:
        """
        DuckDuckGo搜索（无需API Key）

        使用DuckDuckGo的HTML接口
        """
        results = []

        try:
            # 使用duckduckgo-search库（如果可用）
            try:
                from duckduckgo_search import DDGS
                with DDGS() as ddgs:
                    for i, r in enumerate(ddgs.text(query, max_results=num_results), 1):
                        results.append(SearchResult(
                            title=r.get('title', ''),
                            url=r.get('href', ''),
                            snippet=r.get('body', ''),
                            source="DuckDuckGo",
                            rank=i
                        ))
                return results
            except ImportError:
                pass

            # 备用：使用SerpAPI风格（需要实现）
            # 这里返回一个提示，建议安装duckduckgo-search
            logger.warning("未安装 duckduckgo-search，尝试使用备用方法")
            return self._fallback_search(query, num_results)

        except Exception as e:
            logger.error(f"DuckDuckGo搜索失败: {e}")
            return []

    def _search_bing(self, query: str, num_results: int) -> List[SearchResult]:
        """Bing搜索（需要API Key）"""
        api_key = self.api_keys.get("bing")
        if not api_key:
            logger.warning("未配置Bing API Key")
            return []

        try:
            endpoint = "https://api.bing.microsoft.com/v7.0/search"
            headers = {"Ocp-Apim-Subscription-Key": api_key}
            params = urllib.parse.urlencode({
                "q": query,
                "count": num_results,
                "mkt": "zh-CN"
            })

            req = urllib.request.Request(
                f"{endpoint}?{params}",
                headers=headers
            )

            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                data = json.loads(response.read().decode('utf-8'))

            results = []
            for i, item in enumerate(data.get("webPages", {}).get("value", []), 1):
                results.append(SearchResult(
                    title=item.get('name', ''),
                    url=item.get('url', ''),
                    snippet=item.get('snippet', ''),
                    source="Bing",
                    rank=i
                ))

            return results

        except Exception as e:
            logger.error(f"Bing搜索失败: {e}")
            return []

    def _search_brave(self, query: str, num_results: int) -> List[SearchResult]:
        """Brave搜索（需要API Key）"""
        api_key = self.api_keys.get("brave")
        if not api_key:
            logger.warning("未配置Brave API Key")
            return []

        try:
            endpoint = "https://api.search.brave.com/res/v1/web/search"
            headers = {
                "X-Subscription-Token": api_key,
                "Accept": "application/json"
            }
            params = urllib.parse.urlencode({
                "q": query,
                "count": num_results
            })

            req = urllib.request.Request(
                f"{endpoint}?{params}",
                headers=headers
            )

            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                data = json.loads(response.read().decode('utf-8'))

            results = []
            for i, item in enumerate(data.get("web", {}).get("results", []), 1):
                results.append(SearchResult(
                    title=item.get('title', ''),
                    url=item.get('url', ''),
                    snippet=item.get('description', ''),
                    source="Brave",
                    rank=i
                ))

            return results

        except Exception as e:
            logger.error(f"Brave搜索失败: {e}")
            return []

    def _fallback_search(self, query: str, num_results: int) -> List[SearchResult]:
        """
        备用搜索方法

        当主要搜索引擎不可用时，返回提示信息
        """
        return [SearchResult(
            title="搜索功能需要安装依赖",
            url="https://github.com/deedy5/duckduckgo_search",
            snippet="请运行: pip install duckduckgo-search 以启用搜索功能",
            source="System",
            rank=1
        )]

    def summarize_results(
        self,
        results: List[SearchResult],
        llm_client: Optional[Callable] = None
    ) -> str:
        """
        总结搜索结果

        Args:
            results: 搜索结果列表
            llm_client: LLM客户端（可选）

        Returns:
            总结文本
        """
        if not results:
            return "未找到相关结果。"

        # 构建结果文本
        results_text = "\n\n".join([r.to_text() for r in results[:5]])

        if llm_client:
            prompt = f"""根据以下搜索结果，提供一个简洁的回答：

搜索结果：
{results_text}

请总结关键信息，用中文回答。"""

            try:
                return llm_client(prompt)
            except Exception as e:
                logger.warning(f"LLM总结失败: {e}")

        # 不使用LLM的简单总结
        return f"找到 {len(results)} 条结果：\n\n" + results_text
