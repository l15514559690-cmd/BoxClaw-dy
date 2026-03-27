"""BoxClaw 对话 — OpenClaw 对话中枢（骨架）。"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class BoxClawChatPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._stream = QWidget()
        self._stream_layout = QVBoxLayout(self._stream)
        self._stream_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._stream_layout.setSpacing(12)
        self._scroll.setWidget(self._stream)

        self._add_placeholder_bubbles()

        self._input = QTextEdit()
        self._input.setPlaceholderText("输入消息… (Shift+Enter 换行)")
        self._input.setFixedHeight(100)
        self._input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._send = QPushButton("发送")
        self._send.setObjectName("PrimaryButton")
        self._send.setFixedWidth(96)
        self._send.clicked.connect(self._on_send)

        bottom = QHBoxLayout()
        bottom.addWidget(self._input, stretch=1)
        bottom.addWidget(self._send, alignment=Qt.AlignmentFlag.AlignBottom)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.addWidget(self._scroll, stretch=1)
        layout.addLayout(bottom)

    def _add_placeholder_bubbles(self) -> None:
        user = QLabel("你：后续在此接入 OpenClaw 流式输出与历史。")
        user.setWordWrap(True)
        user.setStyleSheet(
            "background: #27272A; border-radius: 10px; padding: 10px 12px; color: #E4E4E7;"
        )
        user.setMaximumWidth(560)
        row_u = QHBoxLayout()
        row_u.addStretch()
        row_u.addWidget(user)

        bot = QLabel("BoxClaw：网关就绪后，消息将经本地 OpenClaw 路由。")
        bot.setWordWrap(True)
        bot.setStyleSheet(
            "background: rgba(99, 102, 241, 0.12); border-radius: 10px; padding: 10px 12px; color: #C7D2FE;"
        )
        bot.setMaximumWidth(560)
        row_b = QHBoxLayout()
        row_b.addWidget(bot)
        row_b.addStretch()

        self._stream_layout.addLayout(row_u)
        self._stream_layout.addLayout(row_b)

    def _on_send(self) -> None:
        text = self._input.toPlainText().strip()
        if not text:
            return
        lab = QLabel(f"你：{text}")
        lab.setWordWrap(True)
        lab.setStyleSheet(
            "background: #27272A; border-radius: 10px; padding: 10px 12px; color: #E4E4E7;"
        )
        lab.setMaximumWidth(560)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(lab)
        self._stream_layout.addLayout(row)
        self._input.clear()
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        bar = self._scroll.verticalScrollBar()
        bar.setValue(bar.maximum())
