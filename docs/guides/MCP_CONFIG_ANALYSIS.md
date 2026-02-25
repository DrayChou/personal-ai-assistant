# MCP 配置分析报告

根据你提供的 `mcpServers` 配置，分析如下：

## 📋 配置概览

| 服务名 | 类型 | 命令 | 状态 |
|--------|------|------|------|
| MiniMax | STDIO | uvx | ✅ 已添加 |
| context7 | STDIO | npx | ✅ 已添加 |
| fetch | STDIO | uvx | ✅ 已存在 |
| mcp-deepwiki | STDIO | npx | ✅ 已添加 |
| memory | STDIO | npx | ⚠️ 可选添加 |
| open-websearch | STDIO | npx | ✅ 已添加 |
| time | STDIO | npx | ✅ 已添加 |

## 🔧 已整合的 MCP 服务

### 1. MiniMax (STDIO 模式)
```yaml
命令: uvx minimax-coding-plan-mcp -y
环境变量:
  - MINIMAX_API_KEY (已配置)
  - MINIMAX_API_HOST (可选，默认 https://api.minimaxi.com)
```
- 功能：Coding Plan 模式，支持代码规划和生成
- 已添加到 `minimax_stdio` 预设
- 与现有的 HTTP 模式 `minimax` 并存

### 2. Context7 (npx)
```yaml
命令: npx -y @upstash/context7-mcp
```
- 功能：文档查询与知识检索
- 无需 API Key
- 自动检测 npx 可用性

### 3. Fetch (uvx)
```yaml
命令: uvx mcp-server-fetch
```
- 功能：获取任意 URL 内容
- 已存在预设中
- 无需 API Key

### 4. DeepWiki (npx)
```yaml
命令: npx -y mcp-deepwiki@latest
```
- 功能：Wiki 知识查询
- 无需 API Key

### 5. Open WebSearch (npx)
```yaml
命令: npx -y open-websearch@latest
环境变量:
  - DEFAULT_SEARCH_ENGINE (默认: duckduckgo)
  - ALLOWED_SEARCH_ENGINES (默认: duckduckgo,bing,brave)
```
- 功能：多引擎网页搜索
- 可作为项目内置搜索的备选
- 环境变量可配置搜索引擎

### 6. Time (npx)
```yaml
命令: npx -y @modelcontextprotocol/server-time
```
- 功能：时间查询与时区转换
- 无需 API Key

### 7. Memory Server (npx) - 可选
```yaml
命令: npx -y @modelcontextprotocol/server-memory
```
- 功能：MCP 官方知识图谱记忆
- ⚠️ **注意**：与项目自有的三层记忆系统独立
- 建议：禁用（设为 false），避免与项目记忆系统冲突

## 📝 添加到 .env 的配置

```bash
# ===== MCP 在线服务 =====
MINIMAX_API_KEY=your_key_here
MINIMAX_API_HOST=https://api.minimaxi.com

# ===== MCP STDIO 服务开关 =====
# 以下服务会自动检测命令（uvx/npx）是否可用
ENABLE_MCP_FETCH=true
ENABLE_MCP_CONTEXT7=true
ENABLE_MCP_DEEPWIKI=true
ENABLE_MCP_MEMORY_SERVER=false  # 建议禁用，与项目记忆系统冲突
ENABLE_MCP_OPEN_WEBSEARCH=true
ENABLE_MCP_TIME=true

# Open WebSearch 搜索引擎配置
MCP_SEARCH_DEFAULT_ENGINE=duckduckgo
MCP_SEARCH_ALLOWED_ENGINES=duckduckgo,bing,brave
```

## 🚀 使用建议

### 高优先级（强烈推荐启用）

1. **MiniMax STDIO** - 如果你的项目涉及代码生成
2. **Fetch** - 获取网页内容，扩展知识来源
3. **Open WebSearch** - 实时搜索，获取最新信息
4. **Time** - 时间相关查询

### 中优先级（根据需求启用）

5. **Context7** - 如果你需要查询技术文档
6. **DeepWiki** - 如果你需要 Wiki 知识

### 低优先级（谨慎启用）

7. **Memory Server** - ⚠️ 与项目自有记忆系统可能冲突
   - 项目已有：工作记忆 + 短期记忆 + 长期记忆三层架构
   - MCP Memory：独立的知识图谱
   - 建议：除非有特殊需求，否则保持禁用

## 🔒 安全提醒

你的 MiniMax API Key 已在配置文件中暴露。建议：

1. **立即重新生成 API Key**
   - 访问：https://www.minimaxi.com/user-center/basic-information/interface-key
   - 删除旧 Key，生成新 Key

2. **使用环境变量而非硬编码**
   ```bash
   # 安全的做法
   export MINIMAX_API_KEY="your_new_key"
   python -m src.main
   ```

3. **添加 .env 到 .gitignore**
   ```bash
   echo ".env" >> .gitignore
   ```

## 🛠️ 快速启用所有 MCP

```bash
# 1. 启用 MCP
export MCP_ENABLED=true

# 2. 设置 MiniMax Key（从环境变量读取）
export MINIMAX_API_KEY="your_new_key"

# 3. 启动助手
python -m src.main
```

或在 `.env` 文件中设置后：
```bash
python -m src.main
```

## 📊 工具能力对比

| 工具 | 项目内置 | MCP 替代 | 建议 |
|------|----------|----------|------|
| 搜索 | ✅ duckduckgo-search | ✅ open-websearch | 可并存，MCP 支持多引擎 |
| 天气 | ❌ | ✅ 高德地图 | 启用高德 MCP |
| 记忆 | ✅ 三层架构 | ✅ MCP Memory | 只用项目内置 |
| 时间 | ❌ | ✅ Time MCP | 启用 |
| 网页获取 | ❌ | ✅ Fetch | 启用 |
| 代码生成 | ✅ LLM | ✅ MiniMax | 可并存 |

## ❓ 常见问题

**Q: STDIO 模式需要安装什么？**
```bash
# uvx (用于 MiniMax, fetch)
curl -LsSf https://astral.sh/uv/install.sh | sh

# npx (用于 context7, deepwiki, memory, open-websearch, time)
# Node.js 自带，确保已安装 Node.js
node --version  # v18+
```

**Q: 如何验证 MCP 服务是否正常工作？**
```bash
python -m src.tools.mcp_manager_cli list
```

**Q: 某个 STDIO 服务启动失败怎么办？**
- 检查命令是否可用：`which uvx` 或 `which npx`
- 检查对应的环境变量是否设置
- 查看日志：`tail -f data/app.log`

**Q: 可以同时使用 HTTP 和 STDIO 模式的 MiniMax 吗？**
- 可以，它们有不同的预设名：`minimax` (HTTP) 和 `minimax_stdio` (STDIO)
- 建议只启用一个，避免重复
