"""BoxClaw 主窗口：侧边栏 + 堆叠页面 + 系统托盘。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QCloseEvent, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from boxclaw.pages import (
    BoxClawChatPage,
    ImageGenPage,
    KnowledgePage,
    MatrixPage,
    SettingsPage,
    VideoGenPage,
)
from boxclaw.styles import BOXCLAW_QSS


def _app_icon() -> QIcon:
    pm = QPixmap(64, 64)
    pm.fill(QColor("#6366F1"))
    return QIcon(pm)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("BoxClaw")
        self.setWindowIcon(_app_icon())
        self.resize(1280, 800)
        self.setMinimumSize(960, 600)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(220)
        s_layout = QVBoxLayout(sidebar)
        s_layout.setContentsMargins(12, 20, 12, 20)
        s_layout.setSpacing(4)

        brand = QLabel("BoxClaw")
        brand.setStyleSheet("font-size: 18px; font-weight: 700; color: #FAFAFA; padding-bottom: 8px;")
        s_layout.addWidget(brand)
        sub = QLabel("本地网关 · 控制台")
        sub.setStyleSheet("font-size: 11px; color: #71717A; padding-bottom: 16px;")
        s_layout.addWidget(sub)

        self._stack = QStackedWidget()
        self._pages: list[tuple[str, QWidget]] = [
            ("知识库", KnowledgePage()),
            ("图文生成", ImageGenPage()),
            ("视频生成", VideoGenPage()),
            ("账号矩阵", MatrixPage()),
            ("BoxClaw 对话", BoxClawChatPage()),
            ("设置", SettingsPage()),
        ]
        for _, w in self._pages:
            self._stack.addWidget(w)

        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)
        for i, (title, _) in enumerate(self._pages):
            btn = QPushButton(title)
            btn.setObjectName("NavButton")
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            btn.setMinimumHeight(40)
            self._nav_group.addButton(btn, i)
            btn.clicked.connect(lambda checked=False, idx=i: self._stack.setCurrentIndex(idx))
            s_layout.addWidget(btn)
        s_layout.addStretch()

        first = self._nav_group.button(0)
        if first:
            first.setChecked(True)

        root.addWidget(sidebar)
        root.addWidget(self._stack, stretch=1)

        self.setStyleSheet(BOXCLAW_QSS)

        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(_app_icon())
        self._tray.setToolTip("BoxClaw — 本地网关运行中")
        self._setup_tray_menu()
        self._tray.show()

        self._tray.activated.connect(self._on_tray_activated)

    def _setup_tray_menu(self) -> None:
        menu = QMenu(self)
        act_show = QAction("显示主界面", self)
        act_show.triggered.connect(self._show_from_tray)
        act_quit = QAction("完全退出", self)
        act_quit.triggered.connect(QApplication.instance().quit)
        menu.addAction(act_show)
        menu.addSeparator()
        menu.addAction(act_quit)
        self._tray.setContextMenu(menu)

    def _show_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_from_tray()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.hide()
        event.ignore()
