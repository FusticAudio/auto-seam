# -*- coding: utf-8 -*-
"""对比各人工标注 seam 文件的缝合配对（确认左右对应约定）。"""
from __future__ import annotations

import json
from pathlib import Path

BASE = Path(r"D:\project\0824cloth\0901dxf\缝合关系文件")

for pkg in sorted(BASE.glob("*.review-package")):
    seam = list(pkg.glob("*.seam.reviewed.json"))
    garment = list(pkg.glob("*.garment.reviewed.json"))
    if not seam or not garment:
        continue
    g = json.load(open(garment[0], encoding="utf-8"))
    s = json.load(open(seam[0], encoding="utf-8"))
    print(f"\n===== {pkg.name} =====")
    for p in g["panels"]:
        print(f"    {p['panel_id']} role={p['role']} piece_name={p.get('piece_name')}")
    for st in s["stitches"]:
        a = ",".join(st["a_groups"])
        b = ",".join(st["b_groups"])
        print(f"    {st['stitch_id']} {st['relation']:26s} {a} <-> {b}")
