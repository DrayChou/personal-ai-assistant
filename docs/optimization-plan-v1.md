# Personal AI Assistant 优化方案 v1.0

## 执行摘要

基于与 claw0/OpenClaw 架构的深入对比分析，当前系统在**智能能力**（记忆、Agent、意图识别）方面已超越 claw0，但在**基础设施**（Gateway、消息队列、多用户支持）方面存在明显短板。本方案旨在补齐这些短板，打造一个生产级的个人 AI 助手。

**当前状态评分：**
- 智能能力: ⭐⭐⭐⭐⭐ (5/5)
- 调度能力: ⭐⭐⭐⭐⭐ (5/5)
- 工具生态: ⭐⭐⭐⭐⭐ (5/5)
- 基础设施: ⭐⭐☆☆☆ (2/5)
- 可靠性: ⭐⭐☆☆☆ (2/5)
- 多用户支持: ⭐☆☆☆☆ (1/5)

**目标状态：**
- 基础设施: ⭐⭐⭐⭐⭐ (5/5)
- 可靠性: ⭐⭐⭐⭐⭐ (5/5)

---

## 第一部分：现状诊断

### 1.1 当前系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        当前系统架构                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │  Personality │    │   Memory     │    │    Task      │       │
│  │   Manager    │    │   System     │    │   Manager    │       │
│  │  (SOUL.md)   │    │ (L0/L1/L2)   │    │   (JSONL)    │       │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘       │
│         │                   │                   │                │
│         └───────────────────┼───────────────────┘                │
│                             ▼                                    │
│                    ┌─────────────────┐                          │
│                    │  SupervisorAgent │                         │
│                    │ (Fast/Single/Multi)│                       │
│                    └────────┬────────┘                          │
│                             │                                    │
│         ┌───────────────────┼───────────────────┐                │
│         ▼                   ▼                   ▼                │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │   Intent     │    │   Hybrid     │    │    MCP       │       │
│  │  Classifier  │    │  Scheduler   │    │    Tools     │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
│                                                                  │
│  接口层: CLI only (stdin/stdout)                                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 核心问题清单

| 编号 | 问题 | 严重程度 | 影响范围 |
|------|------|---------|----------|
| P0-1 | **无 Gateway Server** | 🔴 严重 | 无法远程访问、无 API 接口 |
| P0-2 | **无 Delivery Queue** | 🔴 严重 | 消息可能丢失、无可靠性保证 |
| P0-3 | **Session 不持久化** | 🔴 严重 | 重启后对话历史丢失 |
| P1-1 | **Heartbeat 不完整** | 🟡 中等 | 缺乏主动行为、无互斥机制 |
| P1-2 | **无消息路由** | 🟡 中等 | 单用户限制、无法隔离 |
| P2-1 | **仅 CLI 通道** | 🟢 低 | 使用场景受限 |

### 1.3 与 claw0/OpenClaw 差距分析

```
                    claw0              当前系统              差距
                    ─────              ──────────            ────
Gateway Server      ✅ 完整实现         ❌ 缺失               需新增
Delivery Queue      ✅ 磁盘队列         ❌ 缺失               需新增
Session Store       ✅ JSONL规范        ❌ 内存存储            需重构
Heartbeat           ✅ 6步检查链        ⚠️ 简化版             需增强
Message Routing     ✅ Binding机制      ❌ 缺失               需新增
Multi-Channel       ✅ 插件接口         ❌ CLI only           需扩展

Memory System       ⚠️ TF-IDF          ✅ 向量+意图感知        领先
Agent Architecture  ⚠️ 简单循环          ✅ Supervisor分层     领先
Tool Ecosystem      ⚠️ 4个内置           ✅ MCP无限扩展        领先
Intent Recognition  ⚠️ 规则匹配          ✅ AI+语义路由        领先
```

---

## 第二部分：优化目标

### 2.1 总体目标

构建一个**生产级**的个人 AI 助手系统，具备：
1. **可靠性**：消息不丢失、服务高可用
2. **可扩展性**：支持多通道、多用户、多 Agent
3. **智能化**：保持并增强现有的智能能力优势
4. **可维护性**：清晰的架构、完善的监控

### 2.2 分阶段目标

#### 阶段一：基础设施（4周）
- 实现 Gateway Server (WebSocket + HTTP)
- 实现 Delivery Queue (磁盘持久化)
- 重构 Session Store (JSONL 规范)

