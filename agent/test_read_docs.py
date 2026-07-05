# test_read_docs.py
"""
read_docs 工具测试

覆盖两个层面：
  1. 工具函数单元测试（正常读取 + 安全边界：路径穿越、扩展名白名单、大文件截断）
  2. Agent 集成测试（LLM 能否正确调用 read_docs 工具读取文档）
"""

from dotenv import load_dotenv
import sys
import os
import tempfile

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mini_agent_tools
from mini_agent_tools import read_docs, READ_DOCS_SCHEMA
from mini_agent_runtime import MiniAgentRuntime, ToolRegistry
from my_llm import MyLLM

load_dotenv()


# ============================================================
# 第一部分：工具函数单元测试（不依赖 LLM）
# ============================================================

def test_read_existing_file():
    """正常读取一个存在的文档"""
    print("\n--- 测试1: 读取存在的文件 (README.md) ---")
    result = read_docs("README.md")
    assert result.startswith("📄"), f"应成功读取，实际: {result[:80]}"
    assert "README.md" in result
    print(f"✅ 通过。返回前80字符: {result[:80]}...")


def test_file_not_found():
    """读取不存在的文件应返回错误"""
    print("\n--- 测试2: 读取不存在的文件 ---")
    result = read_docs("no_such_file_xyz.md")
    assert result.startswith("❌") and "不存在" in result, f"实际: {result}"
    print(f"✅ 通过: {result}")


def test_path_traversal_blocked():
    """路径穿越攻击应被拒绝（安全关键）"""
    print("\n--- 测试3: 路径穿越攻击防护 ---")
    attacks = [
        "../../../etc/passwd",
        "..\\..\\..\\Windows\\System32\\drivers\\etc\\hosts",
        "../my_llm.py",  # 试图跳出去读上层（虽然是 .py 但路径越界）
    ]
    for atk in attacks:
        result = read_docs(atk)
        # 要么因扩展名被拒，要么因越界被拒，总之不能成功读取
        assert result.startswith("❌"), f"攻击 '{atk}' 未被拦截！返回: {result[:80]}"
        print(f"   ✅ 已拦截: {atk} → {result[:50]}...")
    print("✅ 通过：所有路径穿越尝试均被拒绝")


def test_extension_whitelist():
    """非白名单扩展名应被拒绝"""
    print("\n--- 测试4: 扩展名白名单 ---")
    result = read_docs("secret.exe")
    assert result.startswith("❌") and "不允许" in result, f"实际: {result}"
    print(f"✅ 通过: {result}")


def test_large_file_truncation():
    """超长文件应被截断"""
    print("\n--- 测试5: 大文件截断 ---")
    # 在文档目录临时造一个大文件
    root = mini_agent_tools.DOCS_ROOT
    big_path = os.path.join(root, "_temp_big_test.txt")
    try:
        with open(big_path, "w", encoding="utf-8") as f:
            f.write("A" * 20000)  # 2万字符，超过默认 8000

        result = read_docs("_temp_big_test.txt")
        assert "已截断" in result, f"应触发截断，实际: {result[:120]}"
        print(f"✅ 通过：大文件被正确截断")
    finally:
        if os.path.exists(big_path):
            os.remove(big_path)


def test_empty_filename():
    """空文件名应返回错误"""
    print("\n--- 测试6: 空文件名 ---")
    result = read_docs("   ")
    assert result.startswith("❌"), f"实际: {result}"
    print(f"✅ 通过: {result}")


def run_unit_tests():
    """运行所有单元测试"""
    print("\n" + "=" * 80)
    print("第一部分：read_docs 工具函数单元测试")
    print("=" * 80)

    tests = [
        test_read_existing_file,
        test_file_not_found,
        test_path_traversal_blocked,
        test_extension_whitelist,
        test_large_file_truncation,
        test_empty_filename,
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
# 第二部分：Agent 集成测试（依赖 LLM）
# ============================================================

def test_agent_reads_doc():
    """测试 Agent 能否调用 read_docs 工具读取文档"""
    print("\n" + "=" * 80)
    print("第二部分：Agent 集成测试 - 让 Agent 读取文档")
    print("=" * 80)

    # 先在文档目录放一个内容确定的测试文件，便于验证
    root = mini_agent_tools.DOCS_ROOT
    test_doc = os.path.join(root, "_agent_test_doc.md")
    with open(test_doc, "w", encoding="utf-8") as f:
        f.write("# 项目说明\n\n本项目的作者是张三，版本号是 v2.5.0。\n")

    try:
        registry = ToolRegistry()
        registry.register(
            "read_docs",
            "读取文档目录内的文本文件，参数 filename 为文件名",
            READ_DOCS_SCHEMA,
            read_docs
        )
        llm = MyLLM()
        agent = MiniAgentRuntime(llm, registry, max_iterations=4)

        question = "请阅读 _agent_test_doc.md 这个文件，告诉我项目的版本号是多少？"
        response = agent.run(question)

        print(f"\n🎯 Agent 最终回答: {response}")

        if "2.5.0" in response or "v2.5.0" in response:
            print("✅ 通过：Agent 成功读取文档并回答出正确版本号")
            return True
        else:
            print("⚠️ Agent 回答中未包含预期版本号，可能是小模型理解偏差")
            return False
    finally:
        if os.path.exists(test_doc):
            os.remove(test_doc)


if __name__ == "__main__":
    print("\n" + "📖" * 40)
    print("read_docs 工具完整测试")
    print("📖" * 40)

    unit_ok = run_unit_tests()

    try:
        test_agent_reads_doc()
    except Exception as e:
        print(f"\n❌ 集成测试异常: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "🎉" * 40)
    print("测试完成")
    print("🎉" * 40)
