@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 打包 exe - 账单合并工具

REM ============================================================
REM   把本项目打包成单文件 exe (dist\账单合并工具.exe)
REM   首次打包约 2-5 分钟,需要已安装 pyinstaller:
REM       pip install pyinstaller
REM ============================================================

echo.
echo 开始打包(首次约 2-5 分钟,请耐心等待)...
echo.

python -m PyInstaller bill_consensus_exe.spec --noconfirm --clean

if errorlevel 1 (
    echo.
    echo ============================================================
    echo   [失败] 打包出错,请检查上方日志。
    echo   常见原因:
    echo     1. 没装 pyinstaller → 运行: pip install pyinstaller
    echo     2. Python 版本过旧  → 需要 Python 3.10+
    echo ============================================================
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   [完成] 打包成功!
echo   产物位置: %cd%\dist\账单合并工具.exe
echo.
echo   使用方法: 把 exe 复制到任意文件夹,双击运行,
echo             账单放到 exe 同级的 bills\ 文件夹即可。
echo ============================================================
echo.
pause
