# 测试计划

## 1. 测试策略

### 1.1 测试层级

```
┌─────────────────────────────────────────────────────────┐
│  端到端测试 (E2E)                                        │
│  - 完整用户流程                                          │
│  - 多通道集成                                            │
├─────────────────────────────────────────────────────────┤
│  集成测试                                                │
│  - Gateway + Agent                                       │
│  - Channel + MessageBus                                  │
│  - SessionStore + FileSystem                             │
├─────────────────────────────────────────────────────────┤
│  单元测试                                                │
│  - 各个模块独立测试                                       │
│  - Mock 外部依赖                                         │
└─────────────────────────────────────────────────────────┘
```

### 1.2 测试覆盖率目标

| 模块 | 目标覆盖率 | 优先级 |
|------|-----------|--------|
| `gateway/` | 80% | P0 |
| `channels/` | 70% | P0 |
| `bus/` | 75% | P1 |
| `chat/session_store.py` | 80% | P0 |

## 2. 单元测试

### 2.1 Gateway 测试

```python
# tests/gateway/test_protocol.py

class TestJSONRPCProtocol:
    """JSON-RPC 协议解析测试"""

    def test_parse_valid_request(self):
        """测试正常请求解析"""
        raw = '{"jsonrpc": "2.0", "id": "1", "method": "chat.send", "params": {"text": "hello"}}'
        request = parse_request(raw)
        assert request.method == "chat.send"
        assert request.id == "1"

    def test_parse_invalid_json(self):
        """测试无效 JSON"""
        raw = 'invalid json'
        with pytest.raises(JSONParseError):
            parse_request(raw)

    def test_parse_missing_method(self):
        """测试缺少 method 字段"""
        raw = '{"jsonrpc": "2.0", "id": "1"}'
        with pytest.raises(InvalidRequestError):
            parse_request(raw)

    def test_build_response(self):
        """测试响应构建"""
        response = build_response("1", {"text": "hello"})
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == "1"
        assert response["result"]["text"] == "hello"

    def test_build_error_response(self):
        """测试错误响应构建"""
        response = build_error_response("1", -32601, "Method not found")
        assert response["error"]["code"] == -32601
        assert response["error"]["message"] == "Method not found"
```

### 2.2 Channel 测试

```python
# tests/channels/test_base.py

class TestBaseChannel:
    """Channel 抽象测试"""

    def test_is_allowed_empty_list(self):
        """空白名单允许所有用户"""
        config = Mock(allow_from=[])
        channel = TestChannel(config, Mock())
        assert channel.is_allowed("user123") is True

    def test_is_allowed_whitelist(self):
        """白名单机制"""
        config = Mock(allow_from=["user123", "user456"])
        channel = TestChannel(config, Mock())
        assert channel.is_allowed("user123") is True
        assert channel.is_allowed("user999") is False

    def test_is_allowed_pipe_separator(self):
        """管道分隔符支持"""
        config = Mock(allow_from=["user123"])
        channel = TestChannel(config, Mock())
        assert channel.is_allowed("user123|nickname") is True
```

### 2.3 Session Store 测试

```python
# tests/chat/test_session_store.py

class TestSessionStore:
    """Session Store 测试"""

    def test_create_session(self, tmp_path):
        """测试创建会话"""
        store = SessionStore(base_dir=str(tmp_path))
        session = store.get_or_create("telegram:user123")
        assert session.session_key == "telegram:user123"
        assert session.channel == "telegram"
        assert session.peer_id == "user123"

    def test_persist_session(self, tmp_path):
        """测试会话持久化"""
        store = SessionStore(base_dir=str(tmp_path))
        session = store.get_or_create("telegram:user123")
        session.add_message("user", "hello")
        store.save(session)

        # 重新加载
        store2 = SessionStore(base_dir=str(tmp_path))
        session2 = store2.get("telegram:user123")
        assert len(session2.messages) == 1
        assert session2.messages[0]["content"] == "hello"

    def test_session_key_parsing(self):
        """测试 Session Key 解析"""
        session = Session.from_key("agent:main:telegram:user123")
        assert session.agent_id == "main"
        assert session.channel == "telegram"
        assert session.peer_id == "user123"
```

## 3. 集成测试

### 3.1 Gateway + Agent 集成

```python
# tests/integration/test_gateway_agent.py

@pytest.mark.asyncio
class TestGatewayAgentIntegration:
    """Gateway 与 Agent 集成测试"""

    async def test_chat_send_full_flow(self):
        """测试完整对话流程"""
        # 1. 启动 Gateway
        gateway = GatewayServer(port=0)  # 随机端口
        await gateway.start()

        # 2. 连接 WebSocket
        uri = f"ws://localhost:{gateway.port}"
        async with websockets.connect(uri) as ws:
            # 3. 发送认证
            await ws.send(json.dumps({
                "jsonrpc": "2.0",
                "id": "auth-1",
                "method": "auth",
                "params": {"token": "test-token"}
            }))

            # 4. 发送消息
            await ws.send(json.dumps({
                "jsonrpc": "2.0",
                "id": "1",
                "method": "chat.send",
                "params": {"text": "你好", "session_key": "test:session"}
            }))

            # 5. 接收响应
            response = await asyncio.wait_for(ws.recv(), timeout=10.0)
            data = json.loads(response)
            assert "result" in data
            assert "text" in data["result"]

        await gateway.stop()
```

### 3.2 Channel + MessageBus 集成

