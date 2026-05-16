# ai-browser

[English](README.md)

专为 AI 智能体设计的浏览器自动化 CLI 工具。采用客户端-守护进程架构，守护进程管理浏览器生命周期，无状态的 CLI 客户端通过 Unix 域套接字上的 JSON-RPC 协议发送命令。

## 设计目标

- **AI 智能体优先**：CLI 接口输出结构化 JSON，面向程序化调用而非人工交互
- **无障碍树驱动**：通过无障碍树快照和 ref 标识定位页面元素，AI 智能体无需视觉解析即可理解并操作页面。快照自动优化（generic 节点折叠、不可见文本移除、包装器剥离），减少 token 消耗
- **会话隔离**：每个会话运行独立的守护进程，拥有独立的浏览器实例、Unix 套接字和可选的持久化用户数据目录
- **默认隐身**：基于 cloakbrowser（Playwright 隐身 Chromium 启动器），规避机器人检测
- **拟人交互**：可选的拟人化模式，支持可配置的预设方案，模拟自然的鼠标移动和输入模式

## 使用场景

- AI 智能体自主浏览网页（信息检索、表单填写、数据提取）
- AI 驱动的自动化 QA 和端到端测试
- JavaScript 渲染页面的网页抓取
- 无头环境下的浏览器任务自动化
- 需要独立浏览器上下文的多会话工作流（如多账号测试）

## 架构

```
┌─────────────┐  Unix Socket   ┌──────────────────────────────────┐
│  CLI 客户端  │ ◄─JSON-RPC───► │          守护进程                  │
│  (无状态)    │                │                                  │
│             │                │  JSON-RPC 服务器                   │
│  ai-browser open   │                │    └─► 浏览器管理器                 │
│  ai-browser click  │                │         └─► Playwright 浏览器      │
│  ai-browser snap   │                │              └─► CDP 会话          │
│  ...        │                │                  └─► AX 无障碍树    │
└─────────────┘                └──────────────────────────────────┘
```

## 安装

需要 Python 3.13+。

```bash
# 克隆仓库
git clone https://github.com/reacerland/ai-browser.git
cd ai-browser

# 使用 uv 安装（推荐）
uv sync

# 或使用 pip 安装
pip install -e .
```

## 使用方法

`ai-browser` 命令也可使用简写 `ai-browser`。

### 开始浏览

```bash
# 打开 URL（自动启动守护进程和浏览器）
ai-browser open https://example.com

# 有头模式（显示浏览器窗口）
ai-browser open https://example.com --headed

# 命名会话（持久化配置保存在 ~/.ab/work/chrome-data/）
ai-browser open https://example.com --session work

# 启用拟人化交互
ai-browser open https://example.com --humanize --human-preset careful
```

### 页面交互

```bash
# 获取无障碍树快照以了解页面结构
ai-browser snapshot
ai-browser snapshot --compact              # 精简视图（仅保留 ref 及其祖先）
ai-browser snapshot --interactive          # 仅显示可交互元素（最大程度节省 token）
ai-browser snapshot --depth 3              # 限制树深度
ai-browser snapshot --selector "nav a"     # 按 CSS 选择器限定范围
ai-browser snapshot --interactive --compact # 最小化输出

# 按定位器查找元素
ai-browser find role button --name "Submit"
ai-browser find text "Sign in"
ai-browser find label "Email"

# 使用快照中的 ref 标识操作元素
ai-browser click A1                        # 点击 ref 为 A1 的元素
ai-browser type A2 "hello@example.com"     # 在元素中输入文本
ai-browser type A2 "text" --clear          # 清空字段后输入
ai-browser fill A3 "value"                 # 替换元素内容
ai-browser hover A4                        # 悬停在元素上
ai-browser dblclick A5                     # 双击元素
ai-browser drag A6 A7                      # 将 A6 拖拽到 A7

# 表单交互
ai-browser select A8 "option_value"        # 选择下拉选项
ai-browser check A9                        # 勾选复选框
ai-browser uncheck A9                      # 取消勾选复选框
ai-browser upload A10 /path/to/file        # 上传文件

# 页面导航
ai-browser scroll down --amount 500        # 滚动页面
ai-browser scroll-into-view A11            # 滚动至元素可见
ai-browser back                            # 后退
ai-browser forward                         # 前进
ai-browser reload                          # 刷新页面
ai-browser press Enter                     # 按下键盘按键
```

