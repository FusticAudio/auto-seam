# -*- coding: utf-8 -*-
"""FastAPI 服务：上传 DXF -> 返回 garment/seam 两个 JSON（前端直接下载）。"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .core import service

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="DXF 自动缝合标注", version="1.0.0")


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


app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
