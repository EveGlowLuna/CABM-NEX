# -*- coding: utf-8 -*-
"""
Frpc客户端管理服务
负责下载、配置和运行frpc客户端
"""
import os
import json
import platform
import subprocess
import requests
import zipfile
import tarfile
from pathlib import Path
from typing import Dict, Optional, List, Any
import logging

logger = logging.getLogger(__name__)


def _mask_token(token: str) -> str:
    """
    在日志中对 token 进行脱敏：将第5-10个字符替换为 '*'
    - 若长度 < 5，不做处理
    - 若 5 <= 长度 <= 10，则从第5位开始全部替换为 '*'
    - 其他情况：仅替换第5-10位（含）
    """
    try:
        if not isinstance(token, str):
            return "***"
        n = len(token)
        if n < 5:
            return token
        start = 4  # 第5个字符的下标
        end = min(10, n)  # 直到第10个字符（含）
        masked_len = end - start
        return token[:start] + ("*" * masked_len) + token[end:]
    except Exception:
        return "***"

class FrpcService:
    def __init__(self):
        self.project_root = Path(__file__).resolve().parent.parent
        self.frpc_dir = self.project_root / "frpc"
        self.frpc_path = None
        self.config_file = self.frpc_dir / "frpc.ini"
        self.ensure_frpc_dir()

    def ensure_frpc_dir(self):
        """确保frpc目录存在"""
        self.frpc_dir.mkdir(exist_ok=True)

    def get_software_info(self) -> Dict[str, any]:
        """
        获取OpenFrp软件资源信息
        """
        try:
            response = requests.get("https://api.openfrp.net/commonQuery/get?key=software")
            response.raise_for_status()
            data = response.json()
            if data.get('flag'):
                return data.get('data', {})
            else:
                logger.error(f"获取软件信息失败: {data.get('msg')}")
                return {}
        except Exception as e:
            logger.error(f"获取软件信息失败: {e}")
            return {}

    def get_download_url(self, software_info: Dict) -> Optional[str]:
        """
        根据系统架构生成下载URL
        使用多个备用下载源
        """
        if not software_info:
            return None

        latest_full = software_info.get('latest_full', '')
        if not latest_full:
            return None

        # 确定系统类型和架构
        system = platform.system().lower()
        machine = platform.machine().lower()

        # 映射系统名称
        system_map = {
            'windows': 'windows',
            'linux': 'linux',
            'darwin': 'darwin',  # 修正macOS的映射
            'freebsd': 'freebsd'
        }

        # 映射架构
        arch_map = {
            'x86_64': 'amd64',
            'amd64': 'amd64',
            'i386': '386',
            'i686': '386',
            'armv7l': 'arm',
            'armv8': 'arm64',
            'aarch64': 'arm64',
            'arm64': 'arm64',
            'armv6': 'arm6',
            'armv5': 'arm5',
            'mips': 'mips',
            'mips64': 'mips64',
            's390x': 's390x'
        }

        sys_name = system_map.get(system, 'linux')
        arch_name = arch_map.get(machine, 'amd64')

        # 构建文件名
        if sys_name == 'windows':
            file_name = f"frpc_windows_{arch_name}.zip"
        else:
            file_name = f"frpc_{sys_name}_{arch_name}.tar.gz"

        # 备用下载源列表（按优先级排序）
        fallback_sources = [
            "https://r.zyghit.cn/download/client",  # 首选高速下载源
            "https://staticassets.naids.com/client",  # 原下载源
            "https://api.openfrp.net"  # API备用源
        ]

        # 尝试每个下载源
        for base_url in fallback_sources:
            download_url = f"{base_url.rstrip('/')}/{latest_full}/{file_name}"
            logger.info(f"尝试下载源: {download_url}")
            return download_url

        return None

    def download_frpc(self, url: str) -> bool:
        """
        下载frpc客户端，支持重试机制
        """
        max_retries = 3

        for attempt in range(max_retries):
            try:
                logger.info(f"尝试下载frpc (第{attempt + 1}次): {url}")
                response = requests.get(url, stream=True, timeout=30)
                response.raise_for_status()

                # 确定文件名
                filename = url.split('/')[-1]
                download_path = self.frpc_dir / filename

                # 下载文件
                with open(download_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

                logger.info(f"下载完成: {download_path}")

                # 解压文件
                return self.extract_frpc(download_path)

            except requests.exceptions.RequestException as e:
                logger.warning(f"下载尝试 {attempt + 1} 失败: {e}")
                if attempt < max_retries - 1:
                    continue
            except Exception as e:
                logger.error(f"下载frpc失败: {e}")
                return False

        return False

    def extract_frpc(self, archive_path: Path) -> bool:
        """
        解压frpc客户端
        """
        try:
            if archive_path.name.endswith('.zip'):
                with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                    zip_ref.extractall(self.frpc_dir)
            elif archive_path.name.endswith('.tar.gz'):
                with tarfile.open(archive_path, 'r:gz') as tar_ref:
                    tar_ref.extractall(self.frpc_dir)

            # 查找frpc可执行文件
            for file in self.frpc_dir.glob('**/frpc*'):
                # 优先选择 Windows 下的 .exe 文件，其次选择可执行权限文件
                if file.is_file() and (file.suffix.lower() == '.exe' or os.access(file, os.X_OK)):
                    self.frpc_path = file
                    logger.info(f"找到frpc: {self.frpc_path}")
                    break

            # 清理下载文件
            archive_path.unlink()

            return self.frpc_path is not None

        except Exception as e:
            logger.error(f"解压frpc失败: {e}")
            return False

    def ensure_frpc_available(self) -> bool:
        """
        确保frpc客户端可用，支持多源下载
        """
        # 检查是否已有frpc
        if self.frpc_path and self.frpc_path.exists():
            return True

        # 查找现有frpc
        for file in self.frpc_dir.glob('**/frpc*'):
            if file.is_file() and (os.access(file, os.X_OK) or file.name.endswith('.exe') or 'frpc' in file.name):
                self.frpc_path = file
                logger.info(f"找到frpc文件: {self.frpc_path}")
                return True

        # 如果没找到，尝试查找frpc目录中的所有exe文件
        for file in self.frpc_dir.glob('*.exe'):
            if 'frpc' in file.name:
                self.frpc_path = file
                logger.info(f"找到frpc文件 (备用查找): {self.frpc_path}")
                return True

        # 下载frpc
        logger.info("未找到frpc客户端，开始下载...")
        software_info = self.get_software_info()
        if not software_info:
            logger.error("无法获取软件信息")
            return False

        # 获取所有可能的下载URL
        download_urls = []
        latest_full = software_info.get('latest_full', '')
        if latest_full:
            # 备用下载源列表（按优先级排序）
            fallback_sources = [
                "https://r.zyghit.cn/download/client",  # 首选高速下载源
                "https://staticassets.naids.com/client",  # 原下载源
                "https://api.openfrp.net"  # API备用源
            ]

            # 确定系统类型和架构
            system = platform.system().lower()
            machine = platform.machine().lower()

            system_map = {
                'windows': 'windows',
                'linux': 'linux',
                'darwin': 'darwin',
                'freebsd': 'freebsd'
            }

            arch_map = {
                'x86_64': 'amd64',
                'amd64': 'amd64',
                'i386': '386',
                'i686': '386',
                'armv7l': 'arm',
                'armv8': 'arm64',
                'aarch64': 'arm64',
                'arm64': 'arm64',
                'armv6': 'arm6',
                'armv5': 'arm5',
                'mips': 'mips',
                'mips64': 'mips64',
                's390x': 's390x'
            }

            sys_name = system_map.get(system, 'linux')
            arch_name = arch_map.get(machine, 'amd64')

            # 构建文件名
            if sys_name == 'windows':
                file_name = f"frpc_windows_{arch_name}.zip"
            else:
                file_name = f"frpc_{sys_name}_{arch_name}.tar.gz"

            # 生成所有下载URL
            for base_url in fallback_sources:
                download_urls.append(f"{base_url.rstrip('/')}/{latest_full}/{file_name}")

        # 尝试每个下载源
        for download_url in download_urls:
            logger.info(f"尝试下载源: {download_url}")
            if self.download_frpc(download_url):
                return True

        logger.error("所有下载源都失败了")
        return False

    def create_config(self, tunnels: List[Dict]) -> bool:
        """
        创建frpc配置文件
        """
        try:
            config = {
                'common': {
                    'server_addr': 'openfrp.net',
                    'server_port': 7000,
                    'token': '',  # 将在运行时设置
                    'log_file': str(self.frpc_dir / 'frpc.log'),
                    'log_level': 'info',
                    'log_max_days': 3
                },
                'proxies': []
            }

            for tunnel in tunnels:
                proxy_config = {
                    'name': tunnel['name'],
                    'type': 'tcp',
                    'local_ip': tunnel['local_addr'],
                    'local_port': tunnel['local_port'],
                    'remote_port': tunnel['remote_port']
                }
                config['proxies'].append(proxy_config)

            with open(self.config_file, 'w', encoding='utf-8') as f:
                # 写入common部分
                f.write('[common]\n')
                for key, value in config['common'].items():
                    f.write(f'{key} = {value}\n')
                f.write('\n')

                # 写入proxy部分
                for i, proxy in enumerate(config['proxies']):
                    f.write(f'[proxy{i}]\n')
                    for key, value in proxy.items():
                        f.write(f'{key} = {value}\n')
                    f.write('\n')

            return True

        except Exception as e:
            logger.error(f"创建配置文件失败: {e}")
            return False

    def run_frpc(self, token: str, proxy_id: Optional[int] = None, timeout: int = 10) -> subprocess.Popen:
        """
        运行frpc客户端，使用OpenFrp简易启动方式（无配置文件）
        """
        if not self.ensure_frpc_available():
            raise Exception("无法获取frpc客户端")

        # 进一步校验可执行文件路径，避免 WinError 193
        if not self.frpc_path or not Path(self.frpc_path).exists():
            raise Exception(f"frpc可执行文件不存在: {self.frpc_path}")
        # 在 Windows 上强制要求 .exe 后缀
        if platform.system().lower() == 'windows':
            if Path(self.frpc_path).suffix.lower() != '.exe':
                # 尝试在目录中寻找 .exe 备用
                candidates = list(self.frpc_dir.glob('**/frpc*.exe'))
                if candidates:
                    self.frpc_path = candidates[0]
                    logger.info(f"自动切换到Windows可执行文件: {self.frpc_path}")
                else:
                    raise Exception(f"当前平台为Windows，但未找到frpc的.exe文件。当前路径: {self.frpc_path}")

        # OpenFrp 简易启动：无配置文件，仅使用 -u/-p。禁用更新检查 -n。
        cmd = [str(self.frpc_path), '-u', token]

        # 如果指定了proxy_id，添加它
        if proxy_id:
            cmd.extend(['-p', str(proxy_id)])  # 隧道ID

        # 添加一些额外的参数来避免更新检查
        cmd.extend(['-n'])  # 禁用更新检查

        # 日志打印命令时进行脱敏：只遮蔽 -u 后的 token
        try:
            masked_cmd_parts = cmd.copy()
            if '-u' in masked_cmd_parts:
                idx = masked_cmd_parts.index('-u')
                if idx + 1 < len(masked_cmd_parts):
                    masked_cmd_parts[idx + 1] = _mask_token(masked_cmd_parts[idx + 1])
            logger.info(f"启动frpc (简易启动，无配置): {' '.join(masked_cmd_parts)}")
        except Exception:
            logger.info(f"启动frpc (简易启动，无配置): {' '.join(cmd[:-1])} ***")
        logger.info(f"工作目录: {self.frpc_dir}")

        # 创建进程，设置更好的错误处理
        try:
            process = subprocess.Popen(
                cmd,
                cwd=str(self.frpc_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL  # 防止进程等待输入
            )
        except OSError as e:
            # 针对 WinError 193 提供更清晰指引
            if getattr(e, 'winerror', None) == 193 or '193' in str(e):
                logger.error("frpc启动失败: 可能尝试执行了非有效的Windows可执行文件 (WinError 193)")
                logger.error(f"可执行路径: {self.frpc_path}")
                logger.error(f"工作目录: {self.frpc_dir}")
                logger.error("请确认: 1) 可执行文件为 frpc*.exe 且与系统位数匹配; 2) 未将配置文件(.ini)误当作可执行; 3) 文件未被Windows阻止 (可用 Unblock-File 解锁)。")
            raise

        # 等待一段时间检查进程是否正常运行
        import time
        time.sleep(5)  # 增加等待时间

        if process.poll() is not None:
            # 进程已经退出，说明启动失败
            stdout, stderr = process.communicate()

            # 解析错误信息
            stdout_msg = stdout.decode('utf-8', errors='ignore').strip() if stdout else ''
            stderr_msg = stderr.decode('utf-8', errors='ignore').strip() if stderr else ''

            error_msg = stderr_msg or stdout_msg or '未知错误'

            logger.error(f"frpc启动失败 - 退出码: {process.returncode}")
            logger.error(f"frpc stdout: {stdout_msg}")
            logger.error(f"frpc stderr: {stderr_msg}")

            # 如果是网络连接被拒绝，直接原样重试一次（无配置，交由 frpc 自行选择节点）
            if 'connectex' in error_msg or 'connection refused' in error_msg.lower() or 'dial tcp' in error_msg:
                retry_cmd = [str(self.frpc_path), '-u', token, '-n']
                if proxy_id:
                    retry_cmd.extend(['-p', str(proxy_id)])
                try:
                    masked_retry = retry_cmd.copy()
                    if '-u' in masked_retry:
                        uidx = masked_retry.index('-u')
                        if uidx + 1 < len(masked_retry):
                            masked_retry[uidx + 1] = _mask_token(masked_retry[uidx + 1])
                    logger.info(f"重试启动frpc(无配置): {' '.join(masked_retry)}")
                except Exception:
                    logger.info("重试启动frpc(无配置): frpc -u *** ...")
                retry_proc = subprocess.Popen(
                    retry_cmd,
                    cwd=str(self.frpc_dir),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.DEVNULL
                )
                time.sleep(5)
                if retry_proc.poll() is not None:
                    r_stdout, r_stderr = retry_proc.communicate()
                    r_out = r_stdout.decode('utf-8', errors='ignore').strip() if r_stdout else ''
                    r_err = r_stderr.decode('utf-8', errors='ignore').strip() if r_stderr else ''
                    logger.error(f"frpc重试仍失败 - 退出码: {retry_proc.returncode}")
                    logger.error(f"stdout: {r_out}")
                    logger.error(f"stderr: {r_err}")
                    error_msg = r_err or r_out or error_msg
                else:
                    logger.info("frpc重试后启动成功")
                    return retry_proc

            # 如果是403错误，可能是token问题或API问题
            if '403 Forbidden' in error_msg or 'API未能正确响应' in error_msg:
                raise Exception("frpc启动失败: API认证失败 (403 Forbidden)。请检查token是否正确，或尝试重新登录获取新token。")
            elif 'The system cannot find the file specified' in error_msg or 'No such file or directory' in error_msg:
                raise Exception(f"frpc启动失败: 配置文件不存在。请检查配置文件路径: {self.config_file}")
            else:
                raise Exception(f"frpc启动失败: {error_msg}")

        logger.info("frpc进程启动成功")
        return process

    def create_minimal_config(self, server_port: int = 7000):
        """
        创建最小的frpc配置文件
        """
        try:
            config_content = f"""[common]
server_addr = openfrp.net
server_port = {server_port}

log_file = ./frpc.log
log_level = info
log_max_days = 3
"""

            with open(self.config_file, 'w', encoding='utf-8') as f:
                f.write(config_content)

            logger.info(f"创建最小配置文件: {self.config_file}")

        except Exception as e:
            logger.error(f"创建配置文件失败: {e}")
            raise Exception(f"无法创建配置文件: {e}")

    def test_frpc_connection(self, token: str) -> Dict[str, Any]:
        """
        测试frpc连接和token有效性
        """
        if not self.ensure_frpc_available():
            return {'success': False, 'error': '无法获取frpc客户端'}

        try:
            logger.info("开始测试frpc连接...")

            # 首先测试frpc是否可以运行（不使用token）
            cmd_basic = [str(self.frpc_path), '--version']
            result_basic = subprocess.run(cmd_basic, capture_output=True, text=True, timeout=10)

            if result_basic.returncode != 0:
                error_msg = result_basic.stderr.strip() or result_basic.stdout.strip() or '未知错误'
                logger.error(f"frpc基本测试失败: {error_msg}")
                return {'success': False, 'error': f'frpc无法运行: {error_msg}'}

            frpc_version = result_basic.stdout.strip()
            logger.info(f"frpc版本: {frpc_version}")

            # 现在测试使用token的连接（无配置文件，简易启动）
            logger.info("测试token认证(无配置)...")
            cmd_auth = [str(self.frpc_path), '-u', token, '-n']

            # 脱敏测试命令日志
            try:
                masked_auth = cmd_auth.copy()
                if '-u' in masked_auth:
                    aidx = masked_auth.index('-u')
                    if aidx + 1 < len(masked_auth):
                        masked_auth[aidx + 1] = _mask_token(masked_auth[aidx + 1])
                logger.info(f"测试命令: {' '.join(masked_auth)}")
            except Exception:
                logger.info("测试命令: frpc -u *** -n")

            process = subprocess.Popen(
                cmd_auth,
                cwd=str(self.frpc_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL
            )

            # 等待几秒钟观察输出
            import time
            time.sleep(5)

            # 获取当前输出
            if process.poll() is None:
                # 进程还在运行，说明基本启动成功
                stdout, stderr = process.communicate(timeout=1)
                process.terminate()
                process.wait()
            else:
                stdout, stderr = process.communicate()

            stdout_msg = stdout.decode('utf-8', errors='ignore').strip() if stdout else ''
            stderr_msg = stderr.decode('utf-8', errors='ignore').strip() if stderr else ''

            logger.info(f"frpc测试输出: {stdout_msg}")
            if stderr_msg:
                logger.warning(f"frpc测试错误: {stderr_msg}")

            # 检查是否有403错误
            if '403 Forbidden' in stderr_msg or 'API未能正确响应' in stderr_msg:
                return {
                    'success': False,
                    'error': 'API认证失败 (403 Forbidden)。请检查token是否正确，或尝试重新登录获取新token。'
                }

            # 网络连接被拒绝时，原样无配置重试一次
            if 'connectex' in stderr_msg or 'connection refused' in stderr_msg.lower() or 'dial tcp' in stderr_msg:
                logger.warning("测试连接被拒绝，进行一次无配置重试...")
                retry_cmd = [str(self.frpc_path), '-u', token, '-n']
                try:
                    masked_retry = retry_cmd.copy()
                    if '-u' in masked_retry:
                        ridx = masked_retry.index('-u')
                        if ridx + 1 < len(masked_retry):
                            masked_retry[ridx + 1] = _mask_token(masked_retry[ridx + 1])
                    logger.info(f"测试重试命令: {' '.join(masked_retry)}")
                except Exception:
                    logger.info("测试重试命令: frpc -u *** -n")
                retry_proc = subprocess.Popen(
                    retry_cmd,
                    cwd=str(self.frpc_dir),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.DEVNULL
                )
                time.sleep(5)
                if retry_proc.poll() is not None:
                    r_stdout, r_stderr = retry_proc.communicate()
                    r_out = r_stdout.decode('utf-8', errors='ignore').strip() if r_stdout else ''
                    r_err = r_stderr.decode('utf-8', errors='ignore').strip() if r_stderr else ''
                    if '403 Forbidden' in r_err or 'API未能正确响应' in r_err:
                        return {'success': False, 'error': 'API认证失败 (403 Forbidden)。请检查token是否正确，或尝试重新登录获取新token。'}
                    if 'error' in r_err.lower() or retry_proc.returncode != 0:
                        return {'success': False, 'error': f'frpc连接测试失败: {r_err or r_out}'}
                    return {'success': True, 'message': f'frpc可用(重试) ，版本: {frpc_version}'}

            # 检查是否有其他错误
            if 'error' in stderr_msg.lower() or process.returncode != 0:
                return {
                    'success': False,
                    'error': f'frpc连接测试失败: {stderr_msg or stdout_msg}'
                }

            # 如果没有明显错误，认为测试通过
            return {
                'success': True,
                'message': f'frpc可用，版本: {frpc_version}'
            }

        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'frpc测试超时，请检查网络连接'}
        except Exception as e:
            logger.error(f"frpc测试失败: {e}")
            return {'success': False, 'error': f'frpc测试异常: {str(e)}'}

# 创建全局实例
frpc_service = FrpcService()