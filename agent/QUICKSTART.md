# 快速开始指南

## 5分钟快速体验 Mini Agent Runtime

### 第一步：检查环境

```bash
# 确保Python 3.8+
python --version

# 确保已经在chapter7目录
cd d:/Desktop/hello-agents-main/code/chapter7

# 检查必要文件
ls mini_agent_runtime.py mini_agent_tools.py demo_mini_agent.py
```

### 第二步：配置API Key

编辑 `.env` 文件，添加你的OpenAI API Key：

```bash
OPENAI_API_KEY=sk-your-api-key-here
```

或者如果使用其他兼容OpenAI的API：

```bash
OPENAI_API_KEY=your-key
LLM_BASE_URL=https://your-api-endpoint/v1
```

### 第三步：运行演示

```bash
python demo_mini_agent.py
```

你将看到4个测试案例的完整执行过程！

### 第四步：运行完整测试（可选）

```bash
python test_mini_agent.py
```

这会运行6个测试用例，覆盖所有功能。

---

## 自己动手试一试

### 示例1：简单使用

创建文件 `my_first_agent.py`：

```python
from dotenv import load_dotenv
from mini_agent_runtime import MiniAgentRuntime, ToolRegistry
from mini_agent_tools import calculator_tool, CALCULATOR_SCHEMA
from my_llm import MyLLM

load_dotenv()

# 1. 创建工具注册表
tool_registry = ToolRegistry()
tool_registry.register(
    "calculator",
    "数学计算器",
    CALCULATOR_SCHEMA,
    calculator_tool
)

# 2. 创建Agent
llm = MyLLM()
agent = MiniAgentRuntime(llm, tool_registry)

# 3. 使用
response = agent.run("请计算 123 * 456")
print(response)
```

运行：
```bash
python my_first_agent.py
```

---

### 示例2：多工具协作

创建文件 `multi_tool_agent.py`：

```python
from dotenv import load_dotenv
from mini_agent_runtime import MiniAgentRuntime, ToolRegistry
from mini_agent_tools import *
from my_llm import MyLLM

load_dotenv()

# 注册多个工具
tool_registry = ToolRegistry()
tool_registry.register("calculator", "计算器", CALCULATOR_SCHEMA, calculator_tool)
tool_registry.register("search", "搜索", SEARCH_SCHEMA, search_tool)
tool_registry.register("weather", "天气", WEATHER_SCHEMA, weather_tool)

# 创建Agent
agent = MiniAgentRuntime(MyLLM(), tool_registry, max_iterations=5)

# 复杂任务
response = agent.run("""
请帮我完成以下任务：
1. 搜索关于AI Agent的信息
2. 查询深圳的天气
3. 计算 (100 + 50) * 3 的结果
""")

print(response)
```

---

### 示例3：会话管理（多轮对话）

创建文件 `session_agent.py`：

```python
from dotenv import load_dotenv
from mini_agent_runtime import MiniAgentRuntime, ToolRegistry
from mini_agent_tools import calculator_tool, CALCULATOR_SCHEMA
from my_llm import MyLLM

load_dotenv()

tool_registry = ToolRegistry()
tool_registry.register("calculator", "计算器", CALCULATOR_SCHEMA, calculator_tool)

agent = MiniAgentRuntime(MyLLM(), tool_registry)

# 使用相同的session_id进行多轮对话
session_id = "user-123"

# 第一轮
response1 = agent.run("请计算 50 + 50", session_id=session_id)
print("第一轮:", response1)

# 第二轮（引用前文）
response2 = agent.run("把刚才的结果乘以3", session_id=session_id)
print("第二轮:", response2)

# 第三轮
response3 = agent.run("再加上25是多少？", session_id=session_id)
print("第三轮:", response3)
```

---

## 自定义工具

### 创建你自己的工具

```python
# 1. 编写工具函数
def my_custom_tool(name: str, age: int) -> str:
    """自定义工具：生成个人介绍"""
    return f"{name}今年{age}岁"

# 2. 定义Schema
MY_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "description": "姓名"
        },
        "age": {
            "type": "integer",
            "description": "年龄"
        }
    },
    "required": ["name", "age"]
}

# 3. 注册
tool_registry.register(
    name="introduce",
    description="生成个人介绍",
    parameters=MY_TOOL_SCHEMA,
    function=my_custom_tool
)

# 4. 使用
agent = MiniAgentRuntime(llm, tool_registry)
response = agent.run("请介绍一下：张三，25岁")
```

---

## 常见问题

### Q1: 如何查看Agent的执行过程？

A: 运行时会自动打印详细日志：
- 📥 Perception: 理解输入
- 🧠 Planning: LLM决策
- ⚡ Action: 工具执行
- 🔍 Reflection: 完成评估

### Q2: 如何限制迭代次数？

A: 在创建Runtime时指定：
```python
agent = MiniAgentRuntime(llm, tool_registry, max_iterations=3)
```

### Q3: 工具调用失败怎么办？

A: Runtime会自动捕获错误并返回错误信息，不会中断整个流程。

### Q4: 如何清除会话历史？

A: 使用SessionManager：
```python
agent.session_manager.delete_session(session_id)
```

### Q5: 支持异步吗？

A: 当前版本是同步的。如需异步，可以基于现有代码扩展：
```python
async def run_async(self, ...):
    # 实现异步版本
```

---

## 进阶使用

### 自定义System Prompt

修改 `mini_agent_runtime.py` 中的 `_build_system_prompt()` 方法：

```python
def _build_system_prompt(self) -> str:
    # 自定义你的系统提示词
    return "你是一个专业的数学助手，擅长解决复杂计算问题..."
```

### 添加工具使用统计

在Tool执行时记录统计：

```python
# 在execute_tool方法中添加
self.tool_stats[name] = self.tool_stats.get(name, 0) + 1
```

### 实现工具链

多个工具串联执行：

```python
# 先计算
result1 = agent.run("计算100+200", session_id="s1")

# 再基于结果查询（通过上下文传递）
result2 = agent.run("用刚才的结果...", session_id="s1")
```

---

## 性能优化建议

1. **减少LLM调用**：设置合理的max_iterations
2. **Context截断**：保持max_turns=10（默认值）
3. **工具缓存**：对重复查询结果进行缓存
4. **并行调用**：多个独立工具可以并行执行（需扩展）

---

## 下一步

- 📖 阅读 [README_MINI_AGENT.md](./README_MINI_AGENT.md) 了解完整功能
- 🏗️ 阅读 [ARCHITECTURE.md](./ARCHITECTURE.md) 理解架构设计
- 📋 阅读 [SUBMISSION.md](./SUBMISSION.md) 查看项目完成度
- 🧪 运行 `test_mini_agent.py` 查看所有测试用例

---

## 获取帮助

如有问题，请：
1. 检查 `.env` 文件配置是否正确
2. 确保API Key有效
3. 查看详细的错误日志
4. 参考测试用例中的使用示例

**祝你使用愉快！** 🎉
