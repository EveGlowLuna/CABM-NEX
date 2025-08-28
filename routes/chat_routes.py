# -*- coding: utf-8 -*-
"""
普通聊天、背景图生成、清空历史
"""
import os
import json
import re
import traceback
from pathlib import Path
from typing import Optional
from flask import Blueprint, request, render_template, jsonify, Response, send_file
from io import BytesIO
import sys

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# 只有在非配置模式下才导入服务
from services.config_service import config_service
need_config = not config_service.initialize()
if not need_config:
    from services.chat_service import chat_service
    from services.image_service import image_service
    from services.option_service import option_service
    from utils.api_utils import APIError

bp = Blueprint('chat', 'chat', url_prefix='')

# ------------------------------------------------------------------
# 工具函数（与 app.py 保持一致）
# ------------------------------------------------------------------
def _parse_assistant_text(raw: str) -> str:
    if not raw:
        return ""
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            text = obj.get('content')
            if isinstance(text, str):
                return text
        if isinstance(obj, str):
            return obj
    except Exception:
        pass
    return str(raw)

def _extract_last_sentence(text: str) -> str:
    import re as _re
    if not text:
        return ""
    text = _re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    sentence_endings = ['。', '！', '？', '!', '?', '.', '…', '♪', '...']
    escaped = ''.join(_re.escape(ch) for ch in sentence_endings)
    pattern = rf"([^ {escaped}]+(?:[{escaped}]+)?)$"
    m = _re.search(pattern, text)
    return m.group(1).strip() if m else text

def _get_last_assistant_sentence_for_character(character_id: str) -> str:
    try:
        history_messages = chat_service.history_manager.load_history(character_id, count=200, max_cache_size=500)
        for msg in reversed(history_messages):
            if msg.get('role') == 'assistant':
                raw = msg.get('content', '')
                text = _parse_assistant_text(raw)
                return _extract_last_sentence(text)
    except Exception as e:
        print(f"提取最后一句失败: {e}")
    return ""

# ------------------------------------------------------------------
# MCP 工具函数
# ------------------------------------------------------------------
def _extract_last_complete_json(text: str) -> Optional[str]:
    """
    从给定文本中提取最后一个完整且平衡的 JSON 对象（忽略字符串内的大括号）
    """
    if not text:
        return None
    in_string = False
    escape = False
    brace_count = 0
    last_complete_end = -1
    current_start = -1
    for i, ch in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == '"':
                in_string = False
            continue
        else:
            if ch == '"':
                in_string = True
                continue
            if ch == '{':
                if brace_count == 0:
                    current_start = i
                brace_count += 1
            elif ch == '}':
                if brace_count > 0:
                    brace_count -= 1
                    if brace_count == 0 and current_start != -1:
                        last_complete_end = i + 1
        # 其他字符不影响 brace 计数
    if last_complete_end != -1 and current_start != -1:
        try:
            candidate = text[current_start:last_complete_end]
            # 验证是合法 JSON
            json.loads(candidate)
            return candidate
        except Exception:
            return None
    return None

def _is_sentence_end(s: str) -> bool:
    """
    判断字符串是否以句子结束符结尾
    """
    if not s:
        return False
    t = s.rstrip()
    if not t:
        return False
    # 句末判断：以常见结束符收尾
    ends = ('。', '！', '？', '!', '?', '.', '…')
    return t.endswith(ends)

