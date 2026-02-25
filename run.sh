#!/bin/bash
# -*- coding: utf-8 -*-
# Personal AI Assistant 启动脚本

cd "$(dirname "$0")" || exit 1

# 检查 uv 是否安装
if ! command -v uv &> /dev/null; then
    echo "❌ 未安装 uv，请先安装: https://docs.astral.sh/uv/"
    exit 1
fi

# 初始化环境（如果不存在）
if [ ! -d ".venv" ]; then
    echo "🔄 初始化虚拟环境..."
    uv venv
fi

# 安装/同步依赖
echo "🔄 同步依赖..."
uv sync

# 运行主程序
echo "🚀 启动 Personal AI Assistant..."
uv run python src/main.py "$@"
