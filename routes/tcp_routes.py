# -*- coding: utf-8 -*-
"""
TCP通信路由
处理TCP隧道管理的Web接口
"""
from flask import Blueprint, request, jsonify, render_template, redirect, url_for
from services.tcp_service import tcp_service
from services.frpc_service import frpc_service
import logging

logger = logging.getLogger(__name__)

tcp_bp = Blueprint('tcp', __name__)

@tcp_bp.route('/tcp')
def tcp_index():
    """
    TCP通信管理页面
    """
    return render_template('tcp_config.html')

@tcp_bp.route('/frp')
def frp_index():
    """
    兼容路由：/frp -> 重定向到 /tcp
    """
    return redirect(url_for('tcp.tcp_index'))

@tcp_bp.route('/api/tcp/login', methods=['POST'])
def login():
    """
    用户登录
    """
    data = request.get_json()
    token = data.get('token', '').strip()

    if not token:
        return jsonify({'success': False, 'error': '请提供token'})

    result = tcp_service.set_credentials(token)
    return jsonify(result)

@tcp_bp.route('/api/tcp/status', methods=['GET'])
def get_status():
    """
    获取登录状态
    """
    token = tcp_service.get_credentials()
    is_logged_in = token is not None
    user_token = tcp_service.get_user_token()

    return jsonify({
        'success': True,
        'is_logged_in': is_logged_in,
        'has_token': bool(token),
        'has_user_token': bool(user_token)
    })

@tcp_bp.route('/api/tcp/nodes', methods=['GET'])
def get_nodes():
    """
    获取节点列表
    """
    result = tcp_service.get_node_list()
    return jsonify(result)

@tcp_bp.route('/api/tcp/tunnels', methods=['GET'])
def get_tunnels():
    """
    获取隧道列表
    """
    result = tcp_service.get_tunnels()
    return jsonify(result)

@tcp_bp.route('/api/tcp/create', methods=['POST'])
def create_tunnel():
    """
    创建TCP隧道
    使用固定名称CABMTCPTUNNEL，自动选择节点和随机端口
    """
    data = request.get_json()

    # 可选参数，默认值
    local_addr = data.get('local_addr', '127.0.0.1')
    local_port = data.get('local_port', 5000)  # CABM默认端口
    node_id = data.get('node_id')  # 如果未提供，将自动选择

    try:
        if local_port:
            local_port = int(local_port)
        if node_id:
            node_id = int(node_id)

        result = tcp_service.create_tcp_tunnel(local_addr, local_port, node_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'success': False, 'error': '参数格式错误'})
    except Exception as e:
        logger.error(f"创建隧道失败: {e}")
        return jsonify({'success': False, 'error': '创建失败'})

@tcp_bp.route('/api/tcp/remove/<int:proxy_id>', methods=['DELETE'])
def remove_tunnel(proxy_id):
    """
    删除隧道
    """
    result = tcp_service.remove_tunnel(proxy_id)
    return jsonify(result)

@tcp_bp.route('/api/tcp/start/<int:proxy_id>', methods=['POST'])
def start_tunnel(proxy_id):
    """
    启动隧道
    """
    result = tcp_service.start_tunnel(proxy_id)
    return jsonify(result)

@tcp_bp.route('/api/tcp/stop/<int:proxy_id>', methods=['POST'])
def stop_tunnel(proxy_id):
    """
    停止隧道
    """
    result = tcp_service.stop_tunnel(proxy_id)
    return jsonify(result)

@tcp_bp.route('/api/tcp/status/<int:proxy_id>', methods=['GET'])
def get_tunnel_status(proxy_id):
    """
    获取隧道状态
    """
    result = tcp_service.get_tunnel_status(proxy_id)
    return jsonify(result)

@tcp_bp.route('/api/tcp/check_restart', methods=['POST'])
def check_and_restart_tunnel():
    """
    检查并自动重启CABMTCPTUNNEL
    """
    result = tcp_service.check_and_restart_tunnel()
    return jsonify(result)

@tcp_bp.route('/api/tcp/connect_address', methods=['GET'])
def get_connect_address():
    """
    获取CABMTCPTUNNEL的连接地址
    """
    address = tcp_service.get_tunnel_connect_address()
    if address:
        return jsonify({'success': True, 'address': address})
    else:
        return jsonify({'success': False, 'error': '未找到CABMTCPTUNNEL或未登录'})

@tcp_bp.route('/api/tcp/test_frpc', methods=['POST'])
def test_frpc():
    """
    测试frpc客户端是否正常工作
    """
    user_token = tcp_service.get_user_token()
    if not user_token:
        return jsonify({'success': False, 'error': '未找到用户密钥(user_token)。请先通过登录刷新凭据。'})

    try:
        result = frpc_service.test_frpc_connection(user_token)
        return jsonify(result)
    except Exception as e:
        logger.error(f"测试frpc失败: {e}")
        return jsonify({'success': False, 'error': str(e)})