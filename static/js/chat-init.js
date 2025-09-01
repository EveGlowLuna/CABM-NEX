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

// 应用亚克力效果类
function applyAcrylicEffect(useAcrylic) {
    const elements = document.querySelectorAll('.acrylic');
    elements.forEach(element => {
        if (useAcrylic) {
            element.classList.remove('no-acrylic');
            element.classList.add('acrylic');
        } else {
            element.classList.remove('acrylic');
            element.classList.add('no-acrylic');
        }
    });
}

// 初始化亚克力效果
function initAcrylicEffect() {
    // 从localStorage获取设置，默认为true（开启）
    const useAcrylicEffect = localStorage.getItem('useAcrylicEffect') !== 'false';
    applyAcrylicEffect(useAcrylicEffect);
    
    // 监听设置变化
    window.addEventListener('acrylicEffectChanged', (event) => {
        applyAcrylicEffect(event.detail);
    });
}

document.addEventListener('DOMContentLoaded', () => {
    // 初始化亚克力效果
    initAcrylicEffect();
    
    // 初始化聊天服务
    initializeChat();
    
    // 设置输入增强功能
    setupInputEnhancements();
    
    // 设置科幻效果
    setupSciFiEffects();
    
    // 设置角色显示
    setupCharacterDisplay();
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