### 获取页面和元素信息

```bash
ai-browser get url                         # 当前页面 URL
ai-browser get title                       # 页面标题
ai-browser get text A1                     # 元素文本内容
ai-browser get html A1                     # 元素内部 HTML
ai-browser get value A1                    # 表单元素值
ai-browser get attr A1 --name href         # 元素属性
ai-browser get box A1                      # 元素边界框

ai-browser is visible A1                   # 元素是否可见
ai-browser is enabled A1                   # 元素是否可用
ai-browser is checked A1                   # 复选框是否已勾选

ai-browser count "div.card"                # 按 CSS 选择器统计元素数量
ai-browser screenshot                      # 截图
ai-browser screenshot -o /tmp/page.png     # 保存截图到文件
ai-browser eval "document.title"           # 执行 JavaScript
ai-browser download A1 /tmp/file.zip       # 点击元素下载文件
```

### 会话管理

```bash
ai-browser ping                            # 检查守护进程是否运行
ai-browser close                           # 关闭默认会话
ai-browser close --session work            # 关闭命名会话
```

### 多会话

```bash
# 每个命名会话独立运行，拥有各自的浏览器
ai-browser open https://site-a.com --session alpha
ai-browser open https://site-b.com --session beta

ai-browser snapshot --session alpha        # 操作 alpha 会话
ai-browser snapshot --session beta         # 操作 beta 会话

ai-browser close --session alpha           # 关闭 alpha，保留 beta
```

## 命令参考

| 命令 | 说明 |
|------|------|
| `open <url>` | 启动守护进程和浏览器，导航到 URL |
| `close` | 关闭浏览器并停止守护进程 |
| `snapshot` | 获取无障碍树快照（支持 `--compact`、`--interactive`、`--depth`、`--selector`） |
| `find <locator> <value>` | 按 role/text/label 等查找元素 |
| `click <ref>` | 点击元素 |
| `type <ref> <text>` | 输入文本 |
| `fill <ref> <value>` | 替换元素内容 |
| `scroll <up\|down>` | 滚动页面 |
| `scroll-into-view <ref>` | 滚动至元素可见 |
| `hover <ref>` | 悬停在元素上 |
| `dblclick <ref>` | 双击元素 |
| `drag <src> <dst>` | 拖拽元素到目标位置 |
| `select <ref> <value>` | 选择下拉选项 |
| `check <ref>` | 勾选复选框 |
| `uncheck <ref>` | 取消勾选复选框 |
| `upload <ref> <files>` | 上传文件 |
| `download <ref> <path>` | 点击元素下载文件 |
| `press <key>` | 按下键盘按键 |
| `get <what> [ref]` | 获取元素属性或页面信息 |
| `is <what> <ref>` | 检查元素状态 |
| `count <selector>` | 统计匹配元素数量 |
| `screenshot` | 截图 |
| `eval <expression>` | 执行 JavaScript |
| `back` | 后退 |
| `forward` | 前进 |
| `reload` | 刷新页面 |
| `wait <target>` | 等待元素或时间 |
| `ping` | 检查守护进程健康状态 |

## 输出格式

所有命令输出 JSON 到 stdout：

```json
{"status": "ok", "data": {"title": "Example Page"}}
```

错误响应：

```json
{"status": "error", "error": {"code": -32000, "message": "Daemon not running. Use 'ai-browser open' first."}}
```

## 开发

```bash
# 安装开发依赖
uv sync --extra dev

# 运行测试
uv run pytest

# 运行端到端测试
uv run pytest tests/e2e/
```

## 许可证

本项目基于 MIT 许可证开源。详见 [LICENSE](LICENSE) 文件。
