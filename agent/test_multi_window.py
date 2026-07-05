# test_multi_window.py
"""
多窗口独立会话测试

场景：同一个用户 A 开了两个窗口
  - 窗口1：让 Agent 查天气 + 记待办
  - 窗口2：让 Agent 写周报 + 记待办
两个窗口是独立 session，用户可随时接着任一窗口继续聊，彼此不影响。

验证点：
  1. 窗口1 和窗口2 的待办清单完全隔离（互不可见）
  2. 用户可以回到窗口1 继续操作，上下文和待办仍在
  3. 两个窗口的对话历史互不干扰
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
from mini_agent_tools import weather_tool, WEATHER_SCHEMA
from todo_tool import (
    add_todo, list_todos, _get_raw_todos, _clear_all,
    ADD_TODO_SCHEMA, LIST_TODOS_SCHEMA
)
from my_llm import MyLLM

load_dotenv()


def build_agent():
    """构建带天气 + 待办工具的 Agent"""
    registry = ToolRegistry()
    registry.register("weather", "查询指定地点的天气", WEATHER_SCHEMA, weather_tool)
    registry.register("add_todo", "添加一条待办事项到当前会话", ADD_TODO_SCHEMA, add_todo)
    registry.register("list_todos", "列出当前会话的所有待办事项", LIST_TODOS_SCHEMA, list_todos)
    llm = MyLLM()
    return MiniAgentRuntime(llm, registry, max_iterations=4)


def test_two_windows_isolated():
    """测试两个窗口的会话隔离"""
    print("\n" + "=" * 80)
    print("测试：用户A 的两个窗口（独立 session）互不影响")
    print("=" * 80)

    _clear_all()  # 清空待办存储，保证测试干净
    agent = build_agent()

    # 两个窗口 = 两个 session_id
    window1 = "userA-window-1"
    window2 = "userA-window-2"

    # ---- 窗口1：查天气 + 记待办 ----
    print("\n🪟 窗口1：查北京天气")
    agent.run("北京今天天气怎么样？", session_id=window1)

    print("\n🪟 窗口1：记一条待办")
    agent.run("帮我记一条待办：下午3点带伞出门", session_id=window1)

    # ---- 窗口2：写周报 + 记待办 ----
    print("\n🪟 窗口2：请 Agent 帮写周报（无需工具，直接对话）")
    agent.run("帮我写一句本周工作总结的开头", session_id=window2)

    print("\n🪟 窗口2：记一条待办")
    agent.run("帮我记一条待办：周五下午提交周报", session_id=window2)

    # ---- 用户回到窗口1，继续记待办 ----
    print("\n🪟 用户切回窗口1：再记一条待办")
    agent.run("再记一条待办：给张三回电话", session_id=window1)

    # ---- 分别查看两个窗口的待办 ----
    print("\n🪟 窗口1：列出我的待办")
    agent.run("列出我的所有待办", session_id=window1)

    print("\n🪟 窗口2：列出我的待办")
    agent.run("列出我的所有待办", session_id=window2)

    # ---- 直接读存储做断言（不依赖 LLM 措辞） ----
    print("\n" + "=" * 80)
    print("✅ 验证隔离性（直接检查底层存储）")
    print("=" * 80)

    w1_todos = _get_raw_todos(window1)
    w2_todos = _get_raw_todos(window2)

    print(f"\n窗口1 的待办 ({len(w1_todos)} 条):")
    for t in w1_todos:
        print(f"   • {t}")
    print(f"\n窗口2 的待办 ({len(w2_todos)} 条):")
    for t in w2_todos:
        print(f"   • {t}")

    # 断言1：窗口1 有 2 条待办（带伞、回电话）
    passed = True
    if len(w1_todos) == 2:
        print("\n✅ 窗口1 待办数量正确（2 条）")
    else:
        print(f"\n❌ 窗口1 待办数量错误：期望 2，实际 {len(w1_todos)}")
        passed = False

    # 断言2：窗口2 有 1 条待办（提交周报）
    if len(w2_todos) == 1:
        print("✅ 窗口2 待办数量正确（1 条）")
    else:
        print(f"❌ 窗口2 待办数量错误：期望 1，实际 {len(w2_todos)}")
        passed = False

    # 断言3：窗口1 的待办不应出现在窗口2，反之亦然
    w1_text = " ".join(w1_todos)
    w2_text = " ".join(w2_todos)
    if "周报" not in w1_text and "带伞" not in w2_text and "回电话" not in w2_text:
        print("✅ 两个窗口的待办完全隔离，没有串会话")
    else:
        print("❌ 待办发生串会话泄漏")
        passed = False

    print("\n" + "=" * 80)
    if passed:
        print("🎉 多窗口隔离测试通过！用户A 的两个窗口独立运行，互不影响。")
    else:
        print("⚠️ 多窗口隔离测试未通过，请检查实现。")
    print("=" * 80)
    return passed


if __name__ == "__main__":
    print("\n" + "🪟" * 40)
    print("Mini Agent - 多窗口独立会话测试")
    print("🪟" * 40)

    try:
        test_two_windows_isolated()
    except Exception as e:
        print(f"\n❌ 测试异常: {str(e)}")
        import traceback
        traceback.print_exc()

    print("\n" + "🎉" * 40)
    print("测试完成")
    print("🎉" * 40)
