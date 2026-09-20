# -*- coding: utf-8 -*-
"""功能改进单元测试：
Feature 1 袖片对称性与前后袖缝配对
Feature 2 unknown_panel 边缘剔除
"""
import math
import sys
import logging
from pathlib import Path

sys.path.insert(0, r'd:\project\0824cloth\0901dxf\auto-annotator')
logging.disable(logging.CRITICAL)

from app.core.semantics import (  # noqa: E402
    match_seams, sleeve_symmetry_score, mirror_seam_overlap,
    validate_sleeve_seam_pair, classify_panel_groups,
    mark_spurious_panels_unknown, _geom_cross_family_banned,
    _chain_endpoints, _canonical_point,
)

PASS = 0
FAIL = 0


def check(label, cond):
    global PASS, FAIL
    PASS += 1 if cond else 0
    FAIL += 0 if cond else 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}")


def _length(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _mk_panel(panel_id, role, edges, groups, piece_name=None):
    """由边 ('id',a,b,group) 与分组构造完整 panel dict。"""
    edge_recs = []
    for eid, a, b, gid in edges:
        edge_recs.append({
            "edge_id": eid, "start_point": list(a), "end_point": list(b),
            "sampled_points": [list(a), list(b)],
            "length": round(_length(a, b), 4), "role": "unknown_edge",
            "group_id": gid,
        })
    group_recs = []
    for gid, member_ids in groups.items():
        glen = sum(e["length"] for e in edge_recs if e["edge_id"] in member_ids)
        pts = []
        for e in edge_recs:
            if e["edge_id"] in member_ids:
                pts += e["sampled_points"]
        midx = sum(p[0] for p in pts) / len(pts)
        midy = sum(p[1] for p in pts) / len(pts)
        group_recs.append({
            "group_id": gid, "panel_id": panel_id, "member_edge_ids": list(member_ids),
            "start_point": edge_recs[0]["start_point"], "end_point": edge_recs[-1]["end_point"],
            "role": "unknown_edge", "length": round(glen, 4),
            "midpoint": [midx, midy],
        })
    # 按成员边顺序回填 start/end
    for g, m in zip(group_recs, groups.values()):
        midx, midy = g["midpoint"]
        pass
    xs = [e["start_point"][0] for e in edge_recs] + [e["end_point"][0] for e in edge_recs]
    ys = [e["start_point"][1] for e in edge_recs] + [e["end_point"][1] for e in edge_recs]
    return {
        "panel_id": panel_id, "role": role, "piece_name": piece_name,
        "bbox": {"min_x": min(xs), "max_x": max(xs), "min_y": min(ys), "max_y": max(ys)},
        "centroid": [sum(xs) / len(xs), sum(ys) / len(ys)],
        "edges": edge_recs, "edge_groups": group_recs,
        "perimeter": sum(e["length"] for e in edge_recs),
    }


def mk_sleeve(panel_id, shift=0.0):
    """单片袖（近似轴对称）。shift>0 时整体右移右半幅，保持袖缝长度不变但破坏镜像关系。"""
    P = [(0, 600), (150 + shift, 450), (230 + shift, 260), (150 + shift, 20),
         (0, 0), (-150, 20), (-230, 260), (-150, 450)]
    # 边：0apex(0)->B,1 B->C,2 C->D(右袖缝),3 D->E(右下摆),4 E->F(下摆),
    #     5 F->G(左袖缝),6 G->H,7 H->apex
    edges = []
    for i in range(8):
        a = P[i]
        b = P[(i + 1) % 8]
        edges.append((f"{panel_id}.e{i+1:03d}", a, b, ""))
    g_cap = [f"{panel_id}.e001", f"{panel_id}.e002", f"{panel_id}.e007", f"{panel_id}.e008"]
    g_hem = [f"{panel_id}.e004", f"{panel_id}.e005"]
    g_ur = [f"{panel_id}.e003"]
    g_ul = [f"{panel_id}.e006"]
    groups = {
        f"{panel_id}.cap": g_cap,
        f"{panel_id}.hem": g_hem,
        f"{panel_id}.underR": g_ur,
        f"{panel_id}.underL": g_ul,
    }
    return _mk_panel(panel_id, "sleeve", edges, groups, "sleeve")


def mk_unknown(panel_id):
    P = [(0, 0), (60, 0), (60, 40), (0, 40)]
    edges = []
    for i in range(4):
        a = P[i]
        b = P[(i + 1) % 4]
        gid = f"{panel_id}.e{(i//1)+1:03d}"
        edges.append((f"{panel_id}.e{i+1:03d}", a, b, gid))
    groups = {f"{panel_id}.e00{i+1}": [f"{panel_id}.e{i+1:03d}"] for i in range(4)}
    return _mk_panel(panel_id, "unknown_panel", edges, groups, "神秘裁片xyz")


def main():
    sym = mk_sleeve("sl_sym")
    cl = classify_panel_groups(sym)
    print("== Feature1：对称单片袖 ==")
    under = cl["underarm"]
    check("分类出 2 个袖底缝边组", len(under) == 2)
    sym_score = sleeve_symmetry_score(sym)
    ov = mirror_seam_overlap(sym, under[0], under[1])
    check(f"整体轴对称得分高 sym={sym_score:.2f}>=0.85", sym_score >= 0.85)
    check(f"前袖缝翻转重合度高 ov={ov:.2f}>=0.85", ov >= 0.85)
    ok, s2, o2 = validate_sleeve_seam_pair(sym, under)
    check("validate_sleeve_seam_pair → True", ok is True)

    stitches = match_seams([sym])
    names = [s["relation"] for s in stitches]
    check("自动生成 front_sleeve_seam_to_back_sleeve_seam",
          "front_sleeve_seam_to_back_sleeve_seam" in names)

    print("== Feature1：非对称单片袖（降级）==")
    asym = mk_sleeve("sl_asym", shift=160)
    cl2 = classify_panel_groups(asym)
    un2 = cl2["underarm"]
    check("非对称袖 2 个袖底缝边组", len(un2) == 2)
    r = min(un2[0]["length"], un2[1]["length"]) / max(un2[0]["length"], un2[1]["length"])
    check(f"两条袖缝长度仍相近 r={r:.2f}>=0.85（长度可触发候选）", r >= 0.85)
    a_sym = sleeve_symmetry_score(asym)
    a_ov = mirror_seam_overlap(asym, un2[0], un2[1])
    check("对称评分被拉低(至少其一低于阈值)",
          a_sym < 0.85 or a_ov < 0.85)
    check("翻转重合度未达标 a_ov=%.2f<0.85" % a_ov, a_ov < 0.85)
    ok2, _, _ = validate_sleeve_seam_pair(asym, un2)
    check("validate_sleeve_seam_pair → False（不自动配对）", ok2 is False)
    st2 = match_seams([asym])
    n2 = [s["relation"] for s in st2]
    check("降级为 seam_pair", "seam_pair" in n2)
    check("不再生成 front_sleeve_seam 专用关系",
          "front_sleeve_seam_to_back_sleeve_seam" not in n2)

    print("== Feature2：unknown_panel 边缘剔除 ==")
    unk = mk_unknown("unk1")
    st3 = match_seams([unk])
    check("只有 unknown_panel → 无任何缝合", st3 == [])
    check("unknown_panel 附注原因", unk.get("edge_participation_note") is not None)

    unk2 = mk_unknown("unk2")
    st4 = match_seams([sym, unk2])
    check("混合场景仍生成常规缝合（袖缝）", len(st4) >= 1)
    unk_edges = {u["edge_id"] for u in unk2["edges"]}
    referenced = set()
    for s in st4:
        referenced |= set(s.get("a_edges", [])) | set(s.get("b_edges", []))
    check("混合场景中无缝合引用 unknown_panel 边缘", referenced.isdisjoint(unk_edges))

    print("== Feature2：伪/琐碎尺寸裁片重标记为 unknown ==")
    big = _mk_panel("big", "front_bodice",
                    [(f"big.e1", (0, 0), (500, 0), "big.g1"),
                     (f"big.e2", (500, 0), (500, 400), "big.g2"),
                     (f"big.e3", (500, 400), (0, 400), "big.g3"),
                     (f"big.e4", (0, 400), (0, 0), "big.g4")],
                    {"big.g1": ["big.e1"], "big.g2": ["big.e2"],
                     "big.g3": ["big.e3"], "big.g4": ["big.e4"]},
                    piece_name="前片")
    tiny = _mk_panel("tiny", "front_bodice",
                     [(f"tiny.e1", (0, 0), (30, 0), "tiny.g1"),
                      (f"tiny.e2", (30, 0), (30, 20), "tiny.g2"),
                      (f"tiny.e3", (30, 20), (0, 20), "tiny.g3"),
                      (f"tiny.e4", (0, 20), (0, 0), "tiny.g4")],
                     {"tiny.g1": ["tiny.e1"], "tiny.g2": ["tiny.e2"],
                      "tiny.g3": ["tiny.e3"], "tiny.g4": ["tiny.e4"]},
                     piece_name="前片")
    marked = mark_spurious_panels_unknown([big, tiny])
    check("大裁片保持 front_bodice", big["role"] == "front_bodice")
    check("小裁片重标记为 unknown_panel", tiny["role"] == "unknown_panel")
    check("标记数量=1", marked == 1)
    check("小裁片 role_source=size_degenerate", tiny.get("role_source") == "size_degenerate")
    st5 = match_seams([big, tiny])  # big 只有下层，tiny 已 unknown
    ref5 = {eid.split('.')[0] for s in st5 for eid in s.get('a_edges', []) + s.get('b_edges', [])}
    check("缝合不引用伪裁片 tiny", "tiny" not in ref5)

    print("== Feature3：几何兜底禁止跨功能组（袖/身/领）交叉缝合 ==")
    # 袖缝(underarm)与主体肩缝(shoulder)即使长度相近，也绝不能在兜底阶段互缝
    check("袖↔身：禁止（袖缝↔肩缝）", _geom_cross_family_banned("sleeve", "front_bodice") is True)
    check("身↔袖：禁止（领口↔袖缝）", _geom_cross_family_banned("back_bodice", "sleeve") is True)
    check("领↔身：禁止", _geom_cross_family_banned("collar", "front_bodice") is True)
    check("身↔领：禁止", _geom_cross_family_banned("back_bodice", "binding_strip") is True)
    check("袖↔领：禁止", _geom_cross_family_banned("sleeve", "collar") is True)
    check("袖↔袖：允许（两片袖上下片）", _geom_cross_family_banned("sleeve", "two_piece_sleeve_upper") is False)
    check("身↔身：允许（贴边/衣身同组）", _geom_cross_family_banned("front_bodice", "back_bodice") is False)
    check("贴边↔身：允许（同属身侧）", _geom_cross_family_banned("front_facing", "front_bodice") is False)

    print("== Feature4：缝合方向统一（同一裁片从左到右、从上到下）==")
    # 构造一段"反向"大边：成员边沿轮廓序，但其物理上最左/最上端应是起点
    # 直接用 _canonical_point 与规范化比较
    check("方向键：更左(x 小)比较更左", _canonical_point([10, 5]) < _canonical_point([20, 5]))
    check("方向键：x 相同→更上(y 大)更靠前", _canonical_point([10, 30]) < _canonical_point([10, 5]))
    # 通过 _chain_endpoints 端到端：物理更左端为起点
    panel_h = {
        "panel_id": "p_h",
        "edges": [
            {"edge_id": "p_h.e1", "start_point": [100.0, 50.0], "end_point": [150.0, 50.0]},
            {"edge_id": "p_h.e2", "start_point": [150.0, 50.0], "end_point": [200.0, 50.0]},
        ],
        "edge_groups": [{"group_id": "g_h", "member_edge_ids": ["p_h.e1", "p_h.e2"]}],
    }
    f, l = _chain_endpoints(panel_h, ["g_h"])
    check("水平大边：起点=更左端(e1.start)", f == {"edge_id": "p_h.e1", "endpoint": "start"})
    check("水平大边：终点=更右端(e2.end)", l == {"edge_id": "p_h.e2", "endpoint": "end"})
    # 反向成员边序：物理更左端位于链尾，仍应被选为起点
    panel_h_rev = {
        "panel_id": "p_hr",
        "edges": [
            {"edge_id": "p_hr.e1", "start_point": [200.0, 50.0], "end_point": [150.0, 50.0]},
            {"edge_id": "p_hr.e2", "start_point": [150.0, 50.0], "end_point": [100.0, 50.0]},
        ],
        "edge_groups": [{"group_id": "g_hr", "member_edge_ids": ["p_hr.e1", "p_hr.e2"]}],
    }
    f2, l2 = _chain_endpoints(panel_h_rev, ["g_hr"])
    check("反向链：起点=链尾的更左端", f2 == {"edge_id": "p_hr.e2", "endpoint": "end"})
    check("反向链：终点=链首的更右端", l2 == {"edge_id": "p_hr.e1", "endpoint": "start"})
    # 竖直大边：x 相同，y 更大（屏幕上更上）为起点
    panel_v = {
        "panel_id": "p_v",
        "edges": [
            {"edge_id": "p_v.e1", "start_point": [30.0, 80.0], "end_point": [30.0, 40.0]},
            {"edge_id": "p_v.e2", "start_point": [30.0, 40.0], "end_point": [30.0, 10.0]},
        ],
        "edge_groups": [{"group_id": "g_v", "member_edge_ids": ["p_v.e1", "p_v.e2"]}],
    }
    f3, l3 = _chain_endpoints(panel_v, ["g_v"])
    check("竖直大边：起点=更上(y大)端", f3 == {"edge_id": "p_v.e1", "endpoint": "start"})
    check("竖直大边：终点=更下(y小)端", l3 == {"edge_id": "p_v.e2", "endpoint": "end"})
    # 空列表 / 缺边回退：不崩溃
    check("空组 → 空 refs", _chain_endpoints(panel_h, []) == ({}, {}))
    check("空边缘 → 空 refs", _chain_endpoints({"edges": [], "edge_groups": []}, ["x"]) == ({}, {}))

    print(f"\n==== 结果: {PASS} 通过, {FAIL} 失败 ====")
    sys.exit(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    main()