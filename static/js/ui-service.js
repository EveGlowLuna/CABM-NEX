// UI服务模块 - 处理界面交互和模态框管理
import { 
    homePage, 
    chatPage, 
    characterName, 
    currentMessage, 
    chatLog,
    messageInput, 
    sendButton, 
    micButton,
    continueButton,
    clickToContinue,
    optionButtonsContainer,
    optionButtons,
    historyModal,
    historyMessages,
    confirmModal,
    confirmMessage,
    loadingIndicator,
    errorContainer,
    errorMessage
} from './dom-elements.js';

// 状态变量
let isProcessing = false;
let isPaused = false;
let messageHistory = [];
let currentTypingTimeout = null;
let currentConfirmCallback = null;
let currentScreenClickHandler = null;

// 获取状态
export function getIsProcessing() {
    return isProcessing;
}

// 按需求：在AI完成后，创建一个新的“我”的气泡，内含三个选项按钮
export function showOptionsAsUserBubble(options) {
    if (!chatLog || !Array.isArray(options) || options.length === 0) return;

    // 先清掉任何旧的选项气泡
    const old = chatLog.querySelector('.chat-bubble.user.option-holder');
    if (old) old.remove();

    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble user option-holder';

    const name = document.createElement('div');
    name.className = 'name';
    name.textContent = '你';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'content';

    const inline = document.createElement('div');
    inline.className = 'inline-options';
    options.forEach((option) => {
        const btn = document.createElement('button');
        btn.className = 'option-button';
        btn.textContent = option;
        btn.addEventListener('click', () => selectOption(option));
        inline.appendChild(btn);
    });

    contentDiv.appendChild(inline);
    bubble.appendChild(name);
    bubble.appendChild(contentDiv);
    chatLog.appendChild(bubble);
    chatLog.scrollTop = chatLog.scrollHeight;
}

export function setIsProcessing(value) {
    isProcessing = value;
}

export function getIsPaused() {
    return isPaused;
}

export function setIsPaused(value) {
    isPaused = value;
}

export function getMessageHistory() {
    return messageHistory;
}

// 显示加载指示器
export function showLoading() {
    isProcessing = true;
    loadingIndicator.style.display = 'flex';
}

// 隐藏加载指示器
export function hideLoading() {
    isProcessing = false;
    loadingIndicator.style.display = 'none';
}

// 显示错误信息
export function showError(message) {
    errorMessage.textContent = message;
    errorContainer.style.display = 'block';
}

// 隐藏错误信息
export function hideError() {
    errorContainer.style.display = 'none';
}

// 更新当前消息
export function updateCurrentMessage(role, content, isStreaming = false) {
    if (!isStreaming && currentTypingTimeout) {
        clearTimeout(currentTypingTimeout);
        currentTypingTimeout = null;
    }

    // 顶部名称始终显示当前角色，不显示“你”
    const currentCharacter = window.getCurrentCharacter ? window.getCurrentCharacter() : null;
    if (currentCharacter) {
        characterName.textContent = currentCharacter.name;
        characterName.style.color = currentCharacter.color;
    } else {
        characterName.textContent = 'AI助手';
        characterName.style.color = '#ffeb3b';
    }

    // 流式内容在右侧对话板中展示一个临时气泡
    if (role === 'assistant' && isStreaming && chatLog) {
        let streaming = document.getElementById('streamingBubble');
        if (!streaming) {
            streaming = document.createElement('div');
            streaming.id = 'streamingBubble';
            streaming.className = 'chat-bubble assistant';
            const name = document.createElement('div');
            name.className = 'name';
            const currentCharacter = window.getCurrentCharacter ? window.getCurrentCharacter() : null;
            name.textContent = currentCharacter ? currentCharacter.name : 'AI';
            const contentDiv = document.createElement('div');
            contentDiv.className = 'content';
            streaming.appendChild(name);
            streaming.appendChild(contentDiv);
            chatLog.appendChild(streaming);
        }
        const contentDiv = streaming.querySelector('.content');
        if (contentDiv) contentDiv.textContent = content;
        chatLog.scrollTop = chatLog.scrollHeight;
        return;
    }

    // 仅当为系统消息时才更新初始系统气泡，避免被后续AI/用户内容覆盖
    if (role === 'system') {
        if (currentMessage) currentMessage.textContent = content;
    }
}

