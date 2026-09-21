# -*- coding: utf-8 -*-
"""滚边条/大边端点对应回归测试。

验证两个设计约束：
  1. 端点识别：即使大边组仅有单条成员小边（滚边条常见形态），也要产出两个独立端点
     （组起点=首边起点、组终点=末边终点）。
  2. 自动标注：point_matches 严格遵循交叉对应 —— A侧起点↔B侧终点、A侧终点↔B侧起点。
"""
import sys
import logging

sys.path.insert(0, r'd:\project\0824cloth\0901dxf\auto-seam\auto-annotator')
logging.disable(logging.CRITICAL)

from app.core.semantics import (  # noqa: E402
    _chain_endpoints, _make_stitch, _canonical_point,
    _binding_long_stitch, _binding_neckline_stitch,
)

PASS = 0
FAIL = 0


def check(label, cond):
    global PASS, FAIL
    PASS += 1 if cond else 0
    FAIL += 0 if cond else 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}")


def _edge(eid, sp, ep, role="seam_edge"):
    return {
        "edge_id": eid,
        "start_point": list(sp),
        "end_point": list(ep),
        "length": None,
        "role": role,
    }


def _bind_panel(panel_id, groups, edges):
    """构造一个含边组定义的裁片（滚边条：厚度方向的两条长边各成一组）。"""
    return {
        "panel_id": panel_id,
        "edges": edges,
        "edge_groups": [
            {"group_id": gid, "member_edge_ids": members}
            for gid, members in groups.items()
        ],
    }


# ---- 场景 1：A/B 两侧各为“单条成员小边”的滚边条大边 ----
# A 侧纵向边：从上到下 (x 相同)
aedgeA = _edge("bindA.line", [10.0, 60.0], [10.0, 20.0])
# B 侧纵向边：同上
aedgeB = _edge("bindB.line", [40.0, 60.0], [40.0, 20.0])
panelA = _bind_panel("bindA", {"bindA.g1": ["bindA.line"]}, [aedgeA])
panelB = _bind_panel("bindB", {"bindB.g1": ["bindB.line"]}, [aedgeB])

# ---- 场景 2：A/B 两侧各为多成员边组（普通大边）----
multiA = _bind_panel(
    "multiA",
    {"multiA.g1": ["mA.e1", "mA.e2"]},
    [
        _edge("mA.e1", [0.0, 50.0], [50.0, 50.0]),
        _edge("mA.e2", [50.0, 50.0], [100.0, 50.0]),
    ],
)
multiB = _bind_panel(
    "multiB",
    {"multiB.g1": ["mB.e1", "mB.e2"]},
    [
        _edge("mB.e1", [200.0, 50.0], [150.0, 50.0]),
        _edge("mB.e2", [150.0, 50.0], [100.0, 50.0]),
    ],
)


def test_chain_single_member_yields_two_endpoints():
    print("== 场景1：单成员组应产出起点+终点两个端点 ==")
    f, l = _chain_endpoints(panelA, ["bindA.g1"])
    check("组起点非空", bool(f))
    check("组终点非空", bool(l))
    check("起点=首(也是唯一)小边绑定的端点", f.get("edge_id") == "bindA.line")
    check("终点=同小边另一端点", l.get("edge_id") == "bindA.line")
    # 物理上：竖向边 x 相同 -> 起点应为 y 更大(更上)端
    sp = _canonical_point(aedgeA["start_point"])
    ep = _canonical_point(aedgeA["end_point"])
    expect_first = "start" if sp <= ep else "end"
    check("起点指向更上端", f.get("endpoint") == expect_first)
    check("两 refs 不重复", dict(f) != dict(l))


def test_make_stitch_cross_single_member():
    print("== 单成员组的自动交叉标注 ==")
    s = _make_stitch("st", "bind", [(panelA, ["bindA.g1"])],
                     [(panelB, ["bindB.g1"])], 0.7, "manual")
    pm = s.get("point_matches") or []
    check("恰好 2 组点对应", len(pm) == 2)
    a_first = _chain_endpoints(panelA, ["bindA.g1"])[0]  # A起点
    a_last = _chain_endpoints(panelA, ["bindA.g1"])[1]   # A终点
    b_first = _chain_endpoints(panelB, ["bindB.g1"])[0]  # B起点
    b_last = _chain_endpoints(panelB, ["bindB.g1"])[1]   # B终点
    check("match[0]: A起点↔B终点", pm[0]["a"] == a_first and pm[0]["b"] == b_last)
    check("match[1]: A终点↔B起点", pm[1]["a"] == a_last and pm[1]["b"] == b_first)


def test_make_stitch_cross_multi_member():
    print("== 多成员组的自动交叉标注 ==")
    s = _make_stitch("st2", "seam", [(multiA, ["multiA.g1"])],
                     [(multiB, ["multiB.g1"])], 0.9, "rule_inferred")
    pm = s.get("point_matches") or []
    check("恰好 2 组点对应", len(pm) == 2)
    a_first = _chain_endpoints(multiA, ["multiA.g1"])[0]
    a_last = _chain_endpoints(multiA, ["multiA.g1"])[1]
    b_first = _chain_endpoints(multiB, ["multiB.g1"])[0]
    b_last = _chain_endpoints(multiB, ["multiB.g1"])[1]
    check("match[0]: A起点↔B终点", pm[0]["a"] == a_first and pm[0]["b"] == b_last)
    check("match[1]: A终点↔B起点", pm[1]["a"] == a_last and pm[1]["b"] == b_first)


