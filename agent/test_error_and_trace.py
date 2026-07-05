# test_error_and_trace.py
"""
异常处理 + 执行 trace/日志 测试

  异常处理：
    1. LLM 调用失败 → 重试后优雅降级，不崩溃
    2. LLM 临时失败后重试成功 → 正常返回
    3. 工具执行抛异常 → 捕获为友好错误，Agent 继续
    4. 调用不存在的工具 → 返回提示，不崩溃
    5. 工具参数不匹配 → 返回参数错误提示

  执行 trace：
    6. 一次带工具的 run 生成完整 trace（perception/planning/tool_call/final）
    7. trace 可导出为 JSON
    8. 工具失败会在 trace 中标记 success=False

前 5 项 + 后 3 项均用「假 LLM」驱动，完全离线、确定性强，不消耗真实 API。
"""

import sys
import os
import json

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mini_agent_runtime import (
    MiniAgentRuntime, ToolRegistry, LLMInvokeError,
)


# ============================================================
# 测试替身（Fake LLM）
# ============================================================
class AlwaysFailLLM:
    """每次调用都抛异常的假 LLM"""
    def invoke(self, messages, **kwargs):
        raise ConnectionError("模拟网络中断")


class FailThenSucceedLLM:
    """前 N 次失败，之后成功的假 LLM（测试重试）"""
    def __init__(self, fail_times=1):
        self.fail_times = fail_times
        self.calls = 0

    def invoke(self, messages, **kwargs):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise TimeoutError(f"模拟超时（第 {self.calls} 次）")
        return "重试后成功返回的回答"


class ScriptedLLM:
    """按预设脚本依次返回的假 LLM（驱动工具调用流程）"""
    def __init__(self, responses):
        self.responses = list(responses)
        self.idx = 0

    def invoke(self, messages, **kwargs):
        if self.idx < len(self.responses):
            resp = self.responses[self.idx]
            self.idx += 1
            return resp
        return "默认最终回答"


# 一些工具
def ok_tool(x: str) -> str:
    return f"处理成功: {x}"


def boom_tool(x: str) -> str:
    raise ValueError("工具内部炸了")


TOOL_SCHEMA = {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]}


# ============================================================
# 异常处理测试
# ============================================================
def test_1_llm_always_fail():
    print("\n" + "=" * 70)
    print("测试1: LLM 持续失败 → 优雅降级不崩溃")
    print("=" * 70)
    agent = MiniAgentRuntime(AlwaysFailLLM(), ToolRegistry(), max_iterations=2)
    resp = agent.run("你好", session_id="err-1")
    print(f"  返回: {resp}")
    assert resp.startswith("⚠️"), "应返回友好降级提示而非抛异常"
    assert "不可用" in resp
    print("  ✅ 通过：LLM 全失败时优雅降级，程序未崩溃")


def test_2_llm_retry_success():
    print("\n" + "=" * 70)
    print("测试2: LLM 首次失败、重试成功")
    print("=" * 70)
    llm = FailThenSucceedLLM(fail_times=1)
    agent = MiniAgentRuntime(llm, ToolRegistry(), max_iterations=2)
    resp = agent.run("你好", session_id="err-2")
    print(f"  LLM 实际被调用 {llm.calls} 次")
    print(f"  返回: {resp}")
    assert "重试后成功" in resp, "重试成功后应返回正常内容"
    assert llm.calls == 2, "应为失败1次+成功1次"
    print("  ✅ 通过：临时失败经重试后成功返回")


def test_3_tool_raises():
    print("\n" + "=" * 70)
    print("测试3: 工具执行抛异常 → 捕获为友好错误")
    print("=" * 70)
    registry = ToolRegistry()
    registry.register("boom", "会抛异常的工具", TOOL_SCHEMA, boom_tool)
    # LLM 先调用 boom 工具，下一轮直接回答
    llm = ScriptedLLM([
        '[TOOL_CALL]\n{"tool": "boom", "arguments": {"x": "test"}}\n[/TOOL_CALL]',
        "已经了解到工具执行失败了。",
    ])
    agent = MiniAgentRuntime(llm, registry, max_iterations=3)
    resp = agent.run("用一下 boom 工具", session_id="err-3")
    print(f"  最终返回: {resp}")

    # 检查工具错误被记录在 trace 中
    session = agent.session_manager.get_session("err-3")
    tool_events = [e for e in session.trace if e.step == "tool_call"]
    assert len(tool_events) == 1, "应有 1 次工具调用记录"
    assert tool_events[0].detail["success"] is False, "工具应标记为失败"
    assert "炸了" in tool_events[0].error, "trace 应记录具体错误"
    print(f"  工具 trace 错误: {tool_events[0].error[:50]}")
    print("  ✅ 通过：工具异常被捕获，Agent 继续运行并记录错误")


def test_4_unknown_tool():
    print("\n" + "=" * 70)
    print("测试4: 调用不存在的工具")
    print("=" * 70)
    registry = ToolRegistry()
    result = registry.execute_tool("not_exist", {"x": "1"})
    print(f"  返回: {result}")
    assert result.startswith("❌") and "不存在" in result
    print("  ✅ 通过：未知工具返回提示，不抛异常")


