# 性格技能系统 (Personality Skills System)

## 概述

性格技能系统让每个性格（猫娘、大小姐等）都拥有专属能力。不同性格可以使用不同的技能，并以独特的风格展示结果。

## 已集成的 8 个技能

| 技能 | 图标 | 类别 | 描述 | 适用性格 |
|------|------|------|------|----------|
| **brave_search** | 🔍 | 搜索 | Brave Search 高质量搜索 | 通用 |
| **exa_search** | 🔎 | 搜索 | Exa AI 语义搜索 | 通用 |
| **browser_automation** | 🤖 | 自动化 | 浏览器自动操作 | 猫娘、战斗修女 |
| **twitter** | 🐦 | 社交 | Twitter 操作 | 大小姐 |
| **code_agent** | 💻 | 开发 | 代码分析与生成 | 战斗修女、默认 |
| **image_gen** | 🎨 | 创意 | 图像生成 | 猫娘 |
| **github_ai_trends** | 📊 | 开发 | GitHub AI 趋势 | 大小姐、默认 |
| **cron_scheduler** | ⏰ | 生产力 | 定时任务 | 通用 |
| **memory_manager** | 🧠 | 生产力 | 记忆管理 | 通用 |

## 架构设计

### 核心组件

```
personality/skills/
├── __init__.py          # 导出主要接口
├── base.py              # BaseSkill 基类和 SkillResult
├── registry.py          # SkillRegistry 技能注册表
└── builtin/             # 内置技能实现
    ├── search.py        # 搜索技能
    ├── browser.py       # 浏览器自动化
    ├── social.py        # 社交媒体
    ├── code.py          # 代码助手
    ├── creative.py      # 创意生成
    ├── github.py        # GitHub 趋势
    ├── scheduler.py     # 定时任务
    └── memory.py        # 记忆管理
```

### 技能基类

每个技能继承 `BaseSkill`，定义：
- `name`: 技能标识名
- `description`: 技能描述
- `icon`: 技能图标
- `category`: 技能分类
- `personality_templates`: 各性格的输出模板

```python
class MySkill(BaseSkill):
    name = "my_skill"
    description = "技能描述"
    icon = "🔧"
    category = "general"

    personality_templates = {
        "default": "结果：{result}",
        "nekomata_assistant": "浮浮酱帮你找到了：{result} ✿",
    }

    def execute(self, **kwargs) -> SkillResult:
        # 实现技能逻辑
        return SkillResult(success=True, content="结果")
```

## 为性格配置技能

在性格配置文件的 front matter 中添加 `skills`：

```yaml
---
name: nekomata_assistant
description: 猫娘助手
skills: ["brave_search", "browser_automation", "image_gen", "cron_scheduler", "memory_manager"]
---
```

### 推荐配置

**猫娘 (nekomata_assistant)** - 可爱、亲近
```yaml
skills: ["brave_search", "browser_automation", "image_gen", "cron_scheduler", "memory_manager"]
```

**大小姐 (ojousama_assistant)** - 傲娇、资讯
```yaml
skills: ["brave_search", "twitter", "github_ai_trends", "cron_scheduler"]
```

**战斗修女 (battle_sister_assistant)** - 严谨、效率
```yaml
skills: ["code_agent", "browser_automation", "cron_scheduler", "memory_manager"]
```

**慵懒猫 (lazy_cat_assistant)** - 懒散、随意
```yaml
skills: ["brave_search", "image_gen", "memory_manager"]
```

## 使用示例

### 代码中使用

```python
from personality.skills import get_skill_registry

# 获取注册表
registry = get_skill_registry()

# 列出所有技能
for skill in registry.list_skills():
    print(f"{skill.icon} {skill.name}")

# 执行技能（自动根据性格格式化）
result = registry.execute(
    "brave_search",
    personality="nekomata_assistant",
    query="Python 教程"
)
print(result.content)

# 获取技能实例自定义调用
skill = registry.get_instance("cron_scheduler")
result = skill.execute(action="create", time_str="08:00", task="起床")
```

### Function Calling 集成

```python
# 获取所有技能的 schema
schemas = registry.get_function_schemas()

# 传递给 LLM 进行 function calling
messages = [
    {"role": "system", "content": "你可以使用以下技能..."},
    {"role": "user", "content": "帮我搜索 Python 教程"}
]

# LLM 返回 function call
# {"name": "brave_search", "arguments": {"query": "Python 教程"}}

# 执行对应的技能
result = registry.execute("brave_search", personality="nekomata_assistant", **arguments)
```

## 扩展新技能

1. 在 `personality/skills/builtin/` 创建新文件
2. 继承 `BaseSkill` 并实现 `execute` 方法
3. 定义 `personality_templates` 为不同性格定制输出
4. 在 `registry.py` 的 `_load_builtin_skills` 中注册

示例：

```python
# personality/skills/builtin/weather.py
from ..base import BaseSkill, SkillResult

class WeatherSkill(BaseSkill):
    name = "weather"
    description = "查询天气"
    icon = "🌤"
    category = "search"

    personality_templates = {
        "default": "天气：{result}",
        "nekomata_assistant": "主人，天气情况：{result} 出门记得带伞喵～",
    }

    def execute(self, city: str, **kwargs) -> SkillResult:
        # 调用天气 API
        weather = fetch_weather(city)
        return SkillResult(success=True, content=weather)
```

## API 密钥配置

在 `.env` 文件中配置：

```bash
# 搜索
BRAVE_API_KEY=your_brave_api_key
EXA_API_KEY=your_exa_api_key

# 社交媒体
TWITTER_BEARER_TOKEN=your_twitter_token

# 图像生成
OPENAI_API_KEY=your_openai_key  # 用于 DALL-E

# GitHub
GITHUB_TOKEN=your_github_token
```

## 待实现功能

- [ ] 实际 API 集成（当前为 mock 数据）
- [ ] 技能执行权限控制
- [ ] 技能使用统计
- [ ] 动态技能加载（插件化）
- [ ] 技能组合（chain）

## 文件清单

| 文件 | 说明 |
|------|------|
| `src/personality/skills/__init__.py` | 模块导出 |
| `src/personality/skills/base.py` | 基类定义 |
| `src/personality/skills/registry.py` | 注册表管理 |
| `src/personality/skills/builtin/*.py` | 8个内置技能 |
| `src/personality/manager.py` | 更新支持 skills 配置 |
| `src/personality/personalities/*.md` | 性格配置文件（添加 skills） |
