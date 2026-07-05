# AI Prompt 与问题解决记录

本文档记录借助 AI 编码助手完成本项目的关键 Prompt、遇到的问题及解决过程。题目允许使用 AI 工具辅助，核心 Agent Runtime 为自行设计实现。

---

## 问题 1：LLM 报 403 / 模型无权限

**现象**：运行 `test_mini_agent.py` 报 `openai.PermissionDeniedError: 403 AccessDenied.Unpurchased`，虽然 `.env` 配的是通义千问却像在调 OpenAI。

**Prompt**：“为什么报错啊 我的 .env 中调用的是 qwen 而不是 openai”

**排查与解决**：
1. 检查 `my_llm.py`，发现 `provider="auto"` 分支直接走父类，没从 `.env` 读取 `LLM_API_KEY/BASE_URL/MODEL_ID` → 补上环境变量读取。
2. 修好后仍 403。写探针脚本调 `/models` 接口，发现 API 能列出 220 个模型但每个模型调用都被拒 → 判定为**账号未购买/授权模型**，非代码问题。
3. 切换到 DashScope 标准接口后报 `Arrearage`（欠费）→ 定位为阿里云账户欠费。

**结论**：代码配置正确，根因是账户权限/欠费。

---

## 问题 2：更换免费可用的 LLM

**Prompt**：“我的阿里云欠费了 有什么其他免费 api key” → 选定 “用 glm-4-flash”。

**解决**：改 `.env` 三项为智谱 GLM（`glm-4-flash` 免费、OpenAI 兼容）。因 `my_llm.py` 已能读环境变量，代码零改动。简单调用验证成功返回。

---

## 问题 3：工具调用其实没生效（隐藏 bug）

**现象**：换 LLM 后 API 通了，但测试“通过”是假象——LLM 输出了工具调用意图，却没真正执行工具。

**排查与解决**：
1. `self.llm.invoke()` 返回 `LLMResponse` 对象，代码却当字符串用 → 两处调用后提取 `.content`。
2. system prompt 要求 `[TOOL_CALL]` 标记，但 glm-4-flash 是小模型，常输出裸格式 `calculator\n{JSON}` → ① 强化 prompt 加示例与规则；② `_parse_tool_calls` 增加兜底解析，无标记时也能从裸文本识别工具调用。

**结果**：6 项测试真正跑通（计算器返回 900、多工具协作、会话记忆等）。

---

## 问题 4：多窗口独立会话

**Prompt**：“用户 A 开窗口1（查天气记待办）、窗口2（写周报记待办），两窗口独立、互不影响，实现这个测试用例。”

**关键设计**：光隔离对话历史不够，**工具产生的数据也要按会话隔离**。
1. `execute_tool` 用 `inspect` 检查工具签名，若含 `session_id` 参数则自动注入（现有工具不受影响，向后兼容）。
2. 新建 `todo_tool.py`，待办以 `session_id` 为键分开存储。
3. 测试断言直接读底层存储而非解析 LLM 措辞，规避小模型输出随机性。

**结果**：窗口1（2 条待办）、窗口2（1 条待办）完全隔离，中途切回窗口1 上下文仍在。

---

## 问题 5：read_docs 工具（含安全）

**Prompt**：“实现 read_docs 工具，并创建测试用例。”

**安全设计**（读文件有风险，做三层防护）：
- 路径穿越防护：`os.path.commonpath` 确保目标在文档根目录内，拦截 `../../etc/passwd`；
- 扩展名白名单：仅允许 `.md/.txt/.py/.json` 等文本类型；
- 大文件截断：超 8000 字符截断，防撑爆上下文。

**结果**：单元测试 6 项（含 3 种路径穿越变体）+ Agent 集成读文档答出版本号，全通过。

---

## 问题 6：Context 有效管理

**Prompt**：“context 有效管理：最大轮次、记住状态、纯对话追问、带工具追问、过长要有基础压缩……查看完成情况，缺失的实现，最后建测试。”

**审查结论**：6 项中 5 项原本已实现，唯独“基础压缩”缺失（`get_context` 只有轮次截断，单条长工具结果能撑爆上下文）。

**解决**：`get_context` 升级为三级管理——轮次限制 + 单条截断 + 总长度压缩（丢最旧 + 插压缩提示，保留最近 `keep_recent` 条）。Runtime 增加 `max_turns` / `max_context_chars` 配置。

**结果**：`test_context.py` 6 项通过（离线 4 项 + 真实 LLM 追问 2 项）。

---

## 问题 7：异常处理 + 执行 trace

**Prompt**：“基本异常处理；工具调用 trace 或执行日志，实现功能。”

**实现**：
- 异常：新增 `AgentError/LLMInvokeError/ToolExecutionError`；`_invoke_llm` 带线性退避重试；`execute_tool` 区分“不存在/参数错误/内部异常”三类；`run()` 全兜底，LLM 不可用时优雅降级而非崩溃。
- trace：新增 `TraceEvent` 数据类，每步（perception/planning/tool_call/final/error）记录耗时、成功标志、错误；存 `Session.trace`，可 `export_trace(as_json=True)`；接入标准 `logging`。

**结果**：`test_error_and_trace.py` 8 项（假 LLM 驱动、离线）全通过；重构后回归 `test_context.py` 6 项仍全过，未破坏既有功能。

---

## 使用 AI 工具的方法总结

1. **先定位再动手**：报错先读相关源码/写探针脚本确认根因（如问题 1 用 `/models` 接口区分“代码问题 vs 账户问题”），不盲目改。
2. **测试断言避开随机性**：涉及小模型输出时，断言优先读底层数据结构（trace / 存储），不依赖 LLM 的自然语言措辞。
3. **向后兼容**：新增能力（如 `session_id` 注入）用签名探测方式，不破坏既有工具。
4. **改后必回归**：每次重构后重跑相关测试，确认无回归。

> LLM：智谱 GLM `glm-4-flash`（真实 API）。核心 Agent Runtime 设计与实现均为手写，未使用 Agent 框架。
