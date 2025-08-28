import subprocess
import os
import sys
import platform
from typing import Optional, Tuple
import logging

logger = logging.getLogger("shell")

def detect_powershell_version() -> Tuple[Optional[str], Optional[str]]:
    """
    检测系统中可用的PowerShell版本

    Returns:
        Tuple[powershell_path, version]: PowerShell路径和版本信息
    """
    import shutil

    # 可能的PowerShell安装路径
    possible_paths = [
        # PowerShell Core 7+ 常见安装路径
        r"C:\Program Files\PowerShell\7\pwsh.exe",
        r"C:\Program Files\PowerShell\7-preview\pwsh.exe",
        r"C:\Program Files\PowerShell\6\pwsh.exe",
        r"C:\Program Files (x86)\PowerShell\7\pwsh.exe",
        r"C:\Program Files (x86)\PowerShell\6\pwsh.exe",
        # Windows PowerShell 5.1 路径
        r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
        r"C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe",
    ]

    # 首先尝试PATH中的pwsh.exe
    pwsh_path = shutil.which("pwsh.exe")
    if pwsh_path:
        possible_paths.insert(0, pwsh_path)

    # 然后尝试PATH中的powershell.exe
    powershell_path = shutil.which("powershell.exe")
    if powershell_path:
        possible_paths.insert(0, powershell_path)

    # 按优先级检测PowerShell版本
    best_version = None
    best_path = None

    for ps_path in possible_paths:
        if not os.path.exists(ps_path):
            continue

        try:
            # 使用完整路径运行PowerShell版本检查命令
            version_cmd = f'"{ps_path}" -Command "$PSVersionTable.PSVersion.ToString()"'
            result = subprocess.run(
                version_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0 and result.stdout.strip():
                version = result.stdout.strip()
                ps_name = "pwsh.exe" if "pwsh" in ps_path.lower() else "powershell.exe"

                logger.info(f"检测到PowerShell: {ps_path}, 版本: {version}")

                # 比较版本，优先选择更高版本
                if best_version is None:
                    best_version = version
                    best_path = ps_path
                else:
                    # 简单的版本比较 (只比较主版本号)
                    current_major = int(version.split('.')[0]) if '.' in version else 0
                    best_major = int(best_version.split('.')[0]) if '.' in best_version else 0

                    if current_major > best_major:
                        best_version = version
                        best_path = ps_path
                    elif current_major == best_major:
                        # 相同主版本，优先选择pwsh (PowerShell Core)
                        if "pwsh" in ps_path.lower() and "pwsh" not in best_path.lower():
                            best_version = version
                            best_path = ps_path

        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError, Exception):
            continue

    if best_path and best_version:
        ps_name = "pwsh.exe" if "pwsh" in best_path.lower() else "powershell.exe"
        logger.info(f"选择最佳PowerShell: {best_path}, 版本: {best_version}")
        return ps_name, best_version

    logger.warning("未检测到PowerShell")
    return None, None

def get_powershell_full_path(ps_exe: str) -> Optional[str]:
    """
    获取PowerShell的完整路径

    Args:
        ps_exe: PowerShell可执行文件名

    Returns:
        完整路径或None
    """
    import shutil

    # 如果已经包含路径，直接返回
    if "\\" in ps_exe or "/" in ps_exe:
        return ps_exe

    # 可能的PowerShell安装路径
    possible_paths = [
        # PowerShell Core 7+ 常见安装路径
        r"C:\Program Files\PowerShell\7\pwsh.exe",
        r"C:\Program Files\PowerShell\7-preview\pwsh.exe",
        r"C:\Program Files\PowerShell\6\pwsh.exe",
        r"C:\Program Files (x86)\PowerShell\7\pwsh.exe",
        r"C:\Program Files (x86)\PowerShell\6\pwsh.exe",
        # Windows PowerShell 5.1 路径
        r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
        r"C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe",
    ]

    if ps_exe == "pwsh.exe":
        # 搜索pwsh.exe
        pwsh_path = shutil.which("pwsh.exe")
        if pwsh_path:
            return pwsh_path

        # 检查常见安装路径
        for path in possible_paths:
            if "pwsh.exe" in path.lower() and os.path.exists(path):
                return path

    elif ps_exe == "powershell.exe":
        # 搜索powershell.exe
        powershell_path = shutil.which("powershell.exe")
        if powershell_path:
            return powershell_path

        # 检查常见安装路径
        for path in possible_paths:
            if "powershell.exe" in path.lower() and os.path.exists(path):
                return path

    return None

def format_powershell_command(command: str, ps_exe: str) -> str:
    """
    根据PowerShell版本格式化命令

    Args:
        command: 原始命令
        ps_exe: PowerShell可执行文件路径（可以是文件名或完整路径）

    Returns:
        格式化后的命令
    """
    # 如果ps_exe包含路径分隔符，说明是完整路径
    if "\\" in ps_exe or "/" in ps_exe:
        # 使用完整路径
        return f'"{ps_exe}" -Command "{command}"'
    else:
        # 使用环境变量PATH中的可执行文件
        if ps_exe == "pwsh.exe":
            # PowerShell Core (pwsh) 支持更现代的语法
            return f'{ps_exe} -Command "{command}"'
        else:
            # Windows PowerShell (powershell.exe)
            return f'{ps_exe} -Command "{command}"'

def run_shell(command: str, timeout: int = 30) -> str:
    """
    执行终端命令并返回输出，优先使用PowerShell。

    Args:
        command: 要执行的命令（字符串）
        timeout: 超时时间（秒，默认30s）

    Returns:
        命令执行结果
    """
    os_name = platform.system()
    try:
        logger.info(f"执行命令: {command}")

        # 检测PowerShell版本
        ps_exe, ps_version = detect_powershell_version()

        if ps_exe and ps_version:
            # 获取完整的PowerShell路径
            full_ps_path = get_powershell_full_path(ps_exe)
            if full_ps_path:
                # 使用完整路径的PowerShell执行命令
                formatted_command = format_powershell_command(command, full_ps_path)
                logger.info(f"使用PowerShell执行: {full_ps_path} (版本: {ps_version})")
            else:
                logger.warning(f"无法获取 {ps_exe} 的完整路径，使用默认shell")
                formatted_command = command
        else:
            # 回退到默认shell
            formatted_command = command
            logger.info("未检测到PowerShell，使用默认shell")

        # 执行命令
        result = subprocess.run(
            formatted_command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        output = result.stdout.strip()
        error = result.stderr.strip()

        logger.info(f"命令执行完成，返回码: {result.returncode}")

        if result.returncode == 0:
            response = output if output else "(命令执行成功，但没有输出)"
            return f"[OS: {os_name}] {response}"
        else:
            error_msg = f"(执行失败，返回码 {result.returncode})"
            if error:
                error_msg += f"\n错误信息: {error}"
            if output:
                error_msg += f"\n输出信息: {output}"
            return f"[OS: {os_name}] {error_msg}"

    except subprocess.TimeoutExpired:
        logger.error(f"命令超时: {command}")
        return f"[OS: {os_name}] (命令超时：超过 {timeout} 秒未完成)"
    except Exception as e:
        logger.error(f"命令执行出错: {command}, 错误: {str(e)}")
        return f"[OS: {os_name}] (执行出错: {e})"