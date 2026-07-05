# Agent Runtime 核心方法详解（第3部分）

## 5.5 run方法（第206-318行）- **最核心的方法**

这是整个Agent Runtime的心脏，实现了完整的4步循环。让我们逐段深入解析。

### 第206-216行：方法签名和文档

```python
def run(self, user_input: str, session_id: Optional[str] = None) -> str:
    """
    运行Agent - 实现完整的4步循环
    
    Args:
        user_input: 用户输入
        session_id: 会话ID（可选）
    
    Returns:
        Agent的最终响应
    """
```

**接口设计分析**:

1. **user_input**: 用户问题（必需）
2. **session_id**: 会话标识（可选）
   - None → 创建新会话
   - 指定ID → 恢复/继续现有会话
3. **返回值**: 字符串（Agent的最终答案）

---

### 第217-226行：会话初始化

```python
# 获取或创建会话
if session_id:
    session = self.session_manager.get_session(session_id)
    if not session:
        session = self.session_manager.create_session(session_id)
else:
    session = self.session_manager.create_session()

# 添加用户消息
session.add_message(Message(role="user", content=user_input))
```

**逻辑流程**:

```
用户传入session_id？
    ├─ 是 → 尝试获取已有会话
    │    ├─ 找到 → 使用现有会话（多轮对话）
    │    └─ 未找到 → 创建新会话（用指定ID）
    └─ 否 → 创建新会话（自动生成ID）

添加用户消息到会话历史
```

**设计考量**:
- 支持单轮对话（不传session_id）
- 支持多轮对话（传入相同session_id）
- 自动处理会话恢复

**第226行：用户消息入历史**
```python
session.add_message(Message(role="user", content=user_input))
```
- 每次对话开始，先记录用户问题
- 构建完整的对话历史

---

### 第228-233行：初始化和日志

```python
print(f"\n{'='*60}")
print(f"🤖 Agent Runtime 启动 (Session: {session.session_id[:8]})")
print(f"{'='*60}")

iteration = 0
final_response = ""
```

**变量初始化**:
1. **iteration**: 当前迭代轮次（从0开始）
2. **final_response**: 最终答案（空字符串表示未完成）

**日志输出**:
- 视觉分隔线（60个等号）
- 显示会话ID前8位（便于追踪）

---

### 第235-299行：主循环 - **4步循环的实现**

```python
while iteration < self.max_iterations:
    iteration += 1
    print(f"\n🔄 Iteration {iteration}/{self.max_iterations}")
```

**循环控制**:
- `while iteration < max_iterations`: 最多执行N轮
- `iteration += 1`: 每轮递增
- 显示进度：`1/5`、`2/5`...

---

### Step 1: Perception（第239-245行）

```python
# Step 1: Perception - 构建上下文
print("📥 Step 1: Perception - 理解用户问题")
context = session.get_context(max_turns=10)

# 构建消息列表
messages = [{"role": "system", "content": self._build_system_prompt()}]
messages.extend(context)
```

**深度解析**:

#### Perception（感知）的含义
- **不是**直接读取user_input
- 而是**理解整个对话上下文**
- 包括：
  - 系统指令（工具列表、规则）
  - 历史对话（前10轮）
  - 当前问题

#### 第241行：获取上下文
```python
context = session.get_context(max_turns=10)
```
- 最近10轮对话（20条消息）
- 防止context过长
- 返回LLM格式的消息列表

#### 第244-245行：构建完整messages

```python
messages = [
    {"role": "system", "content": "你是AI助手，可以使用工具..."},  # System Prompt
    {"role": "user", "content": "计算100+200"},                    # 历史对话
    {"role": "assistant", "content": "好的，我来计算"},
    {"role": "user", "content": "再乘以2"}                         # 当前问题
]
```

**结构分析**:
1. **第一条**：system（必需）
   - 包含工具列表
   - 包含行为规范
   - 每次都重新生成（保证最新）

2. **后续**：对话历史
   - user <-> assistant交替
   - 可能包含tool消息
   - 按时间顺序排列