// 添加消息到历史记录
export function addToHistory(role, content, customName = null) {
    const normalizedRole = role === 'assistant_continue' ? 'assistant' : role;
    messageHistory.push({ role: normalizedRole, content });

    if (!chatLog) return;

    // 移除流式临时气泡（如果存在）
    const streaming = document.getElementById('streamingBubble');
    if (streaming && normalizedRole === 'assistant') {
        streaming.remove();
    }

    const bubble = document.createElement('div');
    bubble.className = `chat-bubble ${normalizedRole}`;

    const name = document.createElement('div');
    name.className = 'name';
    if (normalizedRole === 'user') {
        name.textContent = '你';
    } else if (normalizedRole === 'assistant') {
        const currentCharacter = window.getCurrentCharacter ? window.getCurrentCharacter() : null;
        name.textContent = customName || (currentCharacter ? currentCharacter.name : 'AI');
    } else {
        name.textContent = '系统';
    }

    const contentDiv = document.createElement('div');
    contentDiv.className = 'content';
    contentDiv.textContent = content;

    bubble.appendChild(name);
    bubble.appendChild(contentDiv);
    chatLog.appendChild(bubble);
    chatLog.scrollTop = chatLog.scrollHeight;
}

// 切换历史记录面板
export function toggleHistory() {
    if (!historyModal || !historyMessages) return;
    if (historyModal.style.display === 'flex') {
        historyModal.style.display = 'none';
    } else {
        historyModal.style.display = 'flex';
        historyMessages.scrollTop = historyMessages.scrollHeight;
    }
}

// 更新背景图片
export function updateBackground(url) {
    const backgroundElements = document.getElementsByClassName('background-image');
    if (backgroundElements.length > 0) {
        const backgroundElement = backgroundElements[0];
        const newBackground = document.createElement('div');
        newBackground.className = 'background-image';
        newBackground.style.backgroundImage = `url('${url}')`;
        newBackground.style.opacity = '0';

        backgroundElement.parentNode.appendChild(newBackground);

        setTimeout(() => {
            newBackground.style.opacity = '1';
            backgroundElement.style.opacity = '0';
            setTimeout(() => {
                backgroundElement.remove();
            }, 1000);
        }, 10);
    }
}

// 页面切换函数
export function showHomePage() {
    homePage.classList.add('active');
    chatPage.classList.remove('active');
}

export function showChatPage() {
    homePage.classList.remove('active');
    chatPage.classList.add('active');
}

// 确认返回主页
export function confirmBackToHome() {
    if (messageHistory.length > 0) {
        showConfirmModal('确定要返回吗？', () => {
            showHomePage();
        });
    } else {
        showHomePage();
    }
}

// 确认退出应用
export function confirmExit() {
    showConfirmModal('确定要退出应用吗？', exitApplication);
}

// 退出应用
async function exitApplication() {
    try {
        showLoading();
        
        const response = await fetch('/api/exit', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.error || '请求失败');
        }
        
        window.close();
        
        setTimeout(() => {
            showError('请手动关闭浏览器窗口');
        }, 1000);
        
    } catch (error) {
        console.error('退出应用失败:', error);
        showError(`退出应用失败: ${error.message}`);
        hideLoading();
    }
}

// 显示确认对话框
export function showConfirmModal(message, callback) {
    confirmMessage.textContent = message;
    currentConfirmCallback = callback;
    confirmModal.style.display = 'flex';
}

// 隐藏确认对话框
export function hideConfirmModal() {
    confirmModal.style.display = 'none';
    currentConfirmCallback = null;
}

// 处理确认对话框的确定按钮
export function handleConfirmYes() {
    if (currentConfirmCallback) {
        currentConfirmCallback();
    }
    hideConfirmModal();
}

// 处理确认对话框的取消按钮
export function handleConfirmNo() {
    hideConfirmModal();
}

// 禁用用户输入
export function disableUserInput() {
    messageInput.disabled = true;
    sendButton.disabled = true;
    if (micButton) micButton.disabled = true;
    messageInput.placeholder = "角色正在回复中...";
}

