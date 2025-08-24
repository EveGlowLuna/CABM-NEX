import subprocess

def run_shell(command: str, timeout: int = 5) -> str:
    """
    执行终端命令并返回输出。
    - command: 要执行的命令（字符串）
    - timeout: 超时时间（秒，默认5s）
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        output = result.stdout.strip()
        error = result.stderr.strip()

        if result.returncode == 0:
            return output if output else "(命令执行成功，但没有输出)"
        else:
            return f"(执行失败，返回码 {result.returncode})\n{error or output}"

    except subprocess.TimeoutExpired:
        return f"(命令超时：超过 {timeout} 秒未完成)"
    except Exception as e:
        return f"(执行出错: {e})"
