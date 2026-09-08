# -*- coding: utf-8 -*-
"""绘制裁片轮廓与边组，确认几何方向。"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from app.core.service import annotate_dxf_file  # noqa: E402

DXF = Path(r"D:\project\0824cloth\0901dxf\缝合关系文件\1 2后背小熊短袖.review-package\12后背小熊短袖.reviewed.dxf")
g = annotate_dxf_file(DXF)["garment"]

COLORS = {
    "armhole_edge": "red", "sleeve_cap_edge": "blue", "sleeve_underarm_edge": "orange",
    "shoulder_edge": "green", "side_seam_edge": "purple", "hem_edge": "gray",
    "neckline_edge": "brown", "sleeve_hem_edge": "gray",
}
fig, axes = plt.subplots(1, len(g["panels"]), figsize=(5 * len(g["panels"]), 5))
if len(g["panels"]) == 1:
    axes = [axes]
for ax, p in zip(axes, g["panels"]):
    ax.set_aspect("equal")
    ax.set_title(f"{p['panel_id']} {p['role']}")
    for grp in p["edge_groups"]:
        role = grp.get("role", "unknown")
        color = COLORS.get(role, "black")
        xs, ys = [], []
        for eid in grp["member_edge_ids"]:
            e = next(e for e in p["edges"] if e["edge_id"] == eid)
            pts = e.get("sampled_points") or [e["start_point"], e["end_point"]]
            for pt in pts:
                xs.append(pt[0])
                ys.append(pt[1])
        ax.plot(xs, ys, color=color, linewidth=2, label=role)
        mid = grp.get("midpoint")
        if mid:
            ax.text(mid[0], mid[1], grp["group_id"].split(".")[-1], fontsize=7)
    ax.legend(fontsize=7, loc="best")
plt.tight_layout()
out = ROOT / "panels_viz.png"
plt.savefig(out, dpi=110)
print(f"saved: {out}")
