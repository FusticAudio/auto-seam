# -*- coding: utf-8 -*-
"""批量检查各 DXF 的缝合输出：袖山是否生成、是否存在前后袖窿直连错误。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from app.core.service import annotate_dxf_file  # noqa: E402

BASE = Path(r"D:\project\0824cloth\0901dxf\缝合关系文件")
DXFS = sorted(BASE.rglob("*.reviewed.dxf"))

for dxf in DXFS:
    try:
        res = annotate_dxf_file(dxf)
        g = res["garment"]
        s = res["seam"]
    except Exception as exc:  # noqa: BLE001
        print(f"\n=== {dxf.parent.name}  ERROR {exc}")
        continue
    panels = {p["panel_id"]: p for p in g["panels"]}
    print(f"\n=== {dxf.parent.name} ===")
    for p in g["panels"]:
        print(f"    {p['panel_id']} role={p['role']}")
    for st in s["stitches"]:
        src = st["confidence_source"]
        mark = ""
        # 检查是否为前后袖窿/袖隆错误直连
        a_panels = {gid.split('.')[0] for gid in st['a_groups']}
        b_panels = {gid.split('.')[0] for gid in st['b_groups']}
        rel = st["relation"]
        if rel == "seam_pair" and src == "geometry_inferred":
            mark = "  <-- 几何兜底"
        if rel in ("front_shoulder_to_back_shoulder", "front_side_to_back_side"):
            mark = ""
        if rel == "sleeve_cap_to_armhole":
            mark = "  <-- 袖山入袖窿"
        print(f"    {st['stitch_id']} {rel:36s} {src:16s} {sorted(a_panels)}->{sorted(b_panels)}{mark}")
