# test_context_management.py
"""
Context 管理测试

覆盖需求：
  1. 最大轮次限制         - get_context(max_turns) 只保留最近 N 轮
  2. 记住之前的状态        - 多轮对话历史被正确保留并传回
  3. 纯对话追问           - 无工具场景下能引用上文
  4. 带工具的追问         - 工具结果进入上下文，后续追问可引用
  5. 单条消息截断          - 超长单条消息（如长文档）被截断
  6. 总长度基础压缩        - 超出字符预算时丢弃最旧消息并插入压缩提示

单元测试部分不依赖 LLM，断言稳定；集成测试部分验证真实追问效果。
"""

from dotenv import load_dotenv
import sys
import os

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mini_agent_runtime import Session, Message, MiniAgentRuntime, ToolRegistry
from mini_agent_tools import calculator_tool, CALCULATOR_SCHEMA
from my_llm import MyLLM

load_dotenv()


# ============================================================
# 第一部分：Session.get_context 单元测试（不依赖 LLM）
# ============================================================

def test_max_turns_limit():
    """测试1: 最大轮次限制"""
    print("\n--- 测试1: 最大轮次限制 ---")
    session = Session(session_id="t1")
    # 造 10 轮对话 = 20 条消息
    for i in range(10):
        session.add_message(Message(role="user", content=f"问题{i}"))
        session.add_message(Message(role="assistant", content=f"回答{i}"))

    # 只要最近 3 轮 = 6 条
    context = session.get_context(max_turns=3)
    assert len(context) == 6, f"期望 6 条，实际 {len(context)}"
    # 应保留的是最后 3 轮（问题7~9）
    assert context[0]["content"] == "问题7", f"实际: {context[0]['content']}"
    assert context[-1]["content"] == "回答9"
    print(f"✅ 通过：20 条消息中正确保留最近 3 轮（6 条），最早为 '{context[0]['content']}'")


def test_state_memory():
    """测试2: 记住之前的状态（历史完整保留）"""
    print("\n--- 测试2: 记住之前的状态 ---")
    session = Session(session_id="t2")
    session.add_message(Message(role="user", content="我叫小明"))
    session.add_message(Message(role="assistant", content="你好小明"))
    session.add_message(Message(role="user", content="我叫什么？"))

    context = session.get_context(max_turns=10)
    contents = [c["content"] for c in context]
    assert "我叫小明" in contents, "早期状态丢失"
    assert len(context) == 3
    print(f"✅ 通过：历史状态完整保留，context 含 {len(context)} 条消息")


def test_single_message_truncation():
    """测试5: 单条超长消息截断"""
    print("\n--- 测试5: 单条消息截断 ---")
    session = Session(session_id="t5")
    long_text = "X" * 5000  # 5000 字符的长工具结果
    session.add_message(Message(role="tool", content=long_text))

    context = session.get_context(max_turns=10, max_msg_chars=2000)
    truncated = context[0]["content"]
    assert len(truncated) < 5000, "超长消息未被截断"
    assert "已截断" in truncated, "缺少截断提示"
    print(f"✅ 通过：5000 字符消息被截断至 {len(truncated)} 字符并带提示")


def test_total_length_compression():
    """测试6: 总长度超预算时压缩（丢弃最旧 + 插入提示）"""
    print("\n--- 测试6: 总长度基础压缩 ---")
    session = Session(session_id="t6")
    # 造 8 条各 500 字符的消息，总计约 4000 字符
    for i in range(8):
        role = "user" if i % 2 == 0 else "assistant"
        session.add_message(Message(role=role, content=f"[msg{i}]" + "Y" * 500))

    # 预算设为 1500 字符，且单条不截断（max_msg_chars 调大）
    context = session.get_context(
        max_turns=10, max_chars=1500, max_msg_chars=10000, keep_recent=2
    )

    # 应插入了一条压缩提示
    assert context[0]["role"] == "system", "缺少压缩提示消息"
    assert "上下文压缩" in context[0]["content"], "压缩提示内容不对"

    # 总长度应被控制在预算附近（提示本身有长度，允许略超）
    total = sum(len(c["content"]) for c in context)
    print(f"   压缩后消息数: {len(context)}，总字符: {total}")

    # 最近的消息必须保留（msg7）
    all_text = " ".join(c["content"] for c in context)
    assert "[msg7]" in all_text, "最近消息被误删"
    # 最早的消息应被丢弃（msg0）
    assert "[msg0]" not in all_text, "最旧消息未被压缩"
    print(f"✅ 通过：丢弃最旧消息、保留最近消息、插入压缩提示")


