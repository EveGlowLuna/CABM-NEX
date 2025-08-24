// 主入口文件 - 事件绑定和初始化

import { 
    startButton, 
    backButton, 
    exitButton, 
    sendButton, 
    backgroundButton, 
    historyButton, 
    closeHistoryButton, 
    characterButton, 
    closeCharacterButton, 
    continueButton, 
   // skipButton, 
    errorCloseButton, 
    confirmYesButton, 
    confirmNoButton, 
    closeConfirmButton, 
    messageInput,
    currentMessage,
    clickToContinue
} from './dom-elements.js';

import { 
    showChatPage, 
    confirmBackToHome, 
    confirmExit, 
    toggleHistory, 
    hideError, 
    handleConfirmYes, 
    handleConfirmNo, 
    hideConfirmModal,
    showOptionButtons,
    showError
} from './ui-service.js';

import { 
    loadCharacters, 
    toggleCharacterModal, 
    getCurrentCharacter 
} from './character-service.js';

// 已移除音频与TTS相关功能

import { 
    sendMessage, 
    changeBackground, 
    continueOutput, 
    skipTyping 
} from './chat-service.js';

// 全局错误处理
window.addEventListener('error', (event) => {
    console.error('全局错误:', event.error);
    showError(`发生错误: ${event.error.message}`);
});

window.addEventListener('unhandledrejection', (event) => {
    console.error('未处理的Promise拒绝:', event.reason);
    showError(`请求失败: ${event.reason}`);
});

// 初始化

document.addEventListener('DOMContentLoaded', () => {
    try {
        console.log('开始初始化CABM应用...');
        [
            startButton,
            backButton,
            exitButton,
            sendButton,
            backgroundButton,
            historyButton,
            closeHistoryButton,
            characterButton,
            closeCharacterButton,
            continueButton,
            errorCloseButton,
            confirmYesButton,
            confirmNoButton,
            closeConfirmButton,
            currentMessage,
            clickToContinue
          ].forEach((el, i) => {
            if (!el) {
              console.warn(`元素未找到：索引 ${i}`);
            }
          });
        // 加载角色数据
        //loadCharacters();
        let charactersLoaded = false;

        characterButton.addEventListener('click', () => {
            if (!charactersLoaded) {
                loadCharacters();
                charactersLoaded = true;
            }
            toggleCharacterModal();
        });
        // 绑定页面切换事件
        startButton.addEventListener('click', showChatPage);
        backButton.addEventListener('click', confirmBackToHome);
        exitButton.addEventListener('click', confirmExit);

        // 绑定对话事件
        // sendButton 的点击事件已经在 input-enhancements.js 中处理
        backgroundButton.addEventListener('click', changeBackground);
        historyButton.addEventListener('click', toggleHistory);
        closeHistoryButton.addEventListener('click', toggleHistory);
        characterButton.addEventListener('click', toggleCharacterModal);
        closeCharacterButton.addEventListener('click', toggleCharacterModal);
        continueButton.addEventListener('click', continueOutput);
        //skipButton.addEventListener('click', skipTyping);
        errorCloseButton.addEventListener('click', hideError);

        // 绑定确认对话框事件
        confirmYesButton.addEventListener('click', handleConfirmYes);
        confirmNoButton.addEventListener('click', handleConfirmNo);
        closeConfirmButton.addEventListener('click', hideConfirmModal);

        // 键盘快捷键已经在 input-enhancements.js 中处理

        // 绑定点击事件继续输出
        currentMessage.addEventListener('click', continueOutput);
        clickToContinue.addEventListener('click', continueOutput);
        
        console.log('CABM应用初始化完成');
    } catch (error) {
        console.error('初始化失败:', error);
        showError(`初始化失败: ${error.message}`);
    }
});

// 注册快捷键
function registrationShortcuts(config) {
    document.addEventListener('keydown', e => {
        if (e.key in config) {
            if (e.key.length === 1) {
                if (e.altKey) {
                    config[e.key]();
                }
            } else {
                config[e.key]();
            }
        }
    });
}

registrationShortcuts({
    Enter: continueOutput,
    s: skipTyping,
    h: toggleHistory,
    b: changeBackground
});

// 暴露必要的函数给全局使用
window.getCurrentCharacter = getCurrentCharacter;
window.showOptionButtons = showOptionButtons;
window.showError = showError;
