# -*- coding: utf-8 -*-
"""
CABM 应用入口
"""
import os
import sys
from pathlib import Path
from flask import Flask
from waitress import serve
import mimetypes

# 计算项目根目录
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from services.config_service import config_service
from routes import register_blueprints
from services.tcp_service import tcp_service
import logging

# 配置日志：确保在直接运行 app.py 时也能看到 INFO 级别日志
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
    )

logger = logging.getLogger(__name__)

# 初始化配置
need_config = not config_service.initialize()
if not need_config:
    from services.chat_service import chat_service
    app_config = config_service.get_app_config()
    static_folder = str(project_root / app_config["static_folder"])
    template_folder = str(project_root / app_config["template_folder"])
else:
    static_folder = str(project_root / "static")
    template_folder = str(project_root / "templates")

# 创建 Flask 实例
app = Flask(__name__, static_folder=static_folder, template_folder=template_folder)
app.project_root = project_root
# 注册蓝图
register_blueprints(app)

def auto_start_tunnels():
    """
    自动启动现有隧道
    在应用启动时检查是否有登录状态和现有隧道，如果有就自动尝试启动
    """
    try:
        logger.info("检查自动启动隧道...")

        # 检查是否有登录凭据
        token = tcp_service.get_credentials()
        if not token:
            logger.info("未找到登录凭据，跳过自动启动")
            return

        # 验证登录状态
        login_result = tcp_service.set_credentials(token)
        if not login_result.get('success'):
            logger.warning(f"登录验证失败: {login_result.get('error')}")
            return

        logger.info("登录验证成功，开始检查现有隧道")

        # 获取现有隧道列表
        tunnels_result = tcp_service.get_tunnels()
        if not tunnels_result.get('success'):
            logger.warning(f"获取隧道列表失败: {tunnels_result.get('error')}")
            return

        tunnels = tunnels_result.get('data', {}).get('list', [])
        if not tunnels:
            logger.info("没有找到现有隧道")
            return

        # 查找CABMTCPTUNNEL
        cabm_tunnel = None
        for tunnel in tunnels:
            if tunnel.get('proxyName') == 'CABMTCPTUNNEL':
                cabm_tunnel = tunnel
                break

        if not cabm_tunnel:
            logger.info("未找到CABMTCPTUNNEL")
            return

        # 检查隧道是否已经在运行
        if cabm_tunnel.get('online'):
            logger.info("CABMTCPTUNNEL已经在线，跳过启动")
            return

        # 尝试启动隧道
        proxy_id = cabm_tunnel.get('id')
        if not proxy_id:
            logger.warning("无法获取隧道ID")
            return

        logger.info(f"尝试启动CABMTCPTUNNEL (ID: {proxy_id})")

        # 检查是否已经有进程在运行
        if proxy_id in tcp_service.processes:
            process = tcp_service.processes[proxy_id]
            if process.poll() is None:
                logger.info("隧道进程已在运行中")

                # 获取并显示连接地址
                connect_address = tcp_service.get_tunnel_connect_address()
                if connect_address:
                    logger.info(f"🎉 隧道已在运行中！您可以通过以下地址访问:")
                    logger.info(f"🌐 远程地址: {connect_address}")
                else:
                    logger.warning("无法获取连接地址，请稍后在Web界面中查看")

                return

        # 启动隧道
        start_result = tcp_service.start_tunnel(proxy_id)

        if start_result.get('success'):
            logger.info(f"自动启动隧道成功: {start_result.get('message')}")

            # 等待几秒钟让连接建立，然后获取并显示连接地址
            import time
            time.sleep(3)

            # 获取并显示连接地址
            connect_address = tcp_service.get_tunnel_connect_address()
            if connect_address:
                logger.info(f"🎉 CABMTCPTUNNEL启动成功！")
                logger.info(f"🌐 远程访问地址: {connect_address}")
                logger.info(f"📝 使用说明: 任何设备都可以通过这个地址访问您本地的服务")
                logger.info(f"💡 例如: 在浏览器中访问 {connect_address} 即可连接到您的本地服务")
                logger.info(f"🔗 您也可以将此地址分享给其他人使用")
            else:
                logger.warning("隧道启动成功，但暂时无法获取连接地址。请稍后在Web界面中查看")
        else:
            logger.warning(f"自动启动隧道失败: {start_result.get('error')}")

    except Exception as e:
        logger.error(f"自动启动隧道异常: {e}")

# 在应用启动后自动检查和启动隧道
if not need_config:
    try:
        auto_start_tunnels()
    except Exception as e:
        logger.error(f"自动启动检查异常: {e}")

# app.py

# MIME 类型
mimetypes.add_type('text/javascript', '.js')
mimetypes.add_type('application/javascript', '.mjs')

# 运行入口
if __name__ == '__main__':
    if not need_config:
        chat_service.set_system_prompt("character")
        # 使用 Waitress 作为生产级 WSGI 服务器
        serve(
            app,
            host=app_config.get("host", "127.0.0.1"),
            port=int(app_config.get("port", 5000))
        )
    else:
        # 配置模式下，也使用 Waitress 以避免开发服务器限制
        serve(app, host="127.0.0.1", port=5000)