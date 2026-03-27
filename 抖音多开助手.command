#!/bin/bash
# macOS 一键启动（与「一键启动.command」等价，保留旧文件名）
# ============================================================
cd "$(dirname "$0")"

if ! python3 -c "import PySide6; import qfluentwidgets" 2>/dev/null; then
    echo "首次运行，正在安装依赖（仅需一次）..."
    python3 -m pip install -q -r requirements.txt || {
        echo "依赖安装失败，请执行: pip3 install -r requirements.txt"
        read -r _
        exit 1
    }
fi

exec python3 boxclaw_main.py
