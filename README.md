# BoxClaw

> 原「抖音多开矩阵」by 尖叫（Todliu）（仅供学习参考）
<img width="1280" height="832" alt="image" src="https://github.com/user-attachments/assets/448f22c2-cf65-4b73-9f87-71157b458049" />

**正式入口为单文件** [`boxclaw_main.py`](boxclaw_main.py)：Fluent Design（qfluentwidgets）外壳 + **抖音多账号 WebEngine 沙盒** + **OpenClaw 网关**（子进程、底部终端、内嵌 Web 控制台）在同一进程内。

---

## 功能与模块对照（代码审查摘要）

以下均实现在 `boxclaw_main.py` 中，职责边界如下。

| 模块 | 类型 | 职责 |
|------|------|------|
| **配置 IO** | 函数 | `read/write_openclaw_config_file` 读写侧栏 JSON；`read/write_main_openclaw_config` 读写 OpenClaw 主配置；`resolve_openclaw_main_config_path` 解析路径（含 `OPENCLAW_CONFIG_PATH`）。 |
| **模型写入** | `apply_openclaw_model_api_to_config` | 在完整 `openclaw.json` 上就地更新 `agents.defaults.model` 与 `models.providers`，校验主型号 `provider/model` 前缀与 Provider ID 一致。 |
| **预设表** | `OPENCLAW_PROVIDER_PRESETS` / `OPENCLAW_MODEL_PRESETS` | 服务商与型号快捷项；`_detect_openclaw_provider_preset_key` 从现有配置反推选中项。 |
| **控制台探测** | `discover_openclaw_console_url` | 从网关日志片段、主/侧栏配置、环境变量 URL 中收集候选地址，HTTP 拉取正文前缀，**排除 Canvas 演示页**，按关键词与路径打分，选出主聊天网关 UI。 |
| **OpenClawProcessManager** | `QObject` | `openclaw gateway run` 子进程、stdout 线程、`gateway.log` tail、端口占用时的「接管」逻辑、环境检测、`gateway stop` + 重启、`doctor`、stdin 注入命令、一键安装（macOS Homebrew / Windows winget + `npm i -g openclaw`）。 |
| **DouyinAutomationCore** | `QObject` | 每账号独立 `QWebEngineProfile`（`~/Douyin_Profiles/<名>/`）、注入 stealth 脚本、单账号挂载到 `matrix_container`、缓存清理与退出时释放 WebView。 |
| **MatrixPage** | `BoxClawPage` | 账号下拉、增删、导航按钮、将当前账号 WebView 挂到 `matrix_container`。 |
| **SettingsPage** | `BoxClawPage` | 侧栏 `gateway_autostart`；服务商/主型号单选 + 自定义；保存时写主配置、**`openclaw config validate`**、失败回滚备份；主型号为空则只存侧栏项并仍可重启网关。 |
| **HomeWelcomePage** | `BoxClawPage` | 只读仪表盘卡片（本地配置快照）。 |
| **OpenClawWebPage** | `BoxClawPage` | 内嵌 `QWebEngineView`，默认 `OPENCLAW_PANEL_URL`；「抓取网关页面」后台线程调用 `discover_openclaw_console_url`。 |
| **GatewayTerminalDock** | `QWidget` | 底部开关与日志、展开/收起、一键环境、启动/重启/自动修复、命令行输入。 |
| **BoxClawWindow** | `SplitFluentWindow` / `MSFluentWindow` | 堆叠页 + 右侧列 + 底部终端槽、暗夜紫 QSS、侧栏品牌、导航、托盘、`gateway_autostart` 延迟启动网关。 |

**线程与信号**：`_CmdLogThread` / `_GatewayStdoutReader` / `_LogTailThread` / `_InstallWorkerThread` / `_DiscoverOpenClawPanelWorker` 均通过 `Signal` 回主线程更新 UI 或日志。

---

## 配置文件

| 文件 | 用途 |
|------|------|
| `~/.openclaw/config.json` | BoxClaw 侧栏扩展：当前仅 **`gateway_autostart`**（是否随应用启动网关）。 |
| `~/.openclaw/openclaw.json`（或 `OPENCLAW_CONFIG_PATH`） | OpenClaw 官方主配置：模型、网关端口、`models.providers` 等。 |

保存设置时：若主型号为空，**不修改** `openclaw.json`，仅写入侧栏 JSON 并触发网关重启（若已安装 CLI）。

---

## 环境变量（常用）

| 变量 | 含义 |
|------|------|
| `OPENCLAW_CONFIG_PATH` | 覆盖主配置文件路径。 |
| `OPENCLAW_PORT` | 健康检查/探测默认端口（默认 `18789`）。 |
| `OPENCLAW_URL` | 探测候选 URL 之一。 |
| `OPENCLAW_PANEL_URL` | 内嵌龙虾控制台 WebView 初始地址（默认与 `OPENCLAW_URL` 一致）。 |

---

## 运行与构建

```bash
cd /path/to/boxclaw
python3 -m pip install -r requirements.txt
python3 boxclaw_main.py
```

- macOS 可双击 **`一键启动.command`** / **`抖音多开助手.command`**（需 `chmod +x`）。
- **Windows 便携包**：`py -m PyInstaller --noconfirm --clean windows_build.spec`（需整目录保留 QtWebEngine 等文件）。

### 启动顺序要点（`main()`）

- `QApplication` 之前：`AA_ShareOpenGLContexts`（与 QtWebEngine 共存）。
- macOS：`QTWEBENGINE_CHROMIUM_FLAGS` 默认 `--disable-background-timer-throttling`（可按需调整）。
- `setQuitOnLastWindowClosed(False)`：关闭窗口时默认隐藏（`closeEvent`），托盘仍可驻留。

---

## 数据目录

| 平台 | 抖音账号 Profile |
|------|------------------|
| macOS / Linux | `~/Douyin_Profiles/<目录名>/` |
| Windows | `%USERPROFILE%\Douyin_Profiles\` |

---

## `boxclaw/` 目录说明

仓库内另有 Python 包 [`boxclaw/`](boxclaw/)（`main_window.py`、各 `pages/*`），为**另一套独立壳**示例（非 `boxclaw_main.py` 引用）。**当前文档与推荐入口均以根目录 `boxclaw_main.py` 为准**。

---

## 技术栈

PySide6 / QtWebEngine · PySide6-Fluent-Widgets（`qfluentwidgets`）

---

## 许可证与免责声明

[MIT License](LICENSE)。仅供学习研究，请遵守平台规则与法律法规。
