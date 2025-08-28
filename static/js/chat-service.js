// 聊天服务模块 - 处理消息发送和背景更换
import { 
    messageInput, 
    currentMessage 
} from './dom-elements.js';
import { 
    showLoading, 
    hideLoading, 
    showError, 
    updateCurrentMessage, 
    addToHistory, 
    disableUserInput, 
    enableUserInput, 
    showContinuePrompt, 
    hideContinuePrompt, 
    updateBackground,
    getIsProcessing,
    setIsProcessing,
    setIsPaused
} from './ui-service.js';
import { getCurrentCharacter, handleMoodChange } from './character-service.js';

// 存储MCP工具的详细结果
window.mcpToolResults = window.mcpToolResults || {};

// 流式处理器实例
let streamProcessor = null;

// 发送消息
export async function sendMessage() {
    const message = messageInput.value.trim();

    if (!message) {
        showError('请输入消息');
        return;
    }

    if (getIsProcessing()) {
        showError('正在处理上一条消息，请稍候');
        return;
    }

    // 创建新的流式处理器
    streamProcessor = new StreamProcessor();

    // 跟踪已添加到历史记录的内容长度（与 StreamProcessor 的段落边界对齐）
    let addedToHistoryLength = 0;

    // 判断句子是否包含实质内容（非纯标点/空白）
    const hasSubstance = (s) => /[^\s\u3000\u3002\uff01\uff1f\.!?]/.test(s);

    // 设置回调函数
    streamProcessor.setCallbacks(
        // 字符回调
        (fullContent) => {
            const newContent = fullContent.substring(addedToHistoryLength);
            updateCurrentMessage('assistant', newContent, true);
        },
        // 暂停回调（自动继续，无需用户点击）
        (fullContent) => {
            setIsPaused(true);
            const currentCharacter = getCurrentCharacter();
            const characterName = currentCharacter ? currentCharacter.name : 'AI助手';
            const newContent = (fullContent.substring(addedToHistoryLength) || '');
            // 清理：避免新段开头出现游离标点（中英文句末符号与省略号）
            const cleaned = newContent.replace(/^[\s\u3000]*[\u3002\uff01\uff1f\.\!\?\u2026]+\s*/, '');
            const toAppend = hasSubstance(cleaned) ? cleaned : newContent;
            if (toAppend && hasSubstance(toAppend)) {
                addToHistory('assistant', toAppend, characterName);
                addedToHistoryLength = fullContent.length;
            } else {
                addedToHistoryLength = fullContent.length;
            }
            hideContinuePrompt();
            if (streamProcessor) {
                streamProcessor.continue();
            }
        },
        // 完成回调
        (fullContent) => {
            const currentCharacter = getCurrentCharacter();
            const characterName = currentCharacter ? currentCharacter.name : 'AI助手';
            const remainingContent = (fullContent.substring(addedToHistoryLength) || '');
            const cleanedRemain = remainingContent.replace(/^[\s\u3000]*[\u3002\uff01\uff1f\.\!\?\u2026]+\s*/, '');
            const toAppendFinal = hasSubstance(cleanedRemain) ? cleanedRemain : remainingContent;
            if (toAppendFinal && hasSubstance(toAppendFinal)) {
                addToHistory('assistant', toAppendFinal, characterName);
            }
            hideContinuePrompt();
            enableUserInput();
            setIsPaused(false);
            if (window.pendingOptions && window.pendingOptions.length > 0) {
                if (window.showOptionsAsUserBubble) {
                    window.showOptionsAsUserBubble(window.pendingOptions);
                } else if (window.showOptionButtons) {
                    // 兼容旧逻辑
                    window.showOptionButtons(window.pendingOptions);
                }
                window.pendingOptions = null;
            }
        }
    );

    // 更新当前消息为用户消息
    updateCurrentMessage('user', message);

    // 添加到历史记录
    addToHistory('user', message);

    // 隐藏选项按钮
    if (window.hideOptionButtons) {
        window.hideOptionButtons();
    }

    // 清空输入框并更新状态
    messageInput.value = '';
    
    // 如果有输入框增强功能，更新其状态
    if (window.inputEnhancements) {
        window.inputEnhancements.updateCharCount();
        window.inputEnhancements.updateSendButtonState();
        window.inputEnhancements.autoResize();
    }

    // 禁用用户输入
    disableUserInput();

    try {
        // 发送API请求
        const response = await fetch('/api/chat/stream', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                message,
                mcp_enabled: (typeof window.getMcpEnabled === 'function') ? window.getMcpEnabled() : false
            })
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({
                error: `HTTP ${response.status}: ${response.statusText}`
            }));
            throw new Error(errorData.error || '请求失败');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let sseBuffer = '';

        // 准备接收流式响应（仅用于创建流式气泡，不覆盖系统消息）
        updateCurrentMessage('assistant', '\n', true);

        // 读取流式响应
        while (true) {
            const { done, value } = await reader.read();

            if (done) {
                // 处理缓冲区中残留的行
                if (sseBuffer.trim()) {
                    const maybeLine = sseBuffer.trim();
                    if (maybeLine.startsWith('data: ')) {
                        const jsonStr = maybeLine.slice(6);
                        if (jsonStr === '[DONE]') {
                            streamProcessor.markEnd();
                            break;
                        }
                        try {
                            const data = JSON.parse(jsonStr);
                            if (data.system) {
                                // 在追加系统提示前，先将当前已生成的角色文本固定为历史气泡
                                if (streamProcessor) {
                                    const fullContent = streamProcessor.getFullContentIncludingBuffer?.()
                                        || streamProcessor.getFullContent();
                                    const newContent = (fullContent.substring(addedToHistoryLength) || '');
                                    // 不再清理前导标点，避免标点缺失
                                    const toAppend = newContent;
                                    if (toAppend && hasSubstance(toAppend)) {
                                        const currentCharacter = getCurrentCharacter();
                                        const characterName = currentCharacter ? currentCharacter.name : 'AI助手';
                                        addToHistory('assistant', toAppend, characterName);
                                        addedToHistoryLength = fullContent.length;
                                        // 记录一个待丢弃前缀，用于下一轮到来的助手内容做去重
                                        window.__pendingDropPrefix = toAppend;
                                    }
                                }
                                
                                // 检查是否为MCP工具消息
                                const isMCPMessage = data.system.startsWith('[MCP] 工具完成：');
                                if (isMCPMessage) {
                                    // 为MCP消息生成唯一ID并存储
                                    const messageId = 'mcp_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
                                    window.mcpToolResults[messageId] = {
                                        summary: data.system,
                                        timestamp: new Date().toISOString()
                                    };
                                    
                                    // 添加带有ID的消息到历史记录
                                    addToHistory('system', data.system, '系统');
                                    
                                    // 将消息ID与气泡关联
                                    setTimeout(() => {
                                        const bubbles = document.querySelectorAll('.chat-bubble.system');
                                        const lastBubble = bubbles[bubbles.length - 1];
                                        if (lastBubble && !lastBubble.dataset.messageId) {
                                            lastBubble.dataset.messageId = messageId;
                                        }
                                    }, 0);
                                } else {
                                    addToHistory('system', data.system, '系统');
                                }
                            }
                            if (data.mood !== undefined) handleMoodChange(data.mood);
                            if (data.content) streamProcessor.addData(data.content);
                            if (data.options) window.pendingOptions = data.options;
                        } catch (e) {
                            console.error('解析JSON失败(EOF):', e, jsonStr);
                        }
                    }
                }
                break;
            }

            const chunk = decoder.decode(value, { stream: true });
            sseBuffer += chunk;

            try {
                // 按行解析，但保留不完整的尾部到下次
                let idx;
                while ((idx = sseBuffer.indexOf('\n')) !== -1) {
                    const rawLine = sseBuffer.slice(0, idx);
                    sseBuffer = sseBuffer.slice(idx + 1);
                    const line = rawLine.trim();
                    if (!line) continue;
                    if (!line.startsWith('data: ')) continue;

                    const jsonStr = line.slice(6);
                    if (jsonStr === '[DONE]') {
                        streamProcessor.markEnd();
                        sseBuffer = '';
                        break;
                    }
                    try {
                        const data = JSON.parse(jsonStr);
                        if (data.error) throw new Error(data.error);
                        if (data.mood !== undefined) {
                            handleMoodChange(data.mood);
                        }
                        if (data.content) {
                            // 若上一条为系统提示，且我们刚刚把助手文本固定进历史，则去重处理
                            let incoming = data.content;
                            const prev = window.__pendingDropPrefix || '';
                            if (prev) {
                                // 计算 prev 的后缀与 incoming 前缀的最大重叠
                                const maxK = Math.min(prev.length, 200);
                                let overlap = 0;
                                for (let k = maxK; k > 0; k--) {
                                    if (prev.slice(prev.length - k) === incoming.slice(0, k)) {
                                        overlap = k; break;
                                    }
                                }
                                if (overlap > 0) {
                                    incoming = incoming.slice(overlap);
                                }
                                // 只针对第一批内容进行一次去重
                                window.__pendingDropPrefix = '';
                            }
                            if (incoming) {
                                streamProcessor.addData(incoming);
                            }
                        }
                        if (data.system) {
                            // 在追加系统提示前，先将当前已生成的角色文本固定为历史气泡
                            if (streamProcessor) {
                                const fullContent = streamProcessor.getFullContentIncludingBuffer?.() || streamProcessor.getFullContent();
                                const newContent = (fullContent.substring(addedToHistoryLength) || '');
                                // 不再清理前导标点，避免标点缺失
                                const toAppend = newContent;
                                if (toAppend && hasSubstance(toAppend)) {
                                    const currentCharacter = getCurrentCharacter();
                                    const characterName = currentCharacter ? currentCharacter.name : 'AI助手';
                                    addToHistory('assistant', toAppend, characterName);
                                    addedToHistoryLength = fullContent.length;
                                    // 记录一个待丢弃前缀，用于下一轮到来的助手内容做去重
                                    window.__pendingDropPrefix = toAppend;
                                }
                            }
                            
                            // 检查是否为MCP工具消息
                            const isMCPMessage = data.system.startsWith('[MCP] 工具完成：');
                            if (isMCPMessage) {
                                // 为MCP消息生成唯一ID并存储
                                const messageId = 'mcp_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
                                window.mcpToolResults[messageId] = {
                                    summary: data.system,
                                    timestamp: new Date().toISOString()
                                };
                                
                                // 添加带有ID的消息到历史记录
                                addToHistory('system', data.system, '系统');
                                
                                // 将消息ID与气泡关联
                                setTimeout(() => {
                                    const bubbles = document.querySelectorAll('.chat-bubble.system');
                                    const lastBubble = bubbles[bubbles.length - 1];
                                    if (lastBubble && !lastBubble.dataset.messageId) {
                                        lastBubble.dataset.messageId = messageId;
                                    }
                                }, 0);
                            } else {
                                addToHistory('system', data.system, '系统');
                            }
                        }
                        if (data.options) {
                            window.pendingOptions = data.options;
                        }
                    } catch (e) {
                        console.error('解析JSON失败:', e, jsonStr);
                    }
                }
            } catch (e) {
                console.error('解析流式响应失败:', e);
            }
        }

    } catch (error) {
        console.error('发送消息失败:', error);
        showError(`发送消息失败: ${error.message}`);
        hideLoading();
        enableUserInput();

        if (streamProcessor) {
            streamProcessor.reset();
        }
    }

}

// 更换背景
export async function changeBackground() {
    if (getIsProcessing()) {
        showError('正在处理请求，请稍候');
        return;
    }

    showLoading();

    try {
        const response = await fetch('/api/background', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({})
        });

        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || '请求失败');
        }

        if (data.background_url) {
            updateBackground(data.background_url);

            const promptMessage = data.prompt ?
                `背景已更新，提示词: "${data.prompt}"` :
                '背景已更新';

            // 追加系统提示为独立气泡，避免覆盖初始系统消息
            addToHistory('system', promptMessage, '系统');
        }

    } catch (error) {
        console.error('更换背景失败:', error);
        showError(`更换背景失败: ${error.message}`);
    } finally {
        hideLoading();
    }
}
// 继续输出
export function continueOutput() {
    console.log('continueOutput called, streamProcessor:', streamProcessor);

    if (streamProcessor) {
        hideContinuePrompt();
        streamProcessor.continue();
    }
}

// 跳过打字效果
export function skipTyping() {
    if (streamProcessor && streamProcessor.isProcessing()) {
        streamProcessor.skip();
        hideContinuePrompt();
        enableUserInput();
    }
}

// 暴露给全局使用
window.sendMessage = sendMessage;
window.continueOutput = continueOutput;
