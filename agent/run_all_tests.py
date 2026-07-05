# run_all_tests.py
"""
总测试入口 - 聚合运行所有测试套件并汇总结果

包含的测试模块：
  1. test_mini_agent          - 基础功能（计算器/搜索/天气/多工具/会话/直接回答）
  2. test_multi_session       - 多会话隔离 + 上下文长度
  3. test_multi_window        - 多窗口独立会话（待办按会话隔离）
  4. test_read_docs           - read_docs 工具（含安全边界）
  5. test_context_management  - context 管理（轮次限制/截断/压缩/追问）

用法：
  python run_all_tests.py           # 运行全部
  python run_all_tests.py --fast    # 只跑不依赖 LLM 的单元测试（快速、离线）
"""

from dotenv import load_dotenv
import sys
import os
import traceback

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

# 导入各测试模块的测试函数
import test_context_management as ctx
import test_read_docs as docs
import test_multi_session as msession
import test_multi_window as mwindow


# 是否只跑离线单元测试（不消耗 LLM 调用）
FAST_MODE = "--fast" in sys.argv


# 测试注册表：(套件名, 测试函数, 是否需要 LLM)
TEST_SUITES = [
    # ---- Context 管理：单元测试（离线）----
    ("Context-轮次限制", ctx.test_max_turns_limit, False),
    ("Context-记住状态", ctx.test_state_memory, False),
    ("Context-单条截断", ctx.test_single_message_truncation, False),
    ("Context-长度压缩", ctx.test_total_length_compression, False),
    ("Context-未超预算不压缩", ctx.test_no_compression_when_under_budget, False),
    # ---- read_docs：单元测试（离线）----
    ("ReadDocs-读取文件", docs.test_read_existing_file, False),
    ("ReadDocs-文件不存在", docs.test_file_not_found, False),
    ("ReadDocs-路径穿越防护", docs.test_path_traversal_blocked, False),
    ("ReadDocs-扩展名白名单", docs.test_extension_whitelist, False),
    ("ReadDocs-大文件截断", docs.test_large_file_truncation, False),
    ("ReadDocs-空文件名", docs.test_empty_filename, False),
    # ---- 需要 LLM 的集成测试 ----
    ("Context-纯对话追问", ctx.test_pure_dialogue_followup, True),
    ("Context-带工具追问", ctx.test_tool_followup, True),
    ("ReadDocs-Agent读文档", docs.test_agent_reads_doc, True),
    ("会话隔离-多会话", msession.test_multi_session_isolation, True),
    ("会话隔离-上下文长度", msession.test_session_context_length, True),
    ("多窗口-独立会话", mwindow.test_two_windows_isolated, True),
]


def run_suite():
    """运行所有测试套件并汇总"""
    print("\n" + "🚀" * 40)
    print(f"Mini Agent - 总测试套件 {'(FAST 离线模式)' if FAST_MODE else '(完整模式)'}")
    print("🚀" * 40)

    results = []  # (名称, 状态: PASS/FAIL/SKIP/ERROR)

    for i, (name, func, needs_llm) in enumerate(TEST_SUITES, 1):
        # FAST 模式跳过需要 LLM 的测试
        if FAST_MODE and needs_llm:
            results.append((name, "SKIP"))
            continue

        print(f"\n\n{'#' * 80}")
        print(f"# [{i}/{len(TEST_SUITES)}] {name} {'(需LLM)' if needs_llm else '(离线)'}")
        print(f"{'#' * 80}")

        try:
            ret = func()
            # 有的函数用 assert（返回 None 视为通过），有的返回 bool
            if ret is False:
                results.append((name, "FAIL"))
            else:
                results.append((name, "PASS"))
        except AssertionError as e:
            print(f"❌ 断言失败: {e}")
            results.append((name, "FAIL"))
        except Exception as e:
            print(f"❌ 运行异常: {e}")
            traceback.print_exc()
            results.append((name, "ERROR"))

    # ---- 汇总报告 ----
    print("\n\n" + "=" * 80)
    print("📊 测试汇总报告")
    print("=" * 80)

    icon = {"PASS": "✅", "FAIL": "❌", "ERROR": "💥", "SKIP": "⏭️"}
    for name, status in results:
        print(f"  {icon.get(status, '?')} {status:6} - {name}")

    n_pass = sum(1 for _, s in results if s == "PASS")
    n_fail = sum(1 for _, s in results if s in ("FAIL", "ERROR"))
    n_skip = sum(1 for _, s in results if s == "SKIP")

    print("-" * 80)
    print(f"  总计: {len(results)} 项 | ✅ 通过 {n_pass} | ❌ 失败 {n_fail} | ⏭️ 跳过 {n_skip}")
    print("=" * 80)

    if n_fail == 0:
        print("\n🎉 所有已运行的测试全部通过！")
    else:
        print(f"\n⚠️ 有 {n_fail} 项测试未通过，请检查上面的详细输出。")

    # 返回码：有失败则非 0，便于 CI 集成
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    exit_code = run_suite()
    sys.exit(exit_code)
