# -*- coding: utf-8 -*-
"""
TCP通信服务
管理TCP隧道的创建、启动、停止等
"""
import subprocess
import os
import json
import logging
import time
import random
from pathlib import Path
from typing import Dict, List, Optional, Any

from services.openfrp_service import openfrp_service
from services.frpc_service import frpc_service

logger = logging.getLogger(__name__)

# 固定隧道名称
TUNNEL_NAME = "CABMTCPTUNNEL"
# CABM默认端口
CABM_DEFAULT_PORT = 5000

class TCPService:
    def __init__(self):
        self.project_root = Path(__file__).resolve().parent.parent
        self.config_file = self.project_root / "tcp_config.json"
        self.frpc_path = self.project_root / "frpc.exe"  # Windows
        self.processes = {}  # proxy_id -> process
        self.load_config()

    def load_config(self):
        """
        加载配置文件
        """
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            except Exception as e:
                logger.error(f"加载配置文件失败: {e}")
                self.config = {}
        else:
            self.config = {}
            self.save_config()

    def save_config(self):
        """
        保存配置文件
        """
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")

    def set_credentials(self, token: str) -> Dict[str, Any]:
        """
        设置OpenFrp凭据
        传入的 token 是用于 OpenFrp API 的 Authorization 值。
        同时从用户信息中保存 frpc 简易启动所需的 用户密钥(user_token)。
        """
        result = openfrp_service.login_with_token(token)
        if result['success']:
            # 保存 API Authorization（向后兼容老字段 'token'）
            self.config['authorization'] = token
            self.config['token'] = token
            # 保存用户密钥（frpc -u 所需）
            user_info = result.get('data') or {}
            user_token = user_info.get('token')
            if user_token:
                self.config['user_token'] = user_token
            self.save_config()
        return result

    def get_credentials(self) -> Optional[str]:
        """
        获取用于 API 的 Authorization 值（向后兼容旧配置）
        """
        return self.config.get('authorization') or self.config.get('token')

    def get_user_token(self) -> Optional[str]:
        """
        获取用于 frpc 简易启动(-u)的 用户密钥。
        若不存在，提示需要重新登录以刷新凭据。
        """
        return self.config.get('user_token')

    def get_node_list(self) -> Dict[str, Any]:
        """
        获取可用节点列表
        """
        token = self.get_credentials()
        if not token:
            return {'success': False, 'error': '未登录'}

        # 临时设置token到openfrp_service
        openfrp_service.authorization = token
        return openfrp_service.get_node_list()

    def _select_default_node_id(self) -> Optional[int]:
        """
        选择默认节点：优先 '#9 义乌电信😰'，否则选择第一个可用节点。
        可用条件：status == 200 且 非 fullyLoaded。
        """
        nodes = self.get_node_list()
        if not nodes.get('success'):
            return None
        node_list = (nodes.get('data') or {}).get('list', [])
        if not node_list:
            return None

        def is_available(node: Dict[str, Any]) -> bool:
            try:
                return node.get('status') == 200 and not node.get('fullyLoaded', False)
            except Exception:
                return False

        # 收集可能包含名称的字段
        name_fields = ('name', 'nodeName', 'title', 'remark', 'label', 'displayName')

        # 1) 优先匹配包含“义乌电信”或以“#9”开头的可用节点
        for node in node_list:
            if not is_available(node):
                continue
            text_parts = []
            for f in name_fields:
                v = node.get(f)
                if isinstance(v, str):
                    text_parts.append(v)
            # 也尝试 hostname 里含义不大的信息
            host = node.get('hostname')
            if isinstance(host, str):
                text_parts.append(host)
            text = ' '.join(text_parts)
            if not text:
                continue
            if ('义乌电信' in text) or text.strip().startswith('#9'):
                return node.get('id')

        # 2) 未匹配到则选择第一个可用节点
        for node in node_list:
            if is_available(node):
                return node.get('id')

        return None

    def generate_random_remote_port(self) -> int:
        """
        生成随机远程端口
        """
        return random.randint(1024, 65535)

        # def create_tcp_tunnel(self, local_addr: str = "127.0.0.1", local_port: int = CABM_DEFAULT_PORT,

    
    def create_tcp_tunnel(self, local_addr: str = "0.0.0.0", local_port: int = CABM_DEFAULT_PORT,
                          node_id: int = None) -> Dict[str, Any]:
        """
        创建TCP隧道
        使用固定名称CABMTCPTUNNEL，随机远程端口
        """
        token = self.get_credentials()
        if not token:
            return {'success': False, 'error': '未登录'}

        # 统一本地地址：frpc 作为客户端连接本地服务，应连接到可达的本地目标地址。
        # 注意：0.0.0.0 只能用于“监听”，不能作为连接目标！因此应当使用 127.0.0.1。
        try:
            if local_addr in ("127.0.0.1", "localhost", "0.0.0.0"):
                local_addr = "127.0.0.1"
        except Exception:
            local_addr = "127.0.0.1"

        # 如果没有指定节点ID，使用默认节点（优先 #9 义乌电信😰）
        if node_id is None:
            node_id = self._select_default_node_id()
            if node_id is None:
                return {'success': False, 'error': '没有可用的节点'}

        # 生成随机远程端口
        remote_port = self.generate_random_remote_port()

        # 临时设置token到openfrp_service
        openfrp_service.authorization = token
        result = openfrp_service.create_tcp_proxy(TUNNEL_NAME, local_addr, local_port, remote_port, node_id)
        if result['success']:
            # 保存隧道配置
            if 'tunnels' not in self.config:
                self.config['tunnels'] = []
            tunnel_info = {
                'name': TUNNEL_NAME,
                'local_addr': local_addr,
                'local_port': local_port,
                'remote_port': remote_port,
                'node_id': node_id,
                'proxy_id': result['data'].get('proxy_id'),  # 如果API返回proxy_id
                'created_at': time.time()
            }
            self.config['tunnels'].append(tunnel_info)
            self.save_config()
        return result

    def get_tunnels(self) -> Dict[str, Any]:
        """
        获取隧道列表
        """
        token = self.get_credentials()
        if not token:
            return {'success': False, 'error': '未登录'}

        # 临时设置token到openfrp_service
        openfrp_service.authorization = token
        return openfrp_service.get_user_proxies()

    def remove_tunnel(self, proxy_id: int) -> Dict[str, Any]:
        """
        删除隧道
        """
        token = self.get_credentials()
        if not token:
            return {'success': False, 'error': '未登录'}

        # 临时设置token到openfrp_service
        openfrp_service.authorization = token
        result = openfrp_service.remove_proxy(proxy_id)
        if result['success']:
            # 从配置中移除
            if 'tunnels' in self.config:
                self.config['tunnels'] = [
                    t for t in self.config['tunnels']
                    if t.get('proxy_id') != proxy_id
                ]
                self.save_config()
            # 停止相关进程
            if proxy_id in self.processes:
                self.stop_tunnel(proxy_id)
        return result

    def start_tunnel(self, proxy_id: int) -> Dict[str, Any]:
        """
        启动隧道 - 使用OpenFrp简易启动方式
        """
        if not self.get_credentials():
            return {'success': False, 'error': '未配置凭据'}

        if not self.get_user_token():
            return {'success': False, 'error': '未找到用户密钥(user_token)。请在设置中重新登录，以刷新凭据后再试。'}

        # 检查隧道是否已存在
        if proxy_id in self.processes:
            # 检查进程是否还在运行
            process = self.processes[proxy_id]
            if process.poll() is None:
                return {'success': False, 'error': '隧道已在运行中'}

        try:
            logger.info(f"正在启动OpenFrp隧道: {proxy_id}")

            # 使用 frpc 用户密钥 启动隧道（简易启动方式）
            process = frpc_service.run_frpc(self.get_user_token(), proxy_id)
            self.processes[proxy_id] = process

            logger.info(f"frpc进程启动成功: {proxy_id}")

            # 等待几秒钟让frpc建立连接
            import time
            time.sleep(3)

            # 检查进程是否还在运行
            if process.poll() is not None:
                # 进程已退出
                stdout, stderr = process.communicate()
                stdout_msg = stdout.decode('utf-8', errors='ignore') if stdout else ''
                stderr_msg = stderr.decode('utf-8', errors='ignore') if stderr else ''

                error_output = stderr_msg or stdout_msg or '进程异常退出'
                logger.error(f"frpc进程异常退出 - 退出码: {process.returncode}")
                logger.error(f"stdout: {stdout_msg}")
                logger.error(f"stderr: {stderr_msg}")

                return {'success': False, 'error': f'frpc启动失败: {error_output}'}

            # 验证连接状态并尽量打印远程访问地址
            address = None
            remote_online = None
            # 轮询等待上线（最多 ~15 秒）
            for _ in range(15):
                status_result = self.get_tunnel_status(proxy_id)
                if status_result.get('success'):
                    remote_online = status_result.get('remote_online')
                    if remote_online:
                        address = self.get_tunnel_connect_address()
                        break
                # 进程中途退出则提前失败
                if process.poll() is not None:
                    stdout, stderr = process.communicate()
                    stdout_msg = stdout.decode('utf-8', errors='ignore') if stdout else ''
                    stderr_msg = stderr.decode('utf-8', errors='ignore') if stderr else ''
                    error_output = stderr_msg or stdout_msg or '进程异常退出'
                    logger.error(f"frpc进程异常退出 - 退出码: {process.returncode}")
                    logger.error(f"stdout: {stdout_msg}")
                    logger.error(f"stderr: {stderr_msg}")
                    return {'success': False, 'error': f'frpc启动失败: {error_output}'}
                time.sleep(1)

            # 打印并返回结果
            if remote_online:
                if not address:
                    address = self.get_tunnel_connect_address()
                if address:
                    logger.info("🎉 隧道已启动并连接成功！")
                    logger.info(f"🌐 远程访问地址: {address}")
                    return {'success': True, 'message': '隧道已启动并连接成功', 'address': address}
                else:
                    logger.info("隧道已启动并连接成功，但暂未获取到访问地址")
                    return {'success': True, 'message': '隧道已启动并连接成功'}

            # 未确认远程在线，但进程正常运行
            address = self.get_tunnel_connect_address() or address
            if address:
                logger.info("frpc已启动，等待远程状态刷新...")
                logger.info(f"🌐 远程访问地址(可能稍后可用): {address}")
                return {'success': True, 'message': 'frpc已启动，正在建立连接...', 'address': address}

            logger.info("frpc已启动，正在建立连接...")
            return {'success': True, 'message': 'frpc已启动，正在建立连接... 请稍等片刻。'}

        except Exception as e:
            logger.error(f"启动隧道失败: {e}")
            # 清理失败的进程记录
            if proxy_id in self.processes:
                del self.processes[proxy_id]
            return {'success': False, 'error': str(e)}

    def stop_tunnel(self, proxy_id: int) -> Dict[str, Any]:
        """
        停止隧道
        """
        if proxy_id in self.processes:
            try:
                process = self.processes[proxy_id]
                process.terminate()
                process.wait(timeout=5)
                del self.processes[proxy_id]
                logger.info(f"停止隧道成功: {proxy_id}")
                return {'success': True, 'message': '隧道已停止'}
            except Exception as e:
                logger.error(f"停止隧道失败: {e}")
                return {'success': False, 'error': str(e)}
        else:
            return {'success': False, 'error': '隧道未在运行'}

    def get_tunnel_status(self, proxy_id: int) -> Dict[str, Any]:
        """
        获取隧道状态 - 同时检查本地进程和远程在线状态
        """
        # 检查本地进程状态
        local_running = False
        if proxy_id in self.processes:
            process = self.processes[proxy_id]
            if process.poll() is None:
                local_running = True
            else:
                # 进程已退出，清理
                del self.processes[proxy_id]

        # 获取远程在线状态（通过API）
        try:
            tunnels_result = self.get_tunnels()
            if tunnels_result['success'] and tunnels_result['data']['list']:
                for tunnel in tunnels_result['data']['list']:
                    if tunnel['id'] == proxy_id:
                        remote_online = tunnel.get('online', False)
                        return {
                            'success': True,
                            'status': 'online' if (local_running and remote_online) else 'running' if local_running else 'offline',
                            'local_running': local_running,
                            'remote_online': remote_online
                        }
        except Exception as e:
            logger.warning(f"获取远程状态失败: {e}")

        # 如果API调用失败，回退到本地进程状态
        status = 'running' if local_running else 'stopped'
        return {
            'success': True,
            'status': status,
            'local_running': local_running,
            'remote_online': None  # 未知
        }

    def check_and_restart_tunnel(self) -> Dict[str, Any]:
        """
        检查现有隧道并自动重启
        如果本地端口与CABM运行端口不同，则删除并重启
        """
        token = self.get_credentials()
        if not token:
            return {'success': False, 'error': '未登录'}

        # 获取当前运行的隧道列表
        tunnels_result = self.get_tunnels()
        if not tunnels_result['success']:
            return {'success': False, 'error': '获取隧道列表失败'}

        tunnels = tunnels_result.get('data', {}).get('list', [])
        cabm_tunnel = None

        # 查找CABMTCPTUNNEL
        for tunnel in tunnels:
            if tunnel.get('proxyName') == TUNNEL_NAME:
                cabm_tunnel = tunnel
                break

        if not cabm_tunnel:
            return {'success': False, 'error': '未找到CABMTCPTUNNEL，请先创建'}

        # 检查本地端口是否匹配CABM端口
        current_local_port = cabm_tunnel.get('localPort')
        if current_local_port != CABM_DEFAULT_PORT:
            logger.info(f"本地端口不匹配: 当前{current_local_port}, 需要{CABM_DEFAULT_PORT}，准备重启")

            # 删除现有隧道
            proxy_id = cabm_tunnel.get('id')
            remove_result = self.remove_tunnel(proxy_id)
            if not remove_result['success']:
                return {'success': False, 'error': f'删除旧隧道失败: {remove_result.get("error")}'}

            # 创建新隧道
            create_result = self.create_tcp_tunnel()
            if not create_result['success']:
                return {'success': False, 'error': f'创建新隧道失败: {create_result.get("error")}'}

            # 启动新隧道
            if 'data' in create_result and 'proxy_id' in create_result['data']:
                new_proxy_id = create_result['data']['proxy_id']
                start_result = self.start_tunnel(new_proxy_id)
                if start_result['success']:
                    return {'success': True, 'message': '隧道已重启并启动成功', 'restarted': True}
                else:
                    return {'success': False, 'error': f'启动新隧道失败: {start_result.get("error")}'}

        return {'success': True, 'message': '隧道端口匹配，无需重启'}

    def get_tunnel_connect_address(self) -> Optional[str]:
        """
        获取CABMTCPTUNNEL的连接地址
        """
        token = self.get_credentials()
        if not token:
            return None

        # 获取当前运行的隧道列表
        tunnels_result = self.get_tunnels()
        if not tunnels_result['success']:
            return None

        tunnels = tunnels_result.get('data', {}).get('list', [])
        for tunnel in tunnels:
            if tunnel.get('proxyName') == TUNNEL_NAME:
                return tunnel.get('connectAddress')

        return None

# 创建全局实例
tcp_service = TCPService()