"""视频生成 — Skills 预留页。"""

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class VideoGenPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        title = QLabel("视频生成 (Skills 预留)")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #E4E4E7;")

        hint = QLabel("工作流占位：后续可对接脚本节点、分镜、渲染队列等。")
        hint.setStyleSheet("color: #71717A;")

        self._step1 = QLineEdit()
        self._step1.setPlaceholderText("步骤 1：脚本 / 分镜（占位）")
        self._step2 = QLineEdit()
        self._step2.setPlaceholderText("步骤 2：素材 / 参考（占位）")
        self._step3 = QTextEdit()
        self._step3.setPlaceholderText("步骤 3：备注与队列（占位）…")
        self._step3.setMaximumHeight(100)

        run_row = QHBoxLayout()
        self._btn_run = QPushButton("运行工作流（占位）")
        self._btn_run.setObjectName("PrimaryButton")
        self._btn_run.setEnabled(False)
        run_row.addStretch()
        run_row.addWidget(self._btn_run)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addWidget(QLabel("步骤"))
        layout.addWidget(self._step1)
        layout.addWidget(self._step2)
        layout.addWidget(self._step3)
        layout.addLayout(run_row)
        layout.addStretch()
