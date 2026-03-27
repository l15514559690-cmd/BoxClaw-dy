"""Global QSS for BoxClaw (Modern SaaS dark theme)."""

BOXCLAW_QSS = """
QMainWindow, QWidget {
    background-color: #09090B;
    color: #E4E4E7;
    font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    font-size: 13px;
}

QFrame#Sidebar {
    background-color: #121214;
    border: none;
}

QLabel {
    color: #E4E4E7;
}

QPushButton#NavButton {
    text-align: left;
    padding: 10px 14px 10px 18px;
    border: none;
    border-radius: 8px;
    color: #A1A1AA;
    background-color: transparent;
}

QPushButton#NavButton:hover {
    background-color: rgba(255, 255, 255, 0.04);
    color: #D4D4D8;
}

QPushButton#NavButton:checked {
    background-color: rgba(99, 102, 241, 0.15);
    color: #818CF8;
    border-left: 3px solid #6366F1;
    padding-left: 15px;
}

QStackedWidget {
    background-color: #09090B;
}

QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #18181B;
    border: 1px solid #27272A;
    border-radius: 8px;
    padding: 8px 10px;
    color: #FAFAFA;
    selection-background-color: #6366F1;
}

QLineEdit::placeholder, QTextEdit::placeholder, QPlainTextEdit::placeholder {
    color: #71717A;
}

QTreeView {
    background-color: #18181B;
    border: 1px solid #27272A;
    border-radius: 8px;
    color: #E4E4E7;
    alternate-background-color: #1C1C1F;
    outline: none;
}

QTreeView::item {
    padding: 4px;
}

QTreeView::item:selected {
    background-color: rgba(99, 102, 241, 0.25);
    color: #E0E7FF;
}

QScrollArea {
    border: none;
    background-color: #09090B;
}

QScrollBar:vertical {
    background: #18181B;
    width: 10px;
    border-radius: 5px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #3F3F46;
    border-radius: 5px;
    min-height: 24px;
}

QScrollBar::handle:vertical:hover {
    background: #52525B;
}

QScrollBar:horizontal {
    background: #18181B;
    height: 10px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal {
    background: #3F3F46;
    border-radius: 5px;
    min-width: 24px;
}

QComboBox {
    background-color: #18181B;
    border: 1px solid #27272A;
    border-radius: 8px;
    padding: 8px 10px;
    color: #FAFAFA;
    min-height: 20px;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background-color: #18181B;
    color: #FAFAFA;
    selection-background-color: rgba(99, 102, 241, 0.35);
}

QCheckBox {
    color: #E4E4E7;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #3F3F46;
    background-color: #18181B;
}

QCheckBox::indicator:checked {
    background-color: #6366F1;
    border-color: #6366F1;
}

QFormLayout QLabel {
    color: #A1A1AA;
}

QPushButton#PrimaryButton {
    background-color: #6366F1;
    color: #FAFAFA;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: 600;
}

QPushButton#PrimaryButton:hover {
    background-color: #4F46E5;
}

QPushButton#SecondaryButton {
    background-color: #27272A;
    color: #E4E4E7;
    border: 1px solid #3F3F46;
    border-radius: 8px;
    padding: 8px 16px;
}

QPushButton#SecondaryButton:hover {
    background-color: #3F3F46;
}

QGroupBox {
    border: 1px solid #27272A;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 8px;
    font-weight: 600;
    color: #A1A1AA;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}

QMenu {
    background-color: #18181B;
    border: 1px solid #27272A;
    color: #E4E4E7;
    padding: 4px;
}

QMenu::item:selected {
    background-color: rgba(99, 102, 241, 0.25);
}

QToolTip {
    background-color: #27272A;
    color: #FAFAFA;
    border: 1px solid #3F3F46;
    padding: 6px;
    border-radius: 4px;
}
"""
