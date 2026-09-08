# -*- coding: utf-8 -*-
"""验证修复后的分类逻辑：袖窿/肩缝识别 + 左右侧分布 + 袖山对称轴。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from app.core.service import annotate_dxf_file  # noqa: E402
from app.core.semantics import classify_panel_groups, group_midpoint  # noqa: E402
from app.core.semantics import FRONT_ROLES, BACK_ROLES, SLEEVE_ROLES  # noqa: E402

BASE = Path(r"D:\project\0824cloth\0901dxf\缝合关系文件")

for pkg in sorted(BASE.glob("*.review-package")):
    dxf = list(pkg.glob("*.reviewed.dxf"))
    if not dxf:
        continue
    try:
        g = annotate_dxf_file(dxf[0])["garment"]
    except Exception as exc:
        print(f"\n=== {pkg.name}  ERROR {exc}")
        continue
    print(f"\n===== {pkg.name} =====")
    for p in g["panels"]:
        cl = classify_panel_groups(p)
        if p["role"] in SLEEVE_ROLES:
            for cap in cl["cap"]:
                ys = []
                for eid in cap["member_edge_ids"]:
                    e = next(x for x in p["edges"] if x["edge_id"] == eid)
                    pts = e.get("sampled_points") or [e["start_point"], e["end_point"]]
                    for pt in pts:
                        ys.append(pt[1])
                apex_y = max(ys)
                print(f"    {p['panel_id']} {p['role']:12s} CAP {cap['group_id']} len={round(cap['length'],1)} apex_y={round(apex_y,1)}")
        elif p["role"] in FRONT_ROLES or p["role"] in BACK_ROLES:
            cx = (p["bbox"]["min_x"] + p["bbox"]["max_x"]) / 2.0
            line = f"    {p['panel_id']} {p['role']:20s} cx={round(cx,1)}"
            for kind in ("shoulder", "armhole", "side"):
                for grp in cl[kind]:
                    mx = round(group_midpoint(grp, p["edges"])[0], 1)
                    side = "L" if mx < cx else "R"
                    line += f"\n        {kind:9s}{side} {grp['group_id']:32s} len={round(grp['length'],1)} midx={mx}"
            print(line)
