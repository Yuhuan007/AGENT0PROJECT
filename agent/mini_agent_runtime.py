# mini_agent_runtime.py
"""
2026年Agent技术笔试题 - 从零实现最小可用Agent
不依赖现成框架，实现完整的Agent Runtime
"""

import json
import uuid
import time
import inspect
import logging
import traceback
from typing import Dict, List, Any, Callable, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
import re


# ---- 执行日志：标准 logging，便于运行时观察，可被外部配置 handler/level ----
logger = logging.getLogger("mini_agent")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)


class AgentError(Exception):
    """Agent 运行时的基础异常类型"""


class LLMInvokeError(AgentError):
    """LLM 调用失败（网络、鉴权、限流等）"""


class ToolExecutionError(AgentError):
    """工具执行失败"""


@dataclass
class ToolSchema:
    """工具Schema定义"""
    name: str
    description: str
    parameters: Dict[str, Any]
    function: Callable


@dataclass
class TraceEvent:
    """单条执行追踪事件

    记录 Agent 运行过程中的一个步骤，用于事后分析、调试和测试断言。
    """
    step: str                       # 步骤类型：perception / planning / tool_call / final / error
    iteration: int                  # 所属迭代轮次
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    detail: Dict[str, Any] = field(default_factory=dict)  # 步骤相关的详细数据
    duration_ms: Optional[float] = None                    # 耗时（毫秒）
    error: Optional[str] = None                            # 若该步骤出错，记录错误信息

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Message:
    """消息对象"""
    role: str  # user, assistant, system, tool
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    tool_calls: Optional[List[Dict]] = None
    tool_results: Optional[List[Dict]] = None


@dataclass
class Session:
    """会话管理"""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    messages: List[Message] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    trace: List[TraceEvent] = field(default_factory=list)  # 执行追踪记录

    def add_message(self, message: Message):
        """添加消息到会话"""
        self.messages.append(message)

    def add_trace(self, event: TraceEvent):
        """追加一条执行追踪事件"""
        self.trace.append(event)

    def export_trace(self, as_json: bool = False):
        """导出执行追踪记录

        Args:
            as_json: True 返回 JSON 字符串，False 返回 dict 列表

        Returns:
            trace 的可序列化表示
        """
        data = [e.to_dict() for e in self.trace]
        if as_json:
            return json.dumps(data, ensure_ascii=False, indent=2)
        return data

    def get_context(
        self,
        max_turns: int = 10,
        max_chars: Optional[int] = None,
        max_msg_chars: int = 2000,
        keep_recent: int = 2,
    ) -> List[Dict]:
        """获取上下文，支持三级 context 管理

        1. 轮次限制：只保留最近 max_turns 轮对话（1 轮 ≈ user + assistant 两条）
        2. 单条截断：过长的单条消息（常见于工具返回的长文本）截断到 max_msg_chars，
           保留关键信息的同时避免单条消息撑爆上下文
        3. 长度压缩：若总字符数仍超过 max_chars，从最旧的消息开始丢弃，
           并在开头插入一条摘要占位，告知模型「有若干早期消息被省略」。
           始终保留最近 keep_recent 条消息不被压缩，保证追问的连贯性。

        Args:
            max_turns: 保留的最大对话轮数
            max_chars: 上下文总字符预算，None 表示不做长度压缩
            max_msg_chars: 单条消息的最大字符数，超出则截断
            keep_recent: 长度压缩时至少保留的最近消息条数

        Returns:
            适配 LLM 的消息列表 [{"role": ..., "content": ...}, ...]
        """
        # ---- 第 1 级：轮次限制 ----
        if len(self.messages) > max_turns * 2:
            recent_messages = self.messages[-max_turns * 2:]
        else:
            recent_messages = list(self.messages)

        # ---- 第 2 级：单条消息截断 ----
        def _truncate(content: str) -> str:
            if content and len(content) > max_msg_chars:
                return content[:max_msg_chars] + f"\n...[该消息过长，已截断，原长 {len(content)} 字符]"
            return content

        context = [
            {"role": msg.role, "content": _truncate(msg.content)}
            for msg in recent_messages
        ]

        # ---- 第 3 级：总长度压缩 ----
        if max_chars is not None:
            omitted = 0
            while len(context) > keep_recent and self._context_chars(context) > max_chars:
                context.pop(0)
                omitted += 1

            if omitted > 0:
                summary = {
                    "role": "system",
                    "content": f"【上下文压缩】为控制长度，已省略较早的 {omitted} 条消息，"
                               f"仅保留最近的对话。如需早期信息，请用户重新说明。"
                }
                context.insert(0, summary)

        return context

    @staticmethod
    def _context_chars(context: List[Dict]) -> int:
        """统计上下文的总字符数"""
        return sum(len(item.get("content") or "") for item in context)


