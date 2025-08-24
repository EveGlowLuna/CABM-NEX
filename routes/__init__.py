# -*- coding: utf-8 -*-
"""
统一注册所有蓝图
"""
from flask import Flask
from pathlib import Path
import sys

# 把项目根目录加入 sys.path，保证可以 import services、utils
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from .config_routes import bp as config_bp
from .chat_routes import bp as chat_bp
from .character_routes import bp as character_bp
from .misc_routes import bp as misc_bp

def register_blueprints(app: Flask):
    """把全部蓝图注册到 Flask 实例"""
    app.register_blueprint(config_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(character_bp)
    app.register_blueprint(misc_bp)