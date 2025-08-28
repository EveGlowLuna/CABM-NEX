import os
import re

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


def append_file(file_path: str, content: str) -> str:
    """
    追加内容到文件末尾
    :param file_path: 文件路径
    :param content: 要追加的内容
    :return: 操作结果字符串
    """
    try:
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(content)
        return "文件追加成功"
    except Exception as e:
        return f"文件追加失败: {str(e)}"


def insert_content(file_path: str, line: int, content: str) -> str:
    """
    在指定行插入内容
    :param file_path: 文件路径
    :param line: 插入行号（1-based）
    :param content: 要插入的内容
    :return: 操作结果字符串
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        if line < 1 or line > len(lines) + 1:
            return f"插入失败: 行号超出范围(1-{len(lines)+1})"

        lines.insert(line - 1, content + '\n')

        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)

        return "内容插入成功"
    except Exception as e:
        return f"内容插入失败: {str(e)}"


def search_replace(file_path: str, old_content: str, new_content: str, use_regex: bool = False) -> str:
    """
    搜索并替换文件内容
    :param file_path: 文件路径
    :param old_content: 要替换的旧内容
    :param new_content: 新内容
    :param use_regex: 是否使用正则表达式
    :return: 操作结果字符串
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            file_content = f.read()

        if use_regex:
            try:
                file_content = re.sub(old_content, new_content, file_content)
            except re.error as e:
                return f"正则替换失败: {str(e)}"
        else:
            file_content = file_content.replace(old_content, new_content)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(file_content)

        return "搜索替换成功"
    except Exception as e:
        return f"搜索替换失败: {str(e)}"


def delete_lines(file_path: str, start_line: int, end_line: int) -> str:
    """
    删除指定行范围的内容
    :param file_path: 文件路径
    :param start_line: 起始行号（1-based）
    :param end_line: 结束行号（1-based）
    :return: 操作结果字符串
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        if start_line < 1 or end_line < start_line or end_line > len(lines):
            return f"删除失败: 行号范围无效(1-{len(lines)})"

        del lines[start_line - 1:end_line]

        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)

        return f"删除成功: 删除了 {end_line - start_line + 1} 行"
    except Exception as e:
        return f"删除失败: {str(e)}"
