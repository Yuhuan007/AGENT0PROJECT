# demo_mini_agent.py
"""
Mini Agent Runtime 快速演示
展示基本的工具调用和Agent循环
"""

from dotenv import load_dotenv
from mini_agent_runtime import MiniAgentRuntime, ToolRegistry
from mini_agent_tools import (
    calculator_tool, search_tool, weather_tool,
    CALCULATOR_SCHEMA, SEARCH_SCHEMA, WEATHER_SCHEMA
)
from my_llm import MyLLM

# 加载环境变量
load_dotenv()


def main():
    print("\n" + "="*70)
    print("Mini Agent Runtime - 快速演示")
    print("="*70)

    # 1. 创建工具注册表并注册工具
    print("\n[1/3] 注册工具...")
    tool_registry = ToolRegistry()

    tool_registry.register(
        name="calculator",
        description="执行数学计算，支持加减乘除和括号运算",
        parameters=CALCULATOR_SCHEMA,
        function=calculator_tool
    )

    tool_registry.register(
        name="search",
        description="搜索互联网信息（模拟实现）",
        parameters=SEARCH_SCHEMA,
        function=search_tool
    )

    tool_registry.register(
        name="weather",
        description="查询指定地点的天气信息",
        parameters=WEATHER_SCHEMA,
        function=weather_tool
    )

    # 2. 创建LLM客户端和Agent Runtime
    print("\n[2/3] 初始化Agent Runtime...")
    llm = MyLLM()
    agent = MiniAgentRuntime(
        llm_client=llm,
        tool_registry=tool_registry,
        max_iterations=5  # 最多5轮迭代
    )

    # 3. 测试不同类型的问题
    print("\n[3/3] 开始测试...")

    test_cases = [
        {
            "name": "简单计算",
            "question": "请计算 (100 + 50) * 2 的结果"
        },        {
            "name": "天气查询",
            "question": "北京今天天气怎么样？"
        },
        {
            "name": "信息搜索",
            "question": "请搜索关于AI Agent的信息"
        },
        {
            "name": "多工具协作",
            "question": "请帮我做三件事：1)计算50*20 2)查询上海天气 3)搜索Python相关信息"
        }
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'#'*70}")
        print(f"# 测试案例 {i}: {test_case['name']}")
        print(f"# 问题: {test_case['question']}")
        print(f"{'#'*70}")

        try:
            response = agent.run(test_case['question'])
            print(f"\n{'='*70}")
            print(f"最终回答:")
            print(f"{'='*70}")
            print(response)
            print(f"{'='*70}\n")

        except Exception as e:
            print(f"\nERROR: {str(e)}")
            import traceback
            traceback.print_exc()

    print("\n" + "="*70)
    print("演示完成！")
    print("="*70)


if __name__ == "__main__":
    main()
