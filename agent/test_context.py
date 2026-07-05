# test_context.py
"""
Context 管理专项测试 - 依次测试 6 项功能

  1. 最大轮次限制    - 超过 max_turns 的旧对话被丢弃
  2. 记住之前状态    - 多轮对话历史被完整保留并回传
  3. 纯对话追问      - 无工具场景下能引用上文（需 LLM）
  4. 带工具的追问    - 工具结果进入上下文，追问可引用（需 LLM）
  5. 单条消息截断    - 过长的单条消息（如长文档/工具结果）被截断
  6. 总长度压缩      - 超出字符预算时丢弃最旧消息并插入压缩提示

运行：
  python test_context.py           # 全部 6 项
  python test_context.py --offline # 只跑 1/2/5/6（不依赖 LLM）
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

OFFLINE = "--offline" in sys.argv


# ============================================================
# 功能 1：最大轮次限制
# ============================================================
def test_1_max_turns():
    print("\n" + "=" * 70)
    print("功能 1：最大轮次限制")
    print("=" * 70)

    session = Session(session_id="ctx-1")
    # 构造 10 轮对话（20 条消息）
    for i in range(10):
        session.add_message(Message(role="user", content=f"问题{i}"))
        session.add_message(Message(role="assistant", content=f"回答{i}"))

    # 限定只保留最近 3 轮
    context = session.get_context(max_turns=3)

    print(f"  原始消息数: {len(session.messages)} 条（10 轮）")
    print(f"  限定 max_turns=3 后: {len(context)} 条")
    print(f"  保留范围: '{context[0]['content']}' ~ '{context[-1]['content']}'")

    assert len(context) == 6, f"期望 6 条，实际 {len(context)}"
    assert context[0]["content"] == "问题7", "应从第 7 轮开始保留"
    assert context[-1]["content"] == "回答9", "应保留到最新一轮"
    print("  ✅ 通过：只保留最近 3 轮，更早的对话被丢弃")


# ============================================================
# 功能 2：记住之前状态
# ============================================================
def test_2_state_memory():
    print("\n" + "=" * 70)
    print("功能 2：记住之前的状态")
    print("=" * 70)

    session = Session(session_id="ctx-2")
    session.add_message(Message(role="user", content="我叫小明，是一名工程师"))
    session.add_message(Message(role="assistant", content="你好小明"))
    session.add_message(Message(role="user", content="今天天气不错"))
    session.add_message(Message(role="assistant", content="是的"))

    context = session.get_context(max_turns=10)
    contents = [c["content"] for c in context]

    print(f"  会话内消息数: {len(context)} 条")
    print(f"  首条内容: {contents[0]}")

    assert "我叫小明，是一名工程师" in contents, "早期状态丢失"
    assert len(context) == 4, "历史应完整保留"
    print("  ✅ 通过：早期对话状态（姓名/职业）完整保留在上下文中")


# ============================================================
# 功能 3：纯对话追问（需 LLM）
# ============================================================
def test_3_pure_followup():
    print("\n" + "=" * 70)
    print("功能 3：纯对话追问（无工具）")
    print("=" * 70)

    registry = ToolRegistry()  # 不注册工具
    agent = MiniAgentRuntime(MyLLM(), registry, max_iterations=3)
    sid = "ctx-3"

    print("  第一轮：告诉 Agent 一个信息")
    agent.run("请记住：我的项目代号是 Falcon。", session_id=sid)

    print("  第二轮：追问该信息")
    resp = agent.run("我的项目代号是什么？", session_id=sid)
    print(f"  追问回答: {resp}")

    assert "Falcon" in resp or "falcon" in resp.lower(), "未能记住上文信息"
    print("  ✅ 通过：纯对话追问能正确引用上文")


# ============================================================
# 功能 4：带工具的追问（需 LLM）
# ============================================================
def test_4_tool_followup():
    print("\n" + "=" * 70)
    print("功能 4：带工具的追问")
    print("=" * 70)

    registry = ToolRegistry()
    registry.register("calculator", "执行数学计算", CALCULATOR_SCHEMA, calculator_tool)
    agent = MiniAgentRuntime(MyLLM(), registry, max_iterations=4)
    sid = "ctx-4"

    print("  第一轮：用工具计算 200 + 300")
    r1 = agent.run("帮我算 200 + 300", session_id=sid)
    print(f"  第一轮回答: {r1}")

    print("  第二轮：追问，引用上一步结果")
    r2 = agent.run("把刚才的结果除以5", session_id=sid)
    print(f"  追问结果: {r2}")

    # 200+300=500, 500/5=100
    assert "100" in r2, "带工具的追问结果不符预期（应为 100）"
    print("  ✅ 通过：带工具的追问能引用上一步工具结果（500 / 5 = 100）")


# ============================================================
# 功能 5：单条消息截断
# ============================================================
def test_5_single_truncation():
    print("\n" + "=" * 70)
    print("功能 5：单条超长消息截断")
    print("=" * 70)

    session = Session(session_id="ctx-5")
    session.add_message(Message(role="user", content="请读取文档"))
    # 模拟一个超长工具结果（如 read_docs 读了大文件）
    session.add_message(Message(role="tool", content="文档内容:" + "D" * 6000))

    context = session.get_context(max_turns=10, max_msg_chars=2000)
    tool_msg = context[-1]["content"]

    print(f"  原始工具消息长度: 6006 字符")
    print(f"  截断后长度: {len(tool_msg)} 字符")

    assert len(tool_msg) < 6006, "超长消息未被截断"
    assert "已截断" in tool_msg, "截断后应附带提示"
    # 用户的短消息不受影响
    assert context[0]["content"] == "请读取文档", "短消息不应被截断"
    print("  ✅ 通过：超长工具结果被截断至 2000+ 字符并附提示，短消息不受影响")


# ============================================================
# 功能 6：总长度压缩
# ============================================================
def test_6_length_compression():
    print("\n" + "=" * 70)
    print("功能 6：总长度基础压缩")
    print("=" * 70)

    session = Session(session_id="ctx-6")
    # 造 8 条各 ~500 字符的消息
    for i in range(8):
        role = "user" if i % 2 == 0 else "assistant"
        session.add_message(Message(role=role, content=f"[消息{i}]" + "Z" * 500))

    # 预算 1500 字符，单条不截断以隔离测试总长度压缩
    context = session.get_context(
        max_turns=10, max_chars=1500, max_msg_chars=10000, keep_recent=2
    )

    total = sum(len(c["content"]) for c in context)
    all_text = " ".join(c["content"] for c in context)

    print(f"  原始: 8 条消息，约 4000 字符")
    print(f"  预算: 1500 字符")
    print(f"  压缩后: {len(context)} 条，总 {total} 字符")
    print(f"  首条角色: {context[0]['role']}")

    assert context[0]["role"] == "system", "应在开头插入压缩提示"
    assert "上下文压缩" in context[0]["content"], "压缩提示内容缺失"
    assert "[消息7]" in all_text, "最近消息必须保留"
    assert "[消息0]" not in all_text, "最旧消息应被压缩丢弃"
    print("  ✅ 通过：丢弃最旧消息、保留最近消息、开头插入压缩提示")


# ============================================================
# 主入口：依次运行 6 项
# ============================================================
if __name__ == "__main__":
    print("\n" + "🧠" * 35)
    print(f"Context 管理专项测试 {'(离线模式)' if OFFLINE else '(完整模式)'}")
    print("🧠" * 35)

    # (功能名, 测试函数, 是否需要 LLM)
    suite = [
        ("功能1-最大轮次限制", test_1_max_turns, False),
        ("功能2-记住之前状态", test_2_state_memory, False),
        ("功能3-纯对话追问", test_3_pure_followup, True),
        ("功能4-带工具的追问", test_4_tool_followup, True),
        ("功能5-单条消息截断", test_5_single_truncation, False),
        ("功能6-总长度压缩", test_6_length_compression, False),
    ]

    results = []
    for name, func, needs_llm in suite:
        if OFFLINE and needs_llm:
            results.append((name, "SKIP"))
            print(f"\n⏭️  跳过 {name}（离线模式）")
            continue
        try:
            func()
            results.append((name, "PASS"))
        except AssertionError as e:
            print(f"  ❌ 失败: {e}")
            results.append((name, "FAIL"))
        except Exception as e:
            print(f"  💥 异常: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, "ERROR"))

    # 汇总
    print("\n" + "=" * 70)
    print("📊 汇总")
    print("=" * 70)
    icon = {"PASS": "✅", "FAIL": "❌", "ERROR": "💥", "SKIP": "⏭️"}
    for name, status in results:
        print(f"  {icon[status]} {status:5} - {name}")

    n_pass = sum(1 for _, s in results if s == "PASS")
    n_fail = sum(1 for _, s in results if s in ("FAIL", "ERROR"))
    print("-" * 70)
    print(f"  通过 {n_pass} | 失败 {n_fail} | 跳过 {sum(1 for _, s in results if s == 'SKIP')}")
    print("=" * 70)

    sys.exit(0 if n_fail == 0 else 1)
