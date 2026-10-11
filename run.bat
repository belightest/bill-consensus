@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title 账单合并工具 Bill Consensus

REM ============================================================
REM   账单合并工具 - 一键运行 (放在项目根目录)
REM
REM   用法 1: 双击本 bat → 自动分析 bills\ 里的账单
REM   用法 2: 把账单文件(可多个)拖到本 bat 图标上松手
REM ============================================================

REM ---- 切到脚本所在目录(项目根) ----
cd /d "%~dp0"

REM ---- 自动找 Python ----
set "PYTHON="
where python >nul 2>&1 && (
    python --version 2>nul | findstr /i "Python 3" >nul && set "PYTHON=python"
)
if not defined PYTHON (
    where py >nul 2>&1 && (
        py -3 --version >nul 2>&1 && set "PYTHON=py -3"
    )
)
if not defined PYTHON (
    where python3 >nul 2>&1 && set "PYTHON=python3"
)

if not defined PYTHON (
    echo.
    echo ============================================================
    echo   [错误] 没找到 Python 3
    echo.
    echo   请到 https://www.python.org/downloads/ 下载安装,
    echo   安装时务必勾选 "Add Python to PATH"。
    echo ============================================================
    pause
    exit /b 1
)

echo.
echo ============================================================
echo    账单合并工具 v1.1
echo    使用 Python: !PYTHON!
echo ============================================================
echo.

REM ---- 检查依赖(缺了就自动装) ----
!PYTHON! -c "import pandas, jinja2, openpyxl" >nul 2>&1
if errorlevel 1 (
    echo [提示] 缺少依赖,正在自动安装...
    echo.
    !PYTHON! -m pip install pandas jinja2 openpyxl --quiet
    if errorlevel 1 (
        echo.
        echo [错误] 自动安装失败,请手动运行:
        echo     !PYTHON! -m pip install -r requirements.txt
        pause
        exit /b 1
    )
    echo [完成] 依赖已安装
    echo.
)

REM ---- 没有 bills 目录就建一个 ----
if not exist "bills" (
    mkdir bills
    echo [提示] 已创建 bills\ 文件夹
    echo         以后把账单文件放进去,再双击本程序即可自动分析
    echo.
)

REM ---- 运行主程序 ----
REM %* 接收拖拽过来的文件参数;为空则自动扫 bills\
!PYTHON! bill_consensus\main.py %*

if errorlevel 1 (
    echo.
    echo ============================================================
    echo   [失败] 分析出错,请检查上方日志。
    echo   常见问题:
    echo     1. 账单是 PDF → 请在支付软件里选"导出为 CSV"
    echo     2. 文件打开乱码 → 用 Excel 另存为 "CSV UTF-8"
    echo     3. 图片 OCR → 需要先装 Tesseract-OCR
    echo ============================================================
) else (
    echo.
    echo ============================================================
    echo   [完成] 仪表盘已生成!
    echo   文件位置: %cd%\output\dashboard.html
    echo ============================================================
    set /p OPEN="现在用浏览器打开吗? (Y/N): "
    if /i "!OPEN!"=="Y" start "" "output\dashboard.html"
)

echo.
pause
endlocal
