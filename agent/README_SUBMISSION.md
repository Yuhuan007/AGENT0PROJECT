# Mini Agent Runtime — 提交文档

从零实现的最小可用 Agent，不依赖任何 Agent 框架（无 langgraph / openhands / openclaw），核心 Runtime、工具协议、会话与上下文管理全部手写。

- 语言：Python 3.10+
- LLM：真实 API（智谱 GLM `glm-4-flash`，OpenAI 兼容接口）
- 核心代码：`mini_agent_runtime.py` + `mini_agent_tools.py` + `todo_tool.py`

---

## 一、运行方式

### 1. 环境准备

```bash
cd agent
pip install -r requirements.txt          # 主要依赖: openai, python-dotenv, hello-agents
```

### 2. 配置真实 LLM API

项目使用真实 LLM API（非 mock）。在 `agent/.env` 中配置（当前已配好一份可用的智谱 GLM key）：

```ini
LLM_API_KEY=<你的智谱API Key>          # 获取: https://open.bigmodel.cn/usercenter/apikeys
LLM_MODEL_ID=glm-4-flash               # glm-4-flash 免费额度足够测试
LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
LLM_TIMEOUT=60
```

> 因接口 OpenAI 兼容，切换到通义千问 / DeepSeek / OpenAI 只需改这三个变量，代码无需改动。

### 3. 运行

```bash
# 快速演示（真实 LLM，4 个场景：计算 / 天气 / 搜索 / 多工具协作）
python demo_mini_agent.py

# 基础功能测试套件（6 项，真实 LLM）
python test_mini_agent.py

# 全部测试聚合（17 项，含 context / read_docs / 多会话 / 多窗口）
python run_all_tests.py
python run_all_tests.py --fast     # 仅跑离线单元测试，不消耗 API

# 专项测试
python test_context.py             # context 管理 6 项
python test_error_and_trace.py     # 异常处理 + 执行 trace 8 项（离线）
python test_multi_window.py        # 多窗口独立会话
python test_read_docs.py           # read_docs 工具 + 安全边界
```

### 4. 最小使用示例

```python
from dotenv import load_dotenv
from mini_agent_runtime import MiniAgentRuntime, ToolRegistry
from mini_agent_tools import calculator_tool, CALCULATOR_SCHEMA
from my_llm import MyLLM

load_dotenv()
registry = ToolRegistry()
registry.register("calculator", "执行数学计算", CALCULATOR_SCHEMA, calculator_tool)

agent = MiniAgentRuntime(MyLLM(), registry)
print(agent.run("帮我算 (125 + 375) * 2 - 100"))   # 会话隔离用 session_id="xxx"
```

---

## 二、系统设计

### 2.1 整体架构

```
┌──────────────────────── MiniAgentRuntime ────────────────────────┐
│                                                                    │
│   run(user_input, session_id)                                      │
│        │                                                           │
│        ▼                                                           │
│   ┌─────────────── 4 步循环 (最多 max_iterations 轮) ───────────┐ │
│   │ 1. Perception  取会话历史 → 组装 context（轮次+长度管理）   │ │
│   │ 2. Planning    调 LLM（带重试）→ 决策是否用工具            │ │
│   │ 3. Action      执行工具（异常隔离）或产出最终回答          │ │
│   │ 4. Reflection  有工具调用则回到 1，否则结束                 │ │
│   └────────────────────────────────────────────────────────────┘ │
│                                                                    │
│   SessionManager   ToolRegistry   LLM(MyLLM)   TraceEvent 日志     │
└────────────────────────────────────────────────────────────────────┘
```

### 2.2 核心组件

| 组件 | 职责 | 位置 |
|------|------|------|
| `MiniAgentRuntime` | 4 步循环调度、异常兜底、trace 记录 | `mini_agent_runtime.py` |
| `ToolRegistry` | 工具注册（名称/描述/Schema/函数）、执行、`session_id` 注入 | 同上 |
| `SessionManager` / `Session` | 多会话隔离、消息历史、上下文构建、trace 导出 | 同上 |
| `MyLLM` | 封装 OpenAI 兼容接口，从 `.env` 读配置 | `my_llm.py` |
| 工具集 | calculator / search(mock) / weather(mock) / read_docs / todo | `mini_agent_tools.py`, `todo_tool.py` |

### 2.3 工具调用协议

LLM 通过标记包裹的 JSON 声明工具调用，解析器优先匹配标记，并对小模型不守格式的情况做兜底（裸 JSON / “工具名 + 参数” 也能识别）：

```
[TOOL_CALL]
{"tool": "calculator", "arguments": {"expression": "(125+375)*2"}}
[/TOOL_CALL]
```

### 2.4 已实现的关键能力

