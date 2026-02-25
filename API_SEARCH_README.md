# Public API 搜索功能

## 简介

系统已集成 `public-apis` 搜索功能，可以快速查找 GitHub public-apis 仓库中的免费公共 API。

## 使用方法

### 1. 通过对话搜索 API

可以直接在聊天中询问：

- "有什么免费的天气 API 推荐吗？"
- "帮我找一些汇率 API"
- "有哪些加密货币相关的 API？"
- "搜索一下免费的翻译 API"

### 2. 支持的 API 类别

| 类别 | 说明 | 示例 API |
|------|------|----------|
| weather | 天气预报 | Open-Meteo (免认证), MetaWeather (免认证) |
| currency | 汇率转换 | Frankfurter (免认证), ExchangeRate-API |
| crypto | 加密货币 | CoinGecko (免认证), CoinCap (免认证) |
| ip | IP 定位 | ipapi (免认证), IPify (免认证) |
| translate | 翻译服务 | LibreTranslate (免认证) |
| news | 新闻数据 | NewsAPI, GNews |
| github | GitHub API | GitHub REST API |
| joke | 随机笑话 | JokeAPI (免认证) |
| quote | 名言警句 | Quotable (免认证), Zen Quotes (免认证) |
| image | 图片服务 | Unsplash, Lorem Picsum |
| ai | AI/ML | Hugging Face |

### 3. Function Call 工具

系统已注册以下 function calls：

```python
# 搜索 API
search_public_apis(keyword="weather", category=None, auth_required=None)

# 列出所有类别
list_api_categories()
```

### 4. 代码中使用

```python
from tools import search_public_apis, list_api_categories

# 搜索天气 API
result = search_public_apis("weather")
print(result)

# 只搜索免认证的 API
result = search_public_apis("ip", auth_required=False)
print(result)

# 列出所有类别
result = list_api_categories()
print(result)
```

## API 认证说明

- 🔓 **免认证**: 无需 API Key，可直接使用
- 🔐 **需认证**: 需要注册并获取 API Key

## 意图识别

系统已添加 `API_SEARCH` 意图，可以自动识别以下查询：

- "有什么免费 API"
- "搜索 API"
- "推荐一些 API"
- "找 XX API"

## 文件位置

- 核心实现: `src/tools/public_api_search.py`
- 意图定义: `src/chat/intent_classifier.py`
- 动作处理: `src/chat/action_router.py`
- 函数注册: `src/tools/function_registry.py`
