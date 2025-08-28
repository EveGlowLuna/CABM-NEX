from . import file
from . import searcher
from . import shell
from typing import Dict, Any


TOOLS = {
    "read_file": file.read_file,
    "update_file": file.update_file,
    "create_file": file.create_file,
    "append_file": file.append_file,
    "insert_content": file.insert_content,
    "search_replace": file.search_replace,
    "delete_lines": file.delete_lines,
    "search_and_fetch": searcher.search_and_fetch,
    "run_shell": shell.run_shell
}

# 为提示词准备的工具描述元数据
TOOL_DESCRIPTIONS = {
    "read_file": {
        "desc": "读取指定文件的部分内容。返回字符串内容或错误描述。",
        "args": {
            "file_path": "字符串，绝对或相对路径",
            "start_line": "起始行(字符串或数字)",
            "end_line": "结束行(字符串或数字，最多读取200行)"
        },
        "example": {
            "tool_request": {
                "name": "read_file",
                "args": {"file_path": "path/to/file.py", "start_line": 0, "end_line": 100},
                "reason": "需要阅读文件以回答问题"
            }
        }
    },
    "update_file": {
        "desc": "用给定内容覆盖写入文件。返回操作结果字符串。",
        "args": {
            "file_path": "字符串，文件路径",
            "content": "写入的完整文本内容"
        },
        "example": {
            "tool_request": {
                "name": "update_file",
                "args": {"file_path": "path/to/file.py", "content": "new content"},
                "reason": "需要修改文件"
            }
        }
    },
    "create_file": {
        "desc": "创建文件。返回操作结果字符串。",
        "args": {
            "file_path": "字符串，文件路径"
        },
        "example": {
            "tool_request": {
                "name": "create_file",
                "args": {"file_path": "path/to/file.py"},
                "reason": "需要创建文件"
            }
        }
    },
    "append_file": {
        "desc": "在文件末尾追加内容。返回操作结果字符串。",
        "args": {
            "file_path": "字符串，文件路径",
            "content": "要追加的文本内容"
        },
        "example": {
            "tool_request": {
                "name": "append_file",
                "args": {"file_path": "path/to/file.py", "content": "\nprint('hello')"},
                "reason": "需要在文件末尾添加代码"
            }
        }
    },
    "insert_content": {
        "desc": "在指定行插入内容。返回操作结果字符串。",
        "args": {
            "file_path": "字符串，文件路径",
            "line": "整数，插入行号（1-based）",
            "content": "要插入的文本内容"
        },
        "example": {
            "tool_request": {
                "name": "insert_content",
                "args": {"file_path": "path/to/file.py", "line": 5, "content": "# 新注释"},
                "reason": "需要在第5行插入注释"
            }
        }
    },
    "search_replace": {
        "desc": "搜索并替换文件内容，支持正则表达式。返回操作结果字符串。",
        "args": {
            "file_path": "字符串，文件路径",
            "old_content": "要替换的旧内容",
            "new_content": "新内容",
            "use_regex": "可选，布尔值，是否使用正则表达式，默认false"
        },
        "example": {
            "tool_request": {
                "name": "search_replace",
                "args": {"file_path": "path/to/file.py", "old_content": "old_var", "new_content": "new_var"},
                "reason": "需要替换变量名"
            }
        }
    },
    "delete_lines": {
        "desc": "删除指定行范围的内容。返回操作结果字符串。",
        "args": {
            "file_path": "字符串，文件路径",
            "start_line": "整数，起始行号（1-based）",
            "end_line": "整数，结束行号（1-based）"
        },
        "example": {
            "tool_request": {
                "name": "delete_lines",
                "args": {"file_path": "path/to/file.py", "start_line": 10, "end_line": 15},
                "reason": "需要删除第10-15行的内容"
            }
        }
    },
    "search_and_fetch": {
        "desc": "使用多个搜索引擎（Bing、百度、Google）搜索并抓取页面摘要。返回列表[{title,url,snippet,summary,engine}]。",
        "args": {
            "query": "搜索关键词",
            "count": "可选，结果数量，默认3",
            "max_length": "可选，摘要最大长度，默认1000"
        },
        "example": {
            "tool_request": {
                "name": "search_and_fetch",
                "args": {"query": "最新Python特性", "count": 2},
                "reason": "需要实时信息"
            }
        }
    },
    "run_shell": {
        "desc": "在受限环境中执行命令（超时默认5秒）。返回标准输出或错误信息。",
        "args": {
            "command": "要执行的命令字符串",
            "timeout": "可选，秒，默认30",
            "venv": "可选，虚拟环境文件夹路径，将在执行命令前激活指定的虚拟环境"
        },
        "example": {
            "tool_request": {
                "name": "run_shell",
                "args": {"command": "echo hello", "timeout": 3},
                "reason": "需要系统信息或运行简单命令"
            }
        }
    }
}

def call_tool(tool_name: str, args: Dict[str, Any]) -> Any:
    if tool_name not in TOOLS:
        return {"status": "error", "error": f"未知工具: {tool_name}"}
    return TOOLS[tool_name](**args)

def list_tools_for_prompt() -> Dict[str, Any]:
    """返回工具描述，供系统提示词注入。"""
    return TOOL_DESCRIPTIONS