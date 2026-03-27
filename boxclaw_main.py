#!/usr/bin/env python3
# coding: utf-8
"""
BoxClaw — 本地 AI 网关与自媒体控制台（Fluent Design / qfluentwidgets）

本文件同时包含：Fluent 主壳、本地网关控制台、抖音矩阵多账号沙盒（DouyinAutomationCore，可挂载至 matrix_container）。
macOS 使用 SplitFluentWindow（侧栏树形导航）；Windows/Linux 使用 MSFluentWindow（顶栏导航）。

依赖：python3 -m pip install -r requirements.txt
"""

from __future__ import annotations

import copy
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, NamedTuple, Optional, Union

PROFILES_BASE_DIR = Path.home() / "Douyin_Profiles"
START_URL = "https://creator.douyin.com/"
MAX_ACCOUNTS = 50
APP_NAME = "BoxClaw🦞抖音矩阵控制台—by尖叫"
APP_SUBTITLE = "by \u5c16\u53eb\uff08\u4ec5\u4f9b\u5b66\u4e60\u53c2\u8003\uff09"
# BoxClaw 侧栏小项：仅 gateway_autostart（与 OpenClaw 主配置 openclaw.json 分离）
BOXCLAW_GATEWAY_SIDECAR_PATH = Path.home() / ".openclaw" / "config.json"
# 兼容旧变量名（等同侧栏文件）
OPENCLAW_CONFIG_PATH = BOXCLAW_GATEWAY_SIDECAR_PATH
OPENCLAW_HEALTH_PORT = int(os.environ.get("OPENCLAW_PORT", "18789"))
OPENCLAW_HEALTH_URL = f"http://127.0.0.1:{OPENCLAW_HEALTH_PORT}/health"
# OpenClaw 内置 Web 控制台（可用 OPENCLAW_URL 覆盖完整地址）
OPENCLAW_URL = os.environ.get("OPENCLAW_URL", "http://127.0.0.1:18789")
# 内嵌龙虾控制台 WebView 默认与主网关一致（避免误开 8000 上的 Canvas 演示页）
OPENCLAW_PANEL_URL = os.environ.get("OPENCLAW_PANEL_URL", OPENCLAW_URL)


def read_openclaw_config_file() -> dict[str, Any]:
    """读取侧栏 config.json（仅含 gateway_autostart 等 BoxClaw 扩展字段）。"""
    if not BOXCLAW_GATEWAY_SIDECAR_PATH.is_file():
        return {}
    try:
        return json.loads(BOXCLAW_GATEWAY_SIDECAR_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_openclaw_config_file(data: dict[str, Any]) -> None:
    BOXCLAW_GATEWAY_SIDECAR_PATH.parent.mkdir(parents=True, exist_ok=True)
    BOXCLAW_GATEWAY_SIDECAR_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def resolve_openclaw_main_config_path() -> Path:
    """OpenClaw 主配置（模型、API、gateway.port 等）。与 CLI `openclaw config file` 一致。"""
    env = (os.environ.get("OPENCLAW_CONFIG_PATH") or "").strip()
    if env:
        return Path(env).expanduser()
    return Path.home() / ".openclaw" / "openclaw.json"


def read_main_openclaw_config() -> dict[str, Any]:
    path = resolve_openclaw_main_config_path()
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_main_openclaw_config(data: dict[str, Any]) -> None:
    path = resolve_openclaw_main_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _resolve_openclaw_cli_base() -> list[str]:
    exe = shutil.which("openclaw")
    if exe:
        return [exe]
    return [sys.executable, "-m", "openclaw"]


def run_openclaw_config_validate() -> tuple[bool, str]:
    """调用 `openclaw config validate`，失败时返回 stderr/stdout 摘要。无 CLI 时跳过校验。"""
    cmd = _resolve_openclaw_cli_base() + ["config", "validate"]
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=90,
            env=os.environ.copy(),
        )
    except (FileNotFoundError, OSError) as e:
        return True, f"(跳过校验: {e})"
    out = (r.stdout or "") + "\n" + (r.stderr or "")
    return r.returncode == 0, out.strip()[:1200]


def apply_openclaw_model_api_to_config(
    base: dict[str, Any],
    *,
    provider_id: str,
    base_url: str,
    api_key_plain: Optional[str],
    primary_model: str,
    fallbacks: list[str],
    api_interface: str = "openai-completions",
) -> dict[str, Any]:
    """在完整 openclaw.json 上就地更新模型与 Provider API，保留其余键。"""
    cfg = copy.deepcopy(base)
    pid = (provider_id or "").strip() or "default"
    primary_model = (primary_model or "").strip()
    if not primary_model:
        raise ValueError("主模型 ID 不能为空（例如 volcengine/minimax-m2.5）。")

    prefix = primary_model.split("/", 1)[0] if "/" in primary_model else ""
    if prefix and prefix != pid:
        raise ValueError(
            f"主模型前缀「{prefix}」与 Provider ID「{pid}」不一致，请统一（模型 ID 形如 provider/model）。"
        )

    cfg.setdefault("agents", {}).setdefault("defaults", {})
    ad = cfg["agents"]["defaults"]
    ad.setdefault("model", {})
    ad["model"]["primary"] = primary_model
    ad["model"]["fallbacks"] = list(fallbacks)

    cfg.setdefault("models", {})
    models_root = cfg["models"]
    models_root.setdefault("mode", "replace")
    models_root.setdefault("providers", {})
    prov = models_root["providers"].setdefault(pid, {})
    if (base_url or "").strip():
        prov["baseUrl"] = base_url.strip()
    if api_key_plain is not None and api_key_plain.strip():
        prov["apiKey"] = api_key_plain.strip()
    prov["api"] = (api_interface or "openai-completions").strip()
    # 保留原有 models 列表等子字段
    return cfg


class OpenClawProviderPreset(NamedTuple):
    key: str
    label: str
    provider_id: str
    base_url: str
    api: str


# 与 OpenClaw 中 provider/model 命名一致；自定义由用户填写
OPENCLAW_PROVIDER_PRESETS: tuple[OpenClawProviderPreset, ...] = (
    OpenClawProviderPreset(
        "volcengine",
        "火山引擎",
        "volcengine",
        "https://ark.cn-beijing.volces.com/api/coding/v3",
        "openai-completions",
    ),
    OpenClawProviderPreset(
        "openai",
        "OpenAI 官方",
        "openai",
        "https://api.openai.com/v1",
        "openai-completions",
    ),
    OpenClawProviderPreset(
        "deepseek",
        "DeepSeek",
        "deepseek",
        "https://api.deepseek.com/v1",
        "openai-completions",
    ),
    OpenClawProviderPreset(
        "zhipu",
        "智谱 AI",
        "zhipu",
        "https://open.bigmodel.cn/api/paas/v4",
        "openai-completions",
    ),
    OpenClawProviderPreset(
        "aliyun",
        "阿里云百炼",
        "aliyun",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "openai-completions",
    ),
    OpenClawProviderPreset(
        "siliconflow",
        "硅基流动",
        "siliconflow",
        "https://api.siliconflow.cn/v1",
        "openai-completions",
    ),
    OpenClawProviderPreset(
        "ollama",
        "Ollama (本地)",
        "ollama",
        "http://127.0.0.1:11434/v1",
        "openai-completions",
    ),
    OpenClawProviderPreset("custom", "自定义", "", "", "openai-completions"),
)

# 服务商 key -> (展示名, 完整 model id)
OPENCLAW_MODEL_PRESETS: dict[str, tuple[tuple[str, str], ...]] = {
    "volcengine": (
        ("MiniMax M2.5", "volcengine/minimax-m2.5"),
        ("Kimi K2.5", "volcengine/kimi-k2.5"),
    ),
    "openai": (
        ("GPT-4o", "openai/gpt-4o"),
        ("GPT-4o mini", "openai/gpt-4o-mini"),
    ),
    "deepseek": (("DeepSeek Chat", "deepseek/deepseek-chat"),),
    "zhipu": (("GLM-4", "zhipu/glm-4"),),
    "aliyun": (("通义千问 Max", "aliyun/qwen-max"),),
    "siliconflow": (("DeepSeek-V3 示例", "siliconflow/deepseek-ai/DeepSeek-V3"),),
    "ollama": (("llama3 示例", "ollama/llama3"),),
    "custom": (),
}


def _openclaw_provider_preset_by_key(key: str) -> OpenClawProviderPreset | None:
    for p in OPENCLAW_PROVIDER_PRESETS:
        if p.key == key:
            return p
    return None


def _detect_openclaw_provider_preset_key(
    provider_id: str, base_url: str
) -> str:
    pid = (provider_id or "").strip()
    bu = (base_url or "").strip().rstrip("/")
    best = "custom"
    for p in OPENCLAW_PROVIDER_PRESETS:
        if p.key == "custom":
            continue
        if p.provider_id != pid:
            continue
        pb = p.base_url.strip().rstrip("/")
        if not bu:
            best = p.key
            break
        if pb and (bu == pb or bu.startswith(pb) or pb in bu):
            return p.key
        if not pb:
            best = p.key
    if best != "custom":
        return best
    for p in OPENCLAW_PROVIDER_PRESETS:
        if p.key != "custom" and p.provider_id == pid:
            return p.key
    return "custom"


# 从网关 stdout / gateway.log / config 中解析控制台地址并做 HTTP 可达性探测
_URL_IN_TEXT_RE = re.compile(r"https?://[^\s\)\]\>\"\'\`]+", re.I)


def _normalize_url_fragment(s: str) -> str:
    return s.rstrip(".,;)")


def _collect_ports_from_openclaw_config(cfg: dict[str, Any]) -> list[int]:
    out: list[int] = []

    def walk(o: Any) -> None:
        if isinstance(o, dict):
            for k, v in o.items():
                lk = str(k).lower()
                if lk in ("port", "httpport", "listen", "panelport", "uiport", "gatewayport"):
                    if isinstance(v, int) and 1 <= v <= 65535:
                        out.append(v)
                    elif isinstance(v, str) and v.isdigit():
                        p = int(v)
                        if 1 <= p <= 65535:
                            out.append(p)
                walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)

    walk(cfg)
    seen: set[int] = set()
    uniq: list[int] = []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def _http_get_body_prefix(
    url: str, timeout: float = 2.2, max_bytes: int = 56_000
) -> Optional[str]:
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 BoxClawOpenClawProbe/1"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if not (200 <= int(r.getcode()) < 400):
                return None
            data = r.read(max_bytes)
        return data.decode("utf-8", errors="replace")
    except Exception:
        return None


def _body_is_openclaw_canvas_demo(body: str) -> bool:
    """OpenClaw 内置 Canvas 交互演示页，非主聊天网关。"""
    b = body.lower()
    if "openclaw canvas" in b:
        return True
    if "interactive test page" in b and "auto-reload" in b:
        return True
    if "bridge: missing" in b and "ios=no" in b and "android=no" in b:
        return True
    return False


def _main_chat_body_score(body: str) -> int:
    b = body.lower()
    s = 0
    for kw, w in (
        ("chat", 28),
        ("conversation", 18),
        ("messages", 16),
        ("assistant", 12),
        ("prompt", 8),
        ("gateway", 6),
        ("openclaw", 4),
    ):
        if kw in b:
            s += w
    if all(x in b for x in ("dalek", "photo", "hello")):
        s -= 45
    return s


def _url_path_preference(url: str) -> int:
    low = url.lower()
    s = 0
    if "canvas" in low:
        s -= 120
    if "/chat" in low or low.rstrip("/").endswith("/chat"):
        s += 45
    if "/health" in low:
        s -= 80
    if "/api" in low:
        s -= 25
    return s


def _variants_for_log_url(u: str) -> list[str]:
    u = u.strip()
    if not u:
        return []
    out_v: list[str] = [u]
    if "/health" in u:
        base = u.split("/health", 1)[0].rstrip("/")
        if base:
            out_v.append(base + "/")
    else:
        out_v.append(u.rstrip("/") + "/")
    s2: set[str] = set()
    res: list[str] = []
    for x in out_v:
        if x not in s2:
            s2.add(x)
            res.append(x)
    return res


def _ordered_probe_ports(cfg: dict[str, Any]) -> list[int]:
    extra = _collect_ports_from_openclaw_config(cfg)
    ordered: list[int] = []
    for p in (OPENCLAW_HEALTH_PORT, *extra, 18789, 8000, 3000, 5173):
        if p not in ordered and 1 <= p <= 65535:
            ordered.append(p)
    return ordered


