#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
CABM PySide6 GUI Application
使用PySide6内嵌浏览器显示Web UI
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到系统路径
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QProgressBar
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtCore import QUrl, Qt, QThread, Signal
from PySide6.QtGui import QIcon

import threading
import time

class FlaskThread(QThread):
    """
    在单独线程中运行Flask应用
    """
    server_started = Signal(str, int)
    
    def __init__(self, host="127.0.0.1", port=5000):
        super().__init__()
        self.host = host
        self.port = port
        self.app = None
        
    def run(self):
        try:
            # 导入并启动Flask应用
            from app import app
            self.app = app
            
            # 通知GUI服务器已启动
            self.server_started.emit(self.host, self.port)
            
            # 在线程中运行Flask应用
            from waitress import serve
            serve(app, host=self.host, port=self.port)
        except Exception as e:
            print(f"Error starting Flask server: {e}")


class CABMWindow(QMainWindow):
    """
    CABM主窗口
    """
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CABM - Chat with AI Characters")
        self.setGeometry(100, 100, 1200, 800)
        
        # 设置窗口图标（如果存在）
        icon_path = project_root / "static" / "images" / "default.svg"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        
        # 初始化UI
        self.init_ui()
        
        # 启动Flask服务器
        self.start_flask_server()
        
    def init_ui(self):
        """
        初始化用户界面
        """
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建布局
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        central_widget.setLayout(layout)
        
        # 创建Web视图
        self.web_view = QWebEngineView()
        
        # 启用必要的Web功能
        settings = self.web_view.settings()
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.PluginsEnabled, True)
        settings.setAttribute(QWebEngineSettings.AutoLoadImages, True)
        
        # 添加到布局
        layout.addWidget(self.web_view)
        
        # 创建加载进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # 连接信号
        self.web_view.loadStarted.connect(self.on_load_started)
        self.web_view.loadProgress.connect(self.on_load_progress)
        self.web_view.loadFinished.connect(self.on_load_finished)
        
    def start_flask_server(self):
        """
        启动Flask服务器
        """
        self.flask_thread = FlaskThread()
        self.flask_thread.server_started.connect(self.on_server_started)
        self.flask_thread.start()
        
    def on_server_started(self, host, port):
        """
        服务器启动完成回调
        """
        url = f"http://{host}:{port}"
        self.web_view.load(QUrl(url))
        print(f"Flask server started at {url}")
        
    def on_load_started(self):
        """
        页面开始加载
        """
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
    def on_load_progress(self, progress):
        """
        页面加载进度更新
        """
        self.progress_bar.setValue(progress)
        
    def on_load_finished(self, success):
        """
        页面加载完成
        """
        self.progress_bar.setVisible(False)
        if not success:
            print("Failed to load web page")
        else:
            print("Web page loaded successfully")


def main():
    """
    主函数
    """
    # 设置应用属性
    QApplication.setApplicationName("CABM")
    QApplication.setApplicationVersion("1.0")
    QApplication.setOrganizationName("CABM")
    
    # 创建应用
    app = QApplication(sys.argv)
    
    # 创建并显示主窗口
    window = CABMWindow()
    window.show()
    
    # 运行应用
    sys.exit(app.exec())


if __name__ == "__main__":
    main()