def _process_tool_request(tr, max_ai_iterations, iteration_count, seen_tool_sigs, message, per_request_system_msgs, tool_request_history, has_tool_context):
    """
    处理工具请求
    """
    tool_name = tr.get('name')
    tool_args = tr.get('args') or {}
    reason = tr.get('reason') or ''
    
    if not tool_name:
        return None
        
    # 一旦检测到工具请求：记录本次 assistant 的 tool_request JSON，并进入工具上下文
    try:
        # (空操作，只是记录工具请求历史在主函数中进行)
        pass
    except Exception:
        pass
    has_tool_context = True
    # 轮次计数与检查
    iteration_count += 1
    if iteration_count > max_ai_iterations:
        limit_msg = f"[MCP] 已达到单次请求的最大AI轮次限制({max_ai_iterations})，停止工具调用。"
        return {"type": "limit", "msg": limit_msg}
        
    # 构造去重签名：name+sorted(args)
    try:
        sig = json.dumps({"name": tool_name, "args": tool_args}, sort_keys=True, ensure_ascii=False)
    except Exception:
        sig = f"{tool_name}:{str(tool_args)}"
    if sig in seen_tool_sigs:
        dup_msg = f"[MCP] 检测到重复的工具请求，已跳过：{tool_name} args={tool_args}"
        return {"type": "dup", "msg": dup_msg}
    else:
        seen_tool_sigs.add(sig)
    # 延迟到句末执行实际调用
    return {"type": "call", "name": tool_name, "args": tool_args, "reason": reason}

def _get_max_ai_iterations():
    """
    获取最大AI迭代次数配置
    
    Returns:
        int: 最大迭代次数
    """
    try:
        app_cfg = config_service.get_app_config()
        return int(app_cfg.get('max_ai_iterations', 10))
    except Exception:
        return 10

def _inject_mcp_prompt_to_messages(base_messages, mcp_mod):
    """
    注入MCP工具使用说明到消息列表中
    
    Args:
        base_messages: 基础消息列表
        mcp_mod: MCP模块实例，如果为None则不注入
        
    Returns:
        注入工具说明后的消息列表
    """
    # 如果没有启用MCP或没有MCP模块，则直接返回原始消息列表
    if not mcp_mod:
        return base_messages
        
    try:
        # 获取工具描述
        tools_desc = mcp_mod.list_tools_for_prompt()
        lines = [
            "[MCP 工具使用指南]",
            "始终只输出一个合法的 JSON 对象（不要使用代码块标记）。",
            "JSON 结构: { content:string, mood?:string, tool_request?:{ name:string, args:object, reason:string } }",
            "需要调用工具时：在同一个 JSON 中加入 tool_request 字段；若已对用户输出过部分内容，不要重复这些内容，仅继续后文。",
            "系统返回工具结果后：继续输出新的单个 JSON。若仍需调用工具，可再次提供 tool_request；否则仅给出 content。允许多轮连续调用工具，直到任务完成或达到限制。",
            "严格要求：",
            "- 不要复述之前已经对用户输出过的文本；接着写下去。",
            "- 保留并正确使用原始标点符号，不要删除或改写标点。",
            "- 每轮都只输出一个 JSON 对象，不要输出多段或附加说明。",
            "[工具列表]",
        ]
        for name, meta in tools_desc.items():
            args_desc = ", ".join(f"{k}:{v}" for k, v in (meta.get("args", {}) or {}).items())
            lines.append(f"- {name}: {meta.get('desc','')} 参数: {args_desc}")
        mcp_tool_prompt = "\n".join(lines)
        inserted = False
        for idx, msg in enumerate(base_messages):
            if msg.get("role") == "system":
                base_messages.insert(idx + 1, {"role": "system", "content": mcp_tool_prompt})
                inserted = True
                break
        if not inserted:
            base_messages.insert(0, {"role": "system", "content": mcp_tool_prompt})
    except Exception:
        pass
    return base_messages

# ------------------------------------------------------------------
# 页面路由
# ------------------------------------------------------------------
@bp.route('/')
def home():
    if need_config:
        return render_template('config.html')
    return render_template('index.html')

