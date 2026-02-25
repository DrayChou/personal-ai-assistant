# -*- coding: utf-8 -*-
"""
Agent core logic tests
"""
import pytest
from unittest.mock import MagicMock, AsyncMock

from src.agent.supervisor import SupervisorAgent, ExecutionMode, ExecutionPlan, Step
from src.agent.tools.registry import ToolRegistry
from src.agent.tools.base import Tool, ToolResult, ToolParameter


class MockTool(Tool):
    """Mock tool for testing"""

    name = "mock_tool"
    description = "A mock tool for testing"
    parameters = [
        ToolParameter(name="input", type="string", description="Test input", required=True)
    ]

    async def execute(self, input: str) -> ToolResult:
        return ToolResult(
            success=True,
            data={"result": f"processed: {input}"},
            observation="Mock tool executed successfully"
        )


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client"""
    client = MagicMock()
    client.chat = AsyncMock(return_value="Test response")
    client.stream_chat = AsyncMock(return_value=iter(["chunk1", "chunk2"]))
    return client


@pytest.fixture
def tool_registry():
    """Create tool registry with mock tools"""
    registry = ToolRegistry()
    registry.register(MockTool())
    return registry


@pytest.fixture
def supervisor_agent(mock_llm_client, tool_registry):
    """Create SupervisorAgent instance"""
    return SupervisorAgent(
        llm_client=mock_llm_client,
        tool_registry=tool_registry
    )


class TestExecutionMode:
    """Test ExecutionMode enum"""

    def test_execution_modes_exist(self):
        """Verify all execution modes are defined"""
        assert hasattr(ExecutionMode, "FAST_PATH")
        assert hasattr(ExecutionMode, "SINGLE_STEP")
        assert hasattr(ExecutionMode, "MULTI_STEP")

    def test_execution_mode_values(self):
        """Verify execution mode string values"""
        assert ExecutionMode.FAST_PATH.value == "fast_path"
        assert ExecutionMode.SINGLE_STEP.value == "single_step"
        assert ExecutionMode.MULTI_STEP.value == "multi_step"


class TestIntentAnalysis:
    """Test intent analysis logic"""

    @pytest.mark.asyncio
    async def test_simple_greeting_returns_fast_path(self, supervisor_agent):
        """Simple greetings should return FAST_PATH"""
        test_inputs = ["hello", "hi", "你好", "嗨", "谢谢", "再见"]

        for input_text in test_inputs:
            result = await supervisor_agent._analyze_intent(input_text)
            assert result == ExecutionMode.FAST_PATH, f"Expected FAST_PATH for '{input_text}'"

    @pytest.mark.asyncio
    async def test_long_greeting_returns_single_step(self, supervisor_agent):
        """Long messages with greeting words should not be FAST_PATH"""
        long_input = "hello there, I have a very long message to share with you today"
        result = await supervisor_agent._analyze_intent(long_input)
        assert result != ExecutionMode.FAST_PATH

    @pytest.mark.asyncio
    async def test_task_operations_return_single_step(self, supervisor_agent):
        """Task operations should return SINGLE_STEP"""
        test_inputs = [
            "清理任务",
            "删除任务",
            "有什么任务",
            "查看任务",
            "显示任务",
        ]

        for input_text in test_inputs:
            result = await supervisor_agent._analyze_intent(input_text)
            assert result == ExecutionMode.SINGLE_STEP, f"Expected SINGLE_STEP for '{input_text}'"

    @pytest.mark.asyncio
    async def test_complex_requests_return_multi_step(self, supervisor_agent):
        """Complex multi-step requests should return MULTI_STEP"""
        test_inputs = [
            "帮我总结所有任务然后清理",
            "分析并整理我的记忆",
            "整理并总结今天的工作",
        ]

        for input_text in test_inputs:
            result = await supervisor_agent._analyze_intent(input_text)
            assert result == ExecutionMode.MULTI_STEP, f"Expected MULTI_STEP for '{input_text}'"

    @pytest.mark.asyncio
    async def test_default_returns_single_step(self, supervisor_agent):
        """Unknown requests should default to SINGLE_STEP"""
        test_inputs = [
            "今天天气怎么样",
            "帮我写一段代码",
            "讲个笑话",
        ]

        for input_text in test_inputs:
            result = await supervisor_agent._analyze_intent(input_text)
            assert result == ExecutionMode.SINGLE_STEP, f"Expected SINGLE_STEP for '{input_text}'"


class TestExecutionPlan:
    """Test execution plan generation"""

    def test_step_creation(self):
        """Test Step dataclass"""
        step = Step(
            id="step_1",
            tool_name="test_tool",
            parameters={"arg": "value"}
        )
        assert step.id == "step_1"
        assert step.tool_name == "test_tool"
        assert step.parameters == {"arg": "value"}

    def test_execution_plan_creation(self):
        """Test ExecutionPlan dataclass"""
        plan = ExecutionPlan(
            mode=ExecutionMode.SINGLE_STEP,
            goal="test goal",
            steps=[
                Step(id="s1", tool_name="tool1", parameters={})
            ]
        )
        assert plan.mode == ExecutionMode.SINGLE_STEP
        assert plan.goal == "test goal"
        assert len(plan.steps) == 1

    def test_fast_path_plan_has_no_steps(self):
        """FAST_PATH plan should have empty steps"""
        plan = ExecutionPlan(
            mode=ExecutionMode.FAST_PATH,
            goal="hello",
            steps=[]
        )
        assert len(plan.steps) == 0


class TestToolRegistry:
    """Test tool registry functionality"""

    def test_register_tool(self, tool_registry):
        """Test tool registration"""
        tools = tool_registry.list_tools()
        tool_names = [t.name for t in tools]
        assert "mock_tool" in tool_names

    def test_get_tool(self, tool_registry):
        """Test getting tool from registry"""
        tool = tool_registry.get("mock_tool")
        assert tool is not None
        assert tool.name == "mock_tool"

    def test_get_nonexistent_tool(self, tool_registry):
        """Test getting nonexistent tool returns None"""
        tool = tool_registry.get("nonexistent")
        assert tool is None

    def test_list_tools(self, tool_registry):
        """Test listing all tools"""
        tools = tool_registry.list_tools()
        assert len(tools) > 0
        tool_names = [t.name for t in tools]
        assert "mock_tool" in tool_names

    def test_get_tool_schemas(self, tool_registry):
        """Test getting tool schemas for LLM"""
        schemas = tool_registry.get_schemas()
        assert isinstance(schemas, list)
        assert len(schemas) > 0

        # Check schema structure
        schema = schemas[0]
        assert "type" in schema
        assert schema["type"] == "function"
        assert "function" in schema
        assert "name" in schema["function"]


class TestToolExecution:
    """Test tool execution"""

    @pytest.mark.asyncio
    async def test_mock_tool_execution(self):
        """Test mock tool execute method"""
        tool = MockTool()
        result = await tool.execute(input="test")

        assert result.success is True
        assert result.data["result"] == "processed: test"

    @pytest.mark.asyncio
    async def test_tool_result_properties(self):
        """Test ToolResult properties"""
        result = ToolResult(
            success=True,
            data={"key": "value"},
            observation="Test observation"
        )

        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.observation == "Test observation"


class TestMetricsCollector:
    """Test metrics collection"""

    def test_metrics_collector_initialization(self, supervisor_agent):
        """Test metrics collector is initialized"""
        assert hasattr(supervisor_agent, "metrics")
        assert supervisor_agent.metrics is not None

    def test_record_llm_call(self, supervisor_agent):
        """Test recording LLM call"""
        supervisor_agent.metrics.record_llm_call(1.5)
        assert supervisor_agent.metrics.metrics["llm_calls"] == 1
        assert 1.5 in supervisor_agent.metrics.metrics["llm_latency"]

    def test_record_tool_call(self, supervisor_agent):
        """Test recording tool call"""
        supervisor_agent.metrics.record_tool_call("test_tool", 0.5, True)
        assert "test_tool" in supervisor_agent.metrics.metrics["tool_calls"]
        assert supervisor_agent.metrics.metrics["tool_calls"]["test_tool"]["success"] == 1

    def test_get_summary(self, supervisor_agent):
        """Test getting metrics summary"""
        supervisor_agent.metrics.record_llm_call(1.0)
        summary = supervisor_agent.metrics.get_summary()

        assert "llm_calls" in summary
        assert summary["llm_calls"] == 1
