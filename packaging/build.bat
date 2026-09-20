@echo off
chcp 65001 >nul
REM ============================================================
REM  一键构建「服装裁片自动缝合标注工具」桌面版
REM  依赖：需已存在 auto-annotator\.venv（含 fastapi/uvicorn/ezdxf）
REM  首次构建会自动安装 PyInstaller。
REM =============================================================
setlocal
cd /d "%~dp0"

set "VENV_PY=..\auto-annotator\.venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
  echo [ERROR] 未找到虚拟环境: %VENV_PY%
  echo 请先在 auto-annotator 下创建 .venv 并安装依赖。
  exit /b 1
)

echo [1/3] 检查并安装 PyInstaller ...
"%VENV_PY%" -m pip show PyInstaller >nul 2>&1
if errorlevel 1 (
  "%VENV_PY%" -m pip install pyinstaller || goto :fail
)

echo [2/3] 开始打包 （首次较慢，请耐心等待）...
"%VENV_PY%" -m PyInstaller --clean --noconfirm app.spec || goto :fail

echo [3/3] 整理输出目录 ...
set "OUT=dist\服装裁片自动缝合标注工具"
if exist "%OUT%\使用说明.txt" del "%OUT%\使用说明.txt"
copy /y "README.txt" "%OUT%\使用说明.txt" >nul

echo.
echo 构建完成：%OUT%
echo 双击其中的「启动工具.exe」即可使用。
exit /b 0

:fail
echo [ERROR] 构建失败，请检查上方日志。
exit /b 1