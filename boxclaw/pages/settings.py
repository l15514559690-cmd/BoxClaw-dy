"""设置 — 模型/网关与 OpenClaw 预设（QSettings + 可选 JSON 镜像）。"""

from __future__ import annotations

import json
import os

from PySide6.QtCore import QSettings, QStandardPaths
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class SettingsPage(QWidget):
    KEY_API = "gateway/api_key"
    KEY_BASE = "gateway/base_url"
    KEY_MODEL = "gateway/model_name"
    KEY_PRESET = "openclaw/preset_mode"
    KEY_SHORT_VIDEO = "openclaw/short_video_script"
    KEY_PLAIN_TEXT = "openclaw/plain_text_mode"
    KEY_EXTRA_A = "openclaw/extra_behavior_a"
    KEY_EXTRA_B = "openclaw/extra_behavior_b"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = QSettings("BoxClaw", "BoxClaw")

        self._api = QLineEdit()
        self._api.setEchoMode(QLineEdit.EchoMode.Password)
        self._api.setPlaceholderText("API Key")
        self._base = QLineEdit()
        self._base.setPlaceholderText("https://…")
        self._model = QLineEdit()
        self._model.setPlaceholderText("自定义模型名称")

        self._preset = QComboBox()
        self._preset.addItems(
            [
                "默认",
                "短视频脚本模式",
                "纯文本模式",
                "长文创作模式",
                "代码助手模式",
            ]
        )

        self._cb_short = QCheckBox("短视频脚本模式（预设行为）")
        self._cb_plain = QCheckBox("纯文本模式（预设行为）")
        self._cb_extra_a = QCheckBox("附加行为 A（占位）")
        self._cb_extra_b = QCheckBox("附加行为 B（占位）")

        form_gateway = QFormLayout()
        form_gateway.addRow("API Key", self._api)
        form_gateway.addRow("Base URL", self._base)
        form_gateway.addRow("模型名称", self._model)

        box_g = QGroupBox("模型与网关")
        box_g.setLayout(form_gateway)

        form_preset = QFormLayout()
        form_preset.addRow("预设模式（下拉）", self._preset)
        box_p = QGroupBox("预设选项")
        pv = QVBoxLayout(box_p)
        pv.addLayout(form_preset)
        pv.addWidget(self._cb_short)
        pv.addWidget(self._cb_plain)
        pv.addWidget(self._cb_extra_a)
        pv.addWidget(self._cb_extra_b)

        self._btn_save = QPushButton("保存设置")
        self._btn_save.setObjectName("PrimaryButton")
        self._btn_save.clicked.connect(self._save)

        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(self._btn_save)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("全部图形化配置，无需命令行。"))
        layout.addWidget(box_g)
        layout.addWidget(box_p)
        layout.addLayout(row)
        layout.addStretch()

        self._load()

    def _json_path(self) -> str:
        loc = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        return os.path.join(loc, "BoxClaw", "settings.json")

    def _load(self) -> None:
        self._api.setText(self._settings.value(self.KEY_API, "", str))
        self._base.setText(self._settings.value(self.KEY_BASE, "", str))
        self._model.setText(self._settings.value(self.KEY_MODEL, "", str))
        idx = int(self._settings.value(self.KEY_PRESET, 0, int))
        self._preset.setCurrentIndex(max(0, min(idx, self._preset.count() - 1)))
        self._cb_short.setChecked(self._settings.value(self.KEY_SHORT_VIDEO, False, bool))
        self._cb_plain.setChecked(self._settings.value(self.KEY_PLAIN_TEXT, False, bool))
        self._cb_extra_a.setChecked(self._settings.value(self.KEY_EXTRA_A, False, bool))
        self._cb_extra_b.setChecked(self._settings.value(self.KEY_EXTRA_B, False, bool))

    def _save(self) -> None:
        self._settings.setValue(self.KEY_API, self._api.text())
        self._settings.setValue(self.KEY_BASE, self._base.text())
        self._settings.setValue(self.KEY_MODEL, self._model.text())
        self._settings.setValue(self.KEY_PRESET, self._preset.currentIndex())
        self._settings.setValue(self.KEY_SHORT_VIDEO, self._cb_short.isChecked())
        self._settings.setValue(self.KEY_PLAIN_TEXT, self._cb_plain.isChecked())
        self._settings.setValue(self.KEY_EXTRA_A, self._cb_extra_a.isChecked())
        self._settings.setValue(self.KEY_EXTRA_B, self._cb_extra_b.isChecked())
        self._settings.sync()

        path = self._json_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = {
            "api_key": self._api.text(),
            "base_url": self._base.text(),
            "model_name": self._model.text(),
            "preset_index": self._preset.currentIndex(),
            "preset_label": self._preset.currentText(),
            "behaviors": {
                "short_video_script": self._cb_short.isChecked(),
                "plain_text": self._cb_plain.isChecked(),
                "extra_a": self._cb_extra_a.isChecked(),
                "extra_b": self._cb_extra_b.isChecked(),
            },
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            QMessageBox.warning(self, "JSON 镜像保存失败", str(e))
            return

        QMessageBox.information(self, "已保存", "设置已写入 QSettings，并已镜像到本地 JSON。")