// 启用用户输入
export function enableUserInput() {
    messageInput.disabled = false;
    sendButton.disabled = false;
    if (micButton) micButton.disabled = false;
    messageInput.placeholder = "输入消息...";
}

// 显示"点击屏幕继续"提示
export function showContinuePrompt(promptText = '▽') {
    continueButton.classList.add('active');

    if (clickToContinue) {
        clickToContinue.style.display = 'block';
        clickToContinue.textContent = promptText;
    }

    if (currentScreenClickHandler) {
        document.removeEventListener('click', currentScreenClickHandler);
    }

    currentScreenClickHandler = (e) => {
        const clickedElement = e.target;

        if (clickedElement.tagName === 'BUTTON' ||
            clickedElement.tagName === 'INPUT' ||
            clickedElement.tagName === 'TEXTAREA' ||
            clickedElement.tagName === 'IMG' ||
            clickedElement.classList.contains('modal') ||
            clickedElement.classList.contains('btn') ||
            clickedElement.classList.contains('continue-prompt') ||
            clickedElement.closest('button') ||
            clickedElement.closest('.btn') ||
            clickedElement.closest('.modal') ||
            clickedElement.closest('.history-modal') ||
            clickedElement.closest('.character-modal') ||
            clickedElement.closest('.confirm-modal') ||
            clickedElement.closest('.control-buttons') ||
            clickedElement.closest('.user-input-container') ||
            clickedElement.closest('.chat-header') ||
            clickedElement.closest('.character-container') ||
            clickedElement.closest('.continue-prompt')) {
            return;
        }

        if (clickedElement.closest('.dialog-container') ||
            clickedElement.closest('.background-container') ||
            clickedElement === document.body ||
            clickedElement.classList.contains('page')) {
            console.log('Screen clicked during pause');
            if (window.continueOutput) {
                window.continueOutput();
            }
        }
    };

    setTimeout(() => {
        document.addEventListener('click', currentScreenClickHandler);
    }, 100);
}

// 隐藏"点击屏幕继续"提示
export function hideContinuePrompt() {
    if (clickToContinue) {
        clickToContinue.style.display = 'none';
    }

    continueButton.classList.remove('active');

    if (currentScreenClickHandler) {
        document.removeEventListener('click', currentScreenClickHandler);
        currentScreenClickHandler = null;
    }
}

// 显示选项按钮
export function showOptionButtons(options) {
    // 优先渲染到最近一条“我”的气泡内部
    let placedInline = false;
    if (chatLog) {
        const userBubbles = chatLog.querySelectorAll('.chat-bubble.user');
        const lastUser = userBubbles[userBubbles.length - 1];
        if (lastUser) {
            // 移除旧的内联选项
            const existed = lastUser.querySelector('.inline-options');
            if (existed) existed.remove();

            const inline = document.createElement('div');
            inline.className = 'inline-options';
            options.forEach((option) => {
                const btn = document.createElement('button');
                btn.className = 'option-button';
                btn.textContent = option;
                btn.addEventListener('click', () => selectOption(option));
                inline.appendChild(btn);
            });
            lastUser.appendChild(inline);
            placedInline = true;
        }
    }

    // 兼容回退到原有容器（如未找到用户气泡）
    if (!placedInline) {
        optionButtons.innerHTML = '';
        options.forEach((option) => {
            const button = document.createElement('button');
            button.className = 'option-button';
            button.textContent = option;
            button.addEventListener('click', () => selectOption(option));
            optionButtons.appendChild(button);
        });
        optionButtonsContainer.classList.add('show');
    }
}

// 隐藏选项按钮
export function hideOptionButtons() {
    optionButtonsContainer.classList.remove('show');
    optionButtons.innerHTML = '';
    // 移除专用选项气泡
    if (chatLog) {
        const holder = chatLog.querySelector('.chat-bubble.user.option-holder');
        if (holder) holder.remove();
    }
}

// 选择选项
function selectOption(option) {
    hideOptionButtons();
    messageInput.value = option;
    // 需要调用发送消息函数
    if (window.sendMessage) {
        window.sendMessage();
    }
}

// 暴露给全局使用
window.hideOptionButtons = hideOptionButtons;
window.showOptionsAsUserBubble = showOptionsAsUserBubble;
