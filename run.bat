@echo off
chcp 65001 >nul
:: Personal AI Assistant 启动脚本 (Windows)

cd /d "%~dp0"

:: 检查 uv 是否安装
where uv >nul 2>nul
if %errorlevel% neq 0 (
    echo ❌ 未安装 uv，请先安装: https://docs.astral.sh/uv/
    exit /b 1
)

:: 初始化环境（如果不存在）
if not exist ".venv" (
    echo 🔄 初始化虚拟环境...
    uv venv
)

:: 安装/同步依赖
echo 🔄 同步依赖...
uv sync

:: 运行主程序
echo 🚀 启动 Personal AI Assistant...
uv run python src/main.py %*
