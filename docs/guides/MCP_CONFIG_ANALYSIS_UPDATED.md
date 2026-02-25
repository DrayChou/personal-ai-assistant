# MCP 配置分析（已更新）

根据你提供的 `mcpServers` 配置，分析如下：

## 📋 配置概览

| 服务名 | 类型 | 命令 | 功能 | 状态 |
|--------|------|------|------|------|
| ✅ MiniMax | STDIO | uvx | **网页搜索** + 图片分析 | 已添加 |
| ✅ context7 | STDIO | npx | 文档查询与知识检索 | 已添加 |
| ✅ fetch | STDIO | uvx | 网页内容获取 | 已存在 |
| ✅ mcp-deepwiki | STDIO | npx | Wiki 知识查询 | 已添加 |
| ⚠️ memory | STDIO | npx | 知识图谱记忆 | 可选添加 |
| ✅ open-websearch | STDIO | npx | 多引擎网页搜索 | 已添加 |
| ✅ time | STDIO | npx | 时间查询与时区转换 | 已添加 |

## 🔍 MiniMax MCP 详解

### 功能说明

**minimax-coding-plan-mcp** 是一个专为开发者设计的 MCP 服务器，提供以下工具：

| 工具名 | 功能 | 说明 |
|--------|------|------|
| `web_search` | 网页搜索 | 执行网络搜索并返回结构化结果 |
| `understand_image` | 图片分析 | 基于文本提示分析图片内容 |

### 与 open-websearch 的区别

| 特性 | MiniMax Search | Open WebSearch |
|------|----------------|----------------|
| 搜索引擎 | MiniMax 自有 | DuckDuckGo/Bing/Brave |
| 图片分析 | ✅ 支持 | ❌ 不支持 |
| 需要 API Key | ✅ 是 | ❌ 否 |
| 搜索结果质量 | 优化中文 | 多引擎可选 |

### 建议
- **启用 MiniMax Search**：如果你需要图片分析功能，或更优质的中文搜索结果
- **启用 Open WebSearch**：如果你希望使用多引擎搜索，且不需要图片分析
- **两者都启用**：可以并存，AI 会根据需求自动选择

## 📝 已更新的配置

### `.env` 文件

```bash
# MiniMax MCP - 搜索和图片分析
# minimax-coding-plan-mcp 提供：web_search（网页搜索）、understand_image（图片分析）
MINIMAX_API_KEY=your_key_here
MINIMAX_API_HOST=https://api.minimaxi.com

# MiniMax 搜索 MCP - 网页搜索、图片分析
ENABLE_MCP_MINIMAX_SEARCH=true

# Open WebSearch MCP - 多引擎搜索
# 与 MiniMax 搜索 MCP 功能类似，可二选一启用
ENABLE_MCP_OPEN_WEBSEARCH=false
```

### 预设配置 (`src/tools/mcp_config_manager.py`)

```python
"minimax_search": {
    "name": "minimax_search",
    "source_type": "stdio",
    "command": "uvx",
    "args": ["minimax-coding-plan-mcp", "-y"],
    "description": "MiniMax 搜索 MCP - 网页搜索和图片分析",
    "requires_key": True,
}
```

## 🚀 快速启用

### 方法1：使用环境变量

```bash
# 启用 MiniMax 搜索 MCP
export ENABLE_MCP_MINIMAX_SEARCH=true
export MINIMAX_API_KEY="your_key_here"

# 禁用 Open WebSearch（避免重复）
export ENABLE_MCP_OPEN_WEBSEARCH=false

# 启动
python -m src.main
```

### 方法2：编辑 `.env` 文件

```bash
# 1. 编辑 .env
ENABLE_MCP_MINIMAX_SEARCH=true
ENABLE_MCP_OPEN_WEBSEARCH=false

# 2. 启动
python -m src.main
```

## 🔧 工具能力矩阵

| 功能需求 | MiniMax Search | Open WebSearch | 项目内置搜索 |
|----------|----------------|----------------|--------------|
| 网页搜索 | ✅ | ✅ | ✅ duckduckgo |
| 图片分析 | ✅ | ❌ | ❌ |
| 多引擎支持 | ❌ | ✅ | ❌ |
| 需要 API Key | ✅ | ❌ | ❌ |

## ⚠️ 安全提醒

**请立即重新生成 MiniMax API Key**：
1. 访问 https://www.minimaxi.com/user-center/basic-information/interface-key
2. 删除旧 Key，生成新 Key
3. 更新 `.env` 文件

## 📚 参考链接

- PyPI: https://pypi.org/project/minimax-coding-plan-mcp/
- MiniMax 平台: https://www.minimax.io/
- API 文档: https://platform.minimax.io/docs/coding-plan/intro