@bp.route('/chat')
def chat_page():
    try:
        current_character = chat_service.get_character_config()
        if current_character and "id" in current_character:
            chat_service.set_character(current_character["id"])
    except Exception as e:
        print(f"进入聊天页切换角色失败: {e}")
        traceback.print_exc()

    background = image_service.get_current_background()
    if not background:
        try:
            result = image_service.generate_background()
            if "image_path" in result:
                background = result["image_path"]
        except Exception as e:
            print(f"背景图片生成失败: {e}")

    background_url = None
    if background:
        background_url = f"/static/images/cache/{os.path.basename(background)}"

    character_image_path = os.path.join(bp.static_folder or str(project_root / 'static'), 'images', 'default', '1.png')
    if not os.path.exists(character_image_path):
        print(f"警告: 默认角色图片不存在: {character_image_path}")

    app_config = config_service.get_app_config()

    last_sentence = ""
    try:
        current_character = chat_service.get_character_config()
        if current_character and "id" in current_character:
            last_sentence = _get_last_assistant_sentence_for_character(current_character["id"]) or ""
    except Exception:
        pass

    from utils.plugin import FRONTEND_HOOKS
    plugin_inject_scripts = []
    def collect_inject(route, path):
        if route.endswith('/inject.js'):
            plugin_inject_scripts.append(route)
    for hook in FRONTEND_HOOKS:
        hook(collect_inject)

    return render_template(
        'chat.html',
        background_url=background_url,
        last_sentence=last_sentence,
        plugin_inject_scripts=plugin_inject_scripts
    )

