# -*- coding: utf-8 -*-
"""
Public APIs 检索工具

封装 GitHub public-apis 仓库的 API 检索功能，
可以搜索各种免费公共 API。
"""
from typing import Optional
from dataclasses import dataclass


@dataclass
class APIEntry:
    """API 条目"""
    name: str
    description: str
    auth: str
    https: bool
    cors: str
    category: str
    url: Optional[str] = None


class PublicAPISearch:
    """
    Public APIs 搜索工具

    从 GitHub public-apis 仓库获取免费 API 列表
    """

    # 已知的常用免费 API（内置缓存，避免频繁请求）
    POPULAR_APIS = {
        "weather": [
            APIEntry("Open-Meteo", "全球天气预报，无需API Key", "No", True, "Yes", "Weather", "https://open-meteo.com/"),
            APIEntry("WeatherAPI", "天气预报和历史数据", "apiKey", True, "Yes", "Weather", "https://www.weatherapi.com/"),
            APIEntry("MetaWeather", "天气数据查询", "No", True, "No", "Weather", "https://www.metaweather.com/api/"),
        ],
        "currency": [
            APIEntry("ExchangeRate-API", "汇率转换", "apiKey", True, "Yes", "Currency", "https://www.exchangerate-api.com/"),
            APIEntry("Frankfurter", "汇率数据（基于ECB）", "No", True, "Yes", "Currency", "https://www.frankfurter.app/"),
            APIEntry("CurrencyAPI", "货币汇率", "apiKey", True, "Yes", "Currency", "https://currencyapi.com/"),
        ],
        "crypto": [
            APIEntry("CoinGecko", "加密货币数据", "No", True, "Yes", "Cryptocurrency", "https://www.coingecko.com/api"),
            APIEntry("CoinCap", "实时加密货币价格", "No", True, "Yes", "Cryptocurrency", "https://api.coincap.io/"),
        ],
        "ip": [
            APIEntry("ipapi", "IP地址定位", "No", True, "Unknown", "Geocoding", "https://ipapi.co/"),
            APIEntry("ip-api", "IP地理位置", "No", False, "Unknown", "Geocoding", "http://ip-api.com/"),
            APIEntry("IPify", "获取公网IP", "No", True, "Unknown", "Geocoding", "https://www.ipify.org/"),
        ],
        "translate": [
            APIEntry("LibreTranslate", "开源机器翻译", "No", True, "Unknown", "Translation", "https://libretranslate.com/"),
            APIEntry("MyMemory", "翻译API", "No", True, "Unknown", "Translation", "https://mymemory.translated.net/"),
        ],
        "news": [
            APIEntry("NewsAPI", "全球新闻", "apiKey", True, "Unknown", "News", "https://newsapi.org/"),
            APIEntry("GNews", "新闻搜索", "apiKey", True, "Yes", "News", "https://gnews.io/"),
        ],
        "github": [
            APIEntry("GitHub API", "GitHub 官方API", "OAuth", True, "Yes", "Development", "https://docs.github.com/en/rest"),
        ],
        "joke": [
            APIEntry("JokeAPI", "随机笑话", "No", True, "Yes", "Entertainment", "https://v2.jokeapi.dev/"),
            APIEntry("Official Joke API", "编程笑话", "No", True, "Unknown", "Entertainment", "https://official-joke-api.appspot.com/"),
        ],
        "quote": [
            APIEntry("Quotable", "名言警句", "No", True, "Unknown", "Personality", "https://quotable.io/"),
            APIEntry("Zen Quotes", "禅语和名言", "No", True, "Yes", "Personality", "https://zenquotes.io/"),
        ],
        "image": [
            APIEntry("Unsplash", "免费图片", "apiKey", True, "Unknown", "Photography", "https://unsplash.com/developers"),
            APIEntry("Lorem Picsum", "随机图片", "No", True, "Unknown", "Photography", "https://picsum.photos/"),
        ],
        "ai": [
            APIEntry("Hugging Face", "AI模型推理", "apiKey", True, "Yes", "Machine Learning", "https://huggingface.co/docs/api-inference"),
        ],
    }

    def __init__(self):
        self._all_apis: list[APIEntry] = []
        self._load_all_apis()

    def _load_all_apis(self):
        """加载所有 API 到列表"""
        for apis in self.POPULAR_APIS.values():
            self._all_apis.extend(apis)

    def search(self, keyword: str, category: Optional[str] = None, auth_required: Optional[bool] = None) -> list[APIEntry]:
        """
        搜索 API

        Args:
            keyword: 搜索关键词
            category: 按类别筛选（可选）
            auth_required: 是否需要认证筛选（可选，True/False/None）

        Returns:
            匹配的 API 列表
        """
        keyword_lower = keyword.lower()
        results = []

        for api in self._all_apis:
            # 关键词匹配
            match = (keyword_lower in api.name.lower() or
                     keyword_lower in api.description.lower() or
                     keyword_lower in api.category.lower())

            if not match:
                continue

            # 类别筛选
            if category and category.lower() not in api.category.lower():
                continue

            # 认证要求筛选
            if auth_required is not None:
                api_requires_auth = api.auth != "No"
                if api_requires_auth != auth_required:
                    continue

            results.append(api)

        return results

    def list_categories(self) -> list[str]:
        """列出所有类别"""
        return list(self.POPULAR_APIS.keys())

    def get_by_category(self, category: str) -> list[APIEntry]:
        """按类别获取 API"""
        return self.POPULAR_APIS.get(category.lower(), [])

    def format_result(self, apis: list[APIEntry]) -> str:
        """格式化结果为文本"""
        if not apis:
            return "未找到匹配的 API"

        lines = [f"找到 {len(apis)} 个 API:\n"]

        for i, api in enumerate(apis, 1):
            auth_status = "🔐 需认证" if api.auth != "No" else "🔓 免认证"
            https_status = "🔒 HTTPS" if api.https else "⚠️ HTTP"

            lines.append(f"{i}. **{api.name}**")
            lines.append(f"   描述: {api.description}")
            lines.append(f"   类别: {api.category} | {auth_status} | {https_status}")
            if api.url:
                lines.append(f"   文档: {api.url}")
            lines.append("")

        return "\n".join(lines)


