# Gateway 架构设计文档

## 1. 概述

### 1.1 设计目标

实现一个轻量级的 WebSocket Gateway，为 Personal AI Assistant 提供：
- 多客户端并发接入
- 实时双向通信
- 流式输出支持
- 多通道统一接口

### 1.2 设计原则

参考 nanobot 的极简架构：
- **够用就好**: 只实现核心功能，避免过度设计
- **清晰可读**: 代码即文档，便于维护
- **易于扩展**: 抽象接口支持新通道

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         客户端层                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │   CLI    │ │ Telegram │ │ Discord  │ │  Feishu  │           │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘           │
│       │            │            │            │                  │
│       └────────────┴────────────┴────────────┘                  │
│                         │                                       │
│                         ▼                                       │
├─────────────────────────────────────────────────────────────────┤
│                      Gateway 层                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              WebSocket Server (ws://:8080)              │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │   │
│  │  │  Connection │  │ JSON-RPC    │  │   Auth      │     │   │
│  │  │   Manager   │  │  Protocol   │  │ Middleware  │     │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘     │   │
│  └─────────────────────────┬───────────────────────────────┘   │
│                            │                                    │
├────────────────────────────┼────────────────────────────────────┤
│                      核心层 │                                    │
│  ┌─────────────────────────▼───────────────────────────────┐   │
│  │                   Message Bus                            │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │   │
│  │  │  Inbound     │  │  Outbound    │  │  Internal    │  │   │
│  │  │  Messages    │  │  Messages    │  │  Events      │  │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  │   │
│  └─────────────────────────┬───────────────────────────────┘   │
│                            │                                    │
│  ┌─────────────────────────▼───────────────────────────────┐   │
│  │                   Agent Layer                            │   │
│  │         SupervisorAgent (Fast/Single/Multi)             │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 模块职责

| 模块 | 职责 | 对应文件 |
|------|------|----------|
| **Gateway Server** | WebSocket 连接管理、生命周期 | `gateway/server.py` |
| **JSON-RPC Protocol** | 消息格式解析、方法路由 | `gateway/protocol.py` |
| **Auth Middleware** | Token 认证、权限检查 | `gateway/auth.py` |
| **Message Bus** | 消息分发、解耦 | `bus/message_bus.py` |
| **Channel Manager** | 多通道生命周期管理 | `channels/manager.py` |
| **Session Store** | 会话持久化 | `chat/session_store.py` |

## 3. 核心数据模型

### 3.1 消息类型

```python
# 参考 nanobot/bus/events.py

@dataclass
class InboundMessage:
    """从通道接收的消息"""
    channel: str              # telegram, discord, cli
    sender_id: str            # 用户ID
    chat_id: str              # 聊天ID
    content: str              # 消息内容
    timestamp: datetime
    media: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

@dataclass
class OutboundMessage:
    """发送到通道的消息"""
    channel: str
    chat_id: str
    content: str
    reply_to: str | None = None
    media: list[str] = field(default_factory=list)
```

### 3.2 JSON-RPC 协议

```python
# 请求格式
{
    "jsonrpc": "2.0",
    "id": "req-uuid",
    "method": "chat.send",
    "params": {
        "text": "你好",
        "session_key": "telegram:user123:chat456"
    }
}

# 响应格式
{
    "jsonrpc": "2.0",
    "id": "req-uuid",
    "result": {
        "message_id": "msg-uuid",
        "text": "你好！我是AI助手...",
        "timestamp": "2026-02-24T10:00:00Z"
    }
}

# 流式事件格式
{
    "jsonrpc": "2.0",
    "method": "event",
    "params": {
        "type": "chat.delta",
        "delta": "你好",
        "message_id": "msg-uuid"
    }
}
```

### 3.3 Session 模型

```python
# 参考 claw0 session_key 规范

@dataclass
class Session:
    """用户会话"""
    session_key: str          # agent:main:telegram:user123
    agent_id: str             # main
    channel: str              # telegram
    peer_id: str              # user123
    messages: list[dict]      # 历史消息
    created_at: datetime
    updated_at: datetime
```

## 4. 接口设计

### 4.1 Gateway API 方法

| 方法 | 功能 | 认证 |
|------|------|------|
| `chat.send` | 发送消息 | ✅ |
| `chat.send_stream` | 流式发送 | ✅ |
| `chat.history` | 获取历史 | ✅ |
| `session.list` | 列会话 | ✅ |
| `session.delete` | 删会话 | ✅ |
| `health` | 健康检查 | ❌ |

### 4.2 Channel 抽象接口

```python
# 参考 nanobot/channels/base.py

class BaseChannel(ABC):
    """通道抽象基类"""

    name: str = "base"

    @abstractmethod
    async def start(self) -> None:
        """启动通道，开始监听消息"""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """停止通道，清理资源"""
        pass

    @abstractmethod
    async def send(self, msg: OutboundMessage) -> None:
        """发送消息"""
        pass

    def is_allowed(self, sender_id: str) -> bool:
        """检查发送者是否在白名单"""
        allow_list = getattr(self.config, "allow_from", [])
        if not allow_list:
            return True
        return str(sender_id) in allow_list
```

## 5. 关键流程

### 5.1 消息处理流程

```
┌─────────────┐
│  用户发送消息 │
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌─────────────┐
│   Channel   │────▶│  MessageBus │
│  (Telegram) │     │ publish()   │
└─────────────┘     └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  AgentLoop  │
                    │   process   │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  Supervisor │
                    │    Agent    │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐     ┌─────────────┐
                    │  MessageBus │────▶│   Channel   │
                    │   publish   │     │   send()    │
                    └─────────────┘     └─────────────┘
                                                │
                                                ▼
                                         ┌─────────────┐
                                         │  用户收到回复 │
                                         └─────────────┘
```

### 5.2 流式输出流程

```
Agent 生成
    │
    ├── chunk 1 ──▶ Gateway ──▶ 客户端
    │
    ├── chunk 2 ──▶ Gateway ──▶ 客户端
    │
    ├── chunk 3 ──▶ Gateway ──▶ 客户端
    │
    └── done ─────▶ Gateway ──▶ 客户端 (end marker)
```

## 6. 技术选型

| 组件 | 选型 | 理由 |
|------|------|------|
| WebSocket | `websockets` | Python 原生，异步友好 |
| HTTP | `aiohttp` | 与 websockets 配合好 |
| 消息格式 | JSON-RPC 2.0 | 标准协议，易于调试 |
| 认证 | Bearer Token | 简单有效 |
| 配置 | Pydantic | 类型安全，验证完善 |

## 7. 目录结构

```
src/
├── gateway/                    # NEW
│   ├── __init__.py
│   ├── server.py              # WebSocket 服务器
│   ├── protocol.py            # JSON-RPC 协议
│   ├── auth.py                # Token 认证
│   └── handlers.py            # 方法处理器
│
├── channels/                   # NEW
│   ├── __init__.py
│   ├── base.py                # Channel 抽象
│   ├── manager.py             # 通道管理器
│   ├── telegram.py            # Telegram 实现
│   ├── discord.py             # Discord 实现
│   └── feishu.py              # Feishu 实现
│
├── bus/                        # NEW
│   ├── __init__.py
│   ├── events.py              # 消息类型定义
│   └── message_bus.py         # 消息总线
│
├── chat/
│   ├── session_store.py       # NEW: JSONL 存储
│   └── ...
│
└── main.py                     # MODIFIED: 启动 Gateway
```

## 8. 性能考虑

### 8.1 连接管理

- 使用 `websockets` 库的连接池
- 心跳保活 (30秒间隔)
- 最大连接数限制 (默认 1000)

### 8.2 消息处理

- 异步处理，不阻塞
- 使用 `asyncio.Queue` 缓冲
- 背压控制，防止内存溢出

### 8.3 扩展性

- 水平扩展: 多实例 + Redis 共享 Session
- 垂直扩展: 异步优化，充分利用 CPU

## 9. 安全考虑

### 9.1 认证授权

- Bearer Token 验证
- Token 定期轮换
- IP 白名单 (可选)

### 9.2 输入验证

- JSON Schema 验证
- 消息大小限制 (1MB)
- 频率限制 (每分钟 100 条)

### 9.3 传输安全

- WebSocket over TLS (WSS)
- 敏感字段加密

## 10. 参考实现

- **nanobot**: `nanobot/channels/base.py`, `nanobot/agent/loop.py`
- **claw0**: `s05_gateway_server.py`, `s06_routing.py`
- **openclaw**: Gateway WebSocket control plane

---

**版本**: v1.0
**作者**: AI Assistant
**日期**: 2026-02-24
