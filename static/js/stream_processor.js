/**
 * 流式响应处理器
 * 参考 stream.py 的处理方式，在前端实现流式数据的分段和控制
 */

// 常量配置
const OUTPUT_DELAY = 30; // 每个字符的输出间隔（毫秒）
const END_MARKER = "<END>"; // 结束标记符号
// 关闭断句分割：启用后不会在标点处分段/暂停
const NO_SEGMENTATION = true;
// 暂停输出的分隔符号：仅标点，不在空格处分段（当 NO_SEGMENTATION=false 时生效）
const PAUSE_MARKERS = ['。', '？', '！', '…', '~', '♪', '.', '!', '?'];

class StreamProcessor {
    constructor() {
        this.buffer = [];
        this.active = true;
        this.isPaused = false;
        this.currentParagraph = '';
        this.paragraphs = [];
        this.onCharacterCallback = null;
        this.onPauseCallback = null;
        this.onCompleteCallback = null;
        this.processingTimeout = null;
        this.lastCharWasPauseMarker = false; // 新增：标记上一个字符是否为暂停标记
    }

    /**
     * 设置回调函数
     */
    setCallbacks(onCharacter, onPause, onComplete) {
        this.onCharacterCallback = onCharacter;
        this.onPauseCallback = onPause;
        this.onCompleteCallback = onComplete;
    }

    /**
     * 添加数据到缓冲区
     */
    addData(data) {
        // 将数据逐字符添加到缓冲区
        for (const char of data) {
            this.buffer.push(char);
        }

        // 如果没有在处理且没有暂停，开始处理
        if (!this.processingTimeout && this.active && !this.isPaused) {
            this.processBuffer();
        }
    }

    /**
     * 标记数据结束
     */
    markEnd() {
        this.buffer.push(END_MARKER);
        this.active = false;

        // 如果没有在处理，开始处理
        if (!this.processingTimeout) {
            this.processBuffer();
        }
    }

    /**
     * 处理缓冲区数据
     */
    processBuffer() {
        if (this.buffer.length === 0 || this.processingTimeout) {
            return;
        }

        // 如果暂停，停止处理
        if (this.isPaused) {
            return;
        }

        // 取出一个字符
        const char = this.buffer.shift();

        // 如果是结束标记
        if (char === END_MARKER) {
            // 如果还有未处理的段落，添加到结果中
            if (this.currentParagraph) {
                this.paragraphs.push(this.currentParagraph);
                this.currentParagraph = '';
            }

            // 调用完成回调
            if (this.onCompleteCallback) {
                this.onCompleteCallback(this.paragraphs.join(''));
            }
            return;
        }

        // 检查是否需要分割（当 NO_SEGMENTATION=false 时才启用分割暂停）
        if (!NO_SEGMENTATION) {
            if (this.lastCharWasPauseMarker && !PAUSE_MARKERS.includes(char)) {
                const nextChar = this.buffer.length > 0 ? this.buffer[0] : null;
                if (nextChar !== END_MARKER) {
                    this.handlePause();
                    this.lastCharWasPauseMarker = false;
                    this.buffer.unshift(char);
                    return;
                }
            }
        }

        // 正常字符处理
        this.currentParagraph += char;

        // 调用字符回调
        if (this.onCharacterCallback) {
            this.onCharacterCallback(this.paragraphs.join('') + this.currentParagraph);
        }

        // 更新暂停标记状态（当启用分割时）
        if (!NO_SEGMENTATION) {
            this.lastCharWasPauseMarker = PAUSE_MARKERS.includes(char);
        } else {
            this.lastCharWasPauseMarker = false;
        }

        // 继续处理下一个字符
        this.processingTimeout = setTimeout(() => {
            this.processingTimeout = null;
            this.processBuffer();
        }, OUTPUT_DELAY);
    }

    /**
     * 处理暂停状态
     */
    handlePause() {
        this.isPaused = true;

        // 将当前段落添加到段落列表
        if (this.currentParagraph) {
            this.paragraphs.push(this.currentParagraph);
            this.currentParagraph = '';
        }

        // 调用暂停回调
        if (this.onPauseCallback) {
            this.onPauseCallback(this.paragraphs.join(''));
        }
    }

    /**
     * 继续处理
     */
    continue() {
        console.log('StreamProcessor.continue() called, isPaused:', this.isPaused, 'buffer length:', this.buffer.length);
        
        if (this.isPaused) {
            this.isPaused = false;
            console.log('Unpaused, continuing processing...');

            // 继续处理缓冲区
            if (!this.processingTimeout) {
                this.processBuffer();
            } else {
                console.log('Processing timeout already exists, not calling processBuffer');
            }
        } else {
            console.log('Not paused, no action needed');
        }
    }

    /**
     * 跳过当前处理，直接显示所有内容
     */
    skip() {
        // 清除处理超时
        if (this.processingTimeout) {
            clearTimeout(this.processingTimeout);
            this.processingTimeout = null;
        }

        // 将所有缓冲区内容添加到当前段落
        let remainingContent = '';
        while (this.buffer.length > 0) {
            const char = this.buffer.shift();
            if (char === END_MARKER) {
                break;
            }
            remainingContent += char;
        }

        this.currentParagraph += remainingContent;

        // 如果有内容，添加到段落列表
        if (this.currentParagraph) {
            this.paragraphs.push(this.currentParagraph);
            this.currentParagraph = '';
        }

        // 调用完成回调
        if (this.onCompleteCallback) {
            this.onCompleteCallback(this.paragraphs.join(''));
        }

        // 重置状态
        this.isPaused = false;
        this.active = false;
    }

    /**
     * 重置处理器状态
     */
    reset() {
        // 清除处理超时
        if (this.processingTimeout) {
            clearTimeout(this.processingTimeout);
            this.processingTimeout = null;
        }

        this.buffer = [];
        this.active = true;
        this.isPaused = false;
        this.currentParagraph = '';
        this.paragraphs = [];
        this.lastCharWasPauseMarker = false;
    }

    /**
     * 获取当前完整内容
     */
    getFullContent() {
        return this.paragraphs.join('') + this.currentParagraph;
    }

    /**
     * 获取包含缓冲区在内的完整内容（用于在系统提示到达时结算显示）
     */
    getFullContentIncludingBuffer() {
        const pending = this.buffer.filter(ch => ch !== END_MARKER).join('');
        return this.paragraphs.join('') + this.currentParagraph + pending;
    }

    /**
     * 检查是否正在处理
     */
    isProcessing() {
        return this.active || this.buffer.length > 0 || this.processingTimeout !== null;
    }
}

// 导出类
window.StreamProcessor = StreamProcessor;