# ------------------------------------------------------------------
# API 路由
# ------------------------------------------------------------------
@bp.route('/api/chat', methods=['POST'])
def chat():
    try:
        message = request.json.get('message', '')
        mcp_enabled = bool(request.json.get('mcp_enabled', False))

        if not message:
            return jsonify({'success': False, 'error': '消息不能为空'}), 400
        chat_service.add_message("user", message)
        response = chat_service.chat_completion(stream=False, user_query=message, mcp_enabled=mcp_enabled)
        assistant_message = None
        if "choices" in response and len(response["choices"]) > 0:
            message_data = response["choices"][0].get("message", {})
            if message_data and "content" in message_data:
                assistant_message = message_data["content"]
        return jsonify({
            'success': True,
            'message': assistant_message,
            'history': [msg.to_dict() for msg in chat_service.get_history()]
        })
    except APIError as e:
        return jsonify({'success': False, 'error': e.message}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/chat/stream', methods=['POST'])
def chat_stream():
    try:
        message = request.json.get('message', '')
        mcp_enabled = bool(request.json.get('mcp_enabled', False))
        if not message:
            return jsonify({'success': False, 'error': '消息不能为空'}), 400
        chat_service.add_message("user", message)

        def generate():
            try:
                # 调试：记录本次请求是否启用 MCP
                try:
                    print(f"[MCP][DEBUG] chat_stream started. mcp_enabled={mcp_enabled}")
                except Exception:
                    pass
                # 懒加载导入 MCP 模块
                try:
                    from plugins import mcps as mcp_mod
                except Exception:
                    mcp_mod = None

                # 实现同一轮内的代理循环
                # 解析帮助函数：从给定文本中提取最后一个完整且平衡的 JSON 对象（忽略字符串内的大括号）
                def _extract_last_complete_json(text: str) -> Optional[str]:
                    if not text:
                        return None
                    in_string = False
                    escape = False
                    brace_count = 0
                    last_complete_end = -1
                    current_start = -1
                    for i, ch in enumerate(text):
                        if in_string:
                            if escape:
                                escape = False
                            elif ch == '\\':
                                escape = True
                            elif ch == '"':
                                in_string = False
                            continue
                        else:
                            if ch == '"':
                                in_string = True
                                continue
                            if ch == '{':
                                if brace_count == 0:
                                    current_start = i
                                brace_count += 1
                            elif ch == '}':
                                if brace_count > 0:
                                    brace_count -= 1
                                    if brace_count == 0 and current_start != -1:
                                        last_complete_end = i + 1
                        # 其他字符不影响 brace 计数
                    if last_complete_end != -1 and current_start != -1:
                        try:
                            candidate = text[current_start:last_complete_end]
                            # 验证是合法 JSON
                            json.loads(candidate)
                            return candidate
                        except Exception:
                            return None
                    return None

                def _parse_json_response(full_response: str) -> tuple:
                    """解析 JSON 响应，提取 mood、content 和 tool_request"""
                    try:
                        json_str = _extract_last_complete_json(full_response)
                        if json_str:
                            json_data = json.loads(json_str)
                            
                            mood = json_data.get('mood')
                            content = json_data.get('content', '')
                            
                            tool_request = None
                            if mcp_enabled and mcp_mod and isinstance(json_data, dict) and 'tool_request' in json_data:
                                tool_request = json_data.get('tool_request') or {}
                            
                            return json_str, json_data, mood, content, tool_request
                        return None, None, None, None, None
                    except json.JSONDecodeError:
                        return None, None, None, None, None

                def _is_sentence_end(s: str) -> bool:
                    """
                    判断字符串是否以句子结束符结尾
                    """
                    if not s:
                        return False
                    t = s.rstrip()
                    if not t:
                        return False
                    # 句末判断：以常见结束符收尾
                    ends = ('。', '！', '？', '!', '?', '.', '…')
                    return t.endswith(ends)

                def _handle_tool_call(self, tool_name: str, tool_args: dict, reason: str, mcp_mod, message, per_request_system_msgs, tool_request_history, yield_func, chat_service_add_message_func) -> dict:
                    """处理工具调用，执行工具并返回结果"""
                    try:
                        # 实际调用工具
                        result = mcp_mod.call_tool(tool_name, tool_args)
                        
                        # 构造简洁的前端提示（不含详情）
                        system_msg_front = f"[MCP] 工具完成：{tool_name}（成功）"
                        
                        # 详细结果仅放入模型上下文
                        try:
                            result_str = json.dumps(result, ensure_ascii=False)
                        except Exception:
                            result_str = str(result)
                        if len(result_str) > 800:
                            result_str = result[:800] + '...'
                        system_msg_detail = f"[MCP] 工具完成：{tool_name}，结果：{result_str}"
                        
                        # 说明性提示仅供模型参考，不推送到前端
                        bracket_note = f"[说明] 结构：AI:[{{content: 已处理, tool: {tool_name}, status: ok}}]。方括号内是你基于内容的回应，现在等待你的下一步操作。"
                        
                        # 重申用户原始需求，确保基于工具结果继续
                        user_note = f"[用户原始需求(注意：你需要基于工具结果继续回答)] {message}" if message else ""
                        
                        return {
                            "status": "success",
                            "system_msg_front": system_msg_front,
                            "system_msg_detail": system_msg_detail,
                            "bracket_note": bracket_note,
                            "user_note": user_note,
                            "result": result_str
                        }
                    except Exception as e:
                        # 失败：前端仅显示失败，不展示错误详情
                        err_front = f"[MCP] 工具完成：{tool_name}（失败）"
                        err_msg = f"[MCP] 工具调用失败：{tool_name}，错误：{str(e)}"
                        
                        # 说明性提示仅供模型参考，不推送到前端
                        bracket_note = f"[说明] 结构：AI:[{{content: 已处理, tool: {tool_name}, status: error}}]。方括号内是你基于内容的回应，现在等待你的下一步操作。"
                        
                        # 同样在失败场景下，重申用户原始需求，便于 AI 选择改用其他工具或改写方案
                        user_note = f"[用户原始需求(注意：你需要基于工具结果继续回答)] {message}" if message else ""
                        
                        return {
                            "status": "error",
                            "err_front": err_front,
                            "err_msg": err_msg,
                            "bracket_note": bracket_note,
                            "user_note": user_note
                        }

                def _construct_messages(current_messages: list, per_request_system_msgs: list, tool_request_history: list, has_tool_context: bool) -> list:
                    """构造当前轮次的消息"""
                    if not has_tool_context:
                        return list(current_messages) + per_request_system_msgs
                    else:
                        messages = list(current_messages)
                        if tool_request_history:
                            messages.extend(tool_request_history)
                        messages.extend(per_request_system_msgs)
                        return messages
                # 轮次限制与去重：避免工具反复调用导致死循环
                try:
                    app_cfg = config_service.get_app_config()
                    max_ai_iterations = int(app_cfg.get('max_ai_iterations', 10))
                except Exception:
                    max_ai_iterations = 10
                iteration_count = 0
                seen_tool_sigs = set()
                stop_outer_loop = False
                # 冻结本次请求的提示词：构造一次 base_messages，不在迭代中改动
                base_messages = chat_service.format_messages()
                # 如启用MCP，仅注入一次工具使用说明
                base_messages = _inject_mcp_prompt_to_messages(base_messages, mcp_mod if mcp_enabled else None)
                # 累积在本请求过程中的系统消息（工具结果、说明等），每轮与构造的最小上下文合并
                per_request_system_msgs = []
                # 仅保留系统类提示（角色设定 + MCP 工具说明），用于工具交互后的最小消息集
                system_only_messages = [m for m in base_messages if m.get("role") == "system"]
                # 累积历史的 tool_request（assistant 的 JSON 原文），支持多轮工具调用记忆
                tool_request_history = []  # List[Dict(role=assistant, content=json_str)]
                # 标记：是否进入工具上下文（一旦检测到/执行过工具后为 True），进入后不再携带原始 user
                has_tool_context = False
                while True:
                    # 本轮消息构造：
                    # - 未进入工具上下文：使用冻结的 base_messages（包含原始 user）+ 本轮累计的系统消息
                    # - 已进入工具上下文：严格遵循最小集，只包含 系统提示 + MCP 说明 + 所有历史 tool_request(JSON, role=assistant) + 工具结果系统消息
                    if not has_tool_context:
                        current_messages = list(base_messages) + per_request_system_msgs
                    else:
                        current_messages = list(system_only_messages)
                        if tool_request_history:
                            current_messages.extend(tool_request_history)
                        current_messages.extend(per_request_system_msgs)
                    stream_gen = chat_service.chat_completion(
                        messages=current_messages,
                        stream=True,
                        user_query=None,  # 避免重复附加记忆/细节
                        mcp_enabled=False  # 我们已在 base_messages 中注入一次MCP说明
                    )
                    full_response = ""
                    parsed_mood = None
                    parsed_content = ""
                    saw_tool_request = False
                    # 待执行的工具调用（延迟到句末再执行）
                    pending_tool = None  # dict(type: 'call'|'dup'|'limit'|'error', data:...)

                    for chunk in stream_gen:
                        if chunk is None:
                            continue
                        full_response += chunk
                        try:
                            json_str = _extract_last_complete_json(full_response)
                            if json_str:
                                try:
                                    json_data = json.loads(json_str)

                                    # mood 变化可直接推送
                                    if 'mood' in json_data:
                                        new_mood = json_data['mood']
                                        if new_mood != parsed_mood:
                                            parsed_mood = new_mood
                                            yield f"data: {json.dumps({'mood': parsed_mood})}\n\n"

                                    # 仅在尚未检测到工具调用时流式推送内容；一旦检测到，将暂停继续推送
                                    if 'content' in json_data and not saw_tool_request:
                                        new_content = json_data['content']
                                        if new_content != parsed_content:
                                            if len(new_content) < len(parsed_content):
                                                yield f"data: {json.dumps({'content': new_content})}\n\n"
                                                parsed_content = new_content
                                            else:
                                                content_diff = new_content[len(parsed_content):]
                                                if content_diff:
                                                    yield f"data: {json.dumps({'content': content_diff})}\n\n"
                                                parsed_content = new_content

                                    # 如果已有待执行的工具请求，等待句末再触发
                                    if pending_tool and _is_sentence_end(parsed_content):
                                        kind = pending_tool.get('type')
                                        if kind == 'limit' or kind == 'dup':
                                            msg = pending_tool.get('msg', '')
                                            if msg:
                                                yield f"data: {json.dumps({'system': msg})}\n\n"
                                                try:
                                                    chat_service.add_message("system", msg)
                                                except Exception:
                                                    pass
                                                per_request_system_msgs.append({"role": "system", "content": msg})
                                            stop_outer_loop_local = (kind == 'limit')
                                            pending_tool = None
                                            if stop_outer_loop_local:
                                                stop_outer_loop = True
                                                break
                                            # 对于重复调用，仍进入下一轮让模型继续
                                            break
                                        elif kind == 'call':
                                            tool_name = pending_tool.get('name')
                                            tool_args = pending_tool.get('args') or {}
                                            reason = pending_tool.get('reason') or ''
                                            pending_tool = None
                                            
                                            # 实际调用工具
                                            try:
                                                # 实际调用工具
                                                result = mcp_mod.call_tool(tool_name, tool_args)
                                                # 构造简洁的前端提示（不含详情）
                                                system_msg_front = f"[MCP] 工具完成：{tool_name}（成功）"
                                                yield f"data: {json.dumps({'system': system_msg_front})}\n\n"
                                                # 详细结果仅放入模型上下文
                                                try:
                                                    result_str = json.dumps(result, ensure_ascii=False)
                                                except Exception:
                                                    result_str = str(result)
                                                if len(result_str) > 800:
                                                    result_str = result_str[:800] + '...'
                                                system_msg_detail = f"[MCP] 工具完成：{tool_name}，结果：{result_str}"
                                                try:
                                                    chat_service.add_message("system", system_msg_detail)
                                                except Exception:
                                                    pass
                                                per_request_system_msgs.append({"role": "system", "content": system_msg_detail})
                                                # 说明性提示仅供模型参考，不推送到前端
                                                bracket_note = f"[说明] 结构：AI:[{{content: 已处理, tool: {tool_name}, status: ok}}]。方括号内是你基于内容的回应，现在等待你的下一步操作。"
                                                try:
                                                    chat_service.add_message("system", bracket_note)
                                                except Exception:
                                                    pass
                                                per_request_system_msgs.append({"role": "system", "content": bracket_note})
                                                # 重申用户原始需求，确保基于工具结果继续
                                                if message:
                                                    per_request_system_msgs.append({
                                                        "role": "system",
                                                        "content": f"[用户原始需求(注意：你需要基于工具结果继续回答)] {message}"
                                                    })
                                                try:
                                                    print(f"[MCP][DEBUG] Tool executed: {tool_name}")
                                                except Exception:
                                                    pass
                                                # 一旦执行工具，立刻中断当前流，进入下一轮
                                                break
                                            except Exception as e:
                                                # 失败：前端仅显示失败，不展示错误详情
                                                err_front = f"[MCP] 工具完成：{tool_name}（失败）"
                                                yield f"data: {json.dumps({'system': err_front})}\n\n"
                                                err_msg = f"[MCP] 工具调用失败：{tool_name}，错误：{str(e)}"
                                                try:
                                                    chat_service.add_message("system", err_msg)
                                                except Exception:
                                                    pass
                                                per_request_system_msgs.append({"role": "system", "content": err_msg})
                                                # 说明性提示仅供模型参考，不推送到前端
                                                bracket_note = f"[说明] 结构：AI:[{{content: 已处理, tool: {tool_name}, status: error}}]。方括号内是你基于内容的回应，现在等待你的下一步操作。"
                                                try:
                                                    chat_service.add_message("system", bracket_note)
                                                except Exception:
                                                    pass
                                                per_request_system_msgs.append({"role": "system", "content": bracket_note})
                                                # 同样在失败场景下，重申用户原始需求，便于 AI 选择改用其他工具或改写方案
                                                try:
                                                    if message:
                                                        per_request_system_msgs.append({
                                                            "role": "system",
                                                            "content": f"[用户原始需求(注意：你需要基于工具结果继续回答)] {message}"
                                                        })
                                                except Exception:
                                                    pass
                                                # 工具失败同样中断本轮
                                                break

                                    # 处理工具请求：暂停输出，调用工具，写入history，并开始下一轮
                                    if mcp_enabled and mcp_mod and isinstance(json_data, dict) and 'tool_request' in json_data:
                                        tr = json_data.get('tool_request') or {}
                                        tool_process_result = _process_tool_request(
                                            tr, max_ai_iterations, iteration_count, seen_tool_sigs,
                                            message, per_request_system_msgs, tool_request_history, has_tool_context
                                        )
                                        if tr.get('name'):
                                            saw_tool_request = True
                                            # 一旦检测到工具请求：记录本次 assistant 的 tool_request JSON，并进入工具上下文
                                            try:
                                                if json_str:
                                                    tool_request_history.append({"role": "assistant", "content": json_str})
                                            except Exception:
                                                pass
                                            has_tool_context = True
                                            # 轮次计数与检查
                                            iteration_count += 1
                                            if iteration_count > max_ai_iterations:
                                                limit_msg = f"[MCP] 已达到单次请求的最大AI轮次限制({max_ai_iterations})，停止工具调用。"
                                                pending_tool = {"type": "limit", "msg": limit_msg}
                                                # 等待句末后再提示并结束
                                                continue

                                            # 构造去重签名：name+sorted(args)
                                            try:
                                                sig = json.dumps({"name": tr.get('name'), "args": tr.get('args') or {}}, sort_keys=True, ensure_ascii=False)
                                            except Exception:
                                                sig = f"{tr.get('name')}:{str(tr.get('args') or {})}"
                                            if sig in seen_tool_sigs:
                                                dup_msg = f"[MCP] 检测到重复的工具请求，已跳过：{tr.get('name')} args={tr.get('args') or {}}"
                                                pending_tool = {"type": "dup", "msg": dup_msg}
                                                # 等待句末后提示，再进入下一轮
                                                continue
                                            else:
                                                seen_tool_sigs.add(sig)
                                            # 延迟到句末执行实际调用
                                            if tr.get('name'):
                                                pending_tool = {
                                                    "type": "call", 
                                                    "name": tr.get('name'), 
                                                    "args": tr.get('args') or {}, 
                                                    "reason": tr.get('reason') or ""
                                                }
                                except json.JSONDecodeError:
                                    # 流式传输中可能出现部分JSON未完整闭合的情况，忽略并等待更多数据
                                    pass
                        except Exception:
                            # 如果解析失败，尽量回退为原始片段推送（保持兼容）
                            yield f"data: {json.dumps({'content': chunk})}\n\n"

                    # 一次流式完成
                    if stop_outer_loop:
                        # 达到限制，直接结束
                        yield "data: [DONE]\n\n"
                        return
                    if saw_tool_request:
                        # 不记录本轮的assistant文本，直接进入下一轮（已有工具结果写入history）
                        continue
                    else:
                        # 正常完成，无工具调用；记录并收尾
                        if full_response:
                            chat_service.add_message("assistant", full_response)
                            try:
                                character_id = chat_service.config_service.current_character_id or "default"
                                chat_service.memory_service.add_conversation(
                                    user_message=message,
                                    assistant_message=full_response,
                                    character_name=character_id
                                )
                            except Exception as e:
                                print(f"添加对话到记忆数据库失败: {e}")
                            try:
                                conversation_history = chat_service.format_messages()
                                character_config = chat_service.get_character_config()
                                options = option_service.generate_options(
                                    conversation_history=conversation_history,
                                    character_config=character_config,
                                    user_query=message
                                )
                                if options:
                                    yield f"data: {json.dumps({'options': options})}\n\n"
                            except Exception as e:
                                print(f"选项生成失败: {e}")
                        yield "data: [DONE]\n\n"
                        return
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                yield "data: [DONE]\n\n"

        headers = {
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
        return Response(generate(), mimetype='text/event-stream', headers=headers)
    except APIError as e:
        return jsonify({'success': False, 'error': e.message}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/background', methods=['POST'])
def generate_background():
    try:
        prompt = request.json.get('prompt')
        result = image_service.generate_background(prompt)
        if "image_path" in result:
            rel_path = os.path.relpath(result["image_path"], start=(bp.static_folder or str(project_root / 'static')))
            background_url = f"/static/{rel_path.replace(os.sep, '/')}"
            return jsonify({
                'success': True,
                'background_url': background_url,
                'prompt': result.get('config', {}).get('prompt')
            })
        return jsonify({'success': False, 'error': '背景图片生成失败'}), 500
    except APIError as e:
        return jsonify({'success': False, 'error': e.message}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/clear', methods=['POST'])
def clear_history():
    try:
        chat_service.clear_history()
        prompt_type = request.json.get('prompt_type', 'character')
        chat_service.set_system_prompt(prompt_type)
        return jsonify({'success': True, 'message': '对话历史已清空'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500