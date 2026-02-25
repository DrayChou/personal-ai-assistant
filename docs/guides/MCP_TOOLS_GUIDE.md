# MCP 工具集成指南

本文档介绍如何在 Personal AI Assistant 中配置和使用 MCP (Model Context Protocol) 工具。

## 什么是 MCP?

MCP (Model Context Protocol) 是 Anthropic 提出的开放协议，用于标准化 LLM 与外部工具的通信。它被称为 "AI 的 USB-C 接口"。

## 支持的 MCP 服务

### 预设服务

| 服务 | 类型 | 功能 | 申请地址 |
|------|------|------|----------|
| 高德地图 | HTTP SSE | 地理编码、天气、路径规划 | https://console.amap.com/ |
| 百度地图 | HTTP SSE | 地图服务、位置服务 | https://lbsyun.baidu.com/ |
| MiniMax | HTTP REST | 文本生成、语音合成 | https://www.minimaxi.com/ |
| GLM | HTTP REST | 代码生成、对话 | https://open.bigmodel.cn/ |

### 本地 MCP 服务 (STDIO 模式)

| 服务 | 安装命令 | 功能 |
|------|----------|------|
| fetch | `uvx mcp-server-fetch` | 网页内容获取 |
| filesystem | `npx @modelcontextprotocol/server-filesystem` | 文件系统访问 |
| sqlite | `uvx mcp-server-sqlite` | SQLite 数据库 |

## 配置方法

### 方法一：环境变量（推荐）

在 `.env` 文件中添加：

```env
# 启用 MCP
MCP_ENABLED=true

# 配置各个服务
AMAP_API_KEY=your_amap_key_here
MINIMAX_API_KEY=your_minimax_key_here
GLM_API_KEY=your_glm_key_here
```

启动时会自动从环境变量加载配置。

### 方法二：配置文件

创建 `data/mcp_configs/mcp_config.yaml`：

```yaml
- name: amap
  source_type: http_sse
  endpoint: https://mcp.amap.com/sse
  api_key: ${AMAP_API_KEY}
  description: 高德地图 MCP
  auto_discover: true

- name: fetch
  source_type: stdio
  command: uvx
  args: [mcp-server-fetch]
  enabled: true
```

### 方法三：命令行工具

```bash
# 查看可用预设
python -m src.tools.mcp_manager_cli presets

# 从环境变量发现服务
python -m src.tools.mcp_manager_cli discover

# 添加高德地图 MCP
python -m src.tools.mcp_manager_cli add amap --preset --api-key YOUR_KEY

# 添加自定义 HTTP MCP
python -m src.tools.mcp_manager_cli add myapi --custom --endpoint https://api.example.com/mcp

# 列出所有配置
python -m src.tools.mcp_manager_cli list
```

## 使用 MCP 工具

配置完成后，AI 助手会自动根据用户意图调用相应的 MCP 工具。

### 示例交互

**天气查询:**
```
👤 你: 北京天气怎么样？
🤖 助手: 正在查询北京天气...
      北京今天晴，温度 25°C，空气质量良好。
```

**路径规划:**
```
👤 你: 从北京南站到天安门怎么走？
🤖 助手: 正在规划路线...
      推荐路线：地铁4号线 → 地铁1号线
      预计时间：30分钟
```

## 支持的传输协议

| 协议 | 说明 | 适用场景 |
|------|------|----------|
| HTTP SSE | Server-Sent Events，流式通信 | 在线服务如高德地图 |
| HTTP REST | 标准 HTTP API | MiniMax、GLM 等 |
| STDIO | 标准输入输出 | 本地进程如 uvx/npx |
| WebSocket | 双向流通信 | 实时性要求高的场景 |

## 自定义 MCP 服务

### HTTP MCP 服务

```python
from src.tools import MCPConfigManager

manager = MCPConfigManager()
manager.add_custom_http(
    name="my_weather_api",
    endpoint="https://api.weather.com/v1",
    api_key="your_api_key",
    use_sse=False
)
```

### STDIO MCP 服务

```python
manager.add_custom_stdio(
    name="sqlite",
    command="uvx",
    args=["mcp-server-sqlite", "--db-path", "./data.db"]
)
```

## 从 URL 加载配置

```python
manager.load_from_url("https://example.com/mcp/config.json", name="custom_service")
```

## 故障排除

### MCP 服务未启用

检查 `.env` 文件：
```env
MCP_ENABLED=true
```

### API Key 无效

确认环境变量正确设置：
```bash
export AMAP_API_KEY=your_key_here
```

### STDIO 服务无法启动

确保已安装相应工具：
```bash
# 安装 uv (用于 uvx)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装 Node.js (用于 npx)
# https://nodejs.org/
```

## 更多资源

- [MCP 官方文档](https://modelcontextprotocol.io/)
- [MCP 服务市场](https://mcp.aibase.com/)
- [Anthropic MCP 介绍](https://www.anthropic.com/news/model-context-protocol)
