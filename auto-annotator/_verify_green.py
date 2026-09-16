# -*- coding: utf-8 -*-
"""验证绿线(沿缝线折线)贴合标准：
  V1 折线各中间顶点均取自轮廓(outline) → 点到轮廓最大垂距≈0
  V2 折线世界总长 vs distance_from_mid 相对误差<=0.5%
  V3 端点(中点/刀口)到轮廓最近距离小于1单位(≈1mm)
"""
from __future__ import annotations
import math, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from app.core.service import annotate_dxf_file  # noqa
import app.core.notches as N  # noqa

def pt(a,b): return math.hypot(a[0]-b[0], a[1]-b[1])

def dist_point_to_poly(p_, poly):
    best=1e18
    for i in range(len(poly)-1):
        a=poly[i]; b=poly[i+1]
        ax,ay=a; bx,by=b; px,py=p_
        dx,dy=bx-ax,by-ay
        L2=dx*dx+dy*dy
        t=0 if L2<1e-18 else ((px-ax)*dx+(py-ay)*dy)/L2
        t=max(0,min(1,t))
        cx,cy=ax+t*dx, ay+t*dy
        best=min(best, math.hypot(px-cx,py-cy))
    return best

def main():
    r = annotate_dxf_file(Path(r"d:\project\0824cloth\0901dxf\data\4条纹衬衫.dxf"))
    panels = r["garment"]["panels"]
    byid = {p["panel_id"]: p for p in panels}
    print("验证标准  V1贴合 V2长度 V3端点(基于后端 path_points)\n")
    allok=True
    for lo_id in ("panel_009","panel_011"):
        lo = byid[lo_id]
        outline=[]
        for e in lo.get("edges") or []:
            outline.extend([list(p) for p in (e.get("sampled_points") or [e["start_point"],e["end_point"]])])
        lm = lo["notch_midpoint"]
        for n in lo.get("notches",[]):
            pp = n.get("path_points") or []
            if len(pp) < 2: print(f"{n['notch_id']}: 无path_points"); allok=False; continue
            # V1: 中间顶点贴轮廓（应≈0）
            v1 = max(dist_point_to_poly(v, outline) for v in pp[1:-1]) if len(pp)>2 else 0.0
            # V2: 折线长度 vs distance
            L = sum(pt(pp[i],pp[i+1]) for i in range(len(pp)-1))
            rel = abs(L - n["distance_from_mid"]) / n["distance_from_mid"]
            # V3: 端点=中点/刀口，起末应与对应 world 点重合
            v3s = pt(pp[0], lm); v3e = pt(pp[-1], n["point"])
            # 端点也应贴轮廓
            v3s2=dist_point_to_poly(lm, outline); v3e2=dist_point_to_poly(n["point"], outline)
            ok = v1<0.01 and rel<=0.005 and v3s<0.01 and v3e<0.01 and v3s2<1.0 and v3e2<1.0
            allok &= ok
            print(f"{n['notch_id']}: V1贴合={v1:.4f}{' OK' if v1<0.01 else ' FAIL'}  "
                  f"V2len={L:.2f}/dist={n['distance_from_mid']} rel={rel*100:.3f}% "
                  f"{'OK' if rel<=0.005 else 'FAIL'}  "
                  f"V3端点锚=({v3s:.3f},{v3e:.3f}) 贴轮廓=({v3s2:.3f},{v3e2:.3f}) "
                  f"{'OK' if ok else 'FAIL'}")
    print(f"\n{'所有标准通过' if allok else '存在FAIL项'}")

if __name__=="__main__":
    main()