def test_no_compression_when_under_budget():
    """测试7: 未超预算时不压缩"""
    print("\n--- 测试7: 未超预算不压缩 ---")
    session = Session(session_id="t7")
    session.add_message(Message(role="user", content="短消息1"))
    session.add_message(Message(role="assistant", content="短消息2"))

    context = session.get_context(max_turns=10, max_chars=10000)
    assert len(context) == 2, f"不应压缩，实际 {len(context)} 条"
    assert context[0]["role"] == "user", "不应有压缩提示"
    print("✅ 通过：内容在预算内，未触发压缩")


def run_unit_tests():
    print("\n" + "=" * 80)
    print("第一部分：Context 管理单元测试（不依赖 LLM）")
    print("=" * 80)

    tests = [
        test_max_turns_limit,
        test_state_memory,
        test_single_message_truncation,
        test_total_length_compression,
        test_no_compression_when_under_budget,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"❌ {t.__name__} 失败: {e}")
        except Exception as e:
            print(f"❌ {t.__name__} 异常: {e}")
    print(f"\n单元测试结果: {passed}/{len(tests)} 通过")
    return passed == len(tests)


# ============================================================
# 第二部分：追问集成测试（依赖 LLM）
# ============================================================

def test_pure_dialogue_followup():
    """测试3: 纯对话追问（无工具）"""
    print("\n" + "=" * 80)
    print("第二部分-A：纯对话追问")
    print("=" * 80)

    registry = ToolRegistry()  # 不注册任何工具
    agent = MiniAgentRuntime(MyLLM(), registry, max_iterations=3)
    sid = "followup-pure"

    agent.run("我最喜欢的颜色是蓝色，请记住。", session_id=sid)
    resp = agent.run("我最喜欢的颜色是什么？", session_id=sid)
    print(f"\n🎯 追问回答: {resp}")

    if "蓝" in resp:
        print("✅ 通过：Agent 记住了上文提到的颜色")
        return True
    print("⚠️ 未能正确追问（小模型可能理解偏差）")
    return False


def test_tool_followup():
    """测试4: 带工具的追问"""
    print("\n" + "=" * 80)
    print("第二部分-B：带工具的追问")
    print("=" * 80)

    registry = ToolRegistry()
    registry.register("calculator", "执行数学计算", CALCULATOR_SCHEMA, calculator_tool)
    agent = MiniAgentRuntime(MyLLM(), registry, max_iterations=4)
    sid = "followup-tool"

    r1 = agent.run("帮我算 88 + 12", session_id=sid)
    print(f"\n🎯 第一轮: {r1}")
    r2 = agent.run("把刚才的结果再乘以10", session_id=sid)
    print(f"🎯 追问结果: {r2}")

    # 88+12=100, 100*10=1000
    if "1000" in r2:
        print("✅ 通过：带工具的追问正确（100 * 10 = 1000）")
        return True
    print("⚠️ 带工具追问结果不符预期")
    return False


if __name__ == "__main__":
    print("\n" + "🧠" * 40)
    print("Context 管理完整测试")
    print("🧠" * 40)

    run_unit_tests()

    try:
        test_pure_dialogue_followup()
        test_tool_followup()
    except Exception as e:
        print(f"\n❌ 集成测试异常: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "🎉" * 40)
    print("测试完成")
    print("🎉" * 40)