def _bind_rect_panel():
    """构造滚边条矩形裁片：厚度方向两条竖向长边（x 不同但同为竖向）。"""
    eA = _edge("bindA.line", [10.0, 60.0], [10.0, 20.0])
    eB = _edge("bindB.line", [40.0, 60.0], [40.0, 20.0])
    return {
        "panel_id": "bindRect",
        "bbox": {"min_x": 10.0, "max_x": 40.0, "min_y": 20.0, "max_y": 60.0},
        "edges": [eA, eB],
        "edge_groups": [
            {"group_id": "gA", "member_edge_ids": ["bindA.line"]},
            {"group_id": "gB", "member_edge_ids": ["bindB.line"]},
        ],
    }


def test_binding_long_stitch_parallel():
    print("== 滚边条两长边互缝：点对应应为平行(‖)而非交叉(X) ==")
    panel = _bind_rect_panel()
    s = _binding_long_stitch(panel, ["bindA.line"], ["bindB.line"],
                             "binding_long_edge_to_long_edge", 0.6, "test")
    pm = s.get("point_matches") or []
    check("恰好 2 组点对应", len(pm) == 2)
    # a 侧起点=更上端(y 大)、终点=更下端(y 小)；b 侧同理
    a_first = _chain_endpoints(panel, ["gA"])[0]   # (10,60) 上
    a_last = _chain_endpoints(panel, ["gA"])[1]    # (10,20) 下
    b_first = _chain_endpoints(panel, ["gB"])[0]
    b_last = _chain_endpoints(panel, ["gB"])[1]
    check("match[0]: A起点↔B起点(同侧同向‖)", pm[0]["a"] == a_first and pm[0]["b"] == b_first)
    check("match[1]: A终点↔B终点(同侧同向‖)", pm[1]["a"] == a_last and pm[1]["b"] == b_last)
    check("非交叉: match[0].b 非 B终点", pm[0]["b"] != b_last)


def _neck_panel(pid, x_bbox, sp, ep, gid):
    e = _edge(f"{pid}.line", sp, ep)
    return {
        "panel_id": pid,
        "bbox": {"min_x": x_bbox[0], "max_x": x_bbox[1], "min_y": 0.0, "max_y": 120.0},
        "edges": [e],
        "edge_groups": [{"group_id": gid, "member_edge_ids": [f"{pid}.line"]}],
    }


def test_binding_neckline_stitch_four_matches():
    print("== 滚边条↔大身前后片领口：一对多四点对应 ==")
    # 滚边条长边：水平从左到右，起点 L=更左、终点 R=更右
    binding = {
        "panel_id": "bind",
        "bbox": {"min_x": 0.0, "max_x": 80.0, "min_y": 85.0, "max_y": 90.0},
        "edges": [_edge("bind.long", [0.0, 90.0], [80.0, 90.0])],
        "edge_groups": [{"group_id": "bind.g", "member_edge_ids": ["bind.long"]}],
    }
    # 前片领口：x 质心较小；水平线从左到右
    front = _neck_panel("front", [0.0, 200.0], [0.0, 80.0], [50.0, 80.0], "front.neck")
    # 后片领口：x 质心较大
    back = _neck_panel("back", [300.0, 500.0], [0.0, 40.0], [50.0, 40.0], "back.neck")

    s = _binding_neckline_stitch("", binding, "bind.g", [(front, front["edge_groups"][0]), (back, back["edge_groups"][0])],
                                 0.55, "test")
    pm = s.get("point_matches") or []
    check("恰好 4 组点对应", len(pm) == 4, )
    a_first = _chain_endpoints(binding, ["bind.g"])[0]   # a.L (0,90)
    a_last = _chain_endpoints(binding, ["bind.g"])[1]    # a.R (80,90)
    f_first = _chain_endpoints(front, ["front.neck"])[0]
    f_last = _chain_endpoints(front, ["front.neck"])[1]
    b_first = _chain_endpoints(back, ["back.neck"])[0]
    b_last = _chain_endpoints(back, ["back.neck"])[1]
    # 映射订单：a.L↔前R、a.R↔前L、a.L↔后L、a.R↔后R
    check("a.L ↔ 前片领口 R", pm[0]["a"] == a_first and pm[0]["b"] == f_last)
    check("a.R ↔ 前片领口 L", pm[1]["a"] == a_last and pm[1]["b"] == f_first)
    check("a.L ↔ 后片领口 L", pm[2]["a"] == a_first and pm[2]["b"] == b_first)
    check("a.R ↔ 后片领口 R", pm[3]["a"] == a_last and pm[3]["b"] == b_last)


if __name__ == "__main__":
    test_chain_single_member_yields_two_endpoints()
    test_make_stitch_cross_single_member()
    test_make_stitch_cross_multi_member()
    test_binding_long_stitch_parallel()
    test_binding_neckline_stitch_four_matches()
    print(f"\n==== 通过 {PASS} / 失败 {FAIL} ====")
    sys.exit(1 if FAIL else 0)