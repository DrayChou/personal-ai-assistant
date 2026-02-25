# -*- coding: utf-8 -*-
"""
搜索模块 - 为AI助手提供外部信息获取能力（触觉）

支持：
- Web搜索（DuckDuckGo / Bing / Brave）
- 本地文件搜索
- 知识库搜索
"""
from .web_search import WebSearchClient, SearchResult
from .search_tool import SearchTool

__all__ = [
    'WebSearchClient',
    'SearchResult',
    'SearchTool',
]
