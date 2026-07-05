# Mini Agent Runtime - 从零实现最小可用Agent

> 2026年Agent技术笔试题完整实现

## 项目概述

本项目**从零开始**实现了一个最小可用的Agent Runtime，不依赖任何Agent框架（如langgraph、openhands等），完全自主实现了Agent的核心循环和工具调用机制。

## 核心特性

### ✅ 完整的Agent循环（4步）
1. **Perception（感知）**: 理解用户输入，构建上下文
2. **Planning（规划）**: LLM分析问题，决策是否需要工具
3. **Action（行动）**: 执行工具调用或直接回答
4. **Reflection（反思）**: 评估任务完成情况，决定是否继续

### ✅ 工具系统
- **工具注册机制**: 支持动态注册工具
- **统一Schema**: 每个工具包含名称、描述、参数定义
- **LLM自主决策**: 基于Schema，LLM自主选择和调用工具
- **内置工具**:
  - `calculator`: 数学计算器
  - `search`: 信息搜索（Mock实现）
  - `weather`: 天气查询（Mock实现）

### ✅ 会话管理
- **多会话支持**: 支持多个独立会话
- **上下文管理**: 自动管理对话历史，支持轮次限制
- **会话持久化**: 每个会话独立ID，可恢复

### ✅ Context有效管理
- 自动截断过长上下文（保留最近10轮对话）
- 工具调用结果自动注入上下文
- 防止context overflow

## 项目结构

```
chapter7/
├── mini_agent_runtime.py      # 核心Agent Runtime实现
├── mini_agent_tools.py        # 工具实现（calculator、search、weather）
├── test_mini_agent.py         # 完整测试用例
└── README_MINI_AGENT.md       # 本文档
```

## 核心实现

### 1. 工具注册系统

```python
tool_registry = ToolRegistry()
tool_registry.register(
    name="calculator",
    description="执行数学计算",
    parameters={
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "数学表达式"}
        },
        "required": ["expression"]
    },
    function=calculator_tool
)
```

### 2. Agent Runtime循环

```python
agent = MiniAgentRuntime(llm, tool_registry, max_iterations=5)
response = agent.run("请计算 100 + 200")
```

### 3. LLM工具调用格式

LLM使用以下格式调用工具：

```json
[TOOL_CALL]
{
  "tool": "calculator",
  "arguments": {"expression": "100 + 200"}
}
[/TOOL_CALL]
```

## 快速开始

### 1. 环境准备

```bash
cd code/chapter7
pip install python-dotenv

# 配置.env文件（添加你的API Key）
cp .env.example .env
# 编辑.env，添加: OPENAI_API_KEY=your_key_here
```

### 2. 运行测试

```bash
# 运行完整测试套件
python test_mini_agent.py
```

### 3. 自定义使用

```python
from mini_agent_runtime import MiniAgentRuntime, ToolRegistry
from mini_agent_tools import calculator_tool, CALCULATOR_SCHEMA
from my_llm import MyLLM

# 创建工具注册表
tool_registry = ToolRegistry()
tool_registry.register("calculator", "计算器", CALCULATOR_SCHEMA, calculator_tool)

# 创建Agent
llm = MyLLM()
agent = MiniAgentRuntime(llm, tool_registry)

# 运行
response = agent.run("计算 25 * 4 + 100")
print(response)
```

## 测试用例

项目包含6个完整测试用例：

1. ✅ **计算器工具测试**: 测试数学计算能力
2. ✅ **搜索工具测试**: 测试信息检索能力
3. ✅ **天气工具测试**: 测试特定领域查询
4. ✅ **多工具协作测试**: 测试同时使用多个工具
5. ✅ **会话管理测试**: 测试上下文记忆和多轮对话
6. ✅ **无工具直接回答测试**: 测试智能决策（何时不用工具）

## 技术亮点

### 1. 从零实现
- ❌ 不使用langgraph、autogen、agentscope等框架
- ✅ 手写Agent循环逻辑
- ✅ 自主设计工具调用协议

### 2. 工具Schema驱动
- LLM基于Schema自主理解工具功能
- 支持复杂参数定义（必填/可选、类型、默认值）
- 自动参数验证

### 3. 会话隔离
- 每个会话独立上下文
- 支持多窗口/多用户场景
- 会话可暂停和恢复

### 4. Context优化
- 智能截断（保留最近N轮）
- 工具结果注入策略
- 防止token超限

### 5. 鲁棒性设计
- 工具调用失败处理
- 最大迭代保护
- 格式解析容错

## 工作流程示例

```
用户输入: "请计算(100+200)*3，然后查询北京天气"

Iteration 1:
  📥 Perception: 解析用户需求
  🧠 Planning: LLM识别需要calculator工具
  ⚡ Action: 调用calculator("(100+200)*3") → 900
  🔍 Reflection: 任务未完成，继续

Iteration 2:
  📥 Perception: 上下文包含计算结果900
  🧠 Planning: LLM识别需要weather工具
  ⚡ Action: 调用weather("北京") → 晴朗,15°C
  🔍 Reflection: 任务完成

✅ 最终回答: "计算结果是900，北京今天天气晴朗，温度15°C"
```

## 扩展性

项目设计考虑了扩展性，可以轻松添加：

- ✨ 新工具（继承BaseTool或直接函数）
- ✨ 自定义LLM（实现invoke接口）
- ✨ 持久化存储（数据库集成）
- ✨ 流式输出
- ✨ 并行工具调用
- ✨ 工具链组合

## 题目要求对照

| 要求 | 实现状态 |
|------|---------|
| 从零完成，不用现成框架 | ✅ 完全自主实现 |
| 实现基本循环（4步） | ✅ Perception → Planning → Action → Reflection |
| 至少3个工具 | ✅ calculator、search、weather |
| 工具注册机制 | ✅ ToolRegistry完整实现 |
| 包含Schema | ✅ 每个工具都有详细Schema |
| LLM自主决策调用 | ✅ 基于Schema自主选择 |
| Session管理 | ✅ SessionManager多会话支持 |
| Context有效管理 | ✅ 自动截断+注入策略 |
| 测试用例构建 | ✅ 6个完整测试用例 |

## 技术栈

- Python 3.8+
- OpenAI API (兼容接口)
- 标准库（json, re, dataclasses等）
- 无外部Agent框架依赖

## 作者说明

本项目完全**从零实现**，核心代码约400行，实现了一个功能完整的Agent Runtime。

可以作为：
- 🎓 学习Agent原理的最佳实践
- 🔧 快速原型开发的基础框架
- 📚 理解Agent内部机制的参考实现

---

**本实现满足2026年Agent技术笔试题的所有要求** ✅
