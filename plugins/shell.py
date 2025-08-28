import subprocess
import os
import sys
import platform
from typing import Optional, Tuple
import logging
import shutil

logger = logging.getLogger("shell")

def _get_system_shell() -> str:
    """
    根据操作系统获取默认shell
    
    Returns:
        适合当前系统的shell命令
    """
    system = platform.system().lower()
    
    if system == "windows":
        # Windows系统优先使用cmd，也支持PowerShell
        return "cmd"
    elif system in ["linux", "darwin"]:  # Linux或macOS
        # Unix-like系统检查常用shell
        common_shells = ["/bin/bash", "/bin/zsh", "/bin/sh"]
        for shell in common_shells:
            if os.path.exists(shell):
                return shell
        return "/bin/sh"  # 默认fallback
    else:
        # 其他系统使用系统默认shell
        return os.environ.get("SHELL", "/bin/sh")

def _is_powershell_available() -> Tuple[bool, Optional[str], Optional[str]]:
    """
    检查系统中是否可用PowerShell
    
    Returns:
        Tuple[是否可用, PowerShell路径, 版本信息]
    """
    # 可能的PowerShell安装路径
    possible_paths = [
        # PowerShell Core 7+ 常见安装路径
        "pwsh.exe",  # 在PATH中的pwsh
        r"C:\Program Files\PowerShell\7\pwsh.exe",
        r"C:\Program Files\PowerShell\7-preview\pwsh.exe",
        # Windows PowerShell 5.1 路径
        "powershell.exe",  # 在PATH中的powershell
        r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
    ]

    # 按优先级检测PowerShell版本
    for ps_cmd in possible_paths:
        if not ps_cmd:
            continue
            
        # 检查可执行文件是否存在
        ps_path = shutil.which(ps_cmd) if not os.path.isabs(ps_cmd) else ps_cmd
        if not ps_path or not os.path.exists(ps_path):
            continue

        try:
            # 使用完整路径运行PowerShell版本检查命令
            if platform.system().lower() == "windows":
                version_cmd = [ps_path, "-Command", "$PSVersionTable.PSVersion.ToString()"]
            else:
                # 非Windows系统可能有PowerShell Core
                version_cmd = [ps_path, "-c", "$PSVersionTable.PSVersion.ToString()"]
                
            result = subprocess.run(
                version_cmd,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0 and result.stdout.strip():
                version = result.stdout.strip()
                logger.info(f"检测到PowerShell: {ps_path}, 版本: {version}")
                return True, ps_path, version

        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError, Exception):
            continue

    return False, None, None

def _format_command_for_shell(command: str, shell: str, venv: Optional[str] = None) -> list:
    """
    根据shell类型格式化命令，支持虚拟环境
    
    Args:
        command: 原始命令
        shell: shell路径
        venv: 虚拟环境路径（可选）
        
    Returns:
        格式化后的命令列表
    """
    shell_name = os.path.basename(shell).lower()
    
    # 构建激活虚拟环境的命令
    activation_cmd = ""
    if venv:
        venv = os.path.abspath(venv)
        if platform.system().lower() == "windows":
            # Windows系统
            if "powershell" in shell_name or "pwsh" in shell_name:
                # PowerShell环境
                activation_script = os.path.join(venv, "Scripts", "Activate.ps1")
                if os.path.exists(activation_script):
                    activation_cmd = f'. "{activation_script}"; '
            else:
                # cmd环境
                activation_script = os.path.join(venv, "Scripts", "activate.bat")
                if os.path.exists(activation_script):
                    activation_cmd = f'"{activation_script}" && '
        else:
            # Unix-like系统 (Linux/macOS)
            activation_script = os.path.join(venv, "bin", "activate")
            if os.path.exists(activation_script):
                activation_cmd = f'source "{activation_script}" && '

    full_command = activation_cmd + command

    if "powershell" in shell_name or "pwsh" in shell_name:
        if platform.system().lower() == "windows":
            return [shell, "-Command", full_command]
        else:
            return [shell, "-c", full_command]
    elif "cmd" in shell_name:
        return [shell, "/c", full_command]
    else:
        # Unix-like shells (bash, zsh, sh, etc.)
        return [shell, "-c", full_command]

def _should_use_powershell(command: str, ps_available: bool) -> bool:
    """
    根据命令特征决定是否使用PowerShell
    """
    if not ps_available:
        return False
        
    # 在Windows系统上，根据命令特征决定是否使用PowerShell
    if platform.system().lower() != "windows":
        return False
        
    # 对于明显的PowerShell命令，使用PowerShell
    ps_indicators = [".ps1", "Get-", "Set-", "New-", "Remove-", "Where-Object", "ForEach-Object"]
    return any(indicator in command for indicator in ps_indicators)

def _determine_shell_to_use(default_shell: str, use_powershell: bool, ps_path: Optional[str]) -> str:
    """
    确定最终使用的shell
    """
    if use_powershell and ps_path:
        return ps_path
    else:
        return default_shell

def _execute_command(formatted_command: list, timeout: int, os_name: str, command: str) -> str:
    """
    执行格式化后的命令并返回结果
    """
    try:
        # 执行命令
        result = subprocess.run(
            formatted_command,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding='utf-8'
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
    except UnicodeDecodeError as e:
        logger.error(f"编码错误: {command}, 错误: {str(e)}")
        return f"[OS: {os_name}] (编码错误: {e})"
    except Exception as e:
        logger.error(f"命令执行出错: {command}, 错误: {str(e)}")
        return f"[OS: {os_name}] (执行出错: {e})"

def run_shell(command: str, timeout: int = 30, venv: Optional[str] = None) -> str:
    """
    执行终端命令并返回输出，根据操作系统选择合适的shell。
    
    Args:
        command: 要执行的命令（字符串）
        timeout: 超时时间（秒，默认30s）
        venv: 虚拟环境路径（可选）

    Returns:
        命令执行结果
    """
    os_name = platform.system()
    try:
        logger.info(f"执行命令: {command}")
        if venv:
            logger.info(f"使用虚拟环境: {venv}")
        
        # 获取系统默认shell
        default_shell = _get_system_shell()
        logger.info(f"使用系统默认shell: {default_shell}")
        
        # 检查是否可以使用PowerShell（仅在需要时）
        use_powershell = False
        ps_available, ps_path, ps_version = _is_powershell_available()
        
        # 根据命令特征决定是否使用PowerShell
        if _should_use_powershell(command, ps_available):
            use_powershell = True
            logger.info(f"检测到PowerShell命令特征，使用PowerShell: {ps_path} (版本: {ps_version})")

        # 确定最终使用的shell
        shell_to_use = _determine_shell_to_use(default_shell, use_powershell, ps_path)
            
        # 格式化命令
        formatted_command = _format_command_for_shell(command, shell_to_use, venv)
        logger.info(f"使用shell执行: {shell_to_use}")

        # 执行命令
        return _execute_command(formatted_command, timeout, os_name, command)

    except Exception as e:
        logger.error(f"命令执行出错: {command}, 错误: {str(e)}")
        return f"[OS: {os_name}] (执行出错: {e})"