# Function Call 定义
SEARCH_PUBLIC_APIS_SCHEMA = {
    "name": "search_public_apis",
    "description": "搜索 Public APIs 仓库中的免费公共 API，可以查找天气、汇率、加密货币、新闻、翻译等各种免费 API 服务",
    "parameters": {
        "type": "object",
        "properties": {
            "keyword": {
                "type": "string",
                "description": "搜索关键词，例如：weather, currency, crypto, news, translate, joke, ip"
            },
            "category": {
                "type": "string",
                "description": "按类别筛选（可选），例如：Weather, Currency, Cryptocurrency, News, Translation",
            },
            "auth_required": {
                "type": "boolean",
                "description": "是否需要 API Key 认证（可选）。true=需要认证，false=免认证，null=不限"
            }
        },
        "required": ["keyword"]
    }
}

LIST_API_CATEGORIES_SCHEMA = {
    "name": "list_api_categories",
    "description": "列出所有可用的 API 类别",
    "parameters": {
        "type": "object",
        "properties": {}
    }
}


def search_public_apis(keyword: str, category: Optional[str] = None, auth_required: Optional[bool] = None) -> str:
    """
    搜索公共 API

    Args:
        keyword: 搜索关键词
        category: 类别筛选
        auth_required: 是否需要认证

    Returns:
        格式化的 API 列表
    """
    searcher = PublicAPISearch()
    results = searcher.search(keyword, category, auth_required)
    return searcher.format_result(results)


def list_api_categories() -> str:
    """列出所有 API 类别"""
    searcher = PublicAPISearch()
    categories = searcher.list_categories()
    return "可用的 API 类别:\n" + "\n".join(f"- {cat}" for cat in categories)
