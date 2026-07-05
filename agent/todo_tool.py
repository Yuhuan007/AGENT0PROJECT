# todo_tool.py
"""
待办清单工具（按会话隔离）

关键设计：待办数据以 session_id 为 key 分开存储，
不同会话（不同窗口）的待办互不可见、互不影响。
"""

from typing import Dict, List

# 按会话隔离的待办存储：{session_id: [待办1, 待办2, ...]}
_TODO_STORE: Dict[str, List[str]] = {}


def add_todo(content: str, session_id: str = "default") -> str:
    """
    添加一条待办事项到当前会话

    Args:
        content: 待办内容
        session_id: 会话 ID（由运行时自动注入，无需 LLM 提供）

    Returns:
        操作结果
    """
    todos = _TODO_STORE.setdefault(session_id, [])
    todos.append(content)
    return f"已添加待办：{content}（当前会话共 {len(todos)} 条待办）"


def list_todos(session_id: str = "default") -> str:
    """
    列出当前会话的所有待办事项

    Args:
        session_id: 会话 ID（由运行时自动注入）

    Returns:
        待办列表
    """
    todos = _TODO_STORE.get(session_id, [])
    if not todos:
        return "当前会话暂无待办事项。"

    lines = [f"{i + 1}. {item}" for i, item in enumerate(todos)]
    return "当前会话的待办事项：\n" + "\n".join(lines)


# ---- 供测试直接读取存储用的辅助函数（不注册给 LLM） ----
def _get_raw_todos(session_id: str) -> List[str]:
    """返回某会话的原始待办列表（测试断言用）"""
    return list(_TODO_STORE.get(session_id, []))


def _clear_all():
    """清空所有会话的待办（测试隔离用）"""
    _TODO_STORE.clear()


# 工具 Schema 定义
ADD_TODO_SCHEMA = {
    "type": "object",
    "properties": {
        "content": {
            "type": "string",
            "description": "要添加的待办事项内容"
        }
    },
    "required": ["content"]
}

LIST_TODOS_SCHEMA = {
    "type": "object",
    "properties": {},
    "required": []
}