def _probe_paths_for_port() -> list[str]:
    return ["/", "/chat", "/app", "/ui", "/panel", "/tui"]


def discover_openclaw_console_url(
    manager: Optional["OpenClawProcessManager"] = None,
) -> Optional[str]:
    """识别主聊天/网关 Web UI，排除 OpenClaw Canvas 等演示页。"""
    cfg = read_main_openclaw_config()
    text_parts: list[str] = [
        json.dumps(cfg, ensure_ascii=False),
        json.dumps(read_openclaw_config_file(), ensure_ascii=False),
    ]
    if manager is not None:
        text_parts.insert(0, manager.get_gateway_log_snippet())
    blob = "\n".join(text_parts)

    raw_urls: list[str] = []
    for m in _URL_IN_TEXT_RE.finditer(blob):
        raw_urls.append(_normalize_url_fragment(m.group(0)))

    def log_url_prior(u: str) -> int:
        low = u.lower()
        s = 0
        if "127.0.0.1" in low or "localhost" in low:
            s += 3
        if any(x in low for x in ("chat", "message", "assistant")):
            s += 8
        if "canvas" in low:
            s -= 10
        if any(x in low for x in ("panel", "ui", "dashboard", "console")):
            s += 4
        if "/health" in low:
            s -= 4
        if str(OPENCLAW_HEALTH_PORT) in low or ":18789" in low:
            s += 5
        return s

    raw_urls.sort(key=log_url_prior, reverse=True)

    candidates: list[str] = []
    seen: set[str] = set()

    def add_url(u: str) -> None:
        u = u.strip()
        if not u:
            return
        if not (u.startswith("http://") or u.startswith("https://")):
            return
        key = u.rstrip("/").lower()
        if key in seen:
            return
        seen.add(key)
        candidates.append(u if u.endswith("/") else u + "/")

    for u in raw_urls:
        for v in _variants_for_log_url(u):
            add_url(v)

    for env in (OPENCLAW_URL, OPENCLAW_PANEL_URL):
        env = env.strip()
        if env:
            add_url(env.rstrip("/") + "/")

    for port in _ordered_probe_ports(cfg):
        for path in _probe_paths_for_port():
            add_url(f"http://127.0.0.1:{port}{path}")

    best: Optional[tuple[int, str]] = None
    for url in candidates:
        body = _http_get_body_prefix(url)
        if body is None:
            continue
        if _body_is_openclaw_canvas_demo(body):
            continue
        score = (
            _main_chat_body_score(body)
            + _url_path_preference(url)
            + log_url_prior(url) // 6
        )
        if best is None or score > best[0]:
            best = (score, url)

    if best is not None:
        u = best[1]
        return u if u.endswith("/") else u + "/"

    return None


