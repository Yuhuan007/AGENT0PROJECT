# test_mini_agent.py
"""
Mini Agent Runtime 测试用例
测试完整的Agent循环和工具调用
"""

from dotenv import load_dotenv
import sys
import os

# Windows 控制台默认 GBK 编码，强制 UTF-8 输出以支持 emoji 等字符
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# my_llm.py 位于上一级 chapter7/ 目录
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mini_agent_runtime import MiniAgentRuntime, ToolRegistry
from mini_agent_tools import (
    calculator_tool, search_tool, weather_tool,
    CALCULATOR_SCHEMA, SEARCH_SCHEMA, WEATHER_SCHEMA
)
from my_llm import MyLLM

# 加载环境变量
load_dotenv()


def test_calculator():
    """测试用例1: 计算器工具"""
    print("\n" + "="*80)
    print("测试用例1: 计算器工具测试")
    print("="*80)

    # 创建工具注册表
    tool_registry = ToolRegistry()
    tool_registry.register(
        name="calculator",
        description="执行数学计算，支持加减乘除和括号",
        parameters=CALCULATOR_SCHEMA,
        function=calculator_tool
    )

    # 创建LLM客户端和Agent Runtime
    llm = MyLLM()
    agent = MiniAgentRuntime(llm, tool_registry, max_iterations=3)

    # 测试问题
    question = "请帮我计算：(125 + 375) * 2 - 100 的结果是多少？"
# 
    # 运行Agent
    response = agent.run(question)

    print(f"\n🎯 最终回答: {response}\n")


def test_search():
    """测试用例2: 搜索工具"""
    print("\n" + "="*80)
    print("测试用例2: 搜索工具测试")
    print("="*80)

    tool_registry = ToolRegistry()
    tool_registry.register(
        name="search",        description="搜索互联网信息（模拟实现）",
        parameters=SEARCH_SCHEMA,
        function=search_tool
    )

    llm = MyLLM()
    agent = MiniAgentRuntime(llm, tool_registry, max_iterations=3)

    question = "请帮我搜索一下关于Python编程语言的信息"

    response = agent.run(question)

    print(f"\n🎯 最终回答: {response}\n")


def test_weather():
    """测试用例3: 天气查询工具"""
    print("\n" + "="*80)
    print("测试用例3: 天气查询工具测试")
    print("="*80)

    tool_registry = ToolRegistry()
    tool_registry.register(
        name="weather",
        description="查询指定地点的天气信息",
        parameters=WEATHER_SCHEMA,
        function=weather_tool
    )

    llm = MyLLM()
    agent = MiniAgentRuntime(llm, tool_registry, max_iterations=3)

    question = "北京今天天气怎么样？"

    response = agent.run(question)

    print(f"\n🎯 最终回答: {response}\n")


def test_multi_tools():
    """测试用例4: 多工具协作"""
    print("\n" + "="*80)
    print("测试用例4: 多工具协作测试")
    print("="*80)

    # 注册所有工具
    tool_registry = ToolRegistry()
    tool_registry.register("calculator", "执行数学计算", CALCULATOR_SCHEMA, calculator_tool)
    tool_registry.register("search", "搜索信息", SEARCH_SCHEMA, search_tool)
    tool_registry.register("weather", "查询天气", WEATHER_SCHEMA, weather_tool)

    llm = MyLLM()
    agent = MiniAgentRuntime(llm, tool_registry, max_iterations=5)

    question = "请先搜索一下Agent是什么，然后告诉我北京的天气，最后计算一下25*4的结果"

    response = agent.run(question)

    print(f"\n🎯 最终回答: {response}\n")


def test_session_management():
    """测试用例5: 会话管理测试"""
    print("\n" + "="*80)
    print("测试用例5: 会话管理测试")
    print("="*80)

    tool_registry = ToolRegistry()
    tool_registry.register("calculator", "执行数学计算", CALCULATOR_SCHEMA, calculator_tool)

    llm = MyLLM()
    agent = MiniAgentRuntime(llm, tool_registry, max_iterations=3)

    # 第一轮对话
    session_id = "test-session-001"
    response1 = agent.run("请帮我计算 100 + 200", session_id=session_id)
    print(f"\n🎯 第一轮回答: {response1}\n")

    # 第二轮对话（应该能记住上下文）
    response2 = agent.run("再把刚才的结果乘以2", session_id=session_id)
    print(f"\n🎯 第二轮回答: {response2}\n")


def test_no_tool_needed():
    """测试用例6: 无需工具的直接回答"""
    print("\n" + "="*80)
    print("测试用例6: 无需工具直接回答测试")
    print("="*80)

    tool_registry = ToolRegistry()
    tool_registry.register("calculator", "执行数学计算", CALCULATOR_SCHEMA, calculator_tool)

    llm = MyLLM()
    agent = MiniAgentRuntime(llm, tool_registry, max_iterations=3)

    question = "你好，请介绍一下你自己"

    response = agent.run(question)

    print(f"\n🎯 最终回答: {response}\n")


if __name__ == "__main__":
    print("\n" + "🚀"*40)
    print("Mini Agent Runtime 完整测试套件")
    print("🚀"*40)

    # 运行所有测试
    tests = [
        ("计算器工具", test_calculator),
        ("搜索工具", test_search),
        ("天气工具", test_weather),
        ("多工具协作", test_multi_tools),
        ("会话管理", test_session_management),
        ("无工具直接回答", test_no_tool_needed)
    ]

    for i, (name, test_func) in enumerate(tests, 1):
        try:
            print(f"\n\n{'#'*80}")
            print(f"# 运行测试 {i}/{len(tests)}: {name}")
            print(f"{'#'*80}")
            test_func()
            print(f"✅ 测试 {name} 通过")
        except Exception as e:
            print(f"❌ 测试 {name} 失败: {str(e)}")
            import traceback
            traceback.print_exc()

    print("\n" + "🎉"*40)
    print("所有测试完成！")
    print("🎉"*40)
