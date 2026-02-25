# MCP 配置导入指南

## 📋 分析结果

你的 Claude Desktop MCP 配置已成功分析并整合到项目中。

### 可整合的服务（7个）

| 服务名 | 命令 | 需要 Key | 建议 |
|--------|------|----------|------|
| ✅ MiniMax | uvx minimax-coding-plan-mcp | 是 | 强烈推荐 - 代码生成 |
| ✅ context7 | npx @upstash/context7-mcp | 否 | 推荐 - 文档查询 |
| ✅ fetch | uvx mcp-server-fetch | 否 | 强烈推荐 - 网页获取 |
| ✅ mcp-deepwiki | npx mcp-deepwiki | 否 | 推荐 - Wiki 知识 |
| ⚠️ memory | npx @modelcontextprotocol/server-memory | 否 | 可选 - 与项目记忆冲突 |
| ✅ open-websearch | npx open-websearch | 否 | 推荐 - 多引擎搜索 |
| ✅ time | npx @modelcontextprotocol/server-time | 否 | 推荐 - 时间服务 |

## 🔧 已添加的功能

### 1. 新增 MCP 预设（src/tools/mcp_config_manager.py）

```python
# STDIO 服务（uvx）
- minimax_stdio: MiniMax Coding Plan 模式
- fetch: 网页内容获取

# STDIO 服务（npx）
- context7: Upstash Context7 文档查询
- deepwiki: DeepWiki 知识查询
- memory_mcp: MCP 官方记忆服务
- open_websearch: 多引擎网页搜索
- time: 时间查询与时区转换
```

### 2. 配置导入功能

支持从以下格式导入：
- ✅ Claude Desktop `mcpServers` JSON
- ✅ 标准 MCP 配置 JSON/YAML
- ✅ 远程 URL 配置

## 📝 需要添加到 .env 的配置

```bash
# ===== MCP 在线服务 =====
MINIMAX_API_KEY=your_key_here
MINIMAX_API_HOST=https://api.minimaxi.com

# ===== MCP STDIO 服务开关 =====
ENABLE_MCP_FETCH=true
ENABLE_MCP_CONTEXT7=true
ENABLE_MCP_DEEPWIKI=true
ENABLE_MCP_MEMORY_SERVER=false  # 建议禁用
ENABLE_MCP_OPEN_WEBSEARCH=true
ENABLE_MCP_TIME=true

# Open WebSearch 配置
MCP_SEARCH_DEFAULT_ENGINE=duckduckgo
MCP_SEARCH_ALLOWED_ENGINES=duckduckgo,bing,brave
```

## 🚀 快速开始

### 方法1：使用环境变量（推荐）

```bash
# 1. 复制模板
cp .env.example .env

# 2. 编辑 .env，填入你的 MiniMax API Key
# MINIMAX_API_KEY=your_key_here

# 3. 启用需要的 MCP 服务
# 修改 ENABLE_MCP_* 开关

# 4. 启动
python -m src.main
```

### 方法2：直接导入 Claude Desktop 配置

```python
from src.tools import MCPConfigManager

manager = MCPConfigManager()

# 从 Claude Desktop 配置导入
configs = manager.load_from_claude_desktop_config()

# 或从 JSON 字符串导入
json_content = '''{"mcpServers": {...}}'''
configs = manager.import_from_json(json_content)
```

### 方法3：使用命令行工具

```bash
# 列出所有预设
python -m src.tools.mcp_manager_cli presets

# 从环境变量发现
python -m src.tools.mcp_manager_cli discover

# 查看已配置
python -m src.tools.mcp_manager_cli list
```

## 🧪 测试配置

```bash
# 运行导入示例
python examples/import_claude_mcp_config.py

# 运行完整演示
python examples/mcp_demo.py
```

## 🔒 安全提醒

你的 MiniMax API Key 已在配置中暴露。**请立即**：

1. 访问 https://www.minimaxi.com/user-center/basic-information/interface-key
2. 删除旧 Key，生成新 Key
3. 更新 .env 文件
4. 确保 .env 在 .gitignore 中

## 📊 服务对比建议

| 功能 | 项目内置 | MCP 替代 | 建议 |
|------|----------|----------|------|
| 搜索 | duckduckgo-search | open-websearch | 两者可并存 |
| 天气 | ❌ | 高德地图 | 启用高德 MCP |
| 记忆 | 三层架构 | memory_mcp | 只用内置 |
| 代码生成 | LLM | minimax_stdio | 两者可并存 |
| 文档查询 | ❌ | context7 | 启用 |
| Wiki | ❌ | deepwiki | 启用 |
| 网页获取 | ❌ | fetch | 启用 |
| 时间 | ❌ | time | 启用 |

## 📁 相关文件

- `.env` - 你的配置（已更新）
- `.env.example` - 配置模板
- `docs/MCP_CONFIG_ANALYSIS.md` - 详细分析报告
- `examples/import_claude_mcp_config.py` - 导入示例
- `src/tools/mcp_config_manager.py` - 配置管理器

## ❓ 常见问题

**Q: STDIO 服务需要什么环境？**
```bash
# 安装 uv（包含 uvx）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 确保 Node.js 已安装（包含 npx）
node --version  # v18+
```

**Q: 如何禁用某个 MCP 服务？**
```bash
# 在 .env 中设置
ENABLE_MCP_MEMORY_SERVER=false
```

**Q: 可以同时使用 minimax (HTTP) 和 minimax_stdio (STDIO) 吗？**
- 可以，但不推荐，会重复
- 建议只启用一个：
  - HTTP 模式：更稳定，需要网络
  - STDIO 模式：本地运行，需要 uvx

**Q: MCP 服务启动失败？**
- 检查命令可用性：`which uvx` / `which npx`
- 检查 API Key 是否设置
- 查看日志：`tail -f data/app.log`

## ✅ 完成检查清单

- [x] 分析 7 个 MCP 服务
- [x] 添加 6 个新预设到项目
- [x] 更新 .env 配置
- [x] 创建配置导入功能
- [x] 测试导入流程
- [ ] 重新生成 MiniMax API Key（需要你完成）
- [ ] 安装 uvx / 确保 npx 可用
- [ ] 启动项目测试
