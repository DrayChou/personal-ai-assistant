# MCP 工具与 AI 意图识别集成总结

## 已完成功能

### 1. AI 意图分类器 (`src/chat/ai_intent_classifier.py`)
- 使用 LLM 进行语义级意图识别
- 支持多意图检测和置信度校准
- 自动判断是否需要调用外部工具
- 建议适用的工具列表
- 失败后自动回退到规则分类

### 2. MCP 配置管理器 (`src/tools/mcp_config_manager.py`)
- 从环境变量自动发现 MCP 服务
- 从 URL 加载远程 MCP 配置
- 从本地 YAML/JSON 文件加载配置
- 支持多种传输协议：HTTP SSE、HTTP REST、STDIO、WebSocket
- 预设模板：高德地图、百度地图、MiniMax、GLM、GitHub、fetch

### 3. MCP 客户端 (`src/tools/mcp_client.py`)
- 支持 HTTP 和 SSE 传输协议
- 预设工具定义（天气、地理编码、路径规划等）
- 从配置管理器批量加载服务
- 自动从环境变量配置

### 4. 工具执行器 (`src/tools/tool_executor.py`)
- 统一执行 MCP 工具和注册函数
- 异步批量执行支持
- 执行历史记录
- 结果格式化为 LLM 可理解格式

### 5. 函数注册表 (`src/tools/function_registry.py`)
- 装饰器方式注册 Python 函数为工具
- 自动从类型注解生成参数 Schema
- 支持 OpenAI 和 Anthropic 格式
- 生命周期钩子（before/after/error）

### 6. 配置集成 (`src/config/settings.py`)
- MCP_ENABLED: 启用/禁用 MCP
- AMAP_API_KEY: 高德地图
- BAIDU_MAP_API_KEY: 百度地图
- MINIMAX_API_KEY: MiniMax
- GLM_API_KEY: GLM
- USE_AI_INTENT: 使用 AI 意图分类
- AUTO_TOOL_SELECT: 自动工具选择

### 7. 主程序集成 (`src/main.py`)
- 自动初始化 MCP 配置管理器
- 从环境变量自动发现服务
- 创建 ToolExecutor 并加载工具
- 根据配置选择 AI 或规则意图分类器

### 8. 动作路由器更新 (`src/chat/action_router.py`)
- 支持异步路由
- 天气查询优先使用 MCP 工具
- 集成 ToolExecutor 进行工具调用

### 9. 命令行管理工具 (`src/tools/mcp_manager_cli.py`)
```bash
# 列出配置
python -m src.tools.mcp_manager_cli list

# 发现服务
python -m src.tools.mcp_manager_cli discover

# 添加预设
python -m src.tools.mcp_manager_cli add amap --preset --api-key KEY

# 查看预设
python -m src.tools.mcp_manager_cli presets
```

### 10. 文档和示例
- `.env.example`: 完整配置示例
- `docs/MCP_TOOLS_GUIDE.md`: 使用指南
- `data/mcp_configs/mcp_config_example.yaml`: 配置文件示例
- `examples/mcp_demo.py`: 功能演示脚本

## 快速开始

### 1. 配置环境变量
```bash
# 编辑 .env 文件
MCP_ENABLED=true
USE_AI_INTENT=true
AMAP_API_KEY=your_key_here
```

### 2. 运行演示
```bash
python examples/mcp_demo.py
```

### 3. 启动助手
```bash
python -m src.main
```

## 支持的 MCP 服务

| 服务 | 协议 | 功能 |
|------|------|------|
| 高德地图 | HTTP SSE | 地理编码、天气、路径规划 |
| 百度地图 | HTTP SSE | 地图服务 |
| MiniMax | HTTP REST | 文本生成、语音合成 |
| GLM | HTTP REST | 代码生成、对话 |
| fetch | STDIO | 网页内容获取 |
| filesystem | STDIO | 文件系统访问 |
| sqlite | STDIO | SQLite 数据库 |

## 架构图

```
用户输入
    ↓
AIIntentClassifier (LLM 语义分析)
    ↓
Intent (意图 + 是否需要工具 + 建议工具)
    ↓
ActionRouter
    ↓
ToolExecutor
    ↓
MCPClient / FunctionRegistry
    ↓
外部 MCP 服务 / 本地函数
```

## 下一步建议

1. **获取 API Key**: 申请高德地图等服务的使用权限
2. **配置环境变量**: 将 API Key 添加到 `.env` 文件
3. **测试功能**: 运行演示脚本验证配置
4. **扩展工具**: 根据需要添加更多 MCP 服务或自定义函数