**为什么system放在最前？**
- LLM会优先关注前面的信息
- System Prompt是"宪法"，必须先读

---

### Step 2: Planning（第247-250行）

```python
# Step 2: Planning - LLM决策
print("🧠 Step 2: Planning - 分析并制定计划")
llm_response = self.llm.invoke(messages)
print(f"   LLM输出: {llm_response[:200]}...")
```

**深度解析**:

#### Planning（规划）的含义
- LLM基于上下文做决策
- 决定：
  - 需要调用工具吗？
  - 调用哪个/哪些工具？
  - 参数是什么？
  - 还是直接回答？

#### 第249行：LLM调用

```python
llm_response = self.llm.invoke(messages)
```

**关键点**:
- `invoke`是统一接口（依赖注入的好处）
- 传入完整的messages列表
- 返回LLM的文本输出

**LLM可能的输出**:

**情况1：需要工具**
```
我需要计算这个表达式。

[TOOL_CALL]
{"tool": "calculator", "arguments": {"expression": "100+200"}}
[/TOOL_CALL]

我会等待计算结果。
```

**情况2：不需要工具**
```
你好！我是AI助手，很高兴为你服务。有什么我可以帮你的吗？
```

**情况3：多个工具**
```
我需要做两件事。

[TOOL_CALL]
{"tool": "calculator", "arguments": {"expression": "100+200"}}
[/TOOL_CALL]

[TOOL_CALL]
{"tool": "weather", "arguments": {"location": "北京"}}
[/TOOL_CALL]

两个工具都准备好了。
```

---

### Step 3: Action（第252-295行）

```python
# Step 3: Action - 执行工具或响应
print("⚡ Step 3: Action - 执行操作")
tool_calls = self._parse_tool_calls(llm_response)
```

**分支逻辑**:
```
解析LLM输出
    ├─ 有工具调用 → 执行工具 → 保存结果 → 继续循环
    └─ 无工具调用 → 这是最终答案 → 退出循环
```

---

#### 分支A：有工具调用（第256-288行）

```python
if tool_calls:
    # 执行工具调用
    tool_results = []
    for call in tool_calls:
        tool_name = call.get("tool")
        arguments = call.get("arguments", {})
        print(f"   🔧 调用工具: {tool_name}({arguments})")
        
        result = self.tool_registry.execute_tool(tool_name, arguments)
        tool_results.append({
            "tool": tool_name,
            "result": result
        })
        print(f"   ✅ 工具结果: {result[:100]}...")
```

**执行流程**:

1. **遍历所有工具调用**（第259行）
   ```python
   for call in tool_calls:
   ```
   - 可能有多个工具
   - 按顺序执行

2. **提取参数**（第260-261行）
   ```python
   tool_name = call.get("tool")
   arguments = call.get("arguments", {})
   ```
   - 从JSON提取tool和arguments
   - arguments默认为空字典（容错）

3. **执行工具**（第264行）
   ```python
   result = self.tool_registry.execute_tool(tool_name, arguments)
   ```
   - 调用ToolRegistry的execute_tool
   - 返回字符串结果

4. **收集结果**（第265-268行）
   ```python
   tool_results.append({
       "tool": tool_name,
       "result": result
   })
   ```
   - 记录每个工具的结果
   - 用于后续注入context

**保存assistant消息（第271-277行）**:

```python
clean_response = self._remove_tool_calls_from_text(llm_response)
session.add_message(Message(
    role="assistant",
    content=clean_response,
    tool_calls=tool_calls
))
```

**为什么清理content？**
- `clean_response`: 移除工具调用标记
- 只保留自然语言部分
- `tool_calls`字段单独记录工具调用

**示例**:
```python
# 原始LLM输出
llm_response = "我需要计算。[TOOL_CALL]{...}[/TOOL_CALL]计算中..."

# 清理后
clean_response = "我需要计算。计算中..."

# Message对象
Message(
    role="assistant",
    content="我需要计算。计算中...",  # 清理后的内容
    tool_calls=[{"tool": "calculator", ...}]  # 工具调用记录
)
```

