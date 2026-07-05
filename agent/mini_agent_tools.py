# mini_agent_tools.py
"""
Agent工具实现：calculator、search(mock)、weather
"""

import re
import os
from typing import Dict, Any


def calculator_tool(expression: str) -> str:
    """
    计算器工具 - 执行数学计算

    Args:
        expression: 数学表达式，如 "2 + 3 * 4"

    Returns:
        计算结果
    """
    try:
        # 安全的数学表达式计算
        # 只允许数字、运算符和括号
        allowed_chars = set('0123456789+-*/().,= ')
        if not all(c in allowed_chars for c in expression):
            return "❌ 表达式包含非法字符"

        # 使用eval计算（在受控环境中）
        result = eval(expression)
        return f"计算结果: {result}"

    except Exception as e:
        return f"❌ 计算错误: {str(e)}"


def search_tool(query: str, limit: int = 3) -> str:
    """
    搜索工具 (Mock实现)

    Args:
        query: 搜索查询
        limit: 返回结果数量

    Returns:
        搜索结果
    """
    # Mock搜索结果
    mock_database = {
        "python": [
            "Python是一种高级编程语言，由Guido van Rossum于1991年发布",
            "Python以其简洁的语法和强大的库生态系统而闻名",
            "Python广泛应用于数据科学、机器学习、Web开发等领域"
        ],
        "agent": [
            "AI Agent是能够感知环境、做出决策并采取行动的智能系统",
            "Agent通常包含Perception、Planning、Action、Reflection四个核心环节",
            "常见的Agent框架包括LangChain、AutoGen、AgentScope等"
        ],
        "weather": [
            "天气预报通过气象卫星、雷达和地面观测站收集数据",
            "数值天气预报使用复杂的数学模型模拟大气运动",
            "机器学习正在改进天气预报的准确性"
        ],
        "ai": [
            "人工智能(AI)是计算机科学的一个分支",
            "AI的目标是创建能够执行通常需要人类智能的任务的系统",
            "深度学习是当前AI领域最重要的技术之一"
        ]
    }

    # 简单的关键词匹配
    results = []
    query_lower = query.lower()

    for key, values in mock_database.items():
        if key in query_lower:
            results.extend(values[:limit])
            break

    if not results:
        # 如果没有匹配，返回通用回答
        results = [f"关于 '{query}' 的搜索结果暂时无法获取，这是一个模拟搜索工具。"]

    return "\n".join([f"{i+1}. {r}" for i, r in enumerate(results[:limit])])


def weather_tool(location: str, date: str = "today") -> str:
    """
    天气查询工具 (Mock实现)

    Args:
        location: 地点
        date: 日期，默认为today

    Returns:
        天气信息
    """
    # Mock天气数据
    mock_weather = {
        "北京": {"temp": 15, "condition": "晴朗", "humidity": 45},
        "上海": {"temp": 20, "condition": "多云", "humidity": 65},
        "深圳": {"temp": 25, "condition": "小雨", "humidity": 80},
        "广州": {"temp": 23, "condition": "阴天", "humidity": 70},
        "杭州": {"temp": 18, "condition": "晴朗", "humidity": 55}
    }
    
    # 查找天气信息
    weather = None
    for city, data in mock_weather.items():
        if city in location or location in city:
            weather = data
            break
    
    if not weather:
        weather = {"temp": 20, "condition": "数据不可用", "humidity": 60}
    
    return f"{location} {date}的天气: {weather['condition']}, 温度{weather['temp']}°C, 湿度{weather['humidity']}%"


# 文档根目录：默认为本文件所在的 agent 目录，可通过环境变量 DOCS_ROOT 覆盖
DOCS_ROOT = os.environ.get("DOCS_ROOT", os.path.dirname(os.path.abspath(__file__)))

# 允许读取的文本文件扩展名（白名单，防止读取二进制/敏感文件）
_ALLOWED_DOC_EXTENSIONS = {".md", ".txt", ".py", ".json", ".yaml", ".yml", ".csv", ".rst", ".ini", ".cfg"}

# 单次读取的最大字符数，防止超大文件撑爆上下文
_MAX_DOC_CHARS = 8000


def read_docs(filename: str, max_chars: int = _MAX_DOC_CHARS) -> str:
    """
    文档读取工具 - 读取文档目录内的文本文件

    安全约束：
    - 只能读取 DOCS_ROOT 目录（及其子目录）内的文件，禁止路径穿越（如 ../../etc/passwd）
    - 只能读取白名单扩展名的文本文件
    - 超过 max_chars 的内容会被截断

    Args:
        filename: 相对于文档根目录的文件名，如 "README.md" 或 "docs/guide.txt"
        max_chars: 最大返回字符数，默认 8000

    Returns:
        文件内容，或错误信息
    """
    if not filename or not filename.strip():
        return "❌ 文件名不能为空"

    filename = filename.strip()

    # 扩展名白名单校验
    ext = os.path.splitext(filename)[1].lower()
    if ext not in _ALLOWED_DOC_EXTENSIONS:
        allowed = ", ".join(sorted(_ALLOWED_DOC_EXTENSIONS))
        return f"❌ 不允许读取 '{ext or '无扩展名'}' 类型的文件，仅支持: {allowed}"

    # 解析为绝对路径，并校验是否越界（防止路径穿越攻击）
    root = os.path.abspath(DOCS_ROOT)
    target = os.path.abspath(os.path.join(root, filename))

    # 关键安全检查：目标路径必须在文档根目录之内
    if os.path.commonpath([root, target]) != root:
        return f"❌ 拒绝访问：'{filename}' 超出了允许的文档目录范围"

    if not os.path.exists(target):
        return f"❌ 文件不存在: {filename}"

    if not os.path.isfile(target):
        return f"❌ '{filename}' 不是一个文件"

    try:
        with open(target, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        return f"❌ 无法以文本方式读取 '{filename}'（可能是二进制文件）"
    except Exception as e:
        return f"❌ 读取文件失败: {str(e)}"

    total_chars = len(content)
    if total_chars > max_chars:
        content = content[:max_chars]
        return (
            f"📄 文件 '{filename}'（共 {total_chars} 字符，已截断至前 {max_chars} 字符）:\n\n"
            f"{content}\n\n...[内容过长已截断]"
        )

    return f"📄 文件 '{filename}'（共 {total_chars} 字符）:\n\n{content}"


# 工具的Schema定义（供注册使用）
CALCULATOR_SCHEMA = {
    "type": "object",
    "properties": {
        "expression": {
            "type": "string",
            "description": "要计算的数学表达式，如 '2+3*4'"
        }
    },
    "required": ["expression"]
}

SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "搜索查询内容"
        },
        "limit": {
            "type": "integer",
            "description": "返回结果数量，默认3",
            "default": 3
        }
    },
    "required": ["query"]
}

WEATHER_SCHEMA = {
    "type": "object",
    "properties": {
        "location": {
            "type": "string",
            "description": "查询天气的地点，如 '北京'、'上海'"
        },
        "date": {
            "type": "string",
            "description": "查询日期，默认为today",
            "default": "today"
        }
    },
    "required": ["location"]
}

READ_DOCS_SCHEMA = {
    "type": "object",
    "properties": {
        "filename": {
            "type": "string",
            "description": "要读取的文档文件名，相对于文档目录，如 'README.md'、'docs/guide.txt'"
        },
        "max_chars": {
            "type": "integer",
            "description": "最大返回字符数，默认8000",
            "default": 8000
        }
    },
    "required": ["filename"]
}
