# -*- coding: utf-8 -*-
"""输出 schema：生成 garment.json 与 seam.json（对齐语义库 + 可视化工具兼容字段）。"""
from __future__ import annotations

from typing import Any

SCHEMA_VERSION = "0.2.0"
SEMANTIC_CATALOG_VERSION = "1.0.0"

SUPPORTED_STITCH_TYPES = [
    "seam", "binding", "fold_hem", "dart", "pleat", "zipper",
    "button", "pocket_attach", "waistband", "rib",
]


def _parse_quantity(text: str | None) -> tuple[int, str]:
    if not text:
        return 1, "single"
    parts = [p.strip() for p in text.split(",") if p.strip()]
    count = sum(int(p) for p in parts if p.isdigit())
    if count <= 1:
        return 1, "single"
    if len(parts) == 2 and parts[0] == parts[1]:
        return count, "mirror_pair"
    return count, "repeat"


def build_garment_json(
    garment_id: str,
    records: list[dict[str, Any]],
    panels: list[dict[str, Any]],
    piece_meta: dict[str, dict[str, str]],
    doc_meta: dict[str, str],
    diagnostics: dict[str, Any],
) -> dict[str, Any]:
    for panel in panels:
        meta = piece_meta.get(panel.get("piece_name") or "", {})
        quantity, orientation = _parse_quantity(meta.get("Quantity"))
        panel["cut_mode"] = orientation
        panel["cut_instruction"] = {
            "cut_quantity": quantity,
            "orientation": orientation,
            "side_assignment": ["left", "right"] if orientation == "mirror_pair" else [],
            "cut_on_fold": False,
            "quantity_source": "piece_label" if quantity > 1 else "default",
        }
        panel.pop("_points", None)
        panel.pop("_edge_segments", None)
        panel.pop("_piece_text_positions", None)

    garment: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "semantic_catalog_version": SEMANTIC_CATALOG_VERSION,
        "garment_id": garment_id,
        "garment_category": "top",
        "garment_type": "short_sleeve_top",
        "unit": "mm",
        "source_dxf": doc_meta.get("source_dxf", f"{garment_id}.dxf"),
        "annotated_dxf": None,
        "entities": records,
        "panels": panels,
        "panel_instances": _build_panel_instances(panels),
        "validation": {
            "schema_status": "draft",
            "issues": [],
            "diagnostics": diagnostics,
        },
        "review": {
            "status": "needs_review",
            "created_by": "auto_annotator",
            "notes": [
                "自动标注初稿：角色来自 DXF Piece Name 字段，缝合关系由规则+几何生成，需人工复核。"
            ],
        },
    }
    return garment


def _build_panel_instances(panels: list[dict[str, Any]]) -> list[dict[str, Any]]:
    instances: list[dict[str, Any]] = []
    for panel in panels:
        instruction = panel["cut_instruction"]
        quantity = instruction["cut_quantity"]
        if quantity >= 2:
            for side in ("left", "right"):
                instances.append(
                    {
                        "instance_id": f"{panel['panel_id']}:{side}",
                        "source_panel_id": panel["panel_id"],
                        "role": panel["role"],
                        "side": side,
                        "sequence": 1 if side == "left" else 2,
                        "mirrored": side == "right",
                        "orientation": "mirrored_pair",
                        "cut_on_fold": False,
                    }
                )
        else:
            instances.append(
                {
                    "instance_id": f"{panel['panel_id']}:01",
                    "source_panel_id": panel["panel_id"],
                    "role": panel["role"],
                    "side": "single",
                    "sequence": 1,
                    "mirrored": False,
                    "orientation": "single",
                    "cut_on_fold": False,
                }
            )
    return instances


def build_seam_json(garment_id: str, stitches: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "garment_id": garment_id,
        "status": "draft",
        "supported_stitch_types": SUPPORTED_STITCH_TYPES,
        "stitches": stitches,
        "review": {
            "status": "needs_review",
            "created_by": "auto_annotator",
            "notes": [
                "自动缝合关系仅为候选草稿；确认边语义和方向后再交给 3D 执行器。"
            ],
        },
    }