def sanitize_account_name(name: str) -> str:
    if name is None:
        return ""
    name = str(name).strip()
    if not name:
        return ""
    name = re.sub(r"[\/\\:\*\?\"<>\|\x00-\x1f]+", "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


from PySide6.QtCore import (
    QCoreApplication,
    QObject,
    Qt,
    QThread,
    QSize,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QFont,
    QFontDatabase,
    QIcon,
    QPainter,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtWebEngineCore import (
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineScript,
    QWebEngineSettings,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from qfluentwidgets import (
    BodyLabel,
    ComboBox,
    InfoBar,
    InfoBarPosition,
    NavigationItemPosition,
    PrimaryPushButton,
    PushButton,
    MSFluentWindow,
    SplitFluentWindow,
    SubtitleLabel,
    SwitchButton,
    Theme,
    TitleLabel,
    TransparentToolButton,
    FluentIcon as FIF,
    qrouter,
    setFont,
    setTheme,
)
from qfluentwidgets.components.navigation import NavigationInterface


def emoji_navigation_icon(emoji: str, size: int = 16) -> QIcon:
    """将 emoji 转为 QIcon。

    qfluentwidgets 对 str 会执行 ``QIcon(s)``，Qt 把字符串当作**图片路径**，不是 emoji，
    侧栏/子菜单图标会显示为空。此处用系统彩色字体把 emoji 画进位图再封装为图标。
    """
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHints(
        QPainter.RenderHint.TextAntialiasing | QPainter.RenderHint.SmoothPixmapTransform
    )
    font = QFont()
    fams = set(QFontDatabase.families())
    for name in (
        "Apple Color Emoji",
        "Segoe UI Emoji",
        "Noto Color Emoji",
        "Segoe UI Symbol",
    ):
        if name in fams:
            font.setFamily(name)
            break
    else:
        font.setStyleHint(QFont.StyleHint.SansSerif)
    font.setPixelSize(max(11, size - 3))
    p.setFont(font)
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, emoji)
    p.end()
    return QIcon(pm)


# macOS：SplitFluentWindow 毛玻璃侧栏；其他平台：MSFluentWindow 顶栏风格
_BaseMainWindow = SplitFluentWindow if sys.platform == "darwin" else MSFluentWindow


# ═══════════════════════════════════════════════════════════════
#  OpenClaw 守护进程（subprocess + 日志劫持）
# ═══════════════════════════════════════════════════════════════


class _CmdLogThread(QThread):
    line_ready = Signal(str)

    def __init__(self, cmd: Union[list[str], str], *, shell: bool = False) -> None:
        super().__init__()
        self._cmd = cmd
        self._shell = shell

    def run(self) -> None:
        try:
            p = subprocess.Popen(
                self._cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                shell=self._shell,
            )
            if p.stdout is None:
                self.line_ready.emit("[error] 无法读取命令输出")
                return
            for line in iter(p.stdout.readline, ""):
                if line == "" and p.poll() is not None:
                    break
                if line:
                    self.line_ready.emit(line.rstrip("\r\n"))
            p.wait()
            self.line_ready.emit(f"[exit] code={p.returncode}")
        except Exception as e:
            self.line_ready.emit(f"[error] {e}")


class _GatewayStdoutReader(QThread):
    """读取 gateway run 合并后的 stdout（含 stderr），结束时回传退出码与全文。"""

    line_ready = Signal(str)
    stream_closed = Signal(int, str)

    def __init__(self, stream, proc: subprocess.Popen) -> None:
        super().__init__()
        self._stream = stream
        self._proc = proc
        self._lines: list[str] = []

    def run(self) -> None:
        try:
            for line in iter(self._stream.readline, ""):
                if not line:
                    break
                text = str(line).rstrip("\r\n")
                self._lines.append(text)
                if text:
                    self.line_ready.emit(text)
        finally:
            try:
                self._stream.close()
            except Exception:
                pass
        try:
            if self._proc.poll() is None:
                self._proc.wait(timeout=30)
        except Exception:
            pass
        rc = self._proc.returncode
        full = "\n".join(self._lines)
        self.stream_closed.emit(rc if rc is not None else -1, full)


class _LogTailThread(QThread):
    """对 ~/.openclaw/logs 下日志文件做 tail -f 式轮询。"""

    line_ready = Signal(str)

    def __init__(self, path: Path) -> None:
        super().__init__()
        self._path = path
        self._stop = False

    def run(self) -> None:
        try:
            with open(self._path, encoding="utf-8", errors="replace") as f:
                f.seek(0, 2)
                while not self._stop:
                    line = f.readline()
                    if line:
                        self.line_ready.emit(line.rstrip("\r\n"))
                    else:
                        self.msleep(280)
        except OSError:
            pass

    def stop_tail(self) -> None:
        self._stop = True


class _InstallWorkerThread(QThread):
    """后台执行环境安装，避免阻塞 Qt 主线程。"""

    def __init__(self, mgr: "OpenClawProcessManager") -> None:
        super().__init__(mgr)
        self._mgr = mgr

    def run(self) -> None:
        self._mgr._install_worker()


class OpenClawProcessManager(QObject):
    """使用 subprocess.Popen 管理 OpenClaw；stdout/stderr 经 QThread 读取并 log_ready 输出。"""

    log_ready = Signal(str)
    state_changed = Signal(bool)

    OPENCLAW_START_CMD: list[str] = ["openclaw", "gateway", "run"]

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.os_type = platform.system()
        self._proc: subprocess.Popen | None = None
        self._gateway_reader: Optional[_GatewayStdoutReader] = None
        self._log_tail_thread: Optional[_LogTailThread] = None
        self._adoption_handled = False
        self._running_state_emitted = False
        self._startup_buf: list[str] = []
        self._cmd_threads: list[QThread] = []
        self._env_checked = False
        self._install_thread: Optional[_InstallWorkerThread] = None

    def check_environment(self) -> bool:
        """检测 Node.js / Git 基础依赖。"""
        missing = []
        node_version_tuple: tuple[int, int, int] | None = None
        try:
            out = subprocess.run(["node", "-v"], capture_output=True, text=True, check=True)
            ver_text = (out.stdout or out.stderr or "").strip()
            m = re.search(r"v?(\d+)\.(\d+)\.(\d+)", ver_text)
            if not m:
                missing.append("Node.js")
            else:
                node_version_tuple = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
                if node_version_tuple < (22, 12, 0):
                    missing.append("Node.js")
        except Exception:
            missing.append("Node.js")
        try:
            subprocess.run(["git", "--version"], capture_output=True, text=True, check=True)
        except Exception:
            missing.append("Git")
        if missing:
            self.log_ready.emit(
                "[环境异常] 需安装 Node.js >= 22.12.0 及 Git，请检查系统环境！"
            )
            return False
        self.log_ready.emit(f"[Env] 检测通过 os={self.os_type} node={node_version_tuple}")
        return True

    def _resolve_openclaw_start_cmd(self) -> list[str] | None:
        # 打包后优先直接使用内置命令入口；若命令不可用再降级到当前 Python 模块启动
        exe = shutil.which("openclaw")
        if exe:
            return [exe, "gateway", "run"]
        return [sys.executable, "-m", "openclaw", "gateway", "run"]

    @staticmethod
    def _looks_like_adoption(text: str) -> bool:
        return bool(
            re.search(
                r"(?i)(gateway\s+already\s+running|already\s+in\s+use|"
                r"address\s+already\s+in\s+use|port\s+is\s+already\s+in\s+use|"
                r"eaddrinuse)",
                text,
            )
        )

    def _try_detect_adoption(self, text: str) -> Optional[str]:
        """若输出表明网关已在跑，返回 PID 字符串；无法解析时返回 '?'；否则 None。"""
        if not self._looks_like_adoption(text):
            return None
        for pat in (
            r"(?i)(?:pid|PID)[:\s#=-]*(\d+)",
            r"(?i)process\s+(?:id\s+)?#?\s*(\d+)",
            r"(?i)\(pid\s*(\d+)\)",
        ):
            m = re.search(pat, text)
            if m:
                return m.group(1)
        return "?"

    def _resolve_openclaw_log_file(self) -> Optional[Path]:
        base = Path.home() / ".openclaw" / "logs"
        if not base.is_dir():
            return None
        gw = base / "gateway.log"
        if gw.is_file():
            return gw
        logs = [p for p in base.glob("*.log") if p.is_file()]
        if not logs:
            return None
        return max(logs, key=lambda p: p.stat().st_mtime)

    def get_gateway_log_snippet(self, max_tail: int = 96_000) -> str:
        """供控制台地址探测：网关启动缓冲 + gateway.log 尾部。"""
        parts: list[str] = []
        if self._startup_buf:
            parts.append("\n".join(self._startup_buf))
        path = self._resolve_openclaw_log_file()
        if path is not None and path.is_file():
            try:
                data = path.read_text(encoding="utf-8", errors="replace")
                parts.append(data[-max_tail:])
            except OSError:
                pass
        return "\n".join(parts)

    def _stop_log_tail(self) -> None:
        if self._log_tail_thread is None:
            return
        try:
            self._log_tail_thread.stop_tail()
            if self._log_tail_thread.isRunning():
                self._log_tail_thread.wait(3000)
        except Exception:
            pass
        self._log_tail_thread = None

    def _start_log_tail(self) -> None:
        self._stop_log_tail()
        path = self._resolve_openclaw_log_file()
        if path is None:
            if self._adoption_handled:
                self.log_ready.emit("[BoxClaw 🦞] 已接管进程状态")
            return
        self.log_ready.emit(f"[BoxClaw 🦞] 旁路追踪日志: {path}")
        self._log_tail_thread = _LogTailThread(path)
        self._log_tail_thread.line_ready.connect(
            lambda s: self.log_ready.emit(f"[tail] {s}")
        )
        self._log_tail_thread.start()

    def _finalize_adoption(self, pid_display: Optional[str]) -> None:
        if self._adoption_handled:
            return
        self._adoption_handled = True
        self._running_state_emitted = True
        pid_str = "?" if pid_display in (None, "?") else pid_display
        self.log_ready.emit(
            f"[BoxClaw 🦞] 检测到 OpenClaw 已在后台稳定运行 (PID: {pid_str})。"
            "已自动接管状态，无需重复启动！"
        )
        if self._proc is not None:
            if self._proc.poll() is None:
                try:
                    self._proc.terminate()
                    self._proc.wait(timeout=8)
                except Exception:
                    try:
                        self._proc.kill()
                        self._proc.wait(timeout=4)
                    except Exception:
                        pass
            self._proc = None
        self.state_changed.emit(True)
        self._start_log_tail()
        QTimer.singleShot(120, self._join_readers)

    def _on_gateway_line(self, line: str) -> None:
        self.log_ready.emit(line)
        if self._adoption_handled:
            return
        self._startup_buf.append(line)
        full = "\n".join(self._startup_buf)
        pid_disp = self._try_detect_adoption(full)
        if pid_disp is not None:
            self._finalize_adoption(pid_disp)

    def _on_gateway_stream_closed(self, rc: int, full: str) -> None:
        if self._adoption_handled:
            return
        if self._gateway_reader is None:
            return
        pid_disp = self._try_detect_adoption(full)
        if pid_disp is not None:
            self._finalize_adoption(pid_disp)
            return
        if self._proc is not None and self._proc.poll() is None:
            return
        if self._running_state_emitted:
            return
        if rc != 0:
            self.log_ready.emit(f"[OpenClaw] 网关进程异常退出，code={rc}")
            self._proc = None
            self._join_readers()
            self.state_changed.emit(False)

    def _on_gateway_startup_timeout(self) -> None:
        if self._adoption_handled:
            return
        if self._running_state_emitted:
            return
        if self._proc is None:
            return
        if self._proc.poll() is None:
            self._running_state_emitted = True
            self.state_changed.emit(True)
            self._start_log_tail()

    def start_service(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            self.log_ready.emit("[OpenClaw] 已在运行，跳过启动")
            return
        if self._running_state_emitted and self._proc is None and self._adoption_handled:
            self.log_ready.emit("[OpenClaw] 已吸附接管中，跳过重复启动")
            return
        if not self.check_environment():
            self.state_changed.emit(False)
            return
        self._env_checked = True
        self._stop_log_tail()
        self._join_readers()
        self._startup_buf = []
        self._adoption_handled = False
        self._running_state_emitted = False
        cmd = self._resolve_openclaw_start_cmd()
        if not cmd:
            self.state_changed.emit(False)
            return
        try:
            self.log_ready.emit(f"[OpenClaw] 执行: {' '.join(cmd)}")
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                cwd=str(Path.home()),
                env=os.environ.copy(),
                text=True,
                bufsize=1,
            )
            if self._proc.stdout is None:
                self.log_ready.emit("[OpenClaw] 无法读取网关输出")
                self._proc = None
                self.state_changed.emit(False)
                return
            self._gateway_reader = _GatewayStdoutReader(self._proc.stdout, self._proc)
            self._gateway_reader.line_ready.connect(self._on_gateway_line)
            self._gateway_reader.stream_closed.connect(self._on_gateway_stream_closed)
            self._gateway_reader.start()
            QTimer.singleShot(520, self._on_gateway_startup_timeout)
        except Exception as e:
            self.log_ready.emit(f"[OpenClaw] 启动失败: {e}")
            self._proc = None
            self.state_changed.emit(False)

    def _join_readers(self) -> None:
        if self._gateway_reader is None:
            return
        try:
            self._gateway_reader.line_ready.disconnect()
            self._gateway_reader.stream_closed.disconnect()
        except Exception:
            pass
        if self._gateway_reader.isRunning():
            self._gateway_reader.wait(5000)
        self._gateway_reader = None

    def stop_service(self) -> None:
        self._stop_log_tail()
        if self._proc is not None:
            try:
                self.log_ready.emit("[OpenClaw] 正在停止…")
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=12)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
                    self._proc.wait(timeout=5)
            except Exception as e:
                self.log_ready.emit(f"[OpenClaw] 停止异常: {e}")
            finally:
                self._proc = None
        self._join_readers()
        self._adoption_handled = False
        self._running_state_emitted = False
        self.state_changed.emit(False)

    def restart_service(self) -> None:
        self.stop_service()
        self.start_service()

    def run_command_and_log(
        self, cmd: Union[list[str], str], *, shell: bool = False
    ) -> None:
        if shell and isinstance(cmd, str):
            self.log_ready.emit(f"[cmd] {cmd}")
        else:
            self.log_ready.emit(f"[cmd] {' '.join(cmd) if isinstance(cmd, list) else cmd}")
        t = _CmdLogThread(cmd, shell=shell)
        t.line_ready.connect(self.log_ready.emit)

        def _done() -> None:
            try:
                self._cmd_threads.remove(t)
            except ValueError:
                pass

        t.finished.connect(_done)
        self._cmd_threads.append(t)
        t.start()

    def _resolve_openclaw_cli(self) -> list[str]:
        exe = shutil.which("openclaw")
        if exe:
            return [exe]
        return [sys.executable, "-m", "openclaw"]

    @staticmethod
    def _first_existing_path(candidates: list[Optional[str]]) -> Optional[str]:
        for p in candidates:
            if not p:
                continue
            try:
                path = Path(p)
                if path.is_file():
                    return str(path)
            except OSError:
                continue
        return None

    def _resolve_brew(self) -> Optional[str]:
        return self._first_existing_path(
            [
                shutil.which("brew"),
                "/opt/homebrew/bin/brew",
                "/usr/local/bin/brew",
            ]
        )

    def _resolve_winget(self) -> Optional[str]:
        return self._first_existing_path([shutil.which("winget")])

    def _resolve_npm(self) -> Optional[str]:
        candidates: list[Optional[str]] = [
            shutil.which("npm"),
            "/opt/homebrew/bin/npm",
            "/usr/local/bin/npm",
        ]
        if self.os_type == "Windows":
            pf = os.environ.get("ProgramFiles", r"C:\Program Files")
            pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
            candidates.extend(
                [
                    str(Path(pf) / "nodejs" / "npm.cmd"),
                    str(Path(pf86) / "nodejs" / "npm.cmd"),
                ]
            )
        return self._first_existing_path(candidates)

    def _run_sync_cmd(
        self, cmd: Union[list[str], str], *, shell: bool = False
    ) -> int:
        """在当前线程中执行子进程，将 stdout/stderr 合并流实时写入 log_ready，返回退出码。"""
        try:
            if shell and isinstance(cmd, str):
                self.log_ready.emit(f"[cmd] {cmd}")
            elif isinstance(cmd, list):
                self.log_ready.emit(f"[cmd] {' '.join(cmd)}")
            else:
                self.log_ready.emit(f"[cmd] {cmd}")
            p = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                shell=shell,
            )
            if p.stdout is None:
                self.log_ready.emit("[error] 无法读取命令输出")
                return -1
            for line in iter(p.stdout.readline, ""):
                if line == "" and p.poll() is not None:
                    break
                if line:
                    self.log_ready.emit(line.rstrip("\r\n"))
            rc = p.wait()
            self.log_ready.emit(f"[exit] code={rc}")
            return int(rc) if rc is not None else -1
        except FileNotFoundError as e:
            self.log_ready.emit(f"[error] 命令未找到或无法执行: {e}")
            return -1
        except Exception as e:
            self.log_ready.emit(f"[error] {e}")
            return -1

    def _install_worker(self) -> None:
        """在独立线程中执行：系统依赖 → npm 全局安装 openclaw。"""
        try:
            if self.os_type == "Darwin":
                self._install_worker_darwin()
            elif self.os_type == "Windows":
                self._install_worker_windows()
            else:
                self.log_ready.emit(
                    "[BoxClaw 🦞] 当前系统请手动安装 Node.js（>=22.12）、Git，"
                    "并执行 `npm install -g openclaw`。"
                )
        finally:
            pass

    def _install_worker_darwin(self) -> None:
        brew = self._resolve_brew()
        if not brew:
            self.log_ready.emit(
                "[BoxClaw 🦞] 检测到 Mac 未安装 Homebrew 基础工具。"
                "请打开 Mac 自带的「终端」App，复制并运行以下命令，安装完成后再来点击本按钮：\n"
                '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
            )
            return
        self.log_ready.emit(f"[BoxClaw 🦞] 使用 Homebrew: {brew}")
        rc = self._run_sync_cmd([brew, "install", "node", "git"])
        if rc != 0:
            self.log_ready.emit(
                "[BoxClaw 🦞] brew install 未完全成功，请检查上方日志；仍将继续尝试 npm…"
            )
        npm = self._resolve_npm()
        if not npm:
            self.log_ready.emit(
                "[BoxClaw 🦞] 未找到 npm。请关闭并重开终端，或确认 Node.js 已正确安装。"
            )
            return
        self.log_ready.emit(f"[BoxClaw 🦞] 使用 npm: {npm}")
        rc_npm = self._run_sync_cmd([npm, "install", "-g", "openclaw"])
        if rc_npm == 0:
            self.log_ready.emit(
                "[BoxClaw 🦞] 🎉 环境配置与龙虾核心安装全部完成！现在可以点击【启动 BoxClaw 🦞 龙虾】了。"
            )
        else:
            self.log_ready.emit(
                "[BoxClaw 🦞] npm install -g openclaw 未成功，请根据上方日志排查。"
            )

    def _install_worker_windows(self) -> None:
        winget = self._resolve_winget()
        if not winget:
            self.log_ready.emit(
                "[BoxClaw 🦞] 未找到 winget 包管理器。"
                "请前往 nodejs.org 和 git-scm.com 手动下载安装！"
            )
            return
        agree = ["--accept-package-agreements", "--accept-source-agreements"]
        self.log_ready.emit(f"[BoxClaw 🦞] 使用 winget: {winget}")
        rc1 = self._run_sync_cmd(
            [
                winget,
                "install",
                "-e",
                "--id",
                "OpenJS.NodeJS",
                *agree,
            ]
        )
        rc2 = self._run_sync_cmd(
            [
                winget,
                "install",
                "-e",
                "--id",
                "Git.Git",
                *agree,
            ]
        )
        if rc1 != 0 or rc2 != 0:
            self.log_ready.emit(
                "[BoxClaw 🦞] winget 安装可能已跳过（已安装）或失败，请查看上方日志；仍将继续尝试 npm…"
            )
        npm = self._resolve_npm()
        if not npm:
            self.log_ready.emit(
                "[BoxClaw 🦞] 未找到 npm。请关闭并重开本终端或重新登录，"
                "确保 Node.js 已加入 PATH 后再试。"
            )
            return
        self.log_ready.emit(f"[BoxClaw 🦞] 使用 npm: {npm}")
        rc_npm = self._run_sync_cmd([npm, "install", "-g", "openclaw"])
        if rc_npm == 0:
            self.log_ready.emit(
                "[BoxClaw 🦞] 🎉 环境配置与龙虾核心安装全部完成！现在可以点击【启动 BoxClaw 🦞 龙虾】了。"
            )
        else:
            self.log_ready.emit(
                "[BoxClaw 🦞] npm install -g openclaw 未成功，请根据上方日志排查。"
            )

    def _install_thread_finished(self) -> None:
        self._install_thread = None

    def install_environment(self) -> None:
        if self._install_thread is not None and self._install_thread.isRunning():
            self.log_ready.emit("[BoxClaw 🦞] 环境安装已在进行中，请稍候…")
            return
        self.log_ready.emit(
            "[BoxClaw] 正在自动配置 Node.js 与 Git 运行环境，请耐心等待…"
        )
        self._install_thread = _InstallWorkerThread(self)
        self._install_thread.finished.connect(self._install_thread_finished)
        self._install_thread.start()

    def start_gateway(self) -> None:
        """与顶栏「运行」一致：`gateway run`，并支持输出吸附（已在后台运行）。"""
        self.start_service()

    def restart_gateway(self) -> None:
        """先 gateway stop，再 gateway run，以取回完整控制权。"""
        self.stop_service()
        self.log_ready.emit("[BoxClaw 🦞] 正在执行 openclaw gateway stop …")
        stop_cmd = self._resolve_openclaw_cli() + ["gateway", "stop"]
        t = _CmdLogThread(stop_cmd)
        t.line_ready.connect(self.log_ready.emit)

        def _after() -> None:
            try:
                self._cmd_threads.remove(t)
            except ValueError:
                pass
            QTimer.singleShot(1500, self.start_service)

        t.finished.connect(_after)
        self._cmd_threads.append(t)
        t.start()

    def run_doctor(self) -> None:
        cmd = self._resolve_openclaw_cli() + ["doctor"]
        self.run_command_and_log(cmd)

    def send_command(self, cmd: str) -> None:
        """将用户命令写入 OpenClaw 进程 stdin。"""
        text = str(cmd or "").strip()
        if not text:
            return
        if self._proc is None or self._proc.poll() is not None or self._proc.stdin is None:
            self.log_ready.emit("[stdin] OpenClaw 未运行，命令未发送")
            return
        try:
            payload = (text + "\n").encode("utf-8")
            stream = self._proc.stdin
            # 优先使用 bytes 强灌（符合 Node 进程 stdin 注入预期）
            if hasattr(stream, "buffer"):
                stream.buffer.write(payload)  # type: ignore[attr-defined]
                stream.buffer.flush()  # type: ignore[attr-defined]
            else:
                stream.write(text + "\n")
                stream.flush()
            self.log_ready.emit(f"[stdin] {text}")
        except Exception as e:
            self.log_ready.emit(f"[stdin] 写入失败: {e}")