#### 阶段二：智能增强（2周）
- 增强 Heartbeat (6步检查链 + 主动行为)
- 实现 Message Routing (多 Agent 支持)

#### 阶段三：生态扩展（持续）
- 实现 Multi-Channel 抽象
- 接入 Telegram、Discord 等通道

---

## 第三部分：详细设计方案

### 3.1 Gateway Server 设计

#### 3.1.1 架构设计

```
┌─────────────────────────────────────────────────────────────────┐
│                      Gateway Server                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│   │   Browser   │  │   Mobile    │  │  Webhook    │            │
│   └──────┬──────┘  └──────┬──────┘  └──────┬──────┘            │
│          │                │                │                    │
│          └────────────────┼────────────────┘                    │
│                           ▼                                     │
│   ┌───────────────────────────────────────────────────────┐    │
│   │              WebSocket / HTTP Server                   │    │
│   │  (基于 websockets 库 + aiohttp)                       │    │
│   └───────────────────────┬───────────────────────────────┘    │
│                           │                                     │
│           ┌───────────────┼───────────────┐                    │
│           ▼               ▼               ▼                    │
│   ┌──────────────┐ ┌──────────────┐ ┌──────────────┐          │
│   │  Connection  │ │  JSON-RPC    │ │   Auth       │          │
│   │   Manager    │ │   Router     │ │ Middleware   │          │
│   └──────┬───────┘ └──────┬───────┘ └──────┬───────┘          │
│          │                │                │                   │
│          └────────────────┼────────────────┘                   │
│                           ▼                                    │
│   ┌───────────────────────────────────────────────────────┐   │
│   │              Method Handler Registry                   │   │
│   │  chat.send → run_agent()                              │   │
│   │  chat.history → load_history()                        │   │
│   │  channels.status → get_channels()                     │   │
│   │  health → ok                                          │   │
│   └───────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### 3.1.2 JSON-RPC 2.0 协议规范

**请求格式：**
```json
{
    "jsonrpc": "2.0",
    "id": "req-uuid-001",
    "method": "chat.send",
    "params": {
        "text": "你好，今天天气怎么样？",
        "session_key": "agent:main:cli:user1",
        "context": {
            "channel": "cli",
            "user_id": "user1"
        }
    }
}
```

**响应格式：**
```json
{
    "jsonrpc": "2.0",
    "id": "req-uuid-001",
    "result": {
        "message_id": "msg-uuid-001",
        "text": "你好！我是你的AI助手...",
        "session_key": "agent:main:cli:user1",
        "timestamp": "2026-02-24T10:30:00Z",
        "tokens_used": 150
    }
}
```

**流式事件格式：**
```json
{
    "jsonrpc": "2.0",
    "method": "event",
    "params": {
        "type": "chat.delta",
        "message_id": "msg-uuid-001",
        "delta": "你好",
        "session_key": "agent:main:cli:user1"
    }
}
```

#### 3.1.3 API 端点设计

| 方法 | 功能 | 认证 |
|------|------|------|
| `chat.send` | 发送消息并获取回复 | Bearer Token |
| `chat.send_stream` | 发送消息，流式返回 | Bearer Token |
| `chat.history` | 获取会话历史 | Bearer Token |
| `chat.clear` | 清空会话历史 | Bearer Token |
| `sessions.list` | 列出所有会话 | Bearer Token |
| `sessions.delete` | 删除指定会话 | Bearer Token |
| `memory.recall` | 搜索记忆 | Bearer Token |
| `tasks.list` | 获取任务列表 | Bearer Token |
| `tasks.create` | 创建任务 | Bearer Token |
| `health` | 健康检查 | 无需认证 |

#### 3.1.4 实现代码示例

```python
# src/gateway/server.py

import asyncio
import json
import logging
from typing import Callable, Dict, Any
import websockets
from websockets.server import WebSocketServerProtocol

logger = logging.getLogger("gateway")


