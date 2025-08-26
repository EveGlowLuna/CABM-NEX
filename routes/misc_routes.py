# -*- coding: utf-8 -*-
"""
杂项路由
"""
import sys
from pathlib import Path
from flask import Blueprint, send_from_directory, request, jsonify, send_file, current_app, render_template
from io import BytesIO
import sys
# 动态计算项目根目录
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from services.config_service import config_service
need_config = not config_service.initialize()


bp = Blueprint('misc', __name__, url_prefix='')
@bp.route('/data/images/<path:filename>')
def serve_character_image(filename):
    return send_from_directory(str(project_root / 'data' / 'images'), filename)


# 已移除 /api/tts 端点

@bp.route('/settings')
def settings():
    """设置页面"""
    return render_template('settings.html')
