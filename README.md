# Personal AI Assistant

> 替代 OpenClaw 的个人智能助理
> 基于三层记忆架构，全平台支持，本地优先

---

## 核心特性

### 🛡️ Fallback 机制全覆盖

```
┌─────────────────────────────────────────────────────────────┐
│                     高可用架构                               │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Memory Fallback                                            │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  主存储: SQLite-Vec (向量搜索)                        │ │
│  │  备存储: 文件系统 (关键词搜索)                        │ │
│  │  切换: 自动故障检测 + 无缝切换                       │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                              │
│  LLM Provider Fallback                                      │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  主 LLM: OpenAI / MiniMax / Anthropic                 │ │
│  │  备 LLM: Ollama (本地模型)                           │ │
│  │  策略: FAIL_FAST / FALLBACK_ONCE / ALWAYS_FALLBACK   │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                              │
│  MCP Manager Fallback                                       │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  统一管理所有 MCP 服务器连接                          │ │
│  │  支持配置文件加载 + 预设服务器                        │ │
│  │  自动工具发现 + Schema 转换                          │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 🧠 三层记忆架构

```
┌─────────────────────────────────────────────────────────────┐
│                     记忆系统架构                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Layer 1: 工作记忆 (Working Memory)                          │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  容量: 2000 tokens                                    │ │
│  │  包含: 身份信息 + 当前上下文 + 关键事实                 │ │
│  │  策略: LRU 淘汰，高优先级保留                          │ │
│  └───────────────────────────────────────────────────────┘ │
│                              ↑                               │
│  Layer 2: 长期记忆 (Long-Term Memory)                        │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  存储: SQLite-Vec / SQLite                            │ │
│  │  类型: Facts (置信度0.9+) / Beliefs (0.3-0.8)          │ │
│  │  检索: 语义相似度 + 关键词 + 时间衰减                   │ │
│  └───────────────────────────────────────────────────────┘ │
│                              ↑                               │
│  Layer 3: 原始事件流 (Raw Events)                            │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  格式: JSONL (人类可读)                                │ │
│  │  备份: 自动导出，版本控制友好                           │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 🔧 技术选型

| 组件 | 方案 | 理由 |
|------|------|------|
| **向量存储** | SQLite-Vec | 全平台、单文件、零依赖 |
| **嵌入模型** | Ollama (本地) | 零API成本、隐私优先 |
| **备选嵌入** | OpenAI API | 高质量、远程备选 |
| **存储格式** | JSONL | 人类可读、版本友好 |

---

## 快速开始

### 1. 安装依赖

```bash
# 基础依赖
pip install sqlite-vec numpy

# 可选：Ollama 本地嵌入
# 1. 安装 Ollama: https://ollama.com
# 2. 拉取嵌入模型: ollama pull nomic-embed-text
```

### 2. 运行助理

```bash
python src/main.py
```

### 3. 交互命令

```
🤖 Personal AI Assistant
输入 'exit' 退出，'stats' 查看统计，'consolidate' 手动整合记忆
--------------------------------------------------

👤 You: 你好，我喜欢Python编程

🤖 Assistant: (无相关记忆)

👤 You: stats

📊 统计信息:
  记忆总数: 2
  新增记忆: 2
  检索次数: 0

👤 You: consolidate

🔄 正在整合记忆...
✅ 整合完成:
  收集: 2
  提取事实: 1
  创建摘要: 1

👤 You: exit
👋 再见!
```

---

## 项目结构

```
personal-ai-assistant/
├── src/
│   ├── memory/              # 记忆系统核心
│   │   ├── __init__.py
│   │   ├── types.py         # 类型定义
│   │   ├── working_memory.py    # 工作记忆 (Token 感知压缩)
│   │   ├── long_term_memory.py  # 长期记忆
│   │   ├── fallback_client.py   # Fallback 客户端
│   │   ├── retrieval.py     # 检索Pipeline
│   │   ├── consolidation.py # 记忆整合
│   │   ├── memory_system.py # 主类 (带 Fallback)
│   │   └── embeddings.py    # 嵌入生成
│   ├── agent/               # Agent 核心
│   │   └── tools/
│   │       ├── decorators.py    # @tool() 装饰器
│   │       └── ...
│   ├── channels/            # 多平台适配器
│   │   ├── __init__.py
│   │   ├── base.py          # ChannelAdapter 基类
│   │   └── console.py       # 控制台适配器
│   ├── chat/
│   │   ├── fallback_llm.py  # LLM Provider Fallback
│   │   └── ...
│   ├── tools/
│   │   ├── mcp_manager.py   # 统一 MCP 管理器
│   │   └── ...
│   ├── config/              # 配置管理
│   │   └── settings.py
│   ├── main.py              # 入口
│   └── __init__.py
├── data/                    # 数据目录
│   ├── memories/            # 记忆存储
│   │   └── long_term.db     # SQLite数据库
│   └── app.log              # 日志
├── config/                  # 配置文件
│   └── embedding_config.json
├── tests/                   # 测试 (205+ 测试用例)
├── docs/                    # 文档
│   └── OPTIMIZATION_PLAN.md # 优化计划
└── README.md
```

---

## 与 OpenClaw 对比

| 特性 | OpenClaw | Personal AI Assistant |
|------|----------|----------------------|
| **记忆架构** | 扁平、无差别 | 三层分层架构 |
| **遗忘机制** | ❌ 无 | ✅ 自动衰减 |
| **记忆整合** | ❌ 无 | ✅ 自动Consolidation |
| **本地嵌入** | ⚠️ 依赖外部 | ✅ Ollama本地 |
| **向量存储** | QMD | SQLite-Vec (全平台) |
| **数据迁移** | 复杂 | ✅ JSONL导出 |
| **隐私控制** | 中等 | ✅ 本地优先 |

---

## 环境变量

```bash
# Ollama 配置
export OLLAMA_BASE_URL=http://localhost:11434

# OpenAI 配置（可选）
export OPENAI_API_KEY=sk-xxx

# 日志级别
export LOG_LEVEL=INFO
```

---

## 开发路线图

- [x] 三层记忆架构
- [x] SQLite-Vec 存储
- [x] Ollama 嵌入支持
- [x] OpenAI API 备选
- [x] 记忆整合 (Consolidation)
- [x] 任务管理系统
- [x] 定时调度系统
- [x] LLM 集成 (OpenAI/Ollama)
- [x] 对话上下文管理
- [ ] TUI/GUI 界面
- [ ] MCP 协议支持
- [ ] 记忆导入/导出

---

## 参考

- [SimpleMem](https://github.com/aiming-lab/SimpleMem) - 高效终身记忆
- [sqlite-vec](https://github.com/asg017/sqlite-vec) - SQLite 向量扩展
- [OpenClaw](https://openclaw.ai) - 原 inspiration

---

**版本**: 0.1.0
**协议**: MIT
