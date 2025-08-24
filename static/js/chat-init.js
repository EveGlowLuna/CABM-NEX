// 对话页面的初始化和事件绑定
import { 
    sendMessage, 
    changeBackground, 
    continueOutput, 
    skipTyping 
} from './chat-service.js';

import {
    loadCharacters,
    toggleCharacterModal,
    getCurrentCharacter
} from './character-service.js';

// 已移除配音/录音相关：不再引入 audio-service

import {
    showError,
    hideError,
    toggleHistory,
    handleConfirmYes,
    handleConfirmNo,
    hideConfirmModal
} from './ui-service.js';

// 页面初始化
document.addEventListener('DOMContentLoaded', () => {
    try {
        console.log('开始初始化对话页面...');
        
        // 加载角色数据
        loadCharacters();

        // 绑定按钮事件
        const backgroundButton = document.getElementById('backgroundButton');
        const historyButton = document.getElementById('historyButton');
        const closeHistoryButton = document.getElementById('closeHistoryButton');
        const characterButton = document.getElementById('characterButton');
        const closeCharacterButton = document.getElementById('closeCharacterButton');
        const continueButton = document.getElementById('continueButton');
        const micButton = document.getElementById('micButton');
        const errorCloseButton = document.getElementById('errorCloseButton');
        const messageInput = document.getElementById('messageInput');
        const currentMessage = document.getElementById('currentMessage');
        const clickToContinue = document.getElementById('clickToContinue');
        const mcpToggle = document.getElementById('mcpToggle');

        // 绑定对话事件
        backgroundButton?.addEventListener('click', changeBackground);
        historyButton?.addEventListener('click', toggleHistory);
        closeHistoryButton?.addEventListener('click', toggleHistory);
        characterButton?.addEventListener('click', toggleCharacterModal);
        closeCharacterButton?.addEventListener('click', toggleCharacterModal);
        continueButton?.addEventListener('click', continueOutput);
        // 已移除麦克风录音绑定
        errorCloseButton?.addEventListener('click', hideError);

        // 绑定确认对话框事件
        const confirmYesButton = document.getElementById('confirmYesButton');
        const confirmNoButton = document.getElementById('confirmNoButton');
        const closeConfirmButton = document.getElementById('closeConfirmButton');

        confirmYesButton?.addEventListener('click', handleConfirmYes);
        confirmNoButton?.addEventListener('click', handleConfirmNo);
        closeConfirmButton?.addEventListener('click', hideConfirmModal);

        // 绑定点击事件继续输出
        currentMessage?.addEventListener('click', continueOutput);
        clickToContinue?.addEventListener('click', continueOutput);

        // MCP 开关初始化与事件
        const applyMcpToggleUI = (enabled) => {
            if (!mcpToggle) return;
            mcpToggle.textContent = `MCP 工具：${enabled ? '开启' : '关闭'}`;
            mcpToggle.classList.toggle('primary-btn', !!enabled); // 蓝色
            mcpToggle.classList.toggle('secondary-btn', !enabled); // 灰色
        };

        let mcpEnabled = localStorage.getItem('mcpEnabled');
        mcpEnabled = mcpEnabled === 'true';
        applyMcpToggleUI(mcpEnabled);

        if (mcpToggle) {
            mcpToggle.addEventListener('click', () => {
                mcpEnabled = !mcpEnabled;
                localStorage.setItem('mcpEnabled', String(mcpEnabled));
                applyMcpToggleUI(mcpEnabled);
            });
        }

        // 暴露读取函数
        window.getMcpEnabled = () => !!mcpEnabled;
        
        console.log('对话页面初始化完成');
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
import { showOptionButtons } from './ui-service.js';
window.showOptionButtons = showOptionButtons;
window.showError = showError;
