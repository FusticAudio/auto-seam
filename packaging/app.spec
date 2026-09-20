# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir 配置：双击即用、无需安装依赖的 Windows 桌面工具。

打包内容：
  - seam-preview/ 整目录（index.html 及全部子目录，如 tests/），服务器以 /seam-preview 服务
  - auto-annotator/ 整目录源码与资源（排除 .venv / outputs / build / dist / __pycache__，
    避免把虚拟环境与构建产物打入发行包）
  - annotator-static/（auto-annotator/app/static），服务器以 /dxf-convert 服务
  - auto-annotator 的 Python 包经 pathex 参与静态分析随 exe 一起收集
"""
from pathlib import Path

from PyInstaller.building.datastruct import Tree

# 项目根：packaging 目录的上一级（auto-seam）
SEAM_PREVIEW = Path("../seam-preview").resolve()
ANNOTATOR_STATIC = Path("../auto-annotator/app/static").resolve()
AUTO_ANN_DIR = Path("../auto-annotator").resolve()

# 需从 auto-annotator 数据包中剔除的非发行内容（虚拟环境 / 构建产物 / 输出缓存）
_AUTO_ANN_EXCLUDES = [".venv", "__pycache__", "build", "dist", "outputs", ".git", ".pytest_cache"]

datas = [
    # DXF 转换上传页静态资源（运行时以 /dxf-convert 服务，路径不可变）
    (str(ANNOTATOR_STATIC), "annotator-static"),
]

# ezdxf / uvicorn / 上传用 multipart 依赖动态加载，需整体收集
hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    "python_multipart",
    "multipart",
]

a = Analysis(
    ["run.py"],
    pathex=[
        str(Path(SPECPATH)),
        str(AUTO_ANN_DIR),
    ],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

# 将完整目录树并入数据包（Tree 适合打包整目录，a.datas 为 TOC 容器）：
#   - seam-preview/：index.html 及全部子目录（如 tests/）
#   - auto-annotator/：源码与资源（剔除 .venv / outputs / build / dist / __pycache__）
a.datas += Tree(SEAM_PREVIEW, prefix="seam-preview", excludes=["__pycache__"])
a.datas += Tree(AUTO_ANN_DIR, prefix="auto-annotator", excludes=_AUTO_ANN_EXCLUDES)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="启动工具",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # 保留控制台，便于看到 URL 并通过 Ctrl+C / 关闭窗口退出
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="服装裁片自动缝合标注工具",
)