**保存tool消息（第280-288行）**:

```python
tool_results_text = "\n".join([
    f"工具 {tr['tool']} 返回: {tr['result']}" 
    for tr in tool_results
])
session.add_message(Message(
    role="tool",
    content=tool_results_text,
    tool_results=tool_results
))
```

**为什么单独保存tool消息？**

**消息序列**:
```
1. user: "计算100+200"
2. assistant: "我需要计算。" (tool_calls=[...])
3. tool: "工具 calculator 返回: 300" (tool_results=[...])
4. [下一轮] assistant: "结果是300"
```

**好处**:
- 明确的角色分离
- LLM在下一轮能看到工具结果
- 便于调试工具调用链

---

#### 分支B：无工具调用（第290-295行）

```python
else:
    # 没有工具调用，这是最终回答
    print("   💬 无需工具，直接回答")
    final_response = llm_response
    session.add_message(Message(role="assistant", content=final_response))
    break
```

**判断逻辑**:
- `tool_calls`为空列表 → 没有工具调用
- 说明LLM认为不需要工具
- 可以直接回答

**break退出**:
- 跳出while循环
- 不再继续迭代
- 返回最终答案

---

### Step 4: Reflection（第297-299行）

```python
# Step 4: Reflection - 反思是否需要继续
print("🔍 Step 4: Reflection - 评估任务完成情况")
# 简单策略：如果有工具调用，继续循环；否则结束
```

**Reflection（反思）的含义**:
- 评估任务是否完成
- 决定是否继续循环

**当前实现**:
- **隐式反思**
- 如果有工具调用 → 继续（进入下一轮）
- 如果无工具调用 → 结束（break）

**为什么是"简单策略"？**

**更复杂的Reflection可以**:
1. 显式问LLM："任务完成了吗？"
2. 检查工具结果是否成功
3. 评估答案质量
4. 根据用户反馈调整

**当前策略的优势**:
- 简单高效
- 减少LLM调用
- 适合大多数场景

---

### 第301-312行：达到最大迭代次数

```python
# 如果达到最大迭代次数，生成最终回答
if not final_response:
    print("\n⚠️ 达到最大迭代次数，生成最终回答...")
    context = session.get_context(max_turns=10)
    messages = [{"role": "system", "content": self._build_system_prompt()}]
    messages.extend(context)
    messages.append({
        "role": "user",
        "content": "请基于以上信息，给出完整的最终回答（不要再调用工具）"
    })
    final_response = self.llm.invoke(messages)
    session.add_message(Message(role="assistant", content=final_response))
```

**触发条件**:
- 循环执行了max_iterations轮
- 但仍然没有final_response
- 说明LLM一直在调用工具

**处理策略**:
1. 重新构建context（包含所有工具结果）
2. 添加明确指令："不要再调用工具"
3. 强制生成最终答案

**第307-310行：特殊的user消息**
```python
messages.append({
    "role": "user",
    "content": "请基于以上信息，给出完整的最终回答（不要再调用工具）"
})
```
- 不是用户实际输入
- 是Runtime注入的指令
- 强制LLM总结回答

---

### 第314-318行：返回结果

```python
print(f"\n{'='*60}")
print(f"✅ Agent Runtime 完成")
print(f"{'='*60}\n")

return final_response
```

**返回值**:
- final_response（字符串）
- Agent的最终答案
- 已保存到session历史

---

## 6. 完整执行流程示例

让我们通过一个实际例子理解整个流程：

### 场景：计算任务

```python
agent = MiniAgentRuntime(llm, tool_registry, max_iterations=5)
response = agent.run("请计算 (100 + 200) * 2")
```

### 执行流程：