class GatewayServer:
    """
    WebSocket + JSON-RPC 2.0 网关服务器
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        auth_token: str | None = None,
        agent=None,  # SupervisorAgent 实例
        session_store=None,  # SessionStore 实例
    ):
        self.host = host
        self.port = port
        self.auth_token = auth_token
        self.agent = agent
        self.session_store = session_store

        # 注册的方法处理器
        self._handlers: Dict[str, Callable] = {
            "chat.send": self._handle_chat_send,
            "chat.send_stream": self._handle_chat_send_stream,
            "chat.history": self._handle_chat_history,
            "sessions.list": self._handle_sessions_list,
            "health": self._handle_health,
        }

        # 活跃连接
        self._connections: set[WebSocketServerProtocol] = set()

    async def start(self):
        """启动服务器"""
        logger.info(f"启动 Gateway Server: ws://{self.host}:{self.port}")
        async with websockets.serve(
            self._handle_connection, self.host, self.port
        ):
            await asyncio.Future()  # 永远运行

    async def _handle_connection(self, websocket: WebSocketServerProtocol, path: str):
        """处理新连接"""
        self._connections.add(websocket)
        client_addr = websocket.remote_address
        logger.info(f"新连接: {client_addr}")

        try:
            async for message in websocket:
                try:
                    response = await self._process_message(message, websocket)
                    if response:
                        await websocket.send(json.dumps(response))
                except Exception as e:
                    logger.error(f"处理消息失败: {e}")
                    await websocket.send(json.dumps(self._error_response(None, -32603, str(e))))
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"连接关闭: {client_addr}")
        finally:
            self._connections.discard(websocket)

    async def _process_message(
        self, message: str, websocket: WebSocketServerProtocol
    ) -> dict | None:
        """处理 JSON-RPC 消息"""
        try:
            request = json.loads(message)
        except json.JSONDecodeError:
            return self._error_response(None, -32700, "Parse error")

        # 认证检查
        if self.auth_token and not self._is_authenticated(request):
            return self._error_response(request.get("id"), -32001, "Unauthorized")

        method = request.get("method")
        params = request.get("params", {})
        req_id = request.get("id")

        if method not in self._handlers:
            return self._error_response(req_id, -32601, f"Method not found: {method}")

        try:
            result = await self._handlers[method](params, websocket)
            return {"jsonrpc": "2.0", "id": req_id, "result": result}
        except Exception as e:
            logger.exception(f"Handler {method} failed")
            return self._error_response(req_id, -32603, str(e))

    async def _handle_chat_send(self, params: dict, ws: WebSocketServerProtocol) -> dict:
        """处理 chat.send"""
        text = params.get("text", "")
        session_key = params.get("session_key", "default")

        # 加载会话
        session = self.session_store.get_or_create(session_key)

        # 运行 Agent
        response_text = ""
        async for output in self.agent.handle(text, session.session_id):
            if isinstance(output, str):
                response_text += output

        # 保存会话
        self.session_store.save(session)

        return {
            "message_id": generate_uuid(),
            "text": response_text,
            "session_key": session_key,
            "timestamp": datetime.now().isoformat(),
        }

    async def _handle_chat_send_stream(
        self, params: dict, ws: WebSocketServerProtocol
    ) -> dict:
        """处理 chat.send_stream (流式返回)"""
        text = params.get("text", "")
        session_key = params.get("session_key", "default")
        message_id = generate_uuid()

        # 先返回 message_id
        await ws.send(json.dumps({
            "jsonrpc": "2.0",
            "method": "event",
            "params": {
                "type": "chat.start",
                "message_id": message_id,
                "session_key": session_key,
            }
        }))

        # 流式输出
        async for chunk in self.agent.handle(text, session_key):
            await ws.send(json.dumps({
                "jsonrpc": "2.0",
                "method": "event",
                "params": {
                    "type": "chat.delta",
                    "message_id": message_id,
                    "delta": chunk,
                    "session_key": session_key,
                }
            }))

        # 发送结束标记
        await ws.send(json.dumps({
            "jsonrpc": "2.0",
            "method": "event",
            "params": {
                "type": "chat.end",
                "message_id": message_id,
                "session_key": session_key,
            }
        }))

        return {"message_id": message_id, "stream": True}

    async def _handle_health(self, params: dict, ws: WebSocketServerProtocol) -> dict:
        """健康检查"""
        return {
            "status": "ok",
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
        }

    def _error_response(self, req_id: Any, code: int, message: str) -> dict:
        """构建错误响应"""
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": code, "message": message},
        }

    def _is_authenticated(self, request: dict) -> bool:
        """检查认证"""
        # 从请求头或参数中获取 token
        # 简化版：检查 params 中的 token
        params = request.get("params", {})
        token = params.get("token", "")
        return token == self.auth_token
```

---

### 3.2 Delivery Queue 设计

#### 3.2.1 核心机制

```
┌─────────────────────────────────────────────────────────────────┐
│                      Delivery Queue                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                      Agent Response                      │   │
│  └─────────────────────────┬───────────────────────────────┘   │
│                            ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  enqueue()                                              │   │
│  │  ├── 生成 UUID                                          │   │
│  │  ├── 写入 {uuid}.json.tmp (原子写入)                     │   │
│  │  └── rename 为 {uuid}.json                              │   │
│  └─────────────────────────┬───────────────────────────────┘   │
│                            ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Delivery Worker (后台任务)                             │   │
│  │                                                         │   │
│  │  for queue_file in queue_dir:                          │   │
│  │      delivery = load(queue_file)                       │   │
│  │                                                         │   │
│  │      if delivery.next_retry_at <= now:                 │   │
│  │          success = await attempt_delivery(delivery)    │   │
│  │                                                         │   │
│  │          if success:                                   │   │
│  │              ack() → 删除文件                           │   │
│  │          else:                                         │   │
│  │              fail() → 更新重试计数 + 退避时间           │   │
│  │                                                         │   │
│  │              if retry_count > MAX_RETRIES:             │   │
│  │                  move_to_failed() → failed/ 目录       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  退避时间表: [5s, 25s, 2m, 10m]                                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### 3.2.2 数据结构

```python
# src/infra/delivery_queue.py

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import json
import uuid
import shutil


@dataclass
class QueuedDelivery:
    """队列中的投递任务"""

    id: str                          # 投递ID (UUID)
    channel: str                     # 目标通道 (telegram/discord/cli)
    to: str                          # 接收者ID
    text: str                        # 消息内容
    agent_id: str                    # 来源Agent
    session_key: str                 # 会话标识

    # 元数据
    retry_count: int = 0             # 重试次数
    max_retries: int = 5             # 最大重试次数
    last_error: str | None = None    # 最后错误信息
    enqueued_at: str = ""            # 入队时间 (ISO格式)
    next_retry_at: str = ""          # 下次重试时间 (ISO格式)

    # 退避时间表 (ms)
    BACKOFF_MS = [5_000, 25_000, 120_000, 600_000]  # 5s, 25s, 2m, 10m

    def __post_init__(self):
        if not self.enqueued_at:
            self.enqueued_at = datetime.now().isoformat()
        if not self.next_retry_at:
            self.next_retry_at = self.enqueued_at

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "QueuedDelivery":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def calculate_backoff(self) -> int:
        """计算下次重试的退避时间 (毫秒)"""
        idx = min(self.retry_count, len(self.BACKOFF_MS) - 1)
        return self.BACKOFF_MS[idx]


class DeliveryQueue:
    """
    磁盘持久化的消息投递队列

    保证 At-least-once 投递语义
    """

    def __init__(self, queue_dir: str = "./data/delivery-queue"):
        self.queue_dir = Path(queue_dir)
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self.failed_dir = self.queue_dir / "failed"
        self.failed_dir.mkdir(exist_ok=True)

        self._running = False
        self._worker_task = None

    async def start(self):
        """启动投递工作线程"""
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("Delivery Queue 启动")

    async def stop(self):
        """停止投递工作线程"""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("Delivery Queue 停止")

    def enqueue(
        self,
        channel: str,
        to: str,
        text: str,
        agent_id: str = "main",
        session_key: str = "",
    ) -> str:
        """
        将消息加入投递队列

        使用原子写入保证数据安全：
        1. 先写入 .tmp 文件
        2. fsync 确保落盘
        3. rename 为正式文件名
        """
        delivery = QueuedDelivery(
            id=str(uuid.uuid4()),
            channel=channel,
            to=to,
            text=text,
            agent_id=agent_id,
            session_key=session_key,
        )

        # 原子写入
        file_path = self.queue_dir / f"{delivery.id}.json"
        tmp_path = file_path.with_suffix(".tmp")

        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(delivery.to_dict(), f, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())

            # 原子重命名
            os.rename(tmp_path, file_path)
            logger.debug(f"消息已入队: {delivery.id}")
            return delivery.id

        except Exception as e:
            logger.error(f"入队失败: {e}")
            if tmp_path.exists():
                tmp_path.unlink()
            raise

    def ack(self, delivery_id: str):
        """
        确认投递成功，删除队列文件
        """
        file_path = self.queue_dir / f"{delivery_id}.json"
        try:
            if file_path.exists():
                file_path.unlink()
                logger.debug(f"投递确认: {delivery_id}")
        except Exception as e:
            logger.error(f"确认失败 {delivery_id}: {e}")

    def fail(self, delivery_id: str, error: str):
        """
        标记投递失败，更新重试计数和退避时间
        """
        file_path = self.queue_dir / f"{delivery_id}.json"
        if not file_path.exists():
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                delivery = QueuedDelivery.from_dict(json.load(f))

            delivery.retry_count += 1
            delivery.last_error = error

            # 计算下次重试时间
            backoff_ms = delivery.calculate_backoff()
            next_retry = datetime.now() + timedelta(milliseconds=backoff_ms)
            delivery.next_retry_at = next_retry.isoformat()

            # 写回文件
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(delivery.to_dict(), f, ensure_ascii=False)

            logger.debug(f"投递失败: {delivery_id}, 重试 {delivery.retry_count}, 下次 {next_retry}")

        except Exception as e:
            logger.error(f"标记失败出错 {delivery_id}: {e}")

    def move_to_failed(self, delivery_id: str):
        """
        将超过最大重试次数的消息移入失败目录
        """
        src = self.queue_dir / f"{delivery_id}.json"
        dst = self.failed_dir / f"{delivery_id}.json"

        try:
            if src.exists():
                shutil.move(str(src), str(dst))
                logger.warning(f"消息已移入失败队列: {delivery_id}")
        except Exception as e:
            logger.error(f"移动失败 {delivery_id}: {e}")

    def recover_pending(self) -> list[QueuedDelivery]:
        """
        系统启动时恢复未完成的投递任务
        """
        pending = []
        for file_path in self.queue_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    delivery = QueuedDelivery.from_dict(json.load(f))
                    pending.append(delivery)
            except Exception as e:
                logger.error(f"恢复任务失败 {file_path}: {e}")

        logger.info(f"恢复 {len(pending)} 个待投递任务")
        return pending

    async def _worker_loop(self):
        """投递工作线程主循环"""
        while self._running:
            try:
                await self._process_pending()
                await asyncio.sleep(5)  # 每5秒扫描一次
            except Exception as e:
                logger.error(f"工作线程错误: {e}")
                await asyncio.sleep(10)

    async def _process_pending(self):
        """处理待投递任务"""
        now = datetime.now()

        for file_path in self.queue_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    delivery = QueuedDelivery.from_dict(json.load(f))

                # 检查是否到了重试时间
                next_retry = datetime.fromisoformat(delivery.next_retry_at)
                if next_retry > now:
                    continue

                # 检查是否超过最大重试次数
                if delivery.retry_count >= delivery.max_retries:
                    self.move_to_failed(delivery.id)
                    continue

                # 尝试投递
                success = await self._attempt_delivery(delivery)

                if success:
                    self.ack(delivery.id)
                else:
                    self.fail(delivery.id, "Delivery failed")

            except Exception as e:
                logger.error(f"处理任务失败 {file_path}: {e}")

    async def _attempt_delivery(self, delivery: QueuedDelivery) -> bool:
        """
        实际执行投递

        子类应该重写此方法实现具体的投递逻辑
        """
        # 默认实现：调用注册的 channel 处理器
        handler = self._channel_handlers.get(delivery.channel)
        if handler:
            try:
                await handler(delivery.to, delivery.text)
                return True
            except Exception as e:
                logger.error(f"投递失败: {e}")
                return False
        return False
```

---

### 3.3 Session Store 重构

#### 3.3.1 与 claw0 兼容的 JSONL 格式

```python
# src/chat/session_store.py

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Iterator
from dataclasses import dataclass, asdict

logger = logging.getLogger("chat.session")


@dataclass
class Session:
    """
    会话对象

    与 claw0 兼容的 session_key 格式:
    - agent:<agent_id>:main                    (所有DM共用)
    - agent:<agent_id>:direct:<peer_id>        (每个发送者独立)
    - agent:<agent_id>:<channel>:direct:<peer_id> (按通道隔离)
    """

    session_key: str
    agent_id: str
    channel: str
    peer_id: str
    messages: list[dict] = None
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if self.messages is None:
            self.messages = []
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at

    def add_message(self, role: str, content: str, metadata: dict = None):
        """添加消息"""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        }
        if metadata:
            message["metadata"] = metadata
        self.messages.append(message)
        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class SessionStore:
    """
    JSONL 格式的会话存储

    文件结构:
    data/sessions/
    ├── sessions.jsonl      # 活跃会话 (最近30天)
    ├── archive/            # 归档会话
    └── transcripts/        # 完整对话记录 (按会话ID)
        ├── session-001.jsonl
        └── session-002.jsonl
    """

    def __init__(self, base_dir: str = "./data/sessions"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir = self.base_dir / "archive"
        self.archive_dir.mkdir(exist_ok=True)
        self.transcript_dir = self.base_dir / "transcripts"
        self.transcript_dir.mkdir(exist_ok=True)

        self._sessions: dict[str, Session] = {}
        self._load_sessions()

    def _load_sessions(self):
        """从 JSONL 加载会话"""
        sessions_file = self.base_dir / "sessions.jsonl"
        if not sessions_file.exists():
            return

        try:
            with open(sessions_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    session = Session.from_dict(data)
                    self._sessions[session.session_key] = session
            logger.info(f"已加载 {len(self._sessions)} 个会话")
        except Exception as e:
            logger.error(f"加载会话失败: {e}")

    def _save_sessions(self):
        """保存会话到 JSONL"""
        sessions_file = self.base_dir / "sessions.jsonl"
        try:
            with open(sessions_file, "w", encoding="utf-8") as f:
                for session in self._sessions.values():
                    f.write(json.dumps(session.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"保存会话失败: {e}")

    def _save_transcript(self, session: Session):
        """保存完整对话记录"""
        # 生成安全的文件名
        safe_key = session.session_key.replace(":", "_")
        transcript_file = self.transcript_dir / f"{safe_key}.jsonl"

        try:
            with open(transcript_file, "a", encoding="utf-8") as f:
                for msg in session.messages:
                    f.write(json.dumps(msg, ensure_ascii=False) + "\n")
            # 清空已保存的消息
            session.messages = []
        except Exception as e:
            logger.error(f"保存对话记录失败: {e}")

    def get_or_create(
        self,
        session_key: str,
        agent_id: str = "main",
        channel: str = "cli",
        peer_id: str = "user",
    ) -> Session:
        """获取或创建会话"""
        if session_key in self._sessions:
            return self._sessions[session_key]

        session = Session(
            session_key=session_key,
            agent_id=agent_id,
            channel=channel,
            peer_id=peer_id,
        )
        self._sessions[session_key] = session
        return session

    def get(self, session_key: str) -> Session | None:
        """获取会话"""
        return self._sessions.get(session_key)

    def save(self, session: Session):
        """保存会话"""
        self._sessions[session.session_key] = session
        self._save_sessions()
        # 同时保存对话记录
        self._save_transcript(session)

    def list_sessions(self, agent_id: str | None = None) -> list[Session]:
        """列出会话"""
        sessions = list(self._sessions.values())
        if agent_id:
            sessions = [s for s in sessions if s.agent_id == agent_id]
        return sorted(sessions, key=lambda s: s.updated_at, reverse=True)

    def delete(self, session_key: str):
        """删除会话"""
        if session_key in self._sessions:
            del self._sessions[session_key]
            self._save_sessions()

    def archive_old_sessions(self, days: int = 30):
        """归档旧会话"""
        cutoff = datetime.now().timestamp() - (days * 24 * 3600)
        to_archive = []

        for key, session in list(self._sessions.items()):
            updated = datetime.fromisoformat(session.updated_at).timestamp()
            if updated < cutoff:
                to_archive.append((key, session))

        for key, session in to_archive:
            archive_file = self.archive_dir / f"{session.session_key.replace(':', '_')}.json"
            with open(archive_file, "w", encoding="utf-8") as f:
                json.dump(session.to_dict(), f, ensure_ascii=False)
            del self._sessions[key]

        if to_archive:
            self._save_sessions()
            logger.info(f"归档了 {len(to_archive)} 个旧会话")

    def iter_sessions(self) -> Iterator[Session]:
        """迭代所有会话"""
        yield from self._sessions.values()
```

---

### 3.4 Heartbeat 增强设计

#### 3.4.1 OpenClaw 6步检查链实现

```python
# src/agent/heartbeat.py

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

logger = logging.getLogger("agent.heartbeat")


@dataclass
class HeartbeatConfig:
    """Heartbeat 配置"""

    enabled: bool = True
    interval_seconds: int = 3600  # 默认1小时
    active_start_hour: int = 8    # 活跃时段开始
    active_end_hour: int = 22     # 活跃时段结束
    heartbeat_md_path: Path = Path("./config/HEARTBEAT.md")
    dedup_window_seconds: int = 86400  # 24小时去重


class HeartbeatRunner:
    """
    心跳运行器 - 实现 OpenClaw 6步检查链

    保证 Agent 具备主动行为能力，同时避免打扰用户
    """

    def __init__(
        self,
        config: HeartbeatConfig,
        agent,  # SupervisorAgent 实例
        channel_check_fn: Callable[[], bool],  # 检查通道是否空闲
        agent_check_fn: Callable[[], bool],   # 检查Agent是否空闲
        on_heartbeat: Callable[[str], None],   # 心跳触发回调
    ):
        self.config = config
        self.agent = agent
        self.channel_check_fn = channel_check_fn
        self.agent_check_fn = agent_check_fn
        self.on_heartbeat = on_heartbeat

        self._running = False
        self._task = None
        self._last_run_at = 0
        self._recent_hashes: dict[str, float] = {}  # 内容去重缓存

    async def start(self):
        """启动心跳"""
        if not self.config.enabled:
            logger.info("Heartbeat 已禁用")
            return

        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(f"Heartbeat 启动，间隔 {self.config.interval_seconds}s")

    async def stop(self):
        """停止心跳"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Heartbeat 停止")

    async def _loop(self):
        """主循环"""
        while self._running:
            try:
                if self._should_run():
                    await self._run_heartbeat()
                    self._last_run_at = time.time()

                # 清理过期去重记录
                self._cleanup_dedup_cache()

                await asyncio.sleep(60)  # 每分钟检查一次
            except Exception as e:
                logger.error(f"Heartbeat 循环错误: {e}")
                await asyncio.sleep(300)  # 出错后等待5分钟

    def _should_run(self) -> bool:
        """
        OpenClaw 6步检查链
        """
        # [1] heartbeat 是否启用?
        if not self.config.enabled:
            return False
        logger.debug("[Heartbeat] Step 1: enabled = True")

        # [2] 间隔是否已过?
        now = time.time()
        elapsed = now - self._last_run_at
        if elapsed < self.config.interval_seconds:
            logger.debug(f"[Heartbeat] Step 2: interval not passed ({elapsed:.0f}s < {self.config.interval_seconds}s)")
            return False
        logger.debug("[Heartbeat] Step 2: interval passed")

        # [3] 是否在活跃时段?
        current_hour = datetime.now().hour
        if not (self.config.active_start_hour <= current_hour < self.config.active_end_hour):
            logger.debug(f"[Heartbeat] Step 3: outside active hours ({current_hour})")
            return False
        logger.debug(f"[Heartbeat] Step 3: within active hours ({current_hour})")

        # [4] HEARTBEAT.md 是否存在且有内容?
        if not self.config.heartbeat_md_path.exists():
            logger.debug("[Heartbeat] Step 4: HEARTBEAT.md not found")
            return False

        content = self.config.heartbeat_md_path.read_text(encoding="utf-8").strip()
        if not content:
            logger.debug("[Heartbeat] Step 4: HEARTBEAT.md is empty")
            return False
        logger.debug("[Heartbeat] Step 4: HEARTBEAT.md exists and has content")

        # [5] 主通道是否空闲? (没有正在处理的用户消息)
        if not self.channel_check_fn():
            logger.debug("[Heartbeat] Step 5: channel is busy")
            return False
        logger.debug("[Heartbeat] Step 5: channel is idle")

        # [6] agent 当前是否空闲? (没有在运行中)
        if not self.agent_check_fn():
            logger.debug("[Heartbeat] Step 6: agent is busy")
            return False
        logger.debug("[Heartbeat] Step 6: agent is idle")

        logger.info("[Heartbeat] All 6 checks passed, should run")
        return True

    async def _run_heartbeat(self):
        """执行心跳"""
        try:
            # 读取 HEARTBEAT.md
            heartbeat_content = self.config.heartbeat_md_path.read_text(encoding="utf-8")

            # 构建提示词
            prompt = f"""{heartbeat_content}

Current time: {datetime.now().isoformat()}

Please check the above items and respond with your findings.
If nothing needs attention, respond with exactly: HEARTBEAT_OK"""

            # 运行 Agent
            response_parts = []
            async for output in self.agent.handle(prompt, session_id="heartbeat"):
                if isinstance(output, str):
                    response_parts.append(output)

            response = "".join(response_parts).strip()

            # 检查是否是静默响应
            if "HEARTBEAT_OK" in response:
                logger.debug("Heartbeat returned HEARTBEAT_OK, silent")
                return

            # 检查是否是重复内容
            if self._is_duplicate(response):
                logger.debug("Heartbeat response is duplicate, skipping")
                return

            # 触发回调
            logger.info("Heartbeat triggered proactive message")
            self.on_heartbeat(response)

        except Exception as e:
            logger.error(f"Heartbeat execution failed: {e}")

    def _is_duplicate(self, content: str) -> bool:
        """检查内容是否在24小时内重复"""
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        now = time.time()

        if content_hash in self._recent_hashes:
            last_time = self._recent_hashes[content_hash]
            if now - last_time < self.config.dedup_window_seconds:
                return True

        self._recent_hashes[content_hash] = now
        return False

    def _cleanup_dedup_cache(self):
        """清理过期的去重记录"""
        now = time.time()
        cutoff = now - self.config.dedup_window_seconds
        self._recent_hashes = {
            k: v for k, v in self._recent_hashes.items()
            if v > cutoff
        }
