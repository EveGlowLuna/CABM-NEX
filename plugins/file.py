import os

def create_file(file_path: str) -> bool:
    """
    创建文件函数
    :param file_path: 文件路径
    :return: 是否创建成功
    """
    try:
        with open(file_path, 'w'):
            pass
        return True
    except Exception as e:
        return False


def read_file(file_path: str, start_line: str, end_line: str) -> str:
    try:
        sline = int(start_line) - 1
        eline = int(end_line) - 1
        if eline - sline > 200:
            return f"文件读取失败: 超出范围(预期：200，当前：{eline - sline})"
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            return "\n".join(lines[sline:eline])
    except Exception as e:
        return f"文件读取失败: {str(e)}"

def update_file(file_path: str, content: str) -> str:
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return "文件更新成功"
    except Exception as e:
        return f"文件更新失败: {str(e)}"
