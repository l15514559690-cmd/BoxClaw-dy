"""知识库：本地 Markdown 文件夹浏览与编辑。"""

from __future__ import annotations

import os

from PySide6.QtCore import QDir, QModelIndex, Qt, QStandardPaths
from PySide6.QtWidgets import (
    QFileDialog,
    QFileSystemModel,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QTreeView,
    QVBoxLayout,
    QWidget,
)


class KnowledgePage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_file: str | None = None
        self._dirty = False

        root = self._default_knowledge_root()
        os.makedirs(root, exist_ok=True)

        self._model = QFileSystemModel(self)
        self._model.setRootPath(root)
        self._model.setNameFilters(["*.md", "*.markdown"])
        self._model.setNameFilterDisables(False)
        self._model.setFilter(QDir.Filter.AllDirs | QDir.Filter.Files | QDir.Filter.NoDotAndDotDot)

        self._tree = QTreeView()
        self._tree.setModel(self._model)
        self._tree.setRootIndex(self._model.index(root))
        self._tree.setHeaderHidden(True)
        for col in range(1, self._model.columnCount()):
            self._tree.hideColumn(col)
        self._tree.setAnimated(True)
        self._tree.setIndentation(14)

        self._editor = QTextEdit()
        self._editor.setPlaceholderText("选择左侧 .md 文件，或新建后在此编辑…")
        self._editor.textChanged.connect(self._on_text_changed)

        btn_row = QHBoxLayout()
        self._btn_pick = QPushButton("选择知识库根目录…")
        self._btn_pick.setObjectName("SecondaryButton")
        self._btn_pick.clicked.connect(self._pick_root)
        self._btn_new = QPushButton("新建 Markdown")
        self._btn_new.setObjectName("SecondaryButton")
        self._btn_new.clicked.connect(self._new_file)
        self._btn_save = QPushButton("保存")
        self._btn_save.setObjectName("PrimaryButton")
        self._btn_save.clicked.connect(self._save_current)

        btn_row.addWidget(self._btn_pick)
        btn_row.addWidget(self._btn_new)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_save)

        right = QVBoxLayout()
        right.addWidget(QLabel("Markdown 内容"))
        right.addWidget(self._editor)
        right.addLayout(btn_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        left_wrap = QWidget()
        lv = QVBoxLayout(left_wrap)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.addWidget(QLabel("本地文件"))
        lv.addWidget(self._tree)
        splitter.addWidget(left_wrap)
        rw = QWidget()
        rv = QVBoxLayout(rw)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.addLayout(right)
        splitter.addWidget(rw)
        splitter.setSizes([320, 720])

        layout = QVBoxLayout(self)
        layout.addWidget(splitter)

        self._tree.clicked.connect(self._on_tree_clicked)
        self._root_path = root

    def _default_knowledge_root(self) -> str:
        base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        return os.path.join(base, "BoxClaw", "knowledge")

    def _on_tree_clicked(self, index: QModelIndex) -> None:
        if not index.isValid():
            return
        path = self._model.filePath(index)
        if os.path.isdir(path):
            return
        if not self._maybe_discard():
            return
        self._load_file(path)

    def _load_file(self, path: str) -> None:
        self._current_file = path
        self._dirty = False
        self._editor.blockSignals(True)
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                self._editor.setPlainText(f.read())
        except OSError as e:
            QMessageBox.warning(self, "读取失败", str(e))
            self._editor.clear()
        finally:
            self._editor.blockSignals(False)

    def _on_text_changed(self) -> None:
        self._dirty = True

    def _maybe_discard(self) -> bool:
        if not self._dirty:
            return True
        r = QMessageBox.question(
            self,
            "未保存的更改",
            "当前内容尚未保存，是否放弃更改？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return r == QMessageBox.StandardButton.Yes

    def _save_current(self) -> None:
        if not self._current_file:
            path, _ = QFileDialog.getSaveFileName(
                self,
                "保存 Markdown",
                self._root_path,
                "Markdown (*.md *.markdown)",
            )
            if not path:
                return
            self._current_file = path
        try:
            with open(self._current_file, "w", encoding="utf-8") as f:
                f.write(self._editor.toPlainText())
            self._dirty = False
            self._model.refresh(self._model.index(self._root_path))
        except OSError as e:
            QMessageBox.critical(self, "保存失败", str(e))

    def _new_file(self) -> None:
        if not self._maybe_discard():
            return
        self._current_file = None
        self._dirty = False
        self._editor.blockSignals(True)
        self._editor.clear()
        self._editor.blockSignals(False)

    def _pick_root(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "选择知识库根目录", self._root_path)
        if not d:
            return
        self._root_path = d
        self._model.setRootPath(d)
        self._tree.setRootIndex(self._model.index(d))
        self._current_file = None
        self._dirty = False
        self._editor.clear()