def test_5_tool_bad_args():
    print("\n" + "=" * 70)
    print("测试5: 工具参数不匹配")
    print("=" * 70)
    registry = ToolRegistry()
    registry.register("ok", "正常工具", TOOL_SCHEMA, ok_tool)
    # 缺少必填参数 x，且给了不存在的参数
    result = registry.execute_tool("ok", {"wrong_param": "1"})
    print(f"  返回: {result}")
    assert result.startswith("❌") and "参数" in result
    print("  ✅ 通过：参数错误被捕获为友好提示")


# ============================================================
# 执行 trace 测试
# ============================================================
def test_6_trace_full_flow():
    print("\n" + "=" * 70)
    print("测试6: 带工具的 run 生成完整 trace")
    print("=" * 70)
    registry = ToolRegistry()
    registry.register("ok", "正常工具", TOOL_SCHEMA, ok_tool)
    llm = ScriptedLLM([
        '[TOOL_CALL]\n{"tool": "ok", "arguments": {"x": "hello"}}\n[/TOOL_CALL]',
        "任务完成。",
    ])
    agent = MiniAgentRuntime(llm, registry, max_iterations=3)
    agent.run("用一下 ok 工具", session_id="trace-6")

    session = agent.session_manager.get_session("trace-6")
    steps = [e.step for e in session.trace]
    print(f"  trace 步骤序列: {steps}")

    assert "perception" in steps, "缺少 perception 记录"
    assert "planning" in steps, "缺少 planning 记录"
    assert "tool_call" in steps, "缺少 tool_call 记录"
    assert "final" in steps, "缺少 final 记录"

    # planning 应记录耗时
    planning = next(e for e in session.trace if e.step == "planning")
    assert planning.duration_ms is not None, "planning 应记录耗时"
    print(f"  planning 耗时: {planning.duration_ms}ms")
    print("  ✅ 通过：trace 完整覆盖 感知/规划/工具调用/最终回答 四类步骤")


def test_7_trace_export_json():
    print("\n" + "=" * 70)
    print("测试7: trace 可导出为 JSON")
    print("=" * 70)
    registry = ToolRegistry()
    llm = ScriptedLLM(["直接回答，无需工具。"])
    agent = MiniAgentRuntime(llm, registry, max_iterations=2)
    agent.run("你好", session_id="trace-7")

    session = agent.session_manager.get_session("trace-7")
    json_str = session.export_trace(as_json=True)
    parsed = json.loads(json_str)  # 应能被正常解析

    print(f"  导出 {len(parsed)} 条 trace 事件")
    print(f"  JSON 片段: {json_str[:120]}...")
    assert isinstance(parsed, list) and len(parsed) >= 2
    assert all("step" in e and "timestamp" in e for e in parsed)
    print("  ✅ 通过：trace 成功序列化为合法 JSON")


def test_8_trace_marks_tool_failure():
    print("\n" + "=" * 70)
    print("测试8: 工具失败在 trace 中被标记")
    print("=" * 70)
    registry = ToolRegistry()
    registry.register("boom", "会抛异常的工具", TOOL_SCHEMA, boom_tool)
    registry.register("ok", "正常工具", TOOL_SCHEMA, ok_tool)
    llm = ScriptedLLM([
        '[TOOL_CALL]\n{"tool": "ok", "arguments": {"x": "a"}}\n[/TOOL_CALL]',
        '[TOOL_CALL]\n{"tool": "boom", "arguments": {"x": "b"}}\n[/TOOL_CALL]',
        "结束。",
    ])
    agent = MiniAgentRuntime(llm, registry, max_iterations=4)
    agent.run("先用 ok 再用 boom", session_id="trace-8")

    session = agent.session_manager.get_session("trace-8")
    tool_events = [e for e in session.trace if e.step == "tool_call"]
    outcomes = {e.detail["tool"]: e.detail["success"] for e in tool_events}
    print(f"  工具执行结果: {outcomes}")

    assert outcomes.get("ok") is True, "ok 工具应成功"
    assert outcomes.get("boom") is False, "boom 工具应失败"
    print("  ✅ 通过：成功/失败的工具在 trace 中被正确区分标记")


if __name__ == "__main__":
    print("\n" + "🛡️" * 35)
    print("异常处理 + 执行 Trace 测试")
    print("🛡️" * 35)

    suite = [
        test_1_llm_always_fail,
        test_2_llm_retry_success,
        test_3_tool_raises,
        test_4_unknown_tool,
        test_5_tool_bad_args,
        test_6_trace_full_flow,
        test_7_trace_export_json,
        test_8_trace_marks_tool_failure,
    ]

    results = []
    for func in suite:
        try:
            func()
            results.append((func.__name__, "PASS"))
        except AssertionError as e:
            print(f"  ❌ 失败: {e}")
            results.append((func.__name__, "FAIL"))
        except Exception as e:
            print(f"  💥 异常: {e}")
            import traceback
            traceback.print_exc()
            results.append((func.__name__, "ERROR"))

    print("\n" + "=" * 70)
    print("📊 汇总")
    print("=" * 70)
    icon = {"PASS": "✅", "FAIL": "❌", "ERROR": "💥"}
    for name, status in results:
        print(f"  {icon[status]} {status:5} - {name}")
    n_pass = sum(1 for _, s in results if s == "PASS")
    n_fail = len(results) - n_pass
    print("-" * 70)
    print(f"  通过 {n_pass}/{len(results)}")
    print("=" * 70)

    sys.exit(0 if n_fail == 0 else 1)
