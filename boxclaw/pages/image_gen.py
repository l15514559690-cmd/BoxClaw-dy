"""图文生成 — Skills 预留页。"""

from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class ImageGenPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        title = QLabel("图文生成 (Skills 预留)")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #E4E4E7;")

        hint = QLabel("后续可在此对接图文生成 Skills / 工作流。")
        hint.setStyleSheet("color: #71717A;")

        form = QFormLayout()
        self._prompt = QLineEdit()
        self._prompt.setPlaceholderText("提示词 / 主题占位…")
        self._style = QLineEdit()
        self._style.setPlaceholderText("风格 / 比例等参数占位…")
        form.addRow("参数 A", self._prompt)
        form.addRow("参数 B", self._style)

        extra = QTextEdit()
        extra.setPlaceholderText("扩展说明（占位）…")
        extra.setMaximumHeight(120)

        box = QGroupBox("参数占位")
        inner = QVBoxLayout(box)
        inner.addLayout(form)
        inner.addWidget(extra)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addWidget(box)
        layout.addStretch()