- **工具注册机制**：`register(name, description, parameters, function)`，Schema 随系统提示注入，LLM 自主决策
- **Session 管理**：`session_id` 隔离多会话；工具数据也按会话隔离（如待办清单）
- **Context 有效管理**（三级）：① 轮次限制 ② 单条超长消息截断 ③ 总长度超预算时丢弃最旧消息 + 插入压缩提示
- **异常处理**：LLM 调用失败自动重试并优雅降级；工具异常隔离捕获为友好错误，不使 Agent 崩溃
- **执行 trace / 日志**：每步记录到 `Session.trace`（含耗时、工具成功/失败、错误），可 `export_trace(as_json=True)`；同时接入标准 `logging`
- **read_docs 安全边界**：路径穿越防护 + 扩展名白名单 + 大文件截断

---

## 三、Memory（记忆）说明

本 Agent 的“记忆”即**会话记忆**，实现方式为 `Session.messages` 消息历史 + `get_context()` 的上下文召回，属于会话级短期记忆。

### 3.1 放置方式（Memory 存在哪）

- **载体**：每个 `Session` 对象持有一个 `messages: List[Message]`，按时间顺序追加。`Message` 含 `role`（user/assistant/tool/system）、`content`、`timestamp`、以及可选的 `tool_calls` / `tool_results`。
- **写入时机**：`run()` 执行过程中，以下内容会被写入记忆——
  - 用户输入（`role="user"`）
  - Agent 的回复与其发起的工具调用（`role="assistant"`，剥离 `[TOOL_CALL]` 标记后存正文，工具调用存入 `tool_calls` 字段）
  - 工具执行结果（`role="tool"`）
- **隔离**：`SessionManager.sessions` 以 `session_id` 为键存放多个 `Session`，不同会话（不同用户 / 不同窗口）的记忆互不可见。工具产生的数据（如待办）同样按 `session_id` 隔离。
- **生命周期**：进程内内存存储，随会话存在；`delete_session()` 可清除。执行 trace 单独存于 `Session.trace`，与对话记忆分离，便于导出分析。

### 3.2 召回时机（Memory 何时被读取）

- **每轮 Perception 阶段**调用 `session.get_context(max_turns, max_chars)` 召回历史，拼到系统提示之后送入 LLM。这是追问能力的基础——无论纯对话追问还是带工具的追问，都靠这一步把上文带回。
- **召回策略（三级筛选，兼顾相关性与长度预算）**：
  1. **轮次限制** `max_turns`：只取最近 N 轮，丢弃过旧对话；
  2. **单条截断** `max_msg_chars`：单条过长消息（常见于工具返回的长文本）截断并标注，避免一条撑爆上下文；
  3. **长度压缩** `max_chars`：总字符超预算时，从最旧开始丢弃，并在开头插入“已省略 N 条”的系统提示；`keep_recent` 保证最近若干条永不被压缩，维持追问连贯。

> 说明：这是**基础压缩**（丢弃 + 占位提示），非 LLM 摘要式压缩，符合题目“复杂压缩不必实现”的要求。长度按字符估算（对中文偏保守），零额外成本。

---

## 四、测试覆盖

| 测试文件 | 覆盖内容 | 项数 |
|----------|----------|------|
| `test_mini_agent.py` | 计算器 / 搜索 / 天气 / 多工具协作 / 会话 / 无工具直答 | 6 |
| `test_context.py` | 轮次限制 / 记住状态 / 纯对话追问 / 带工具追问 / 单条截断 / 长度压缩 | 6 |
| `test_multi_session.py` | 多会话隔离 / 上下文长度 | 2 |
| `test_multi_window.py` | 多窗口独立会话（待办按会话隔离） | 1 |
| `test_read_docs.py` | read_docs 正常读取 + 安全边界（路径穿越/白名单/截断） | 7 |
| `test_error_and_trace.py` | 异常处理（重试/降级/工具异常）+ 执行 trace | 8 |
| `run_all_tests.py` | 聚合入口，`--fast` 跑离线部分 | 17 |

真实 LLM 下 `run_all_tests.py` 全部 17 项通过；`test_error_and_trace.py` 8 项（离线、假 LLM 驱动）全部通过。

---

## 五、文件清单

```
agent/
├── mini_agent_runtime.py      # 核心 Runtime（循环/会话/上下文/异常/trace）
├── mini_agent_tools.py        # calculator / search / weather / read_docs
├── todo_tool.py               # 待办工具（按会话隔离，演示 Memory 隔离）
├── my_llm.py                  # LLM 封装（OpenAI 兼容，读 .env）
├── demo_mini_agent.py         # 快速演示
├── run_all_tests.py           # 测试聚合入口
├── test_*.py                  # 各项测试
├── .env                       # LLM 配置（真实 API）
├── requirements.txt
├── README_SUBMISSION.md       # 本文档
└── AI_PROMPT_LOG.md           # AI Prompt 与问题解决记录
```