```python
# tests/integration/test_channel_bus.py

@pytest.mark.asyncio
class TestChannelBusIntegration:
    """Channel 与 MessageBus 集成测试"""

    async def test_message_flow(self):
        """测试消息流转"""
        bus = MessageBus()
        received_messages = []

        # 订阅消息
        async def handler(msg):
            received_messages.append(msg)

        bus.subscribe_inbound(handler)

        # 模拟 Channel 接收消息
        channel = MockChannel(config={}, bus=bus)
        await channel.simulate_receive("user123", "chat456", "hello")

        # 验证消息到达
        await asyncio.sleep(0.1)  # 等待异步处理
        assert len(received_messages) == 1
        assert received_messages[0].content == "hello"
```

## 4. 端到端测试

### 4.1 CLI 场景

```python
# tests/e2e/test_cli_flow.py

@pytest.mark.asyncio
class TestCLIFlow:
    """CLI 端到端测试"""

    async def test_complete_conversation(self):
        """测试完整对话"""
        # 启动 Gateway
        async with run_gateway() as gateway:
            # 使用 CLI 客户端连接
            cli = CLIClient(gateway.port)

            # 发送多条消息
            response1 = await cli.send("你好")
            assert "你好" in response1 or "Hello" in response1

            response2 = await cli.send("今天天气怎么样？")
            assert len(response2) > 0

            # 验证历史记录
            history = await cli.get_history()
            assert len(history) >= 2
```

### 4.2 多通道场景

```python
# tests/e2e/test_multi_channel.py

@pytest.mark.asyncio
class TestMultiChannel:
    """多通道端到端测试"""

    async def test_telegram_and_discord(self):
        """测试 Telegram 和 Discord 同时在线"""
        async with run_gateway(channels=["telegram", "discord"]) as gateway:
            # 模拟 Telegram 用户发送
            telegram = MockTelegramClient(gateway)
            await telegram.send_message("user_tg", "来自 Telegram")

            # 模拟 Discord 用户发送
            discord = MockDiscordClient(gateway)
            await discord.send_message("user_dc", "来自 Discord")

            # 验证两个通道都收到回复
            tg_response = await telegram.get_last_response()
            dc_response = await discord.get_last_response()

            assert len(tg_response) > 0
            assert len(dc_response) > 0
```

## 5. 性能测试

### 5.1 并发连接测试

```python
# tests/performance/test_concurrent.py

@pytest.mark.asyncio
class TestConcurrentConnections:
    """并发性能测试"""

    async def test_100_concurrent_connections(self):
        """测试 100 个并发连接"""
        async with run_gateway() as gateway:
            connections = []

            # 建立 100 个连接
            for i in range(100):
                ws = await websockets.connect(f"ws://localhost:{gateway.port}")
                connections.append(ws)

            # 同时发送消息
            async def send_and_receive(ws, idx):
                await ws.send(json.dumps({
                    "jsonrpc": "2.0",
                    "id": str(idx),
                    "method": "health"
                }))
                return await asyncio.wait_for(ws.recv(), timeout=5.0)

            results = await asyncio.gather(*[
                send_and_receive(ws, i) for i, ws in enumerate(connections)
            ])

            assert len(results) == 100

            # 关闭连接
            for ws in connections:
                await ws.close()
```

### 5.2 压力测试

```bash
# 使用 wrk 或自定义脚本进行压力测试

# WebSocket 压力测试
python tests/performance/ws_bench.py \
    --host localhost \
    --port 8080 \
    --connections 1000 \
    --duration 60 \
    --messages-per-second 100

# 预期结果:
# - 连接成功率 > 99.9%
# - 平均响应时间 < 500ms
# - 内存使用稳定，无泄漏
```

## 6. 测试环境

### 6.1 测试配置

```python
# tests/conftest.py

import pytest
import tempfile
import shutil

@pytest.fixture
def temp_workspace():
    """临时工作目录"""
    path = tempfile.mkdtemp()
    yield path
    shutil.rmtree(path)

@pytest.fixture
async def gateway_server(temp_workspace):
    """Gateway 服务器 Fixture"""
    from gateway.server import GatewayServer

    server = GatewayServer(
        host="127.0.0.1",
        port=0,  # 随机端口
        auth_token="test-token",
        workspace=temp_workspace
    )
    await server.start()
    yield server
    await server.stop()

@pytest.fixture
def mock_agent():
    """Mock Agent"""
    from unittest.mock import AsyncMock
    agent = AsyncMock()
    agent.handle = AsyncMock(return_value=["Hello!"])
    return agent
```

### 6.2 CI/CD 集成

```yaml
# .github/workflows/test.yml

name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.11', '3.12']

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}

    - name: Install dependencies
      run: |
        pip install -e ".[test]"

    - name: Run unit tests
      run: |
        pytest tests/unit -v --cov=src --cov-report=xml

    - name: Run integration tests
      run: |
        pytest tests/integration -v

    - name: Run e2e tests
      run: |
        pytest tests/e2e -v

    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

## 7. 测试 checklist

### 7.1 开发阶段

- [ ] 单元测试通过
- [ ] 集成测试通过
- [ ] 代码覆盖率 > 70%
- [ ] 静态类型检查通过 (mypy)
- [ ] 代码风格检查通过 (ruff)

### 7.2 发布阶段

- [ ] 端到端测试通过
- [ ] 性能测试达标
- [ ] 安全审计通过
- [ ] 文档完整

## 8. 测试工具

| 工具 | 用途 | 命令 |
|------|------|------|
| pytest | 测试框架 | `pytest` |
| pytest-asyncio | 异步测试 | `pytest -v` |
| pytest-cov | 覆盖率 | `pytest --cov=src` |
| mypy | 类型检查 | `mypy src/` |
| ruff | 代码风格 | `ruff check src/` |
| websockets | WS 测试 | 内置 |

---

**版本**: v1.0
**更新**: 2026-02-24