class ToolRegistry:
    """工具注册表"""

    def __init__(self):
        self.tools: Dict[str, ToolSchema] = {}

    def register(self, name: str, description: str, parameters: Dict, function: Callable):
        """注册工具"""
        tool = ToolSchema(
            name=name,
            description=description,
            parameters=parameters,
            function=function
        )
        self.tools[name] = tool
        print(f"✅ 工具已注册: {name}")

    def get_tool(self, name: str) -> Optional[ToolSchema]:
        """获取工具"""
        return self.tools.get(name)

    def get_tools_schema_for_llm(self) -> List[Dict]:
        """生成供LLM使用的工具Schema"""
        schemas = []
        for tool in self.tools.values():
            schemas.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters
            })
        return schemas

    def execute_tool(self, name: str, arguments: Dict, session_id: Optional[str] = None) -> str:
        """执行工具（带异常处理）

        若工具函数签名中包含 session_id 参数，则自动注入当前会话 ID，
        使工具能够按会话隔离存储数据（如待办清单）。现有工具不含该参数，行为不变。

        任何执行异常都会被捕获并转成友好的错误字符串返回，不会向上抛出导致 Agent 崩溃。
        """
        tool = self.get_tool(name)
        if not tool:
            logger.warning(f"尝试调用不存在的工具: {name}")
            return f"❌ 工具 '{name}' 不存在，可用工具: {', '.join(self.tools.keys()) or '无'}"

        if not isinstance(arguments, dict):
            logger.warning(f"工具 {name} 的参数不是字典: {type(arguments)}")
            return f"❌ 工具 '{name}' 的参数格式错误，应为 JSON 对象"

        try:
            call_args = dict(arguments)
            # 检查工具函数是否声明了 session_id 参数，是则注入
            sig = inspect.signature(tool.function)
            if "session_id" in sig.parameters and session_id is not None:
                call_args["session_id"] = session_id

            result = tool.function(**call_args)
            logger.info(f"工具 {name} 执行成功")
            return str(result)
        except TypeError as e:
            # 参数不匹配（缺少必填参数、多余参数等）
            logger.error(f"工具 {name} 参数错误: {e}")
            return f"❌ 工具 '{name}' 参数错误: {str(e)}"
        except Exception as e:
            # 工具内部逻辑异常，捕获后返回，不让它冒泡到主循环
            logger.error(f"工具 {name} 执行失败: {e}\n{traceback.format_exc()}")
            return f"❌ 工具 '{name}' 执行失败: {str(e)}"


class SessionManager:
    """会话管理器 - 支持多窗口管理"""

    def __init__(self):
        self.sessions: Dict[str, Session] = {}

    def create_session(self, session_id: Optional[str] = None) -> Session:
        """创建新会话"""
        session = Session(session_id=session_id or str(uuid.uuid4()))
        self.sessions[session.session_id] = session
        print(f"✅ 创建会话: {session.session_id}")
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """获取会话"""
        return self.sessions.get(session_id)

    def delete_session(self, session_id: str):
        """删除会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            print(f"🗑️ 删除会话: {session_id}")


class MiniAgentRuntime:
    """
    最小可用Agent Runtime
    实现完整的 Perception -> Planning -> Action -> Reflection 循环
    """

    def __init__(
        self,
        llm_client,
        tool_registry: ToolRegistry,
        max_iterations: int = 5,
        max_turns: int = 10,
        max_context_chars: int = 12000,
    ):
        """
        初始化Agent Runtime

        Args:
            llm_client: LLM客户端（需要有invoke方法）
            tool_registry: 工具注册表
            max_iterations: 单次 run 内的最大迭代次数（防止工具调用死循环）
            max_turns: 传入上下文的最大对话轮数
            max_context_chars: 上下文总字符预算，超出触发基础压缩
        """
        self.llm = llm_client
        self.tool_registry = tool_registry
        self.max_iterations = max_iterations
        self.max_turns = max_turns
        self.max_context_chars = max_context_chars
        self.session_manager = SessionManager()

    def _build_system_prompt(self) -> str:
        """构建系统提示词，包含工具信息"""
        tools_schema = self.tool_registry.get_tools_schema_for_llm()

        prompt = """你是一个智能助手，可以使用工具来帮助回答问题。

