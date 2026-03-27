#!/bin/bash
# ============================================================
#   macOS 版一键启动器
#   BoxClaw（含嵌入的抖音矩阵）— 双击运行（无需打包 .app）
#   单文件入口：boxclaw_main.py（含抖音矩阵 + Fluent 外壳）
#   需本机已安装 Python 3.9+（首次运行会自动 pip 安装依赖）
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