# ═══════════════════════════════════════════════════════════════
#  DouyinAutomationCore — Profile / WebEngine 沙盒（UI 由 MatrixPage 承载）
# ═══════════════════════════════════════════════════════════════


def matrix_account_route_key(dir_name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_]", "_", dir_name)
    if not s or s[0].isdigit():
        s = "acc_" + s
    return f"matrixSandbox_{s}"


class DouyinAutomationCore(QObject):
    """抖音矩阵：多账号 Profile 隔离与 WebView 沙盒。"""

    accounts_changed = Signal()
    account_added = Signal(str, str)
    account_removed = Signal(str)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._window = parent
        self.profile_cache: dict = {}
        self.views: dict = {}
        self.dir_to_display: dict[str, str] = {}
        self._ordered_accounts: list[str] = []

        self._stash = QWidget(parent)
        self._stash.hide()
        sl = QVBoxLayout(self._stash)
        sl.setContentsMargins(0, 0, 0, 0)

        qapp = QApplication.instance()
        if qapp:
            qapp.aboutToQuit.connect(self._on_about_to_quit)

    _STEALTH_JS = r"""
        (function(){
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            if (!window.chrome) { window.chrome = {}; }
            if (!window.chrome.runtime) {
                window.chrome.runtime = {
                    connect: function(){},
                    sendMessage: function(){}
                };
            }
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    {name:'Chrome PDF Plugin', filename:'internal-pdf-viewer',
                     description:'Portable Document Format',length:1},
                    {name:'Chrome PDF Viewer', filename:'mhjfbmdgcfjbbpaeojofohoefgiehjai',
                     description:'',length:1},
                    {name:'Native Client', filename:'internal-nacl-plugin',
                     description:'',length:2}
                ]
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['zh-CN', 'zh', 'en-US', 'en']
            });
            const origQuery = window.Permissions && Permissions.prototype.query;
            if (origQuery) {
                Permissions.prototype.query = function(params) {
                    if (params.name === 'notifications') {
                        return Promise.resolve({state: Notification.permission});
                    }
                    return origQuery.call(this, params);
                };
            }
            const getParam = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(p) {
                if (p === 37445) return 'Google Inc. (Apple)';
                if (p === 37446) return 'ANGLE (Apple, ANGLE Metal Renderer: Apple M-series, Unspecified Version)';
                return getParam.call(this, p);
            };
            if (navigator.connection) {
                Object.defineProperty(navigator.connection, 'rtt', {get: () => 100});
            }
        })();
        """

    def get_profile(self, dir_name: str) -> QWebEngineProfile:
        if dir_name in self.profile_cache:
            return self.profile_cache[dir_name]
        qapp = QApplication.instance()
        if qapp is None:
            raise RuntimeError("QApplication required")
        root_dir = PROFILES_BASE_DIR / dir_name
        persistent = root_dir / "webengine"
        cache = root_dir / "webengine_cache"
        persistent.mkdir(parents=True, exist_ok=True)
        cache.mkdir(parents=True, exist_ok=True)
        profile = QWebEngineProfile(dir_name, qapp)
        profile.setPersistentStoragePath(str(persistent))
        profile.setCachePath(str(cache))
        profile.setPersistentCookiesPolicy(QWebEngineProfile.ForcePersistentCookies)
        ua = profile.httpUserAgent()
        ua = re.sub(r"\s*QtWebEngine/[\d.]+", "", ua)
        ua = re.sub(r"\s*HeadlessChrome/", " Chrome/", ua)
        ua = re.sub(r"\s{2,}", " ", ua).strip()
        profile.setHttpUserAgent(ua)
        s = profile.settings()
        s.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
        s.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        s.setAttribute(QWebEngineSettings.JavascriptCanOpenWindows, False)
        s.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, False)
        s.setAttribute(QWebEngineSettings.PluginsEnabled, True)
        s.setAttribute(QWebEngineSettings.ScrollAnimatorEnabled, True)
        stealth = QWebEngineScript()
        stealth.setName(f"stealth_{dir_name}")
        stealth.setSourceCode(self._STEALTH_JS)
        stealth.setInjectionPoint(QWebEngineScript.DocumentCreation)
        stealth.setWorldId(QWebEngineScript.MainWorld)
        stealth.setRunsOnSubFrames(True)
        profile.scripts().insert(stealth)
        self.profile_cache[dir_name] = profile
        return profile

    def _resync_sandbox_webview(self, view: QWebEngineView, host: QWidget) -> None:
        """切换宿主或尺寸变化后，强制布局与页面内响应式脚本重新计算，避免大片留白或裁切。"""
        if view is None or host is None:
            return
        view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        view.setMinimumSize(2, 2)
        view.show()
        view.raise_()
        view.updateGeometry()
        host.updateGeometry()
        page = view.page()
        if page is None:
            return
        js = """
        (function() {
            try {
                var w = window;
                w.dispatchEvent(new Event('resize'));
                if (w.visualViewport) {
                    try { w.visualViewport.dispatchEvent(new Event('resize')); } catch (e) {}
                }
                var d = document;
                if (d.body) {
                    var ev = d.createEvent('HTMLEvents');
                    ev.initEvent('resize', true, true);
                    w.dispatchEvent(ev);
                }
            } catch (e) {}
            void 0;
        })();
        """

        def ping() -> None:
            p = view.page()
            if p is not None:
                p.runJavaScript(js)

        QTimer.singleShot(0, ping)
        QTimer.singleShot(120, ping)
        QTimer.singleShot(400, ping)

    def _shelve_all_webviews_from_host(self, host: QWidget) -> None:
        """沙盒里同时只能显示一个账号：先把宿主布局里已有控件全部移入隐藏暂存区，再挂当前账号。"""
        lay = host.layout()
        if lay is None:
            return
        stash_lay = self._stash.layout()
        while lay.count():
            item = lay.takeAt(0)
            w = item.widget()
            if w is None:
                continue
            w.hide()
            w.setParent(self._stash)
            if stash_lay is not None:
                stash_lay.addWidget(w)

    def _ensure_view(self, dir_name: str, host: QWidget) -> QWebEngineView:
        if dir_name in self.views:
            v = self.views[dir_name]
            old = v.parent()
            if old is not None:
                ol = old.layout()
                if ol is not None:
                    ol.removeWidget(v)
            lay = host.layout()
            if lay is None:
                lay = QVBoxLayout(host)
                lay.setContentsMargins(0, 0, 0, 0)
            lay.addWidget(v, 1)
            self._resync_sandbox_webview(v, host)
            return v
        profile = self.get_profile(dir_name)
        view = QWebEngineView(host)
        page = QWebEnginePage(profile, view)
        view.setPage(page)
        lay = host.layout()
        if lay is None:
            lay = QVBoxLayout(host)
            lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(view, 1)
        self.views[dir_name] = view

        def _on_any_load_finished(ok: bool) -> None:
            if ok:
                self._resync_sandbox_webview(view, host)

        page.loadFinished.connect(_on_any_load_finished)
        QTimer.singleShot(80, lambda: view.load(QUrl(START_URL)))
        self._resync_sandbox_webview(view, host)
        return view

    def attach_view_to_sandbox(self, dir_name: str, host: QWidget) -> None:
        self._shelve_all_webviews_from_host(host)
        self._ensure_view(dir_name, host)

    def clear_http_caches(self) -> None:
        reply = QMessageBox.question(
            self._window,
            "\U0001f9f9 \u6e05\u7406\u7f13\u5b58",
            "\u786e\u5b9a\u8981\u6e05\u7406\u6240\u6709\u8d26\u53f7\u7684\u8fd0\u884c\u7f13\u5b58\u5417\uff1f\n\uff08\u4e0d\u4f1a\u5f71\u54cd\u767b\u5f55\u72b6\u6001\uff09",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        for _name, profile in self.profile_cache.items():
            profile.clearHttpCache()
        QMessageBox.information(self._window, "\u2705 \u5b8c\u6210", "\u7f13\u5b58\u6e05\u7406\u5b8c\u6bd5\uff01")

    def register_account(self, dir_name: str, display_name: str) -> bool:
        if dir_name in self.dir_to_display:
            return False
        if len(self.dir_to_display) >= MAX_ACCOUNTS:
            return False
        (PROFILES_BASE_DIR / dir_name).mkdir(parents=True, exist_ok=True)
        self.dir_to_display[dir_name] = display_name
        self._ordered_accounts.append(dir_name)
        self.account_added.emit(dir_name, display_name)
        self.accounts_changed.emit()
        return True

    def rename_account(self, dir_name: str, new_display: str) -> None:
        if dir_name in self.dir_to_display:
            self.dir_to_display[dir_name] = new_display.strip()
            self.accounts_changed.emit()

    def remove_account(self, dir_name: str) -> bool:
        if dir_name not in self.dir_to_display:
            return False
        v = self.views.pop(dir_name, None)
        if v:
            try:
                v.stop()
                v.setPage(None)
                v.deleteLater()
            except Exception:
                pass
        prof = self.profile_cache.pop(dir_name, None)
        if prof:
            try:
                prof.clearHttpCache()
            except Exception:
                pass
        self.dir_to_display.pop(dir_name, None)
        if dir_name in self._ordered_accounts:
            self._ordered_accounts.remove(dir_name)
        target = PROFILES_BASE_DIR / dir_name
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        self.account_removed.emit(dir_name)
        self.accounts_changed.emit()
        return True

    def _on_about_to_quit(self) -> None:
        for _dn, view in list(self.views.items()):
            if view is None:
                continue
            try:
                view.stop()
                view.setPage(None)
            except Exception:
                pass
        self.views.clear()


class BoxClawPage(QWidget):
    """侧栏子界面基类：子类必须设置全局唯一的 objectName（路由键）。"""

    pass


# SplitFluentWindow 标题栏悬浮在内容区之上，业务页主布局需预留此上边距（与 qfluentwidgets 标题栏高度匹配）
PAGE_TOP_INSET_FOR_TITLEBAR = 12

# 暗夜紫主题（非纯黑：冷紫灰底 + 紫罗兰高光 + 多色信息点；仅 UI，不改动矩阵沙盒逻辑）
UI_BG_ROOT = "#12101c"
UI_BG_CARD = "#1c1830"
UI_BG_CARD_SOFT = "#211d38"
UI_BG_ELEVATED = "#262140"
UI_NAV_BG = "rgba(22, 18, 38, 0.97)"
UI_BORDER_PURPLE = "rgba(139, 92, 246, 0.38)"
UI_BORDER_PURPLE_SOFT = "rgba(167, 139, 250, 0.18)"
UI_TEXT_PRIMARY = "#f1f5f9"
UI_TEXT_MUTED = "rgba(203, 213, 225, 0.72)"
UI_ACCENT = "#c4b5fd"
UI_ACCENT_DEEP = "#8b5cf6"
# 仪表盘卡片左侧色条（功能区分）
DASH_STRIPE_COLORS = ("#8b5cf6", "#22d3ee", "#fbbf24", "#34d399", "#f472b6", "#818cf8")


# ---------------------------------------------------------------------------
# 账号矩阵 — DouyinAutomationCore 执行层（WebView 挂载至 matrix_container）
# ---------------------------------------------------------------------------
class MatrixPage(BoxClawPage):
    def __init__(self, parent: Optional[QWidget], core: "DouyinAutomationCore") -> None:
        super().__init__(parent)
        self.setObjectName("matrixPageInterface")
        self._core = core
        self._dir_order: list[str] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, PAGE_TOP_INSET_FOR_TITLEBAR, 24, 24)
        layout.setSpacing(12)
        mp_title = SubtitleLabel("抖音账号矩阵", self)
        mp_title.setObjectName("matrixPageTitle")
        layout.addWidget(mp_title)

        bar = QHBoxLayout()
        bar.setSpacing(10)
        bar.addWidget(BodyLabel("当前账号", self))
        self._combo = ComboBox(self)
        self._combo.setMinimumWidth(200)
        self._combo.currentIndexChanged.connect(self._on_combo_index_changed)
        bar.addWidget(self._combo, stretch=1)

        btn_add = PrimaryPushButton("添加账号", self)
        btn_add.clicked.connect(self._add_account)
        btn_rm = PushButton("移除账号", self)
        btn_rm.clicked.connect(self._remove_account)
        btn_cache = PushButton("清理缓存", self)
        btn_cache.clicked.connect(core.clear_http_caches)

        bar.addWidget(btn_add)
        bar.addWidget(btn_rm)
        bar.addWidget(btn_cache)
        layout.addLayout(bar)

        nav_bar = QHBoxLayout()
        nav_bar.setContentsMargins(0, 0, 0, 8)
        self.btn_back = TransparentToolButton(FIF.PAGE_LEFT, self)
        self.btn_back.setToolTip("后退")
        self.btn_forward = TransparentToolButton(FIF.PAGE_RIGHT, self)
        self.btn_forward.setToolTip("前进")
        self.btn_refresh = TransparentToolButton(FIF.SYNC, self)
        self.btn_refresh.setToolTip("刷新")
        nav_bar.addWidget(self.btn_back)
        nav_bar.addWidget(self.btn_forward)
        nav_bar.addWidget(self.btn_refresh)
        self.btn_creator = PushButton("抖音创作者中心", self)
        self.btn_main = PushButton("抖音主站", self)
        nav_bar.addWidget(self.btn_creator)
        nav_bar.addWidget(self.btn_main)
        nav_bar.addStretch()
        self.btn_back.clicked.connect(self._nav_back)
        self.btn_forward.clicked.connect(self._nav_forward)
        self.btn_refresh.clicked.connect(self._nav_refresh)
        self.btn_creator.clicked.connect(self._nav_to_creator)
        self.btn_main.clicked.connect(self._nav_to_main)
        layout.addLayout(nav_bar)

        self.matrix_container = QWidget(self)
        self.matrix_container.setObjectName("matrix_container")
        self.matrix_container.setMinimumHeight(240)
        self.matrix_container.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        ml = QVBoxLayout(self.matrix_container)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(0)
        layout.addWidget(self.matrix_container, stretch=1)

        core.accounts_changed.connect(self._refresh_account_combo)

    def _current_dir(self) -> str | None:
        idx = self._combo.currentIndex()
        if 0 <= idx < len(self._dir_order):
            return self._dir_order[idx]
        return None

    def _refresh_account_combo(self) -> None:
        prev = self._current_dir()
        self._combo.blockSignals(True)
        self._combo.clear()
        self._dir_order = list(self._core._ordered_accounts)
        for dn in self._dir_order:
            self._combo.addItem(self._core.dir_to_display.get(dn, dn))
        self._combo.blockSignals(False)
        if not self._dir_order:
            return
        new_idx = 0
        if prev and prev in self._dir_order:
            new_idx = self._dir_order.index(prev)
        self._combo.blockSignals(True)
        self._combo.setCurrentIndex(new_idx)
        self._combo.blockSignals(False)
        self._attach_sandbox()

    def _on_combo_index_changed(self, index: int) -> None:
        if index < 0 or index >= len(self._dir_order):
            return
        self._attach_sandbox()

    def _attach_sandbox(self) -> None:
        dn = self._current_dir()
        if not dn:
            return
        self._core.attach_view_to_sandbox(dn, self.matrix_container)

    def _get_current_view(self) -> QWebEngineView | None:
        dn = self._current_dir()
        if dn and dn in self._core.views:
            return self._core.views[dn]
        return None

    def _nav_back(self) -> None:
        v = self._get_current_view()
        if v:
            v.back()

    def _nav_forward(self) -> None:
        v = self._get_current_view()
        if v:
            v.forward()

    def _nav_refresh(self) -> None:
        v = self._get_current_view()
        if v:
            v.reload()

    def _nav_to_creator(self) -> None:
        v = self._get_current_view()
        if v:
            v.load(QUrl("https://creator.douyin.com/creator-micro/content/upload"))

    def _nav_to_main(self) -> None:
        v = self._get_current_view()
        if v:
            v.load(QUrl("https://www.douyin.com/"))

    def _add_account(self) -> None:
        raw, ok = QInputDialog.getText(self, "添加账号", "账号目录名（将创建在 ~/Douyin_Profiles 下）：")
        if not ok:
            return
        name = sanitize_account_name(raw)
        if not name:
            QMessageBox.warning(self, "提示", "请输入有效的账号名称")
            return
        if name in self._core.dir_to_display:
            QMessageBox.information(self, "提示", "该账号已存在")
            return
        if not self._core.register_account(name, name):
            QMessageBox.warning(self, "提示", f"最多支持 {MAX_ACCOUNTS} 个账号")
            return

    def _remove_account(self) -> None:
        dn = self._current_dir()
        if not dn:
            QMessageBox.information(self, "提示", "没有可移除的账号")
            return
        disp = self._core.dir_to_display.get(dn, dn)
        r = QMessageBox.question(
            self,
            "确认移除",
            f"将删除账号「{disp}」的配置与本地 Profile 目录，是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if r != QMessageBox.StandardButton.Yes:
            return
        self._core.remove_account(dn)


# ---------------------------------------------------------------------------
# 系统设置
# ---------------------------------------------------------------------------
class SettingsPage(BoxClawPage):
    """侧栏 gateway_autostart（config.json）+ OpenClaw 主配置（openclaw.json）模型与 API。"""

    def __init__(self, parent: Optional[QWidget], openclaw_manager: "OpenClawProcessManager") -> None:
        super().__init__(parent)
        self.setObjectName("settingsInterface")
        self._openclaw = openclaw_manager
        self._model_group: Optional[QButtonGroup] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(24, PAGE_TOP_INSET_FOR_TITLEBAR, 24, 24)
        root.setSpacing(12)

        head = SubtitleLabel("系统设置", self)
        setFont(head, 24)
        head.setStyleSheet(f"color: {UI_TEXT_PRIMARY};")
        root.addWidget(head)

        hint = BodyLabel(
            "主配置与官方 CLI 一致（openclaw config get/set）。修改 API 后保存会校验配置并重启网关。",
            self,
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {UI_TEXT_MUTED};")
        root.addWidget(hint)

        path_side = BodyLabel(f"BoxClaw 侧栏项：{BOXCLAW_GATEWAY_SIDECAR_PATH}", self)
        path_side.setWordWrap(True)
        path_side.setStyleSheet(f"color: {UI_TEXT_MUTED};")
        root.addWidget(path_side)
        path_main = BodyLabel(f"OpenClaw 主配置：{resolve_openclaw_main_config_path()}", self)
        path_main.setWordWrap(True)
        path_main.setStyleSheet(f"color: {UI_TEXT_MUTED};")
        root.addWidget(path_main)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget(scroll)
        layout = QVBoxLayout(inner)
        layout.setSpacing(14)

        sec_gw = SubtitleLabel("网关", self)
        setFont(sec_gw, 16)
        layout.addWidget(sec_gw)
        row = QHBoxLayout()
        sw_lbl = BodyLabel("随应用静默启动 OpenClaw 网关", self)
        sw_lbl.setStyleSheet(f"color: {UI_TEXT_PRIMARY};")
        row.addWidget(sw_lbl)
        self._gw_switch = SwitchButton(self)
        row.addWidget(self._gw_switch)
        row.addStretch()
        layout.addLayout(row)

        sec_m = SubtitleLabel("模型与 API", self)
        setFont(sec_m, 16)
        layout.addWidget(sec_m)
        m_hint = BodyLabel(
            "选择快捷服务商 / 主型号，或选「自定义」后手动填写。主型号未选且留空时，仅保存「随应用启动」。",
            self,
        )
        m_hint.setWordWrap(True)
        m_hint.setStyleSheet(f"color: {UI_TEXT_MUTED};")
        layout.addWidget(m_hint)

        preset_box = QFrame(self)
        preset_box.setObjectName("openclawPresetBox")
        pbl = QVBoxLayout(preset_box)
        pbl.setContentsMargins(14, 12, 14, 12)
        pbl.setSpacing(10)

        qs = BodyLabel("快捷选择服务商", self)
        qs.setStyleSheet(f"color: {UI_TEXT_PRIMARY}; font-weight: 600;")
        pbl.addWidget(qs)
        qs_sub = BodyLabel("单选一项自动填充下方接口信息；选「自定义」后可编辑。", self)
        qs_sub.setWordWrap(True)
        qs_sub.setStyleSheet(f"color: {UI_TEXT_MUTED};")
        pbl.addWidget(qs_sub)

        self._prov_group = QButtonGroup(self)
        prov_grid = QGridLayout()
        prov_grid.setSpacing(8)
        for i, pr in enumerate(OPENCLAW_PROVIDER_PRESETS):
            rb = QRadioButton(pr.label)
            rb.setProperty("preset_key", pr.key)
            self._prov_group.addButton(rb)
            r, c = divmod(i, 3)
            prov_grid.addWidget(rb, r, c)
        pbl.addLayout(prov_grid)

        mm = BodyLabel("快捷选择主型号", self)
        mm.setStyleSheet(f"color: {UI_TEXT_PRIMARY}; font-weight: 600;")
        pbl.addWidget(mm)
        self._model_radio_host = QWidget(preset_box)
        self._model_radio_layout = QVBoxLayout(self._model_radio_host)
        self._model_radio_layout.setContentsMargins(0, 0, 0, 0)
        self._model_radio_layout.setSpacing(6)
        pbl.addWidget(self._model_radio_host)

        layout.addWidget(preset_box)

        def _pair(label: str, w: QWidget, helpt: str = "") -> None:
            hb = QVBoxLayout()
            hb.setSpacing(4)
            rowh = QHBoxLayout()
            lb = BodyLabel(label, self)
            lb.setStyleSheet(f"color: {UI_TEXT_PRIMARY};")
            lb.setMinimumWidth(120)
            rowh.addWidget(lb, 0)
            rowh.addWidget(w, 1)
            hb.addLayout(rowh)
            if helpt:
                ht = BodyLabel(helpt, self)
                ht.setWordWrap(True)
                ht.setStyleSheet(f"color: {UI_TEXT_MUTED}; font-size: 11px;")
                hb.addWidget(ht)
            layout.addLayout(hb)

        self._provider_edit = QLineEdit(self)
        self._provider_edit.setPlaceholderText("自定义标识，如 openai、volcengine")
        _pair(
            "服务商 ID",
            self._provider_edit,
            "与主型号前缀一致；仅在选择「自定义」服务商时可编辑。",
        )

        self._base_url_edit = QLineEdit(self)
        self._base_url_edit.setPlaceholderText("https://api.openai.com/v1")
        _pair(
            "接口地址",
            self._base_url_edit,
            "模型 API 根地址，多为 OpenAI 兼容；Ollama 可填 http://127.0.0.1:11434/v1",
        )

        self._api_type_combo = ComboBox(self)
        self._api_type_combo.addItem("OpenAI 兼容 (最常用)")
        self._api_type_combo.setItemData(0, "openai-completions")
        self._api_type_combo.setMinimumWidth(280)
        _pair(
            "接口类型",
            self._api_type_combo,
            "多数中转与 Ollama 使用「OpenAI 兼容」即可；仅自定义服务商时可改。",
        )

        self._api_key_edit = QLineEdit(self)
        self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_edit.setPlaceholderText("sk-… 留空保留已保存密钥")
        _pair("API Key", self._api_key_edit, "访问服务所需密钥；留空表示本次不覆盖已保存值。")

        self._primary_edit = QLineEdit(self)
        self._primary_edit.setPlaceholderText("provider/model，如 volcengine/minimax-m2.5")
        _pair(
            "主型号 ID",
            self._primary_edit,
            "选择快捷型号时自动填入；选「自定义」主型号时可编辑。",
        )

        self._fallbacks_edit = QLineEdit(self)
        self._fallbacks_edit.setPlaceholderText("逗号分隔备选型号")
        _pair("备选型号", self._fallbacks_edit, "可选，逗号分隔。")

        layout.addStretch()
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        self._prov_group.buttonClicked.connect(self._on_provider_radio_clicked)
        raw = read_openclaw_config_file()
        self._gw_switch.setChecked(bool(raw.get("gateway_autostart", False)))
        self._load_openclaw_model_fields()

        save = PrimaryPushButton("保存设置", self)
        save.clicked.connect(self._save)
        root.addWidget(save, alignment=Qt.AlignmentFlag.AlignLeft)

    def _current_provider_preset_key(self) -> str:
        btn = self._prov_group.checkedButton()
        if btn is None:
            return "custom"
        k = btn.property("preset_key")
        return str(k) if k else "custom"

    def _on_provider_radio_clicked(self, _btn: QAbstractButton) -> None:
        self._apply_provider_fields_from_preset(self._current_provider_preset_key())
        self._rebuild_model_radios(self._current_provider_preset_key(), select_full_id=None)
        self._sync_custom_fields_enabled()

    def _apply_provider_fields_from_preset(self, preset_key: str) -> None:
        pr = _openclaw_provider_preset_by_key(preset_key)
        if pr is None or pr.key == "custom":
            return
        self._provider_edit.setText(pr.provider_id)
        self._base_url_edit.setText(pr.base_url)
        idx = self._api_type_combo.findData(pr.api)
        if idx >= 0:
            self._api_type_combo.setCurrentIndex(idx)

    def _rebuild_model_radios(
        self, provider_key: str, select_full_id: Optional[str]
    ) -> None:
        if self._model_group is not None:
            try:
                self._model_group.buttonClicked.disconnect(self._on_model_radio_clicked)
            except (TypeError, RuntimeError):
                pass
            for b in list(self._model_group.buttons()):
                self._model_group.removeButton(b)
                b.deleteLater()
            self._model_group.deleteLater()
        self._model_group = QButtonGroup(self)
        while self._model_radio_layout.count():
            item = self._model_radio_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        choices = list(OPENCLAW_MODEL_PRESETS.get(provider_key, ()))
        primary = (select_full_id or "").strip()
        picked = False

        self._model_group.blockSignals(True)
        first_preset_rb: Optional[QRadioButton] = None
        for label, mid in choices:
            rb = QRadioButton(f"{label}  ({mid})")
            rb.setProperty("full_model_id", mid)
            rb.setProperty("is_custom_model", False)
            self._model_group.addButton(rb)
            self._model_radio_layout.addWidget(rb)
            if first_preset_rb is None:
                first_preset_rb = rb
            if primary and mid == primary:
                rb.setChecked(True)
                picked = True

        rb_c = QRadioButton("自定义（手动输入主型号）")
        rb_c.setProperty("full_model_id", "")
        rb_c.setProperty("is_custom_model", True)
        self._model_group.addButton(rb_c)
        self._model_radio_layout.addWidget(rb_c)
        if not picked:
            if first_preset_rb is not None:
                first_preset_rb.setChecked(True)
            else:
                rb_c.setChecked(True)

        self._model_group.blockSignals(False)
        self._model_group.buttonClicked.connect(self._on_model_radio_clicked)

        btn = self._model_group.checkedButton()
        if btn is not None:
            if btn.property("is_custom_model"):
                self._primary_edit.setText(primary)
            else:
                fm = btn.property("full_model_id")
                if isinstance(fm, str) and fm:
                    self._primary_edit.setText(fm)
        self._sync_custom_fields_enabled()

    def _on_model_radio_clicked(self, btn: Optional[QAbstractButton]) -> None:
        if btn is None:
            return
        if not btn.property("is_custom_model"):
            mid = btn.property("full_model_id")
            if isinstance(mid, str) and mid:
                self._primary_edit.setText(mid)
        self._sync_custom_fields_enabled()

    def _sync_custom_fields_enabled(self) -> None:
        pk = self._current_provider_preset_key()
        prov_custom = pk == "custom"
        self._provider_edit.setReadOnly(not prov_custom)
        self._base_url_edit.setReadOnly(not prov_custom)
        self._api_type_combo.setEnabled(prov_custom)

        mb = self._model_group.checkedButton() if self._model_group else None
        model_custom = mb is not None and bool(mb.property("is_custom_model"))
        self._primary_edit.setReadOnly(not model_custom)

    def _load_openclaw_model_fields(self) -> None:
        main = read_main_openclaw_config()
        providers = (
            main.get("models", {}).get("providers", {})
            if isinstance(main.get("models"), dict)
            else {}
        )
        pid = next(iter(providers), "") if providers else ""
        prov = providers.get(pid, {}) if pid and isinstance(providers.get(pid), dict) else {}
        base_url = str(prov.get("baseUrl", "") or "")
        pk = _detect_openclaw_provider_preset_key(pid, base_url)

        self._prov_group.blockSignals(True)
        for b in self._prov_group.buttons():
            if b.property("preset_key") == pk:
                b.setChecked(True)
                break
        else:
            for b in self._prov_group.buttons():
                if b.property("preset_key") == "custom":
                    b.setChecked(True)
                    break
        self._prov_group.blockSignals(False)

        self._apply_provider_fields_from_preset(pk)
        if pk == "custom":
            self._provider_edit.setText(pid)
            self._base_url_edit.setText(base_url)
            api_v = str(prov.get("api", "") or "openai-completions")
            ix = self._api_type_combo.findData(api_v)
            self._api_type_combo.setCurrentIndex(ix if ix >= 0 else 0)

        self._api_key_edit.clear()

        ad = main.get("agents", {}).get("defaults", {}) if isinstance(main.get("agents"), dict) else {}
        model = ad.get("model", {}) if isinstance(ad.get("model"), dict) else {}
        primary = str(model.get("primary", "") or "")

        self._rebuild_model_radios(pk, select_full_id=primary)

        fb = model.get("fallbacks", [])
        if isinstance(fb, list):
            self._fallbacks_edit.setText(", ".join(str(x) for x in fb))
        else:
            self._fallbacks_edit.setText("")

        self._sync_custom_fields_enabled()

    def _save(self) -> None:
        win = self.window()
        side = read_openclaw_config_file()
        side["gateway_autostart"] = self._gw_switch.isChecked()
        try:
            write_openclaw_config_file(side)
        except OSError as e:
            InfoBar.error("保存失败", str(e), duration=5000, parent=win, position=InfoBarPosition.TOP)
            return

        mb = self._model_group.checkedButton() if self._model_group else None
        model_custom = mb is not None and bool(mb.property("is_custom_model"))
        primary = self._primary_edit.text().strip()
        if not model_custom:
            fm = mb.property("full_model_id") if mb else None
            if isinstance(fm, str) and fm.strip():
                primary = fm.strip()

        if not primary:
            InfoBar.success(
                "已保存",
                "已更新侧栏「随应用启动」；未选择/填写主型号，未改动 openclaw.json。",
                duration=3200,
                parent=win,
                position=InfoBarPosition.TOP,
            )
            self._openclaw.restart_service()
            return

        main_path = resolve_openclaw_main_config_path()
        main_prev = read_main_openclaw_config()
        backup_text: Optional[str] = None
        if main_path.is_file():
            try:
                backup_text = main_path.read_text(encoding="utf-8")
            except OSError:
                backup_text = None

        pkey = self._current_provider_preset_key()
        pr = _openclaw_provider_preset_by_key(pkey)
        if pr is not None and pkey != "custom" and pr.key != "custom":
            pid = pr.provider_id
            base_url = pr.base_url
            api_if = pr.api
        else:
            pid = self._provider_edit.text().strip() or "volcengine"
            base_url = self._base_url_edit.text().strip()
            ix = self._api_type_combo.currentIndex()
            api_if = self._api_type_combo.itemData(ix)
            if not isinstance(api_if, str) or not api_if.strip():
                api_if = "openai-completions"
            else:
                api_if = api_if.strip()

        key_text = self._api_key_edit.text().strip()
        fb_raw = self._fallbacks_edit.text().strip()
        fallbacks = [x.strip() for x in fb_raw.split(",") if x.strip()]

        try:
            new_main = apply_openclaw_model_api_to_config(
                main_prev,
                provider_id=pid,
                base_url=base_url,
                api_key_plain=key_text if key_text else None,
                primary_model=primary,
                fallbacks=fallbacks,
                api_interface=api_if or "openai-completions",
            )
        except ValueError as e:
            InfoBar.warning("无法保存", str(e), duration=6000, parent=win, position=InfoBarPosition.TOP)
            return

        try:
            write_main_openclaw_config(new_main)
        except OSError as e:
            InfoBar.error("写入主配置失败", str(e), duration=5000, parent=win, position=InfoBarPosition.TOP)
            return

        ok, msg = run_openclaw_config_validate()
        if not ok:
            if backup_text is not None:
                try:
                    main_path.write_text(backup_text, encoding="utf-8")
                except OSError:
                    pass
            InfoBar.error(
                "配置未通过校验，已恢复备份",
                msg or "openclaw config validate 失败",
                duration=8000,
                parent=win,
                position=InfoBarPosition.TOP,
            )
            return

        InfoBar.success(
            "已保存",
            "已写入主配置并校验通过，正在重启 OpenClaw…",
            duration=2800,
            parent=win,
            position=InfoBarPosition.TOP,
        )
        self._openclaw.restart_service()
        self._api_key_edit.clear()
        self._load_openclaw_model_fields()


# ---------------------------------------------------------------------------
# 启动默认首页（仪表盘卡片，只读展示；不触碰矩阵沙盒逻辑）
# ---------------------------------------------------------------------------
class HomeWelcomePage(BoxClawPage):
    """应用启动时默认展示：暗夜仪表盘风格，数据来自本地配置只读快照。"""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("homeWelcomeInterface")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, PAGE_TOP_INSET_FOR_TITLEBAR + 16, 28, 28)
        layout.setSpacing(22)

        title = TitleLabel("仪表盘", self)
        setFont(title, 26)
        title.setStyleSheet(f"color: {UI_TEXT_PRIMARY}; letter-spacing: 0.5px;")
        sub = BodyLabel("OpenClaw 运行状态与抖音矩阵概览", self)
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color: {UI_TEXT_MUTED};")
        layout.addWidget(title)
        layout.addWidget(sub)

        primary, gw_port, n_acc = self._read_dashboard_snapshot()
        grid = QGridLayout()
        grid.setSpacing(16)
        cards: list[tuple[str, str]] = [
            ("OpenClaw 网关端口", gw_port if gw_port else "—（见 openclaw.json）"),
            ("主模型", primary if primary else "未配置"),
            ("矩阵账号", f"{n_acc} 个"),
            ("龙虾控制台", "侧栏进入 · 内嵌网关面板"),
            ("抖音矩阵", "多账号 Profile 沙盒 · 与首页独立"),
            ("系统设置", "模型 / API · 网关自启动"),
        ]
        for i, (ct, cb) in enumerate(cards):
            r, c = divmod(i, 3)
            grid.addWidget(self._dash_card(ct, cb, i), r, c)
        layout.addLayout(grid)
        layout.addStretch(1)

    def _read_dashboard_snapshot(self) -> tuple[str, str, int]:
        primary = ""
        port = ""
        try:
            main = read_main_openclaw_config()
            ad = main.get("agents", {})
            if isinstance(ad, dict):
                m = ad.get("defaults", {}).get("model", {})
                if isinstance(m, dict):
                    primary = str(m.get("primary", "") or "")
            gw = main.get("gateway", {})
            if isinstance(gw, dict):
                port = str(gw.get("port", "") or "")
        except Exception:
            pass
        n = 0
        try:
            if PROFILES_BASE_DIR.is_dir():
                n = len([p for p in PROFILES_BASE_DIR.iterdir() if p.is_dir()])
        except Exception:
            pass
        return primary, port, n

    def _dash_card(self, title: str, body: str, stripe_idx: int) -> QFrame:
        card = QFrame(self)
        card.setObjectName("homeDashCard")
        card.setMinimumHeight(100)
        stripe = QFrame(card)
        stripe.setObjectName("homeDashStripe")
        color = DASH_STRIPE_COLORS[stripe_idx % len(DASH_STRIPE_COLORS)]
        stripe.setStyleSheet(f"background-color: {color};")
        stripe.setFixedWidth(5)
        inner = QWidget(card)
        vl = QVBoxLayout(inner)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(8)
        t = BodyLabel(title, inner)
        t.setStyleSheet(f"color: {UI_TEXT_MUTED}; font-size: 12px;")
        b = SubtitleLabel(body, inner)
        setFont(b, 13)
        b.setWordWrap(True)
        b.setStyleSheet(f"color: {UI_TEXT_PRIMARY};")
        vl.addWidget(t)
        vl.addWidget(b)
        hl = QHBoxLayout(card)
        hl.setContentsMargins(14, 14, 14, 14)
        hl.setSpacing(12)
        hl.addWidget(stripe, 0, Qt.AlignmentFlag.AlignTop)
        hl.addWidget(inner, 1)
        return card


# ---------------------------------------------------------------------------
# OpenClaw — 内嵌 Web 控制台（QWebEngineView）
# ---------------------------------------------------------------------------
class _DiscoverOpenClawPanelWorker(QThread):
    """后台探测网关控制台地址，避免阻塞界面线程。"""

    panel_url_ready = Signal(str)

    def __init__(self, manager: Optional["OpenClawProcessManager"]) -> None:
        super().__init__()
        self._mgr = manager

    def run(self) -> None:
        self.panel_url_ready.emit(discover_openclaw_console_url(self._mgr) or "")


class OpenClawWebPage(BoxClawPage):
    """加载 OpenClaw 网关 Web UI（默认 OPENCLAW_PANEL_URL，与主网关端口一致）。"""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        manager: Optional["OpenClawProcessManager"] = None,
    ) -> None:
        super().__init__(parent)
        self._manager = manager
        self._discover_worker: Optional[_DiscoverOpenClawPanelWorker] = None
        self._view: Optional[QWebEngineView] = None
        self.setObjectName("openclawWebInterface")
        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(10, PAGE_TOP_INSET_FOR_TITLEBAR + 4, 10, 0)
        self._root_layout.setSpacing(10)

        bar = QFrame(self)
        bar.setObjectName("openclawWebBar")
        hl = QHBoxLayout(bar)
        hl.setContentsMargins(14, 10, 14, 10)
        hl.setSpacing(8)
        hl.addStretch(1)
        self._btn_grab = PrimaryPushButton(FIF.SYNC, "抓取网关页面", bar)
        self._btn_grab.setToolTip(
            "从网关日志、配置文件与本机端口自动识别控制台地址并打开"
        )
        self._btn_grab.clicked.connect(self._on_grab_gateway)
        hl.addWidget(self._btn_grab)

        # 延迟创建 QWebEngineView：启动即加载 WebEngine 在 Windows 打包环境下易闪退（子进程/沙箱）
        self._webview_host = QWidget(self)
        whl = QVBoxLayout(self._webview_host)
        whl.setContentsMargins(0, 0, 0, 0)
        self._root_layout.addWidget(bar, 0)
        self._root_layout.addWidget(self._webview_host, 1)

    def ensure_webview(self) -> None:
        if self._view is not None:
            return
        self._view = QWebEngineView(self._webview_host)
        lay = self._webview_host.layout()
        if lay is not None:
            lay.addWidget(self._view)
        self._view.setUrl(QUrl(OPENCLAW_PANEL_URL))

    def _on_grab_gateway(self) -> None:
        self.ensure_webview()
        if self._discover_worker is not None and self._discover_worker.isRunning():
            return
        self._btn_grab.setEnabled(False)
        self._btn_grab.setText("识别中…")
        w = _DiscoverOpenClawPanelWorker(self._manager)
        self._discover_worker = w
        w.panel_url_ready.connect(self._on_panel_url_ready)
        w.finished.connect(w.deleteLater)
        w.start()

    def _on_panel_url_ready(self, url: str) -> None:
        self._btn_grab.setEnabled(True)
        self._btn_grab.setText("抓取网关页面")
        self._discover_worker = None
        win = self.window()
        if not url:
            InfoBar.warning(
                "未识别到网关",
                "请确认 OpenClaw 网关已启动，或检查 ~/.openclaw 日志与端口。",
                duration=4500,
                parent=win,
                position=InfoBarPosition.TOP,
            )
            return
        self.ensure_webview()
        if self._view is not None:
            self._view.setUrl(QUrl(url))
        InfoBar.success(
            "已打开控制台",
            url,
            duration=3200,
            parent=win,
            position=InfoBarPosition.TOP,
        )


