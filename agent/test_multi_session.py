# test_multi_session.py
"""
测试多会话隔离：验证不同 session_id 的会话互不干扰
"""

from dotenv import load_dotenv
import sys
import os

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mini_agent_runtime import MiniAgentRuntime, ToolRegistry
from mini_agent_tools import calculator_tool, CALCULATOR_SCHEMA
from my_llm import MyLLM

load_dotenv()


def test_multi_session_isolation():
    """测试多会话隔离"""
    print("\n" + "="*80)
    print("测试：多个独立会话的隔离性")
    print("="*80)

    # 创建 Agent
    tool_registry = ToolRegistry()
    tool_registry.register("calculator", "执行数学计算", CALCULATOR_SCHEMA, calculator_tool)
    llm = MyLLM()
    agent = MiniAgentRuntime(llm, tool_registry, max_iterations=3)

    print("\n" + "-"*80)
    print("场景：两个用户(Alice 和 Bob)同时使用 Agent，各自的会话应该互不干扰")
    print("-"*80)

    # === Alice 的会话 ===
    print("\n👤 Alice 的第一轮对话（session-alice）")
    alice_session = "session-alice"
    alice_r1 = agent.run("请帮我计算 50 + 50", session_id=alice_session)
    print(f"💬 Alice 收到回答: {alice_r1[:100]}...")

    # === Bob 的会话（此时 Alice 的会话还在） ===
    print("\n👤 Bob 的第一轮对话（session-bob）")
    bob_session = "session-bob"
    bob_r1 = agent.run("请帮我计算 10 * 10", session_id=bob_session)
    print(f"💬 Bob 收到回答: {bob_r1[:100]}...")

    # === Alice 的第二轮：引用"刚才的结果" ===
    print("\n👤 Alice 的第二轮对话（应该记住她自己的 50+50=100）")
    alice_r2 = agent.run("把刚才的结果乘以3", session_id=alice_session)
    print(f"💬 Alice 收到回答: {alice_r2[:100]}...")

    # === Bob 的第二轮：引用"刚才的结果" ===
    print("\n👤 Bob 的第二轮对话（应该记住他自己的 10*10=100）")
    bob_r2 = agent.run("把刚才的结果加上5", session_id=bob_session)
    print(f"💬 Bob 收到回答: {bob_r2[:100]}...")

    # === 验证结果 ===
    print("\n" + "="*80)
    print("✅ 验证结果")
    print("="*80)

    # Alice: 50+50=100, 100*3=300
    print(f"Alice 的完整对话:")
    print(f"  第1轮: 50 + 50 → {alice_r1}")
    print(f"  第2轮: 刚才结果(100) * 3 → {alice_r2}")
    if "300" in alice_r2:
        print("  ✅ Alice 的上下文正确（100 * 3 = 300）")
    else:
        print("  ❌ Alice 的上下文可能有误")

    # Bob: 10*10=100, 100+5=105
    print(f"\nBob 的完整对话:")
    print(f"  第1轮: 10 * 10 → {bob_r1}")
    print(f"  第2轮: 刚才结果(100) + 5 → {bob_r2}")
    if "105" in bob_r2:
        print("  ✅ Bob 的上下文正确（100 + 5 = 105）")
    else:
        print("  ❌ Bob 的上下文可能有误")

    # 判断是否隔离
    if "300" in alice_r2 and "105" in bob_r2:
        print("\n🎉 多会话隔离测试通过！Alice 和 Bob 的会话完全独立。")
        return True
    else:
        print("\n⚠️ 多会话隔离可能存在问题，请检查 SessionManager 实现。")
        return False


def test_session_context_length():
    """测试会话上下文长度限制"""
    print("\n" + "="*80)
    print("测试：会话上下文长度限制（get_context 的 max_turns 参数）")
    print("="*80)

    tool_registry = ToolRegistry()
    tool_registry.register("calculator", "执行数学计算", CALCULATOR_SCHEMA, calculator_tool)
    llm = MyLLM()
    agent = MiniAgentRuntime(llm, tool_registry, max_iterations=3)

    session_id = "test-context-limit"

    print("\n进行 5 轮对话，测试上下文是否正确保留...")
    for i in range(1, 6):
        question = f"请计算 {i} + {i}"
        response = agent.run(question, session_id=session_id)
        print(f"  第{i}轮: {question} → {response[:50]}...")

    print("\n第6轮：询问之前的结果")
    response = agent.run("刚才第1轮的结果是多少？", session_id=session_id)
    print(f"  回答: {response[:100]}...")

    if "2" in response:  # 第1轮: 1+1=2
        print("✅ 上下文保留测试通过")
    else:
        print("⚠️ 可能超出上下文窗口，或模型未能理解历史")


if __name__ == "__main__":
    print("\n" + "🔬"*40)
    print("Mini Agent - 多会话管理专项测试")
    print("🔬"*40)

    try:
        # 测试1：多会话隔离
        test_multi_session_isolation()

        # 测试2：上下文长度
        test_session_context_length()

    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()

    print("\n" + "🎉"*40)
    print("测试完成")
    print("🎉"*40)