```
┌─ Iteration 1 ─────────────────────────────────────────────┐
│                                                             │
│ Step 1: Perception                                          │
│   context = []  # 空（首次对话）                            │
│   messages = [                                              │
│     {"role": "system", "content": "你是AI助手，有工具..."}, │
│     {"role": "user", "content": "请计算 (100+200)*2"}      │
│   ]                                                         │
│                                                             │
│ Step 2: Planning                                            │
│   llm_response = "我需要使用计算器。                        │
│                   [TOOL_CALL]                               │
│                   {"tool": "calculator",                    │
│                    "arguments": {"expression": "(100+200)*2"}}│
│                   [/TOOL_CALL]"                             │
│                                                             │
│ Step 3: Action                                              │
│   tool_calls = [{"tool": "calculator", ...}]               │
│   执行工具: calculator(expression="(100+200)*2")            │
│   结果: "计算结果: 600"                                      │
│   保存assistant消息 + tool消息                              │
│                                                             │
│ Step 4: Reflection                                          │
│   有工具调用 → 继续                                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─ Iteration 2 ─────────────────────────────────────────────┐
│                                                             │
│ Step 1: Perception                                          │
│   context = [                                               │
│     {"role": "user", "content": "请计算..."},               │
│     {"role": "assistant", "content": "我需要使用..."},      │
│     {"role": "tool", "content": "计算结果: 600"}           │
│   ]                                                         │
│   messages = system + context                               │
│                                                             │
│ Step 2: Planning                                            │
│   llm_response = "根据计算结果，(100+200)*2 = 600"         │
│   # 没有工具调用标记                                        │
│                                                             │
│ Step 3: Action                                              │
│   tool_calls = []  # 空                                     │
│   → 直接回答分支                                            │
│   final_response = "根据计算结果，(100+200)*2 = 600"       │
│   break  # 退出循环                                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘

返回: "根据计算结果，(100+200)*2 = 600"
```

---

## 7. 设计模式与架构总结

### 7.1 使用的设计模式

1. **注册表模式（Registry）**: ToolRegistry
2. **依赖注入（Dependency Injection）**: llm_client
3. **策略模式（Strategy）**: 不同的LLM实现
4. **建造者模式（Builder）**: System Prompt构建
5. **模板方法模式（Template Method）**: 4步循环

### 7.2 关键设计原则

1. **单一职责**:
   - ToolRegistry只管工具
   - SessionManager只管会话
   - MiniAgentRuntime只管执行流程

2. **开闭原则**:
   - 对扩展开放：可以添加新工具、新LLM
   - 对修改关闭：核心逻辑不变

3. **依赖倒置**:
   - Runtime依赖抽象（llm.invoke接口）
   - 不依赖具体LLM实现

4. **接口隔离**:
   - LLM只需要invoke方法
   - 工具只需要function

### 7.3 核心技术点总结

| 技术点 | 用途 | 关键代码 |
|--------|------|----------|
| dataclass | 快速定义数据类 | @dataclass |
| 类型注解 | 代码可读性 | Optional[str] |
| 正则表达式 | 解析工具调用 | re.findall |
| JSON | 工具调用格式 | json.loads |
| 依赖注入 | 解耦LLM实现 | __init__(llm_client) |
| 迭代保护 | 防止死循环 | max_iterations |
| Context截断 | 控制token | max_turns |
| 错误处理 | 鲁棒性 | try-except |

---

## 8. 学习建议

### 对于初学者：
1. 先理解数据结构（Message、Session、ToolSchema）
2. 再理解工具注册（ToolRegistry）
3. 最后理解核心循环（run方法）

### 对于进阶者：
1. 研究System Prompt的设计技巧
2. 理解Context管理策略
3. 思考Reflection的改进方向
4. 考虑分布式、持久化扩展

### 对于架构师：
1. 评估可扩展性设计
2. 思考生产环境部署
3. 考虑性能优化方向
4. 设计监控和可观测性

---

**总代码行数**: 318行  
**核心循环**: 约80行（第235-318行）  
**复杂度**: 中等  
**可读性**: 高  

这是一个**教学级**的Agent实现，兼顾了**简洁性**和**完整性**。