# ---------------------------------------------------------------------------
# 底部终端（Gateway 控制台 + 一键环境 / 引擎）
# ---------------------------------------------------------------------------
class GatewayTerminalDock(QWidget):
    """底部可折叠控制台：顶栏 + 日志区 + 工具条 + 命令行。"""

    TOOLBAR_HEIGHT = 44
    ACTION_BAR_HEIGHT = 44
    COLLAPSED_HEIGHT = TOOLBAR_HEIGHT
    EXPANDED_HEIGHT = 300

    def __init__(self, manager: OpenClawProcessManager, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._manager = manager
        self._expanded = False
        self.setObjectName("gatewayTerminalDock")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        toolbar = QWidget(self)
        toolbar.setObjectName("gatewayDockToolbar")
        toolbar.setFixedHeight(self.TOOLBAR_HEIGHT)
        tl = QHBoxLayout(toolbar)
        tl.setContentsMargins(12, 2, 12, 2)
        tl.setSpacing(8)
        self._title = SubtitleLabel("OpenClaw 🦞 控制台", toolbar)
        setFont(self._title, 16)
        self._switch = SwitchButton(toolbar)
        self._switch.setOnText("运行")
        self._switch.setOffText("停止")
        self._switch.checkedChanged.connect(self._on_switch_changed)
        self._btn_fold = PushButton("展开", toolbar)
        self._btn_fold.clicked.connect(self._toggle_expand)
        tl.addWidget(self._title)
        tl.addStretch()
        tl.addWidget(self._switch)
        tl.addWidget(self._btn_fold)
        root.addWidget(toolbar)

        self._stack = QStackedWidget(self)
        self._placeholder = QWidget(self._stack)
        ph = QVBoxLayout(self._placeholder)
        ph.setContentsMargins(16, 8, 16, 8)
        ph.addWidget(BodyLabel("OpenClaw 引擎未就绪。请在此开启。Lobster is loading...", self._placeholder))
        ph.addStretch()

        self._terminal_page = QWidget(self._stack)
        tplay = QVBoxLayout(self._terminal_page)
        tplay.setContentsMargins(0, 0, 0, 0)
        tplay.setSpacing(6)
        self._editor = QPlainTextEdit(self._terminal_page)
        self._editor.setReadOnly(True)
        self._editor.setFont(QFont("Consolas", 11))
        self._editor.setStyleSheet(
            f"QPlainTextEdit {{ background-color: {UI_BG_CARD}; color: {UI_TEXT_PRIMARY}; "
            f"border: 1px solid {UI_BORDER_PURPLE_SOFT}; border-radius: 12px; padding: 8px; }}"
        )
        self._editor.setPlainText("[INFO] BoxClaw 网关引擎已就绪。\n[INFO] 正在监听底层服务...\n")
        tplay.addWidget(self._editor, 1)

        action_bar = QWidget(self._terminal_page)
        action_bar.setFixedHeight(self.ACTION_BAR_HEIGHT)
        ab = QHBoxLayout(action_bar)
        ab.setContentsMargins(0, 4, 0, 4)
        ab.setSpacing(8)
        self.btn_env = PushButton(FIF.SETTING, "一键配置运行环境", action_bar)
        self.btn_start = PrimaryPushButton(FIF.ROBOT, "启动 BoxClaw 🦞 龙虾", action_bar)
        self.btn_restart = PushButton("重启 🦞", action_bar)
        self.btn_doctor = PushButton("自动修复", action_bar)
        ab.addWidget(self.btn_env)
        ab.addWidget(self.btn_start)
        ab.addWidget(self.btn_restart)
        ab.addWidget(self.btn_doctor)
        ab.addStretch()
        tplay.addWidget(action_bar, 0)

        self._cmd = QLineEdit(self._terminal_page)
        self._cmd.setPlaceholderText("输入 OpenClaw 命令并回车...")
        self._cmd.returnPressed.connect(self._submit_command)
        tplay.addWidget(self._cmd, 0)

        self._stack.addWidget(self._placeholder)
        self._stack.addWidget(self._terminal_page)
        self._stack.setCurrentWidget(self._placeholder)
        root.addWidget(self._stack, 1)

        self.btn_env.clicked.connect(self._manager.install_environment)
        self.btn_start.clicked.connect(self._manager.start_gateway)
        self.btn_restart.clicked.connect(self._manager.restart_gateway)
        self.btn_doctor.clicked.connect(self._manager.run_doctor)

        self._manager.log_ready.connect(self.append_plain_line)
        self._manager.state_changed.connect(self._on_service_state_changed)
        self._stack.setVisible(False)
        self.setMinimumHeight(self.COLLAPSED_HEIGHT)
        self.setMaximumHeight(self.COLLAPSED_HEIGHT)

    def _on_switch_changed(self, checked: bool) -> None:
        if checked:
            self._manager.start_service()
        else:
            self._manager.stop_service()

    def _on_service_state_changed(self, running: bool) -> None:
        self._switch.blockSignals(True)
        self._switch.setChecked(running)
        self._switch.blockSignals(False)
        self._stack.setCurrentWidget(self._terminal_page if running else self._placeholder)

    def _toggle_expand(self) -> None:
        self._expanded = not self._expanded
        h = self.EXPANDED_HEIGHT if self._expanded else self.COLLAPSED_HEIGHT
        self.setMinimumHeight(h)
        self.setMaximumHeight(h)
        self._stack.setVisible(self._expanded)
        self._btn_fold.setText("收起" if self._expanded else "展开")

    def _submit_command(self) -> None:
        cmd = self._cmd.text().strip()
        if not cmd:
            return
        self._manager.send_command(cmd)
        self._cmd.clear()

    def append_plain_line(self, text: str) -> None:
        self._editor.appendPlainText(text)
        self._editor.verticalScrollBar().setValue(self._editor.verticalScrollBar().maximum())
        if self._stack.currentWidget() is self._placeholder:
            self._stack.setCurrentWidget(self._terminal_page)

    def append_log(self, html: str) -> None:
        plain = re.sub(r"<[^>]+>", "", html)
        self.append_plain_line(plain)


IntegratedConsoleDock = GatewayTerminalDock

# ---------------------------------------------------------------------------
# 主窗口 + 托盘
# ---------------------------------------------------------------------------
class BoxClawWindow(_BaseMainWindow):
    """本地服务网关可视化控制台：启动即登录。macOS=SplitFluentWindow；其他=MSFluentWindow。"""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("BoxClaw🦞抖音矩阵控制台—by尖叫")
        self.resize(1280, 800)
        self.setWindowIcon(QIcon())
        self._polish_title_bar_chrome()

        if sys.platform == "darwin":
            self._configure_macos_title_bar()

        self._matrix_core = DouyinAutomationCore(self)
        self._openclaw_manager = OpenClawProcessManager(self)

        self._repack_stack_with_terminal()

        self.home_welcome = HomeWelcomePage(self)
        self.openclaw_web = OpenClawWebPage(self, self._openclaw_manager)
        self.matrix = MatrixPage(self, self._matrix_core)
        self.settings = SettingsPage(self, self._openclaw_manager)

        self._console = GatewayTerminalDock(self._openclaw_manager, self._terminal_panel)
        tlay = QVBoxLayout(self._terminal_panel)
        tlay.setContentsMargins(0, 0, 0, 0)
        tlay.setSpacing(0)
        tlay.addWidget(self._console)

        self._load_matrix_accounts_from_disk()

        QApplication.instance().aboutToQuit.connect(self._openclaw_manager.stop_service)
        _cfg = read_openclaw_config_file()
        if _cfg.get("gateway_autostart"):
            QTimer.singleShot(900, self._openclaw_manager.start_service)

        self._apply_dark_claw_palette()
        self._configure_navigation_chrome()
        self._inject_brand()
        self._init_nav()
        self._init_tray()

    def _apply_dark_claw_palette(self) -> None:
        """暗夜紫主壳：紫灰底、大圆角、淡紫边与多色点缀；矩阵区仅容器样式，不改动 WebView 沙盒。"""
        if hasattr(self, "setCustomBackgroundColor"):
            self.setCustomBackgroundColor(UI_BG_ROOT, UI_BG_ROOT)
        self.setStyleSheet(
            f"""
            QWidget {{
                color: {UI_TEXT_PRIMARY};
            }}
            QWidget#rightColumnHost {{
                background-color: {UI_BG_ROOT};
            }}
            QWidget#boxclawNavPanel {{
                background-color: {UI_NAV_BG};
                border-right: 1px solid {UI_BORDER_PURPLE_SOFT};
            }}
            QWidget#terminalPanelHost {{
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 {UI_BG_ELEVATED}, stop:1 {UI_BG_CARD});
                border-top: 1px solid {UI_BORDER_PURPLE_SOFT};
                border-top-left-radius: 16px;
                border-top-right-radius: 16px;
            }}
            QWidget#gatewayDockToolbar {{
                background-color: {UI_BG_CARD_SOFT};
                border-bottom: 1px solid {UI_BORDER_PURPLE_SOFT};
            }}
            QLabel, SubtitleLabel, BodyLabel, TitleLabel {{
                color: {UI_TEXT_PRIMARY};
            }}
            QFrame#homeDashCard {{
                background-color: {UI_BG_CARD};
                border: 1px solid {UI_BORDER_PURPLE_SOFT};
                border-radius: 18px;
            }}
            QFrame#homeDashStripe {{
                border-radius: 5px;
                min-width: 5px;
                max-width: 5px;
            }}
            QFrame#openclawWebBar {{
                background-color: {UI_BG_CARD_SOFT};
                border: 1px solid {UI_BORDER_PURPLE_SOFT};
                border-radius: 14px;
            }}
            QFrame#openclawPresetBox {{
                background: {UI_BG_CARD_SOFT};
                border: 1px solid {UI_BORDER_PURPLE_SOFT};
                border-radius: 14px;
            }}
            QWidget#matrix_container {{
                background: transparent;
                border: 1px solid {UI_BORDER_PURPLE_SOFT};
                border-radius: 16px;
            }}
            SubtitleLabel#matrixPageTitle {{
                color: {UI_TEXT_PRIMARY};
                font-weight: 600;
            }}
            QPlainTextEdit, QTextEdit, QLineEdit {{
                background: {UI_BG_CARD};
                color: {UI_TEXT_PRIMARY};
                border: 1px solid {UI_BORDER_PURPLE_SOFT};
                border-radius: 11px;
                padding: 6px 10px;
                selection-background-color: {UI_ACCENT_DEEP};
                selection-color: #faf5ff;
            }}
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollArea > QWidget > QWidget {{
                background: transparent;
            }}
            QComboBox, ComboBox {{
                background: {UI_BG_CARD};
                color: {UI_TEXT_PRIMARY};
                border: 1px solid {UI_BORDER_PURPLE_SOFT};
                border-radius: 10px;
                padding: 5px 10px;
            }}
            QComboBox:hover, ComboBox:hover {{
                border-color: {UI_BORDER_PURPLE};
            }}
            QRadioButton {{
                color: {UI_TEXT_PRIMARY};
                spacing: 8px;
            }}
            QStackedWidget {{
                background: transparent;
            }}
            PrimaryPushButton {{
                background-color: {UI_ACCENT_DEEP};
                border: none;
                border-radius: 12px;
                padding: 8px 18px;
                color: #faf5ff;
                font-weight: 600;
            }}
            PrimaryPushButton:hover {{
                background-color: #9333ea;
            }}
            PrimaryPushButton:pressed {{
                background-color: #7e22ce;
            }}
            PushButton {{
                background-color: {UI_BG_CARD_SOFT};
                border: 1px solid {UI_BORDER_PURPLE_SOFT};
                border-radius: 11px;
                padding: 6px 14px;
                color: {UI_TEXT_PRIMARY};
            }}
            PushButton:hover {{
                background-color: {UI_BG_ELEVATED};
                border-color: {UI_BORDER_PURPLE};
            }}
            """
        )

    def _repack_stack_with_terminal(self) -> None:
        self._right_column = QWidget(self)
        self._right_column.setObjectName("rightColumnHost")
        self._right_column_layout = QVBoxLayout(self._right_column)
        self._right_column_layout.setContentsMargins(0, 0, 0, 0)
        self._right_column_layout.setSpacing(0)
        self._terminal_panel = QWidget(self._right_column)
        self._terminal_panel.setObjectName("terminalPanelHost")
        self._right_column_layout.addWidget(self.stackedWidget, stretch=1)
        self._right_column_layout.addWidget(self._terminal_panel, 0)

        wl = getattr(self, "widgetLayout", None)
        if wl is not None:
            wl.removeWidget(self.stackedWidget)
            wl.addWidget(self._right_column, 1)
        else:
            self.hBoxLayout.removeWidget(self.stackedWidget)
            self.hBoxLayout.addWidget(self._right_column, 1)

    def _load_matrix_accounts_from_disk(self) -> None:
        PROFILES_BASE_DIR.mkdir(parents=True, exist_ok=True)
        existing = sorted(
            [p.name for p in PROFILES_BASE_DIR.iterdir() if p.is_dir()],
            key=lambda s: s.lower(),
        )
        for dn in existing:
            if dn not in self._matrix_core.dir_to_display:
                self._matrix_core.register_account(dn, dn)

    def _polish_title_bar_chrome(self) -> None:
        """去掉顶栏图标与标题文案：品牌仅在左侧导航展示，避免与侧栏重复。"""
        tb = self.titleBar
        if hasattr(tb, "iconLabel"):
            tb.iconLabel.hide()
        tl = getattr(tb, "titleLabel", None)
        if tl is not None:
            tl.hide()

    def _configure_macos_title_bar(self) -> None:
        """无边框窗口在 macOS 上使用系统交通灯，隐藏库自带的右侧最小化/最大化/关闭。"""
        self.setSystemTitleBarButtonVisible(True)
        tb = self.titleBar
        for attr in ("minBtn", "maxBtn", "closeBtn"):
            b = getattr(tb, attr, None)
            if b is not None:
                b.hide()
        if hasattr(tb, "hBoxLayout"):
            m = tb.hBoxLayout.contentsMargins()
            tb.hBoxLayout.setContentsMargins(max(m.left(), 8), m.top(), max(m.right(), 12), m.bottom())

    def _configure_navigation_chrome(self) -> None:
        nav = self.navigationInterface
        if hasattr(nav, "setExpandWidth"):
            nav.setExpandWidth(220)
        if hasattr(nav, "setMinimumExpandWidth"):
            nav.setMinimumExpandWidth(640)
        if hasattr(nav, "setAcrylicEnabled"):
            nav.setAcrylicEnabled(True)
        # 收紧侧栏上下留白，减少「菜单区」与顶栏之间的空洞感
        if isinstance(nav, NavigationInterface):
            panel = nav.panel
            panel.setObjectName("boxclawNavPanel")
            panel.vBoxLayout.setContentsMargins(0, 0, 0, 4)
            panel.topLayout.setContentsMargins(6, 0, 6, 0)
            panel.scrollLayout.setContentsMargins(4, 0, 4, 0)
            # 返回多在子路由才用，默认隐藏，避免与汉堡菜单各占一行显得杂乱
            panel.returnButton.hide()

    def _inject_brand(self) -> None:
        """侧栏品牌区：放入滚动区首项，与主导航紧邻，避免顶栏区纵向堆叠过高。"""
        nav = self.navigationInterface
        if not isinstance(nav, NavigationInterface):
            return
        panel = nav.panel
        brand = QWidget(panel.scrollWidget)
        brand.setObjectName("navBrandHost")
        vl = QVBoxLayout(brand)
        vl.setContentsMargins(12, 0, 12, 10)
        vl.setSpacing(2)
        title = SubtitleLabel("BoxClaw 🦞", brand)
        setFont(title, 15)
        title.setWordWrap(False)
        title.setStyleSheet(f"color: {UI_TEXT_PRIMARY};")
        sub = BodyLabel("抖音矩阵控制台 · by尖叫", brand)
        setFont(sub, 11)
        sub.setStyleSheet(f"color: {UI_TEXT_MUTED};")
        sub.setWordWrap(True)
        line = QFrame(brand)
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(2)
        line.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:1,y2:0, "
            f"stop:0 {UI_ACCENT_DEEP}, stop:0.55 {UI_ACCENT}, stop:1 transparent); "
            f"border: none; max-height: 2px; min-height: 2px;"
        )
        vl.addWidget(title)
        vl.addWidget(sub)
        vl.addSpacing(8)
        vl.addWidget(line)
        # 与首页、龙虾控制台同一滚动列，主导航紧跟品牌区下方
        panel.scrollLayout.insertWidget(0, brand)

    def _init_nav(self) -> None:
        pos = NavigationItemPosition.SCROLL

        # 图标须为 QIcon：传 str 时库会 QIcon(路径)，emoji 会被当成无效路径而空白
        self.addSubInterface(self.home_welcome, emoji_navigation_icon("🏠"), "首页", pos)
        self.addSubInterface(self.openclaw_web, emoji_navigation_icon("🦞"), "龙虾控制台", pos)
        self.addSubInterface(self.matrix, emoji_navigation_icon("📱"), "抖音矩阵", pos)

        self.addSubInterface(
            self.settings, emoji_navigation_icon("⚙️"), "系统设置", NavigationItemPosition.BOTTOM
        )

        qrouter.setDefaultRouteKey(self.stackedWidget, self.home_welcome.objectName())
        self.switchTo(self.home_welcome)

        self.stackedWidget.currentChanged.connect(self._on_stack_interface_changed)

        nav = self.navigationInterface
        if hasattr(nav, "setCollapsible"):
            nav.setCollapsible(False)
        if hasattr(nav, "expand"):
            nav.expand(useAni=False)

    def _on_stack_interface_changed(self, index: int) -> None:
        """仅在进入「龙虾控制台」时创建 WebEngine，避免启动阶段加载 Chromium 导致 Windows 闪退。"""
        w = self.stackedWidget.widget(index)
        if w is self.openclaw_web:
            self.openclaw_web.ensure_webview()

    def _init_tray(self) -> None:
        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(FIF.ROBOT.qicon())
        self._tray.setToolTip("BoxClaw🦞抖音矩阵控制台—by尖叫")
        menu = QMenu()
        show_act = QAction("显示主界面", self)
        show_act.triggered.connect(self._show_main)
        quit_act = QAction("完全退出", self)
        quit_act.triggered.connect(QApplication.instance().quit)
        menu.addAction(show_act)
        menu.addSeparator()
        menu.addAction(quit_act)
        self._tray.setContextMenu(menu)
        self._tray.show()
        self._tray.activated.connect(self._on_tray)

    def _show_main(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _on_tray(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_main()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.hide()
        event.ignore()


def main() -> None:
    # QtWebEngine 与其它 OpenGL 组件共存时必须在 QApplication 之前设置（降低 macOS 随机闪退）
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
    if sys.platform == "darwin":
        # 可按需取消注释排查 GPU/沙箱相关崩溃
        # os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
        # 减轻后台/休眠时 Chromium 定时器与 WebView 的竞态（可按需调整或清空）
        os.environ.setdefault(
            "QTWEBENGINE_CHROMIUM_FLAGS",
            "--disable-background-timer-throttling",
        )
    elif sys.platform == "win32":
        # Windows 下打包或部分环境 Chromium 子进程沙箱会导致进程立即退出（表现为双击 exe 闪退）
        os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

    app = QApplication(sys.argv)
    app.setApplicationName("BoxClaw🦞抖音矩阵控制台—by尖叫")
    app.setOrganizationName("BoxClaw")
    app.setQuitOnLastWindowClosed(False)

    # 全局暗夜主题（Fluent Dark + 壳体自定义深色样式）
    setTheme(Theme.DARK, save=False)

    win = BoxClawWindow()
    win.show()

    if sys.platform == "win32":
        try:
            win.setMicaEffectEnabled(True)
        except Exception:
            pass

    sys.exit(app.exec())


def _write_startup_crash_log() -> Path:
    base = Path.home() / ".boxclaw"
    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError:
        base = Path.home()
    log = base / "startup_error.log"
    try:
        import traceback

        log.write_text(traceback.format_exc(), encoding="utf-8")
    except OSError:
        pass
    return log


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log_path = _write_startup_crash_log()
        if sys.platform == "win32":
            try:
                import ctypes

                ctypes.windll.user32.MessageBoxW(
                    0,
                    f"启动失败，详情见：\n{log_path}",
                    "BoxClaw",
                    0x10,
                )
            except Exception:
                pass
        raise
