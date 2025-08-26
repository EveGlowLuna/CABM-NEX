# -*- coding: utf-8 -*-
"""
OpenFrp API服务
处理与OpenFrp API的交互，包括用户认证、隧道管理等
"""
import requests
import json
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class OpenFrpService:
    def __init__(self):
        self.base_url = "https://api.openfrp.net"
        self.access_url = "https://access.openfrp.net"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'CABM-OSA/1.0',
            'Content-Type': 'application/json'
        })
        self.authorization = None
        self.user_info = None

    def login_with_token(self, token: str) -> Dict[str, Any]:
        """
        使用token登录
        """
        try:
            response = self.session.post(
                f"{self.base_url}/frp/api/getUserInfo",
                headers={'Authorization': token}
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('flag'):
                    self.authorization = token
                    self.user_info = data['data']
                    logger.info("登录成功")
                    return {'success': True, 'data': data['data']}
                else:
                    return {'success': False, 'error': data.get('msg', '登录失败')}
            else:
                return {'success': False, 'error': f'HTTP {response.status_code}'}
        except Exception as e:
            logger.error(f"登录失败: {e}")
            return {'success': False, 'error': str(e)}

    def get_user_proxies(self) -> Dict[str, Any]:
        """
        获取用户隧道列表
        """
        if not self.authorization:
            return {'success': False, 'error': '未登录'}

        try:
            response = self.session.post(
                f"{self.base_url}/frp/api/getUserProxies",
                headers={'Authorization': self.authorization}
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('flag'):
                    return {'success': True, 'data': data['data']}
                else:
                    return {'success': False, 'error': data.get('msg', '获取失败')}
            else:
                return {'success': False, 'error': f'HTTP {response.status_code}'}
        except Exception as e:
            logger.error(f"获取隧道列表失败: {e}")
            return {'success': False, 'error': str(e)}

    def get_node_list(self) -> Dict[str, Any]:
        """
        获取节点列表，并过滤掉无权限访问的节点
        """
        if not self.authorization:
            return {'success': False, 'error': '未登录'}

        try:
            response = self.session.post(
                f"{self.base_url}/frp/api/getNodeList",
                headers={'Authorization': self.authorization}
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('flag'):
                    # 过滤掉无权限访问的节点
                    filtered_list = []
                    for node in data['data']['list']:
                        if node.get('hostname') != "您无权查询此节点的地址" and node.get('port') != "您无权查询此节点的地址":
                            filtered_list.append(node)
                    # 更新节点列表和总数
                    data['data']['list'] = filtered_list
                    data['data']['total'] = len(filtered_list)
                    logger.info(f"过滤后节点数量: {len(filtered_list)}")
                    return {'success': True, 'data': data['data']}
                else:
                    return {'success': False, 'error': data.get('msg', '获取失败')}
            else:
                return {'success': False, 'error': f'HTTP {response.status_code}'}
        except Exception as e:
            logger.error(f"获取节点列表失败: {e}")
            return {'success': False, 'error': str(e)}

    def create_tcp_proxy(self, name: str, local_addr: str, local_port: int,
                        remote_port: int, node_id: int) -> Dict[str, Any]:
        """
        创建TCP隧道
        """
        if not self.authorization:
            return {'success': False, 'error': '未登录'}

        payload = {
            "autoTls": "false",
            "custom": "",
            "dataEncrypt": False,
            "dataGzip": False,
            "domain_bind": "",
            "forceHttps": False,
            "local_addr": local_addr,
            "local_port": str(local_port),
            "name": name,
            "node_id": node_id,
            "proxyProtocolVersion": False,
            "remote_port": remote_port,
            "type": "tcp"
        }

        try:
            response = self.session.post(
                f"{self.base_url}/frp/api/newProxy",
                json=payload,
                headers={'Authorization': self.authorization}
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('flag'):
                    logger.info(f"创建TCP隧道成功: {name}")
                    return {'success': True, 'data': data}
                else:
                    return {'success': False, 'error': data.get('msg', '创建失败')}
            else:
                return {'success': False, 'error': f'HTTP {response.status_code}'}
        except Exception as e:
            logger.error(f"创建TCP隧道失败: {e}")
            return {'success': False, 'error': str(e)}

    def remove_proxy(self, proxy_id: int) -> Dict[str, Any]:
        """
        删除隧道
        """
        if not self.authorization:
            return {'success': False, 'error': '未登录'}

        payload = {"proxy_id": proxy_id}

        try:
            response = self.session.post(
                f"{self.base_url}/frp/api/removeProxy",
                json=payload,
                headers={'Authorization': self.authorization}
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('flag'):
                    logger.info(f"删除隧道成功: {proxy_id}")
                    return {'success': True, 'data': data}
                else:
                    return {'success': False, 'error': data.get('msg', '删除失败')}
            else:
                return {'success': False, 'error': f'HTTP {response.status_code}'}
        except Exception as e:
            logger.error(f"删除隧道失败: {e}")
            return {'success': False, 'error': str(e)}

    def is_logged_in(self) -> bool:
        """
        检查是否已登录
        """
        return self.authorization is not None

    def get_user_info(self) -> Optional[Dict]:
        """
        获取用户信息
        """
        return self.user_info

# 创建全局实例
openfrp_service = OpenFrpService()