```

**HEARTBEAT.md 示例：**
```markdown
# Heartbeat Instructions

Check the following and report ONLY if action is needed:

1. Review today's tasks and identify any overdue items
2. Check for upcoming deadlines within the next 24 hours
3. Review the user's recent memories for any unresolved issues
4. Check if there are any reminders set for this time

If nothing needs attention, respond with exactly: HEARTBEAT_OK

If action is needed:
- Be concise and specific
- Suggest concrete next steps
- Use a friendly, proactive tone
```

---

## 第四部分：实施路线图

### 4.1 阶段一：基础设施（4周）

#### Week 1-2: Gateway Server
- [ ] 实现 WebSocket 服务器框架
- [ ] 实现 JSON-RPC 2.0 协议解析
- [ ] 实现认证中间件 (Bearer Token)
- [ ] 实现核心方法 (chat.send, chat.history, health)
- [ ] 集成到 main.py 启动流程

#### Week 3: Delivery Queue
- [ ] 实现 QueuedDelivery 数据类
- [ ] 实现原子写入机制
- [ ] 实现退避重试逻辑
- [ ] 实现后台工作线程
- [ ] 集成到 Agent 响应流程

#### Week 4: Session Store 重构
- [ ] 实现 Session 数据类
- [ ] 实现 JSONL 读写
- [ ] 实现 claw0 兼容的 session_key
- [ ] 重构 ChatSession 使用新的 SessionStore
- [ ] 实现会话归档功能

### 4.2 阶段二：智能增强（2周）

#### Week 5: Heartbeat 增强
- [ ] 实现 HeartbeatConfig
- [ ] 实现 6步检查链
- [ ] 实现互斥锁机制
- [ ] 实现24小时去重
- [ ] 创建 HEARTBEAT.md 模板

#### Week 6: Message Routing (可选)
- [ ] 实现 Binding 数据类
- [ ] 实现匹配算法
- [ ] 实现多 Agent 支持
- [ ] 集成到 Gateway

### 4.3 阶段三：生态扩展（持续）

- [ ] 实现 Channel 抽象接口
- [ ] 实现 TelegramChannel
- [ ] 实现 DiscordChannel
- [ ] 实现 WebhookChannel

---

## 第五部分：风险评估与缓解

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| Gateway 引入安全漏洞 | 中 | 高 | 强制认证、输入验证、速率限制 |
| Delivery Queue 磁盘IO性能瓶颈 | 中 | 中 | 批量处理、异步写入、定期归档 |
| Session Store 数据丢失 | 低 | 高 | 原子写入、定期备份、WAL日志 |
| Heartbeat 打扰用户 | 中 | 中 | 6步检查链、去重机制、活跃时段 |
| 重构引入回归Bug | 中 | 中 | 完整测试、灰度发布、快速回滚 |

---

## 第六部分：成功指标

### 6.1 技术指标
- [ ] Gateway Server 支持 100+ 并发连接
- [ ] Delivery Queue 保证 99.9% 消息不丢失
- [ ] Session Store 支持 1000+ 会话
- [ ] Heartbeat 误触发率 < 1%

### 6.2 体验指标
- [ ] 系统重启后对话历史完整恢复
- [ ] 网络中断后消息自动重发
- [ ] Agent 能主动提醒重要事项
- [ ] 支持多客户端同时接入

---

## 附录：参考资源

- claw0 项目: https://github.com/shareAI-lab/claw0
- OpenClaw 项目: https://github.com/openclaw/openclaw
- JSON-RPC 2.0 规范: https://www.jsonrpc.org/specification
- WebSocket 协议: https://tools.ietf.org/html/rfc6455

---

**文档版本**: v1.0
**最后更新**: 2026-02-24
**作者**: AI Assistant