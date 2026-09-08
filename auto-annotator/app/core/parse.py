# -*- coding: utf-8 -*-
"""DXF 解析：实体展开、GBK 文本修复、Piece Name 字段切分与元数据提取。"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from .geometry import bbox, clean_number, clean_point, geometry_hash, polyline_length

SUPPORTED_TYPES = {"LWPOLYLINE", "POLYLINE", "LINE", "ARC", "SPLINE", "TEXT", "MTEXT", "INSERT"}
CURVE_TYPES = {"LINE", "LWPOLYLINE", "POLYLINE", "ARC", "SPLINE"}
MAX_INSERT_DEPTH = 16


def fix_gbk_text(text: str | None) -> str:
    """还原 BOKE 以 ANSI_1252 伪装的 GBK 中文（如 'ÎÞÊ¡' -> '无省'）。"""
    if not text:
        return ""
    try:
        return text.encode("latin1", errors="ignore").decode("gbk", errors="ignore")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def parse_dxf(path: Path, flattening_distance: float = 1.0) -> list[dict[str, Any]]:
    import ezdxf

    doc = ezdxf.readfile(path)
    expanded: list[tuple[Any, list[dict[str, str]]]] = []
    for modelspace_entity in doc.modelspace():
        expanded.extend(_expand_inserts(modelspace_entity))
    records: list[dict[str, Any]] = []
    for entity, block_path in expanded:
        kind = entity.dxftype()
        if kind not in SUPPORTED_TYPES:
            continue
        # 过滤审阅工具附加层（XG_*：面板标注/边标注/缝合标记/评审备注），
        # 这些是元数据层，不属于设计内容，避免误判为裁片。
        if str(entity.dxf.get("layer", "0")).startswith("XG_"):
            continue
        points = _flatten(entity, flattening_distance)
        closed = _is_closed(entity, points)
        if closed and len(points) > 1 and points[0] == points[-1]:
            points = points[:-1]
        source_handle = str(entity.dxf.get("handle", "") or "")
        handle_parts = [item["insert_handle"] for item in block_path if item["insert_handle"]]
        if source_handle:
            handle_parts.append(source_handle)
        record: dict[str, Any] = {
            "handle": "/".join(handle_parts),
            "layer": str(entity.dxf.get("layer", "0")),
            "entity_type": kind,
            "points": points,
            "is_closed": closed,
            "bbox": bbox(points),
            "length": clean_number(polyline_length(points, closed)),
            "geometry_hash": geometry_hash(kind, points),
        }
        if block_path:
            record["block_path"] = block_path
        text = _text(entity)
        if text is not None:
            record["text"] = text
        records.append(record)
    return records


def parse_dxf_bytes(data: bytes, flattening_distance: float = 1.0) -> list[dict[str, Any]]:
    fd, tmp_path = tempfile.mkstemp(suffix=".dxf")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        return parse_dxf(Path(tmp_path), flattening_distance)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def _expand_inserts(
    entity: Any,
    block_path: list[dict[str, str]] | None = None,
    block_stack: tuple[str, ...] = (),
) -> list[tuple[Any, list[dict[str, str]]]]:
    block_path = block_path or []
    result: list[tuple[Any, list[dict[str, str]]]] = [(entity, block_path)]
    if entity.dxftype() != "INSERT" or len(block_stack) >= MAX_INSERT_DEPTH:
        return result
    block_name = str(entity.dxf.name)
    if block_name in block_stack:
        return result
    child_path = block_path + [
        {"insert_handle": str(entity.dxf.get("handle", "") or ""), "block_name": block_name}
    ]
    try:
        for child in entity.virtual_entities():
            result.extend(_expand_inserts(child, child_path, block_stack + (block_name,)))
    except (AttributeError, TypeError, ValueError):
        pass
    return result


def _flatten(entity: Any, distance: float = 1.0) -> list[list[float]]:
    kind = entity.dxftype()
    try:
        if kind in {"LWPOLYLINE", "POLYLINE"}:
            from ezdxf.path import make_path

            return [clean_point(v) for v in make_path(entity).flattening(distance)]
        if kind == "LINE":
            return [clean_point(entity.dxf.start), clean_point(entity.dxf.end)]
        if kind in {"ARC", "SPLINE"}:
            return [clean_point(v) for v in entity.flattening(distance)]
        if kind in {"TEXT", "MTEXT", "INSERT"}:
            insert = entity.dxf.get("insert", (0.0, 0.0))
            return [clean_point(insert)]
    except (AttributeError, TypeError, ValueError):
        return []
    return []


def _is_closed(entity: Any, points: list[list[float]]) -> bool:
    kind = entity.dxftype()
    if kind in {"LWPOLYLINE", "POLYLINE"}:
        return bool(entity.is_closed)
    return len(points) > 2 and points[0] == points[-1]


def _text(entity: Any) -> str | None:
    try:
        if entity.dxftype() == "TEXT":
            return fix_gbk_text(str(entity.dxf.text))
        if entity.dxftype() == "MTEXT":
            return fix_gbk_text(str(entity.plain_text()))
        if entity.dxftype() == "INSERT":
            return str(entity.dxf.name)
    except (AttributeError, TypeError, ValueError):
        return None
    return None


# ---------------------------------------------------------------------------
# Piece Name 字段切分
# ---------------------------------------------------------------------------

def map_entities_to_pieces(records: list[dict[str, Any]]) -> dict[str, Any]:
    """按 DXF 实体顺序，把 'Piece Name: xxx' 之后的实体归属到对应片。

    返回:
      handle_to_piece: handle -> piece_name
      piece_meta:      piece_name -> {category, fabric, size, quantity}
      doc_meta:        文档级元数据（Style Name / Author / Version / Units ...）
    """
    handle_to_piece: dict[str, str] = {}
    piece_meta: dict[str, dict[str, str]] = {}
    doc_meta: dict[str, str] = {}
    current: str | None = None
    current_meta: dict[str, str] | None = None
    for record in records:
        if record["entity_type"] not in {"TEXT", "MTEXT"}:
            if current is not None:
                handle_to_piece[record["handle"]] = current
            continue
        text = record.get("text", "")
        if not text:
            continue
        text = text.strip()
        if text.startswith("Piece Name:"):
            current = text.split(":", 1)[1].strip()
            current_meta = piece_meta.setdefault(current, {})
            continue
        for key in ("Style Name:", "Author:", "VERSION:", "Units:", "Sample Size:"):
            if text.startswith(key):
                doc_meta[key.rstrip(":").lower()] = text.split(":", 1)[1].strip()
        if current_meta is not None:
            for key in ("Category:", "Fabric:", "Size:", "Quantity:"):
                if text.startswith(key):
                    current_meta[key.rstrip(":")] = text.split(":", 1)[1].strip()
    return {
        "handle_to_piece": handle_to_piece,
        "piece_meta": piece_meta,
        "doc_meta": doc_meta,
    }
