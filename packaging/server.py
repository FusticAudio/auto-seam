# -*- coding: utf-8 -*-
"""桌面工具统一 FastAPI 应用（模块名 server 以避免与 auto-annotator 的 app 包撞名）。

把两套功能合为一个可双击运行的桌面工具：
  - POST /api/annotate     上传 DXF，返回 garment / seam / summary 三个 JSON
  - /seam-preview/         裁片预览 / 人工缝合 / 语义编辑（seam-preview/index.html）
  - /dxf-convert/          DXF 转换上传页（auto-annotator 自带 static/index.html）
  - /                     重定向到 /seam-preview/
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

_DESKTOP_DIR = Path(__file__).resolve().parent           # <auto-seam>/desktop
_AUTO_SEAM_DIR = _DESKTOP_DIR.parent                      # <auto-seam>
_AUTO_ANN_DIR = _AUTO_SEAM_DIR / "auto-annotator"        # <auto-seam>/auto-annotator


def _frozen_root() -> Path:
    """PyInstaller 冻结态的资源根目录。"""
    return Path(getattr(sys, "_MEIPASS", "."))


def resource_dirs():
    """返回 (seam_preview_dir, annotator_static_dir)，兼容冻结/源码两种模式。

    冻结态：静态资源被打进 _MEIPASS 下的 seam-preview / annotator-static。
    源码态：直接指向 auto-seam 下现有文件。
    """
    if getattr(sys, "frozen", False):
        root = _frozen_root()
        seam = root / "seam-preview"
        annotator = root / "annotator-static"
        if seam.is_dir() and annotator.is_dir():
            return seam, annotator
    # 源码态兜底
    return (
        _AUTO_SEAM_DIR / "seam-preview",
        _AUTO_ANN_DIR / "app" / "static",
    )


# 把 auto-annotator 目录加入 sys.path，以复用其 app.core.service（不复制逻辑）
if str(_AUTO_ANN_DIR) not in sys.path:
    sys.path.insert(0, str(_AUTO_ANN_DIR))

from app.core import service  # noqa: E402  (auto-annotator 的可导入根包为 app)

SEAM_PREVIEW_DIR, ANNOTATOR_STATIC_DIR = resource_dirs()

app = FastAPI(title="服装裁片自动缝合标注 · 桌面工具", version="1.0.0")


@app.post("/api/annotate")
async def annotate(file: UploadFile = File(...)) -> JSONResponse:
    if not (file.filename or "").lower().endswith(".dxf"):
        raise HTTPException(status_code=400, detail="请上传 .dxf 文件")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="文件为空")
    try:
        result = service.annotate_dxf_bytes(data, file.filename or "upload.dxf")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"解析失败: {exc}") from exc
    return JSONResponse(result)


# 拆分为两页：编辑器 + DXF 转换页
app.mount(
    "/seam-preview",
    StaticFiles(directory=str(SEAM_PREVIEW_DIR), html=True),
    name="seam-preview",
)
app.mount(
    "/dxf-convert",
    StaticFiles(directory=str(ANNOTATOR_STATIC_DIR), html=True),
    name="dxf-convert",
)


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/seam-preview/")