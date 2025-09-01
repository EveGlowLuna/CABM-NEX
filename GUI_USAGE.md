# CABM PySide6 GUI 使用说明

CABM 现在支持使用 PySide6 内嵌浏览器的方式来显示 UI，替代传统的直接在浏览器中打开的方式。

## 启动方式

有两种方式可以启动 GUI 版本：

### 方法一：使用 start.py 启动

```bash
python start.py --gui
```

### 方法二：直接运行 GUI 脚本

```bash
python cabm_gui.py
```

## 功能特点

1. **内嵌浏览器**：使用 Qt WebEngine 内嵌整个 Web UI，无需额外打开浏览器
2. **统一窗口**：所有功能都在一个窗口中展示，更加集成
3. **原生体验**：提供更接近原生应用的使用体验
4. **兼容性**：完全兼容现有的 Web UI 功能

## 依赖要求

GUI 版本需要额外安装以下依赖：

```
pyside6==6.8.1
pyqt6-webengine==6.8.0
```

可以通过以下命令安装所有依赖：

```bash
pip install -r requirements.txt
```

## 技术实现

GUI 版本使用以下技术实现：

1. **PySide6**：用于创建主窗口和 GUI 组件
2. **Qt WebEngine**：用于内嵌显示 Web UI
3. **多线程**：Flask 服务器在后台线程中运行
4. **信号槽机制**：用于线程间通信

## 已知限制

1. 启动时间可能比纯 Web 版本稍长，因为需要初始化 Qt 环境
2. 内存占用可能比纯 Web 版本稍高
3. 在某些 Linux 系统上可能需要额外配置才能正常显示

## 故障排除

### 1. GUI 窗口无法显示

确保已安装所有依赖：
```bash
pip install -r requirements.txt
```

### 2. 页面加载失败

检查 Flask 服务器是否正常启动，查看控制台输出。

### 3. JavaScript 功能异常

确保在 WebEngine 设置中启用了 JavaScript：
```python
settings = self.web_view.settings()
settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
```

## 开发说明

GUI 相关代码位于 [cabm_gui.py](cabm_gui.py) 文件中，主要包括：

1. `FlaskThread` 类：在后台线程中运行 Flask 服务器
2. `CABMWindow` 类：主窗口类，包含 Web 视图
3. `main()` 函数：程序入口点

如需修改 GUI 行为，可以直接编辑 [cabm_gui.py](cabm_gui.py) 文件。