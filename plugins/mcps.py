from . import file
from . import searcher
from . import shell
from typing import Dict, Any


TOOLS = {
    "read_file": file.read_file,
    "update_file": file.update_file,
    "create_file": file.create_file,
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
    "search_and_fetch": {
        "desc": "使用Bing搜索并抓取页面摘要。返回列表[{title,url,snippet,summary}]。",
        "args": {
            "query": "搜索关键词",
            "count": "可选，结果数量，默认3",
            "max_length": "可选，摘要最大长度，默认500"
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
            "timeout": "可选，秒，默认30"
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