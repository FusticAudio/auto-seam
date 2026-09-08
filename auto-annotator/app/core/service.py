# -*- coding: utf-8 -*-
"""编排服务：DXF 字节 -> (garment.json, seam.json)。"""
from __future__ import annotations

import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from .panels import build_panel_topology, detect_panels
from .parse import map_entities_to_pieces, parse_dxf
from .schema import build_garment_json, build_seam_json
from .semantics import (
    assign_roles, mark_spurious_panels_unknown, match_seams, reclassify_binding_strips,
)

logger = logging.getLogger("auto_annotator")

# 若上层未配置日志则启用基础输出，便于调试 binding strip 等语义判断
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )


def _safe_garment_id(filename: str) -> str:
    stem = Path(filename).stem
    stem = re.sub(r"[^\w\u4e00-\u9fff-]", "", stem)
    return stem[:60] or "garment"


def annotate_dxf_file(path: Path) -> dict[str, Any]:
    records = parse_dxf(path)
    return _annotate_records(records, _safe_garment_id(path.name), Path(path).name)


def annotate_dxf_bytes(data: bytes, filename: str) -> dict[str, Any]:
    fd, tmp_path = tempfile.mkstemp(suffix=".dxf")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        records = parse_dxf(Path(tmp_path))
        return _annotate_records(records, _safe_garment_id(filename), filename)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def _annotate_records(records: list[dict[str, Any]], garment_id: str, source_dxf: str) -> dict[str, Any]:
    piece_info = map_entities_to_pieces(records)
    piece_info["doc_meta"]["source_dxf"] = source_dxf

    panels, diagnostics = detect_panels(records)
    build_panel_topology(panels)
    assign_roles(panels, piece_info["handle_to_piece"])

    # 几何兜底：矩形领口滚条 collar -> binding_strip（在其上建立长边互缝）
    reclassify_binding_strips(panels)
    # 几何兜底：尺寸占比过小的伪/碎线裁片重标记为 unknown_panel（其边缘不参与缝合）
    mark_spurious_panels_unknown(panels)

    # 兜底角色用最近片名文本位置
    piece_positions = _piece_text_positions(records)
    for panel in panels:
        panel["_piece_text_positions"] = [
            (name, pos) for name, pos in piece_positions
        ]

    stitches = match_seams(panels)

    # 兜底角色缺失时再用最近文本补一次（不影响已赋值角色）
    for panel in panels:
        if panel["role"] == "unknown_panel" and panel.get("piece_name") is None:
            panel["piece_name"] = panel["_piece_text_positions"][0][0] if panel["_piece_text_positions"] else None

    garment = build_garment_json(garment_id, records, panels, piece_info["piece_meta"], piece_info["doc_meta"], diagnostics)
    seam = build_seam_json(garment_id, stitches)
    summary = _build_summary(garment, seam)
    return {"garment": garment, "seam": seam, "summary": summary}


def _piece_text_positions(records: list[dict[str, Any]]) -> list[tuple[str, list[float]]]:
    positions: list[tuple[str, list[float]]] = []
    for record in records:
        if record.get("entity_type") in {"TEXT", "MTEXT"}:
            text = record.get("text", "")
            if isinstance(text, str) and text.startswith("Piece Name:"):
                points = record.get("points") or []
                if points:
                    positions.append((text.split(":", 1)[1].strip(), points[0]))
    return positions


def _build_summary(garment: dict[str, Any], seam: dict[str, Any]) -> dict[str, Any]:
    panel_rows = [
        {
            "panel_id": p["panel_id"],
            "role": p["role"],
            "piece_name": p.get("piece_name"),
            "area": p["area"],
            "edges": len(p["edges"]),
            "groups": len(p["edge_groups"]),
        }
        for p in garment["panels"]
    ]
    stitch_rows = [
        {
            "stitch_id": s["stitch_id"],
            "relation": s["relation"],
            "type": s["type"],
            "a": s.get("a"),
            "b": s.get("b"),
            "a_panel": s["a"].split(".")[0] if s.get("a") else "",
            "b_panel": s["b"].split(".")[0] if s.get("b") else "",
            "a_edges": len(s.get("a_edges") or []),
            "b_edges": len(s.get("b_edges") or []),
            "confidence": s.get("confidence"),
            "confidence_source": s.get("confidence_source"),
        }
        for s in seam["stitches"]
    ]
    return {
        "garment_id": garment["garment_id"],
        "panel_count": len(garment["panels"]),
        "stitch_count": len(seam["stitches"]),
        "panels": panel_rows,
        "stitches": stitch_rows,
        "review_status": "needs_review",
    }
