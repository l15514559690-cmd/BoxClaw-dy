"""账号矩阵 — 预留嵌入 douyin-boxclaw 模块。"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class MatrixPage(QWidget):
    """`embed_layout` 为后续整体嵌入 QWebEngineView / 子模块的干净容器。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        host = QWidget()
        self.embed_layout = QVBoxLayout(host)
        self.embed_layout.setContentsMargins(24, 24, 24, 24)

        hint = QLabel("账号矩阵模块加载区 (待对接 douyin-boxclaw)")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("font-size: 16px; color: #A1A1AA;")
        self.embed_layout.addStretch()
        self.embed_layout.addWidget(hint)
        self.embed_layout.addStretch()

        outer.addWidget(host)