## 可用工具
"""
        for tool in tools_schema:
            prompt += f"\n### {tool['name']}"
            prompt += f"\n描述: {tool['description']}"
            prompt += f"\n参数: {json.dumps(tool['parameters'], ensure_ascii=False)}\n"

        prompt += """
## 工作流程
1. **Perception**: 理解用户问题
2. **Planning**: 分析是否需要使用工具，制定计划
3. **Action**: 调用工具或直接回答
4. **Reflection**: 基于结果反思是否完成任务

## 工具调用格式
当需要使用工具时，你必须严格使用以下格式（务必包含 [TOOL_CALL] 和 [/TOOL_CALL] 标记）：

[TOOL_CALL]
{"tool": "工具名称", "arguments": {"参数名": "参数值"}}
[/TOOL_CALL]

### 正确示例
用户问："帮我计算 (125 + 375) * 2"
你的回答：
[TOOL_CALL]
{"tool": "calculator", "arguments": {"expression": "(125 + 375) * 2"}}
[/TOOL_CALL]

### 重要规则
- 必须用 [TOOL_CALL] 开头、[/TOOL_CALL] 结尾包裹工具调用
- 标记之间是合法的 JSON，包含 "tool" 和 "arguments" 两个字段
- 一次可以调用多个工具（写多个 [TOOL_CALL] 块）
- 收到工具返回结果后，用自然语言总结出最终答案，此时不要再输出 [TOOL_CALL]
- 如果不需要工具，直接用自然语言回答
"""
        return prompt

    def _parse_tool_calls(self, text: str) -> List[Dict]:
        """解析LLM输出中的工具调用"""
        # 优先解析标准格式：[TOOL_CALL]...[/TOOL_CALL]
        pattern = r'\[TOOL_CALL\](.*?)\[/TOOL_CALL\]'
        matches = re.findall(pattern, text, re.DOTALL)

        tool_calls = []
        for match in matches:
            try:
                call_data = json.loads(match.strip())
                tool_calls.append(call_data)
            except json.JSONDecodeError as e:
                print(f"⚠️ 工具调用解析失败: {e}")
                continue

        # 兜底：若没有标准标记，尝试从裸文本识别工具调用
        # （部分小模型不遵循标记格式，直接输出 "工具名\n{JSON}"）
        if not tool_calls:
            tool_calls = self._parse_tool_calls_fallback(text)

        return tool_calls

    def _parse_tool_calls_fallback(self, text: str) -> List[Dict]:
        """兜底解析：识别未包裹标记的工具调用格式"""
        tool_calls = []
        known_tools = set(self.tool_registry.tools.keys())

        # 提取文本中所有的 JSON 对象
        for json_match in re.finditer(r'\{.*?\}', text, re.DOTALL):
            snippet = json_match.group()
            try:
                data = json.loads(snippet)
            except json.JSONDecodeError:
                continue

            if not isinstance(data, dict):
                continue

            # 情况1：已经是 {"tool": ..., "arguments": ...} 格式
            if "tool" in data and data.get("tool") in known_tools:
                tool_calls.append({
                    "tool": data["tool"],
                    "arguments": data.get("arguments", {})
                })
                continue

            # 情况2：裸参数 JSON，前面一行是工具名，如 "calculator\n{...}"
            prefix = text[:json_match.start()]
            # 取 JSON 前最后出现的已知工具名
            matched_tool = None
            for tool_name in known_tools:
                if tool_name in prefix:
                    idx = prefix.rfind(tool_name)
                    if matched_tool is None or idx > matched_tool[1]:
                        matched_tool = (tool_name, idx)
            if matched_tool:
                tool_calls.append({
                    "tool": matched_tool[0],
                    "arguments": data
                })

        return tool_calls

    def _remove_tool_calls_from_text(self, text: str) -> str:
        """从文本中移除工具调用标记"""
        pattern = r'\[TOOL_CALL\].*?\[/TOOL_CALL\]'
        cleaned = re.sub(pattern, '', text, flags=re.DOTALL)
        return cleaned.strip()

    def _invoke_llm(self, messages: List[Dict], max_retries: int = 2) -> str:
        """调用 LLM 并处理异常与重试

        LLM 调用可能因网络抖动、限流等临时性原因失败，这里做有限次重试。
        重试仍失败则抛出 LLMInvokeError，由 run() 统一捕获并优雅降级。

        Args:
            messages: 发送给 LLM 的消息列表
            max_retries: 失败后的最大重试次数

        Returns:
            LLM 返回的文本内容

        Raises:
            LLMInvokeError: 重试后仍失败
        """
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                response = self.llm.invoke(messages)
                # invoke 返回 LLMResponse 对象，提取其中的文本内容
                if hasattr(response, "content"):
                    response = response.content
                return response or ""
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    wait = 1.5 * (attempt + 1)  # 简单线性退避
                    logger.warning(
                        f"LLM 调用失败（第 {attempt + 1}/{max_retries + 1} 次），"
                        f"{wait:.1f}s 后重试: {e}"
                    )
                    time.sleep(wait)
                else:
                    logger.error(f"LLM 调用最终失败（已重试 {max_retries} 次）: {e}")

        raise LLMInvokeError(f"LLM 调用失败: {last_error}")

    def run(self, user_input: str, session_id: Optional[str] = None) -> str:
        """
        运行Agent - 实现完整的4步循环
        
        Args:
            user_input: 用户输入
            session_id: 会话ID（可选）
        
        Returns:
            Agent的最终响应
        """
        # 获取或创建会话
        if session_id:
            session = self.session_manager.get_session(session_id)
            if not session:
                session = self.session_manager.create_session(session_id)
        else:
            session = self.session_manager.create_session()
        
        # 添加用户消息
        session.add_message(Message(role="user", content=user_input))

        print(f"\n{'='*60}")
        print(f"🤖 Agent Runtime 启动 (Session: {session.session_id[:8]})")
        print(f"{'='*60}")
        logger.info(f"Agent 启动 session={session.session_id[:8]} 输入={user_input[:50]}")

        iteration = 0
        final_response = ""

        try:
            final_response = self._run_loop(session)
        except LLMInvokeError as e:
            # LLM 调用彻底失败，优雅降级而非崩溃
            logger.error(f"运行终止（LLM 不可用）: {e}")
            session.add_trace(TraceEvent(
                step="error", iteration=iteration, error=str(e),
                detail={"type": "LLMInvokeError"}
            ))
            final_response = f"⚠️ 抱歉，AI 服务暂时不可用（{e}），请稍后重试。"
            session.add_message(Message(role="assistant", content=final_response))
        except Exception as e:
            # 兜底：任何未预期异常都不应让程序崩溃
            logger.error(f"运行发生未预期异常: {e}\n{traceback.format_exc()}")
            session.add_trace(TraceEvent(
                step="error", iteration=iteration, error=str(e),
                detail={"type": type(e).__name__, "traceback": traceback.format_exc()}
            ))
            final_response = f"⚠️ 处理请求时发生错误：{str(e)}"
            session.add_message(Message(role="assistant", content=final_response))

        print(f"\n{'='*60}")
        print(f"✅ Agent Runtime 完成")
        print(f"{'='*60}\n")

        return final_response

    def _run_loop(self, session: "Session") -> str:
        """Agent 主循环（被 run() 包裹以统一处理异常）"""
        iteration = 0
        final_response = ""

        while iteration < self.max_iterations:
            iteration += 1
            print(f"\n🔄 Iteration {iteration}/{self.max_iterations}")

            # Step 1: Perception - 构建上下文（带轮次限制 + 长度压缩）
            print("📥 Step 1: Perception - 理解用户问题")
            context = session.get_context(
                max_turns=self.max_turns,
                max_chars=self.max_context_chars,
            )
            session.add_trace(TraceEvent(
                step="perception", iteration=iteration,
                detail={"context_messages": len(context)}
            ))

            messages = [{"role": "system", "content": self._build_system_prompt()}]
            messages.extend(context)

            # Step 2: Planning - LLM决策（带重试与异常处理）
            print("🧠 Step 2: Planning - 分析并制定计划")
            t0 = time.time()
            llm_response = self._invoke_llm(messages)
            planning_ms = (time.time() - t0) * 1000
            print(f"   LLM输出: {llm_response[:200]}...")
            session.add_trace(TraceEvent(
                step="planning", iteration=iteration, duration_ms=round(planning_ms, 1),
                detail={"llm_output_preview": llm_response[:200]}
            ))

            # Step 3: Action - 执行工具或响应
            print("⚡ Step 3: Action - 执行操作")
            tool_calls = self._parse_tool_calls(llm_response)

            if tool_calls:
                tool_results = self._execute_tool_calls(tool_calls, session, iteration)

                # 保存assistant消息（包含工具调用）
                clean_response = self._remove_tool_calls_from_text(llm_response)
                session.add_message(Message(
                    role="assistant", content=clean_response, tool_calls=tool_calls
                ))
                # 保存工具结果消息
                tool_results_text = "\n".join(
                    f"工具 {tr['tool']} 返回: {tr['result']}" for tr in tool_results
                )
                session.add_message(Message(
                    role="tool", content=tool_results_text, tool_results=tool_results
                ))
            else:
                # 没有工具调用，这是最终回答
                print("   💬 无需工具，直接回答")
                final_response = llm_response
                session.add_message(Message(role="assistant", content=final_response))
                session.add_trace(TraceEvent(
                    step="final", iteration=iteration,
                    detail={"response_preview": final_response[:200]}
                ))
                break

            print("🔍 Step 4: Reflection - 评估任务完成情况")

        # 达到最大迭代次数仍无最终回答，强制生成一次
        if not final_response:
            print("\n⚠️ 达到最大迭代次数，生成最终回答...")
            logger.warning(f"达到最大迭代次数 {self.max_iterations}，强制收尾")
            context = session.get_context(
                max_turns=self.max_turns, max_chars=self.max_context_chars,
            )
            messages = [{"role": "system", "content": self._build_system_prompt()}]
            messages.extend(context)
            messages.append({
                "role": "user",
                "content": "请基于以上信息，给出完整的最终回答（不要再调用工具）"
            })
            final_response = self._invoke_llm(messages)
            session.add_message(Message(role="assistant", content=final_response))
            session.add_trace(TraceEvent(
                step="final", iteration=iteration,
                detail={"forced": True, "response_preview": final_response[:200]}
            ))

        return final_response

    def _execute_tool_calls(
        self, tool_calls: List[Dict], session: "Session", iteration: int
    ) -> List[Dict]:
        """执行一批工具调用，并逐个记录 trace"""
        tool_results = []
        for call in tool_calls:
            tool_name = call.get("tool")
            arguments = call.get("arguments", {})
            print(f"   🔧 调用工具: {tool_name}({arguments})")

            t0 = time.time()
            result = self.tool_registry.execute_tool(
                tool_name, arguments, session_id=session.session_id
            )
            duration_ms = round((time.time() - t0) * 1000, 1)
            # 工具返回以 ❌ 开头视为执行失败
            is_error = isinstance(result, str) and result.startswith("❌")

            tool_results.append({"tool": tool_name, "result": result})
            print(f"   {'⚠️' if is_error else '✅'} 工具结果: {result[:100]}...")

            session.add_trace(TraceEvent(
                step="tool_call", iteration=iteration, duration_ms=duration_ms,
                error=result if is_error else None,
                detail={
                    "tool": tool_name,
                    "arguments": arguments,
                    "result_preview": result[:200],
                    "success": not is_error,
                }
            ))
        return tool_results
