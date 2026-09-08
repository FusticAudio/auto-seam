# -*- coding: utf-8 -*-
"""语义推理：片名 -> 版片角色；边组几何分类；缝合关系规则匹配 + 几何兜底。"""
from __future__ import annotations

import logging
import math
from typing import Any

logger = logging.getLogger(__name__)

# 绑定条（binding strip）精确名称（忽略大小写与多余空白）
BINDING_STRIP_NAME = "binding strip"

# ---------------------------------------------------------------------------
# 片名关键词 -> 版片角色（语义库 §3），按关键词长度降序匹配
# ---------------------------------------------------------------------------
ROLE_RULES: list[tuple[str, str]] = [
    ("左前育克", "left_front_yoke"),
    ("右前育克", "right_front_yoke"),
    ("前育克", "front_yoke"),
    ("后育克", "back_yoke"),
    ("两片袖大袖", "two_piece_sleeve_upper"),
    ("两片袖小袖", "two_piece_sleeve_under"),
    ("左前衣片", "left_front_bodice"),
    ("右前衣片", "right_front_bodice"),
    ("左后衣片", "left_back_bodice"),
    ("右后衣片", "right_back_bodice"),
    ("衬衫上领", "shirt_collar_upper"),
    ("衬衫领座", "shirt_collar_stand"),
    ("门襟里贴", "facing"),
    ("前门襟贴边", "front_facing"),
    ("袖口贴边", "sleeve_facing"),
    ("领口贴边", "neck_facing"),
    ("袖窿贴边", "armhole_facing"),
    ("下摆贴边", "hem_facing"),
    ("斜裁滚条", "bias_binding"),
    ("滚边条", "binding_strip"),
    ("领螺纹", "binding_strip"),
    ("插肩袖", "raglan_sleeve"),
    ("连身袖", "kimono_sleeve"),
    ("袖克夫", "cuff"),
    ("袖衩片", "sleeve_placket"),
    ("前袖片", "front_sleeve"),
    ("后袖片", "back_sleeve"),
    ("前腰头", "front_waistband"),
    ("后腰头", "back_waistband"),
    ("腰头", "waistband"),
    ("前腰贴", "waistband"),
    ("腰贴", "waistband"),
    ("立领", "stand_collar"),
    ("翻驳领", "lapel"),
    ("缺口驳领", "notched_lapel"),
    ("青果领", "shawl_collar"),
    ("帽中片", "hood_center_panel"),
    ("帽侧片", "hood_side_panel"),
    ("帽片", "hood_side_panel"),
    ("袋盖", "flap"),
    ("口袋布", "pocket_bag"),
    ("贴袋", "patch_pocket"),
    ("嵌线袋", "welt_pocket_piece"),
    ("前里布", "front_lining"),
    ("后里布", "back_lining"),
    ("袖里布", "sleeve_lining"),
    ("里布", "lining"),
    ("门襟", "placket"),
    ("袖口", "cuff"),
    ("后袖", "back_sleeve"),
    ("后上", "back_yoke"),
    ("后中", "back_bodice"),
    ("后下", "back_bodice"),
    ("前上", "front_bodice"),
    ("前下", "front_bodice"),
    ("左前", "left_front_bodice"),
    ("右前", "right_front_bodice"),
    ("左后", "left_back_bodice"),
    ("右后", "right_back_bodice"),
    ("前片", "front_bodice"),
    ("后片", "back_bodice"),
    ("前襟", "placket"),
    ("里贴", "facing"),
    ("贴边", "facing"),
    ("见返", "facing"),
    ("里襟", "fly_shield"),
    ("插角片", "godet_panel"),
    ("门襟延伸", "fly_extension"),
    ("前裆", "front_pants"),
    ("后裆", "back_pants"),
    ("前裤", "front_pants"),
    ("后裤", "back_pants"),
    ("前裙", "skirt_front"),
    ("后裙", "skirt_back"),
    ("裙片", "skirt_panel"),
    ("领脚", "shirt_collar_stand"),
    ("上领", "shirt_collar_upper"),
    ("领", "collar"),
    ("袖", "sleeve"),
    ("前", "front_bodice"),
    ("后", "back_bodice"),
]

FRONT_ROLES = {"front_bodice", "right_front_bodice", "left_front_bodice"}
BACK_ROLES = {"back_bodice", "right_back_bodice", "left_back_bodice", "back_yoke"}
BODICE_ROLES = FRONT_ROLES | BACK_ROLES
SLEEVE_ROLES = {"sleeve", "front_sleeve", "back_sleeve", "one_piece_sleeve",
                "two_piece_sleeve_upper", "two_piece_sleeve_under", "raglan_sleeve", "kimono_sleeve"}
COLLAR_ROLES = {"collar", "stand_collar", "shirt_collar_upper", "shirt_collar_stand",
                "binding_strip", "bias_binding", "lapel", "notched_lapel", "shawl_collar"}

# 边组 -> 边语义（语义库 §5.2 / §5.3）
EDGE_ROLE_MAP = {
    "hem": "hem_edge",
    "neckline": "front_neckline_edge" if False else "neckline_edge",
    "shoulder": "shoulder_edge",
    "armhole": "armhole_edge",
    "side": "side_seam_edge",
    "cap": "sleeve_cap_edge",
    "underarm": "sleeve_underarm_edge",
    "sleeve_hem": "sleeve_hem_edge",
    "long_edge": "unknown_edge",
}


def is_binding_strip_name(piece_name: str | None) -> bool:
    """精确匹配名称为 "binding strip" 的裁片（忽略大小写与多余空白）。

    仅当完整名称（剥离首尾、压缩空白、小写化）与 "binding strip" 完全一致时
    返回 True，用于排除类似但并不完全相同的名称（如 "binding"、"binding strip x"）。
    """
    if not piece_name:
        return False
    normalized = " ".join(piece_name.split()).lower()
    return normalized == BINDING_STRIP_NAME


def role_from_piece_name(piece_name: str | None) -> tuple[str, str | None, float]:
    """片名 -> (role, matched_keyword, confidence)。无匹配返回 unknown_panel。"""
    if not piece_name:
        return "unknown_panel", None, 0.0
    if is_binding_strip_name(piece_name):
        return "binding_strip", BINDING_STRIP_NAME, 0.98
    for keyword, role in sorted(ROLE_RULES, key=lambda item: -len(item[0])):
        if keyword in piece_name:
            confidence = 0.9 if len(keyword) >= 2 else 0.6
            return role, keyword, confidence
    return "unknown_panel", None, 0.0


def assign_roles(panels: list[dict[str, Any]], handle_to_piece: dict[str, str]) -> None:
    """为每个面板绑定 piece_name（源句柄 -> 片名，兜底最近文本）与 role。"""
    for panel in panels:
        handles = panel["source_entity"].get("handles") or [panel["source_entity"]["handle"]]
        piece_name = next((handle_to_piece.get(h) for h in handles if handle_to_piece.get(h)), None)
        if piece_name is None:
            piece_name = _nearest_piece_text(panel, handle_to_piece)
        role, keyword, confidence = role_from_piece_name(piece_name)
        panel["piece_name"] = piece_name
        panel["role"] = role
        panel["role_source"] = "piece_name" if keyword else "unknown"
        panel["confidence"] = round(min(panel["confidence"], confidence or 0.3) if not keyword else
                                   max(panel["confidence"] * 0.6, confidence) if piece_name else panel["confidence"], 3)


def reclassify_binding_strips(panels: list[dict[str, Any]]) -> None:
    """几何兜底：将被归类为 collar、但实为细长矩形（领口滚条）的裁片重分类为 binding_strip。

    短袖针织领口多用细长矩形滚条构成（如 12后背小熊短袖的 "领" 为 500×49 矩形）；
    真正的衬衫领 / 两片领为异形或多片（如 CK POLO 的两片领、LV 的领+领脚）。
    仅当 role==collar 且几何判定为长条矩形时重分类，避免误伤异形真领。
    重分类后由 match_seams 步骤 2.5 为其建立两条长边的互缝。
    """
    for panel in panels:
        if panel.get("role") != "collar":
            continue
        sides = rectangle_long_edges(panel)
        if sides is None:
            continue
        logger.info(
            "binding strip %s: role=collar 且为长条矩形，重分类为 binding_strip（piece_name=%r）",
            panel["panel_id"], panel.get("piece_name"),
        )
        panel["role"] = "binding_strip"
        panel["role_source"] = "shape_inferred"


# 伪裁片尺寸判定：该裁片最大边长占本服装最大裁片边长之比低于此值即视为琐碎/伪裁片。
# 依据 11 个样本统计：真小裁片（门襟 0.24、拉边 0.24、后袖 0.25~0.28）均 >=0.24，
# 伪裁片（13FG 0.09/0.11、14KITH 0.13、15LV 0.02、9BOY 0.09）均 <=0.13，取 0.20 可完全分离。
_UNKNOWN_SIZE_RATIO_MAX = 0.20


def mark_spurious_panels_unknown(panels: list[dict[str, Any]]) -> int:
    """将尺寸远小于服装主体（<0.20 最大裁片边长）的伪/琐碎裁片重标记为 unknown_panel。

    这类伪裁片多由 DXF 中的碎线/内部标记/残片形成，却被 Piece Name 误判为
    front/back 等有效类型。标记为 unknown_panel 后，match_seams 步骤 0 会将其
    所有边缘排除在缝合之外，并写入不参与缝合的原因提示。

    返回本次标记的伪裁片数量。
    """
    if not panels:
        return 0
    max_side = max(
        max(x["bbox"]["max_x"] - x["bbox"]["min_x"],
            x["bbox"]["max_y"] - x["bbox"]["min_y"]) for x in panels
    )
    if max_side <= 0:
        return 0
    marked = 0
    for panel in panels:
        w = panel["bbox"]["max_x"] - panel["bbox"]["min_x"]
        h = panel["bbox"]["max_y"] - panel["bbox"]["min_y"]
        ratio = max(w, h) / max_side
        if ratio >= _UNKNOWN_SIZE_RATIO_MAX:
            continue
        if panel.get("role") == "unknown_panel":
            continue
        logger.info(
            "panel %s: 尺寸占比=%.2f(<%.2f)，判定为琐碎/伪裁片，重标记为 unknown_panel（piece_name=%r）",
            panel["panel_id"], ratio, _UNKNOWN_SIZE_RATIO_MAX, panel.get("piece_name"),
        )
        panel["role"] = "unknown_panel"
        panel["role_source"] = "size_degenerate"
        marked += 1
    return marked


def _nearest_piece_text(panel: dict[str, Any], handle_to_piece: dict[str, str]) -> str | None:
    # 兜底：按面板质心到片名文本位置最近者（需在 schema 阶段注入文本位置）
    texts = panel.get("_piece_text_positions") or []
    if not texts:
        return None
    cx, cy = panel["centroid"]
    best = None
    best_dist = float("inf")
    for name, (tx, ty) in texts:
        dist = ((cx - tx) ** 2 + (cy - ty) ** 2) ** 0.5
        if dist < best_dist:
            best_dist = dist
            best = name
    return best


# ---------------------------------------------------------------------------
# 边组几何分类
# ---------------------------------------------------------------------------

def group_midpoint(group: dict[str, Any], edges: list[dict[str, Any]]) -> list[float]:
    lookup = {e["edge_id"]: e for e in edges}
    xs: list[float] = []
    ys: list[float] = []
    for edge_id in group.get("member_edge_ids") or []:
        edge = lookup.get(edge_id)
        if not edge:
            continue
        for pt in edge.get("sampled_points") or [edge["start_point"], edge["end_point"]]:
            xs.append(pt[0])
            ys.append(pt[1])
    if not xs:
        return [0.0, 0.0]
    return [sum(xs) / len(xs), sum(ys) / len(ys)]


def _group_y_span(group: dict[str, Any], edges: list[dict[str, Any]]) -> tuple[float, float]:
    """返回边组的 (最高y, 最低y)（基于采样点/端点）。"""
    lookup = {e["edge_id"]: e for e in edges}
    ys: list[float] = []
    for edge_id in group.get("member_edge_ids") or []:
        edge = lookup.get(edge_id)
        if not edge:
            continue
        for pt in edge.get("sampled_points") or [edge["start_point"], edge["end_point"]]:
            ys.append(pt[1])
    if not ys:
        return 0.0, 0.0
    return max(ys), min(ys)


def classify_panel_groups(panel: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """按几何位置把面板边组分类为 hem/neckline/shoulder/armhole/side/cap/underarm 等。"""
    result: dict[str, list[dict[str, Any]]] = {
        "hem": [], "neckline": [], "shoulder": [], "armhole": [],
        "side": [], "cap": [], "underarm": [], "sleeve_hem": [],
        "long_edge": [], "other": [],
    }
    groups = panel.get("edge_groups") or []
    edges = panel.get("edges") or []
    if not groups:
        return result
    box = panel["bbox"]
    w = box["max_x"] - box["min_x"]
    h = box["max_y"] - box["min_y"]
    if w <= 0 or h <= 0:
        return result
    cx, cy = panel["centroid"]
    role = panel["role"]
    mids = {g["group_id"]: group_midpoint(g, edges) for g in groups}

    if role in BODICE_ROLES:
        _classify_bodice(result, groups, mids, box, cx, w, h, edges)
    elif role in SLEEVE_ROLES:
        _classify_sleeve(result, groups, mids, box)
    elif role in COLLAR_ROLES:
        _classify_collar(result, groups)
    else:
        result["other"] = list(groups)
    # 写回边组/边语义角色
    role_map = {"hem": "hem_edge", "neckline": "neckline_edge", "shoulder": "shoulder_edge",
                "armhole": "armhole_edge", "side": "side_seam_edge", "cap": "sleeve_cap_edge",
                "underarm": "sleeve_underarm_edge", "sleeve_hem": "sleeve_hem_edge",
                "long_edge": "unknown_edge"}
    edge_lookup = {e["edge_id"]: e for e in edges}
    for kind, items in result.items():
        semantic = role_map.get(kind)
        if not semantic:
            continue
        for group in items:
            group["role"] = semantic
            for edge_id in group.get("member_edge_ids") or []:
                edge = edge_lookup.get(edge_id)
                if edge and edge["role"] == "unknown_edge":
                    edge["role"] = semantic
    return result


def _classify_bodice(result: dict[str, list[dict[str, Any]]], groups: list[dict[str, Any]],
                     mids: dict[str, list[float]], box: dict[str, float],
                     cx: float, w: float, h: float, edges: list[dict[str, Any]]) -> None:
    min_y = box["min_y"]
    hem = [g for g in groups if mids[g["group_id"]][1] <= min_y + 0.15 * h]
    rest = [g for g in groups if g["group_id"] not in {x["group_id"] for x in hem}]
    result["hem"] = hem
    top = [g for g in rest if mids[g["group_id"]][1] >= min_y + 0.7 * h]
    # 领口：顶部、靠近水平中心
    neckline = [g for g in top if abs(mids[g["group_id"]][0] - cx) <= 0.15 * w]
    if neckline:
        result["neckline"] = [max(neckline, key=lambda g: g["length"])]
        rest = [g for g in rest if g["group_id"] not in {x["group_id"] for x in result["neckline"]}]
    # 侧缝：每侧取底端接近下摆（纵向延伸到底部）的最长边组
    side_cands = ([g for g in rest if mids[g["group_id"]][0] < cx],
                  [g for g in rest if mids[g["group_id"]][0] >= cx])
    hem_level = min_y + 0.25 * h
    for side_items in side_cands:
        reach_hem = [g for g in side_items if _group_y_span(g, edges)[1] <= hem_level]
        if reach_hem:
            side_seam = max(reach_hem, key=lambda g: g["length"])
            result["side"].append(side_seam)
    used_ids = {g["group_id"] for g in result["hem"] + result["neckline"] + result["side"]}
    # 袖窿：每侧剩余边组中纵向延伸最大者（从肩点垂到腋下）
    remaining = [g for g in rest if g["group_id"] not in used_ids]
    for side_items in ([g for g in remaining if mids[g["group_id"]][0] < cx],
                       [g for g in remaining if mids[g["group_id"]][0] >= cx]):
        if not side_items:
            continue
        armhole = max(side_items, key=lambda g: _group_y_span(g, edges)[0] - _group_y_span(g, edges)[1])
        result["armhole"].append(armhole)
    used_ids |= {g["group_id"] for g in result["armhole"]}
    # 肩缝：剩余中位于顶部的边组（两端都位于肩部区域）
    top_level = min_y + 0.6 * h
    for g in rest:
        if g["group_id"] in used_ids:
            continue
        if mids[g["group_id"]][1] >= top_level:
            result["shoulder"].append(g)
        else:
            result["other"].append(g)


def _classify_sleeve(result: dict[str, list[dict[str, Any]]], groups: list[dict[str, Any]],
                     mids: dict[str, list[float]], box: dict[str, float]) -> None:
    if len(groups) <= 2:
        result["other"] = list(groups)
        return
    ordered = sorted(groups, key=lambda g: mids[g["group_id"]][1])
    result["sleeve_hem"] = [ordered[0]]
    min_mid_y = mids[ordered[0]["group_id"]][1]
    max_mid_y = mids[ordered[-1]["group_id"]][1]
    cap_threshold = max_mid_y - 0.15 * (max_mid_y - min_mid_y)
    caps = [g for g in groups if mids[g["group_id"]][1] >= cap_threshold]
    result["cap"] = caps
    result["underarm"] = [g for g in groups
                          if g["group_id"] not in {x["group_id"] for x in result["sleeve_hem"]}
                          and g["group_id"] not in {x["group_id"] for x in caps}]


def _classify_collar(result: dict[str, list[dict[str, Any]]], groups: list[dict[str, Any]]) -> None:
    if not groups:
        return
    ordered = sorted(groups, key=lambda g: -g["length"])
    result["long_edge"] = ordered[:2]
    result["other"] = ordered[2:]


# ---------------------------------------------------------------------------
# 袖片对称性检测与前后袖缝匹配验证
#
# 单片袖（one-piece sleeve）的前袖缝线与后袖缝线应互成镜像：将前袖缝线沿
# 袖片对称轴翻转后，应与后袖缝线形状接近重合。袖片整体应接近轴对称。
# ---------------------------------------------------------------------------
_SYM_SCORE_MIN = 0.85  # 袖片整体轴对称得分阈值
_SYM_OVERLAP_MIN = 0.85  # 前袖缝翻转后与后袖缝形状重合得分阈值


def _all_points(panel: dict[str, Any]) -> list[list[float]]:
    pts: list[list[float]] = []
    for edge in panel.get("edges") or []:
        pts.extend(edge.get("sampled_points") or [edge["start_point"], edge["end_point"]])
    return pts


def _avg_nearest_dist(src_pts: list[list[float]], tgt_pts: list[list[float]]) -> float:
    """src 每个点到 tgt 最近点的平均距离；任一边为空返回无穷大。"""
    if not src_pts or not tgt_pts:
        return float("inf")
    total = 0.0
    for sx, sy in src_pts:
        best = min(math.hypot(sx - tx, sy - ty) for tx, ty in tgt_pts)
        total += best
    return total / len(src_pts)


def _group_points(panel: dict[str, Any], groups: list[dict[str, Any]]) -> list[list[float]]:
    lookup = {e["edge_id"]: e for e in panel["edges"]}
    pts: list[list[float]] = []
    for group in groups:
        for edge_id in group.get("member_edge_ids") or []:
            edge = lookup.get(edge_id)
            if edge:
                pts.extend(edge.get("sampled_points") or [edge["start_point"], edge["end_point"]])
    return pts


def sleeve_symmetry_score(panel: dict[str, Any]) -> float:
    """袖片整体轴对称得分（0~1）。

    以袖片垂直中轴（质心 x）为镜轴，把全部轮廓点做镜像，度量镜像点与原轮廓
    最近点平均距离相对其特征尺度的占比。越接近轴对称，得分越高。
    """
    pts = _all_points(panel)
    if len(pts) < 4:
        return 0.0
    axis_x = sum(p[0] for p in pts) / len(pts)
    reflected = [[2.0 * axis_x - x, y] for x, y in pts]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    scale = max(max(xs) - min(xs), max(ys) - min(ys))
    if scale < 1e-9:
        return 0.0
    dist = _avg_nearest_dist(reflected, pts)
    return max(0.0, 1.0 - dist / scale)


def mirror_seam_overlap(panel: dict[str, Any], front_group: dict[str, Any],
                        back_group: dict[str, Any]) -> float:
    """前袖缝线翻转后与后袖缝线形状的重合度（0~1）。

    沿袖片垂直中轴翻转前袖缝线上的点，度量与后袖缝线最近点平均距离相对
    袖缝线长度的占比。两线互成镜像时得分趋近 1。
    """
    a = _group_points(panel, [front_group])
    b = _group_points(panel, [back_group])
    if len(a) < 2 or len(b) < 2:
        return 0.0
    axis_x = sum(p[0] for p in _all_points(panel)) / len(_all_points(panel))
    a_ref = [[2.0 * axis_x - x, y] for x, y in a]
    scale = max(front_group.get("length", 0.0) or 0.0,
                back_group.get("length", 0.0) or 0.0)
    if scale < 1e-9:
        return 0.0
    dist = _avg_nearest_dist(a_ref, b)
    return max(0.0, 1.0 - dist / scale)


def validate_sleeve_seam_pair(panel: dict[str, Any], underarm_groups: list[dict[str, Any]],
                             ) -> tuple[bool, float, float]:
    """验证单片袖的前/后袖缝是否可配对缝合。

    返回 (通过与否, 整体轴对称得分, 翻转重合度)。当袖片整体接近轴对称 且
    前袖缝翻转与后袖缝形状接近重合时返回 True。
    """
    sym = sleeve_symmetry_score(panel)
    overlap = mirror_seam_overlap(panel, underarm_groups[0], underarm_groups[1])
    ok = sym >= _SYM_SCORE_MIN and overlap >= _SYM_OVERLAP_MIN
    return ok, sym, overlap


# ---------------------------------------------------------------------------
# 形状分析：binding strip 矩形检测与长边识别
# ---------------------------------------------------------------------------
_RECT_PAR_TOL = 12.0  # 边与主轴平行/垂直的判定容差（度），容忍微小形状偏差
_RECT_SHAPE_RATIO = 0.96  # 与主轴对齐（平行+垂直）的边长占周长比，低于此视为非矩形
_RECT_EVEN_RATIO = 0.85  # 两条长边长度比下限（平行对边应近似相等）
_RECT_ASPECT_MIN = 1.2  # 长边总长 / 短边总长 比下限，防止近正方形被误判为矩形长条


def _edge_unit_dir(edge: dict[str, Any]) -> tuple[float, float] | None:
    """返回边首尾方向单位向量，退化（长度≈0）时返回 None。"""
    pts = edge.get("sampled_points") or [edge["start_point"], edge["end_point"]]
    if len(pts) < 2:
        return None
    dx = pts[-1][0] - pts[0][0]
    dy = pts[-1][1] - pts[0][1]
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return None
    return dx / length, dy / length


def _panel_principal_axis(panel: dict[str, Any]) -> tuple[float, float] | None:
    """用 PCA（协方差矩阵特征方向）求裁片的延伸主轴单位向量。

    主轴即最大方差方向：对细长矩形即其长边方向，因此结果与裁片摆放旋转无关。
    点数过少时返回 None。
    """
    pts: list[list[float]] = []
    for edge in panel.get("edges") or []:
        pts.extend(edge.get("sampled_points") or [edge["start_point"], edge["end_point"]])
    n = len(pts)
    if n < 4:
        return None
    cx = sum(p[0] for p in pts) / n
    cy = sum(p[1] for p in pts) / n
    sxx = syy = sxy = 0.0
    for x, y in pts:
        x -= cx
        y -= cy
        sxx += x * x
        syy += y * y
        sxy += x * y
    theta = 0.5 * math.atan2(2.0 * sxy, sxx - syy)
    return math.cos(theta), math.sin(theta)


def rectangle_long_edges(panel: dict[str, Any]) -> tuple[list[str], list[str]] | None:
    """判定裁片是否为矩形，若是则返回两条长边的 member edge id 列表 (side_a, side_b)。

    - 矩形判定带容差：以 PCA 主轴为准，要求绝大多数边与主轴平行或垂直。
    - 长边识别与方向无关：主轴即长边方向，按垂直于主轴的投影符号把两条长边分开。
    - 非矩形 / 无法可靠提取两条长边时返回 None。
    """
    axis = _panel_principal_axis(panel)
    if axis is None:
        logger.debug("binding strip %s: 点数不足，无法做矩形判定", panel.get("panel_id"))
        return None
    ortho = (-axis[1], axis[0])  # 垂直于主轴的单位方向（短边方向）
    tol = math.cos(math.radians(_RECT_PAR_TOL))

    centroid = panel["centroid"]
    parallel: list[dict[str, Any]] = []  # ∥ 主轴 -> 两条长边候选
    perpendicular: list[dict[str, Any]] = []  # ⊥ 主轴 -> 两条短边
    total_len = aligned_len = 0.0
    for edge in panel.get("edges") or []:
        length = float(edge.get("length", 0.0) or 0.0)
        total_len += length
        direction = _edge_unit_dir(edge)
        if direction is None:
            continue
        along = abs(direction[0] * axis[0] + direction[1] * axis[1])
        cross = abs(direction[0] * ortho[0] + direction[1] * ortho[1])
        if along >= tol:
            parallel.append(edge)
            aligned_len += length
        elif cross >= tol:
            perpendicular.append(edge)
            aligned_len += length

    # 矩形排他性：绝大多数边须与主轴平行或垂直
    if total_len <= 1e-9 or aligned_len / total_len < _RECT_SHAPE_RATIO:
        logger.info(
            "binding strip %s: 非矩形（对齐边占比 %.1f%%），跳过长边缝合",
            panel.get("panel_id"), (aligned_len / total_len * 100) if total_len else 0.0,
        )
        return None
    if not parallel:
        return None

    def offset_of(edge: dict[str, Any]) -> float:
        pts = edge.get("sampled_points") or [edge["start_point"], edge["end_point"]]
        mx = sum(p[0] for p in pts) / len(pts) - centroid[0]
        my = sum(p[1] for p in pts) / len(pts) - centroid[1]
        return mx * ortho[0] + my * ortho[1]

    # 按垂直于主轴的投影符号把 ∥ 主轴的边分成两条长边
    side_a = [e for e in parallel if offset_of(e) >= 0.0]
    side_b = [e for e in parallel if offset_of(e) < 0.0]
    if not side_a or not side_b:
        logger.info("binding strip %s: 长边无法分成两侧，跳过", panel.get("panel_id"))
        return None

    long_a = sum(float(e.get("length", 0.0) or 0.0) for e in side_a)
    long_b = sum(float(e.get("length", 0.0) or 0.0) for e in side_b)
    short_len = sum(float(e.get("length", 0.0) or 0.0) for e in perpendicular)
    evenness = min(long_a, long_b) / max(long_a, long_b) if long_a and long_b else 0.0
    aspect = (long_a + long_b) / (2.0 * short_len) if short_len > 1e-9 else float("inf")

    if evenness < _RECT_EVEN_RATIO or aspect < _RECT_ASPECT_MIN:
        logger.info(
            "binding strip %s: 矩形度不足（长边比=%.2f 长/短比=%.2f），跳过",
            panel.get("panel_id"), evenness, aspect,
        )
        return None

    # 按轮廓顺序排序，保持方向的连续性
    order = {e["edge_id"]: i for i, e in enumerate(panel["edges"])}
    ids_a = sorted((e["edge_id"] for e in side_a), key=lambda eid: order[eid])
    ids_b = sorted((e["edge_id"] for e in side_b), key=lambda eid: order[eid])
    logger.info(
        "binding strip %s: 识别为矩形，长边A=%d边/%.1fmm 长边B=%d边/%.1fmm",
        panel.get("panel_id"), len(ids_a), long_a, len(ids_b), long_b,
    )
    return ids_a, ids_b


# ---------------------------------------------------------------------------
# 缝合关系匹配
# ---------------------------------------------------------------------------

def _chain_endpoints(panel: dict[str, Any], group_ids: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    """返回 (first_edge_ref, last_edge_ref)，按面板轮廓顺序。"""
    edge_lookup = {e["edge_id"]: e for e in panel["edges"]}
    ordered = []
    for gid in group_ids:
        group = next((g for g in panel["edge_groups"] if g["group_id"] == gid), None)
        if group:
            ordered.extend(group["member_edge_ids"])
    if not ordered:
        return {}, {}
    return (
        {"edge_id": ordered[0], "endpoint": "start"},
        {"edge_id": ordered[-1], "endpoint": "end"},
    )


def _make_stitch(stitch_id: str, relation: str,
                 side_a: list[tuple[dict[str, Any], list[str]]],
                 side_b: list[tuple[dict[str, Any], list[str]]],
                 confidence: float, source: str, type_: str = "seam") -> dict[str, Any]:
    """side_x: [(panel, [group_id, ...]), ...]，支持一侧跨多个面板（如袖山对前后袖窿）。"""
    a_ids: list[str] = []
    b_ids: list[str] = []
    a_groups_all: list[str] = []
    b_groups_all: list[str] = []
    a_refs: list[dict[str, Any]] = []
    b_refs: list[dict[str, Any]] = []
    for panel, group_ids in side_a:
        group_lookup = {g["group_id"]: g for g in panel["edge_groups"]}
        for gid in group_ids:
            group = group_lookup.get(gid)
            if group:
                a_ids.extend(group["member_edge_ids"])
                a_groups_all.append(gid)
        first, last = _chain_endpoints(panel, group_ids)
        if first and last:
            a_refs.append(first)
            a_refs.append(last)
    for panel, group_ids in side_b:
        group_lookup = {g["group_id"]: g for g in panel["edge_groups"]}
        for gid in group_ids:
            group = group_lookup.get(gid)
            if group:
                b_ids.extend(group["member_edge_ids"])
                b_groups_all.append(gid)
        first, last = _chain_endpoints(panel, group_ids)
        if first and last:
            b_refs.append(first)
            b_refs.append(last)
    a_first = a_refs[0] if a_refs else {}
    a_last = a_refs[-1] if a_refs else {}
    b_first = b_refs[0] if b_refs else {}
    b_last = b_refs[-1] if b_refs else {}
    return {
        "stitch_id": stitch_id,
        "type": type_,
        "relation": relation,
        "a": a_ids[0] if a_ids else "",
        "b": b_ids[0] if b_ids else "",
        "a_edges": a_ids,
        "b_edges": b_ids,
        "a_groups": a_groups_all,
        "b_groups": b_groups_all,
        "direction": "by_points",
        "point_matches": [
            {"a": dict(a_first), "b": dict(b_last)},
            {"a": dict(a_last), "b": dict(b_first)},
        ] if a_first and b_first else [],
        "length_tolerance": 0.03,
        "confidence": round(confidence, 2),
        "confidence_source": source,
        "review_status": "needs_review",
    }


def _greedy_faces(a_list: list[dict[str, Any]], b_list: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """按中点距离最近 + 长度比，1:1 贪心配对。"""
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    used_b: set[str] = set()
    for a in sorted(a_list, key=lambda g: -g["length"]):
        best_b = None
        best_score = -1.0
        for b in b_list:
            if b["group_id"] in used_b:
                continue
            ratio = min(a["length"], b["length"]) / max(a["length"], b["length"]) if a["length"] and b["length"] else 0.0
            if ratio < 0.85:
                continue
            score = ratio
            if best_b is None or score > best_score:
                best_score = score
                best_b = b
        if best_b is not None:
            pairs.append((a, best_b))
            used_b.add(best_b["group_id"])
    return pairs


def _cap_halves(cap: dict[str, Any], edges: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    """沿袖片对称轴（袖山最高点处）把袖山弧线分为左右两半。

    返回 (left_edge_ids, right_edge_ids)。袖片按上下方向放置，对称轴过袖山顶点
    的竖直中线；左侧为弧线的较小 x 半边，右侧为较大 x 半边。
    """
    lookup = {e["edge_id"]: e for e in edges}
    apex: list[float] = [0.0, 0.0]
    best_y = -1e18
    for edge_id in cap.get("member_edge_ids") or []:
        edge = lookup.get(edge_id)
        if not edge:
            continue
        for pt in edge.get("sampled_points") or [edge["start_point"], edge["end_point"]]:
            if pt[1] > best_y:
                best_y = pt[1]
                apex = pt
    axis_x = apex[0]
    left: list[str] = []
    right: list[str] = []
    for edge_id in cap.get("member_edge_ids") or []:
        edge = lookup.get(edge_id)
        if not edge:
            continue
        pts = edge.get("sampled_points") or [edge["start_point"], edge["end_point"]]
        mid_x = sum(pt[0] for pt in pts) / len(pts)
        (left if mid_x <= axis_x else right).append(edge_id)
    return left, right


def _group_length(edge_ids: list[str], edges: list[dict[str, Any]]) -> float:
    lookup = {e["edge_id"]: e for e in edges}
    return sum(lookup[eid]["length"] for eid in edge_ids if eid in lookup)


def _pick_armhole(armholes: list[tuple[dict[str, Any], dict[str, Any]]], side: str,
                  target_len: float, used: set[str]) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """从 (panel, group) 袖窿候选中选出指定侧（按面板质心横坐标分左右）且长度最接近者。

    side="left" 取质心左侧袖窿，side="right" 取质心右侧袖窿。
    """
    best: tuple[dict[str, Any], dict[str, Any]] | None = None
    best_ratio = 0.0
    for panel, group in armholes:
        if group["group_id"] in used:
            continue
        if not group["length"] or not target_len:
            continue
        cx = (panel["bbox"]["min_x"] + panel["bbox"]["max_x"]) / 2.0
        gx = group_midpoint(group, panel["edges"])[0]
        if side == "left" and gx >= cx:
            continue
        if side == "right" and gx < cx:
            continue
        ratio = min(group["length"], target_len) / max(group["length"], target_len)
        if ratio > best_ratio:
            best_ratio = ratio
            best = (panel, group)
    return best if best_ratio >= 0.75 else None


def _cap_half_stitch(sleeve: dict[str, Any], cap: dict[str, Any], half_edge_ids: list[str],
                     bodice: dict[str, Any], armhole: dict[str, Any],
                     relation: str, confidence: float, source: str,
                     stitch_id: str = "") -> dict[str, Any]:
    """袖山半弧 ↔ 单个袖窿 的缝合记录（半弧为沿对称轴分出的左/右半边边 id 列表）。"""
    ah_edges = armhole["member_edge_ids"]
    return {
        "stitch_id": stitch_id,
        "type": "seam",
        "relation": relation,
        "a": half_edge_ids[0] if half_edge_ids else "",
        "b": ah_edges[0] if ah_edges else "",
        "a_edges": list(half_edge_ids),
        "b_edges": list(ah_edges),
        "a_groups": [cap["group_id"]],
        "b_groups": [armhole["group_id"]],
        "direction": "by_points",
        "point_matches": [
            {"a": {"edge_id": half_edge_ids[0], "endpoint": "start"},
             "b": {"edge_id": ah_edges[-1], "endpoint": "end"}},
            {"a": {"edge_id": half_edge_ids[-1], "endpoint": "end"},
             "b": {"edge_id": ah_edges[0], "endpoint": "start"}},
        ] if half_edge_ids and ah_edges else [],
        "length_tolerance": 0.05,
        "confidence": round(confidence, 2),
        "confidence_source": source,
        "review_status": "needs_review",
    }


def _binding_long_stitch(panel: dict[str, Any], side_a_ids: list[str], side_b_ids: list[str],
                         relation: str, confidence: float, source: str,
                         stitch_id: str = "") -> dict[str, Any]:
    """binding strip 两条长边之间的缝合记录（type=binding）。

    side_a / side_b 为矩形长边两半的 edge id 列表，格式与现有 stitch 记录一致。
    """
    group_of: dict[str, str] = {}
    for group in panel.get("edge_groups") or []:
        for edge_id in group["member_edge_ids"]:
            group_of[edge_id] = group["group_id"]
    a_groups = sorted({group_of[e] for e in side_a_ids if e in group_of})
    b_groups = sorted({group_of[e] for e in side_b_ids if e in group_of})
    return {
        "stitch_id": stitch_id,
        "type": "binding",
        "relation": relation,
        "a": side_a_ids[0] if side_a_ids else "",
        "b": side_b_ids[0] if side_b_ids else "",
        "a_edges": list(side_a_ids),
        "b_edges": list(side_b_ids),
        "a_groups": a_groups,
        "b_groups": b_groups,
        "direction": "by_points",
        "point_matches": [
            {"a": {"edge_id": side_a_ids[0], "endpoint": "start"},
             "b": {"edge_id": side_b_ids[-1], "endpoint": "end"}},
            {"a": {"edge_id": side_a_ids[-1], "endpoint": "end"},
             "b": {"edge_id": side_b_ids[0], "endpoint": "start"}},
        ] if side_a_ids and side_b_ids else [],
        "length_tolerance": 0.05,
        "confidence": round(confidence, 2),
        "confidence_source": source,
        "review_status": "needs_review",
    }


def _geom_cross_family_banned(role_a: str, role_b: str) -> bool:
    """几何兜底是否禁止 role_a 与 role_b 两个裁片互缝。

    若二者分属 袖/身/领 三个功能组中的任意两个不同组，则禁止交叉缝合
    （袖↔身、领↔身、袖↔领 均不允许在兜底阶段建立缝合关系）。
    """
    if role_a in SLEEVE_ROLES and role_b in (BODICE_ROLES | COLLAR_ROLES):
        return True
    if role_b in SLEEVE_ROLES and role_a in (BODICE_ROLES | COLLAR_ROLES):
        return True
    if role_a in BODICE_ROLES and role_b in COLLAR_ROLES:
        return True
    if role_b in BODICE_ROLES and role_a in COLLAR_ROLES:
        return True
    return False


def match_seams(panels: list[dict[str, Any]]) -> list[dict[str, Any]]:
    classified = {p["panel_id"]: classify_panel_groups(p) for p in panels}
    stitches: list[dict[str, Any]] = []
    used_groups: set[str] = set()
    counter = [0]

    # 0) unknown_panel：其所有边缘不参与任何缝合（记录原因并从缝合范围排除）
    for panel in panels:
        if panel.get("role") != "unknown_panel":
            continue
        reason = (f"panel {panel['panel_id']} (role=unknown_panel, piece_name="
                  f"{panel.get('piece_name')!r})：未能从 Piece Name 推断裁片类型，"
                  f"其所有边缘（{len(panel.get('edge_groups') or [])} 个边组）不参与任何缝合关系建立。")
        logger.info("binding strip排除缝合：%s", reason)
        panel["edge_participation_note"] = (
            "unknown_panel：该裁片所有边缘不参与任何缝合关系建立"
        )
    panels = [p for p in panels if p.get("role") != "unknown_panel"]

    def add(stitch: dict[str, Any]) -> None:
        counter[0] += 1
        stitch["stitch_id"] = f"stitch_{counter[0]:03d}"
        stitches.append(stitch)
        used_groups.update(stitch["a_groups"])
        used_groups.update(stitch["b_groups"])

    # 1) 前后片：肩缝 + 侧缝（注意裁片方向与实际穿着方向的对应关系：
    #    后片左侧 ↔ 前片右侧，后片右侧 ↔ 前片左侧，两侧合成同一侧缝/肩缝圈）
    fronts = [p for p in panels if p["role"] in FRONT_ROLES]
    backs = [p for p in panels if p["role"] in BACK_ROLES]
    for front in fronts:
        for back in backs:
            f = classified[front["panel_id"]]
            b = classified[back["panel_id"]]
            f_cx = (front["bbox"]["min_x"] + front["bbox"]["max_x"]) / 2.0
            b_cx = (back["bbox"]["min_x"] + back["bbox"]["max_x"]) / 2.0
            f_sh_l = [g for g in f["shoulder"] if group_midpoint(g, front["edges"])[0] < f_cx]
            f_sh_r = [g for g in f["shoulder"] if group_midpoint(g, front["edges"])[0] >= f_cx]
            b_sh_l = [g for g in b["shoulder"] if group_midpoint(g, back["edges"])[0] < b_cx]
            b_sh_r = [g for g in b["shoulder"] if group_midpoint(g, back["edges"])[0] >= b_cx]
            for a, bb in _greedy_faces(f_sh_r, b_sh_l):
                add(_make_stitch("", "front_shoulder_to_back_shoulder",
                                 [(front, [a["group_id"]])], [(back, [bb["group_id"]])],
                                 0.7, "rule_inferred"))
            for a, bb in _greedy_faces(f_sh_l, b_sh_r):
                add(_make_stitch("", "front_shoulder_to_back_shoulder",
                                 [(front, [a["group_id"]])], [(back, [bb["group_id"]])],
                                 0.7, "rule_inferred"))
            f_si_l = [g for g in f["side"] if group_midpoint(g, front["edges"])[0] < f_cx]
            f_si_r = [g for g in f["side"] if group_midpoint(g, front["edges"])[0] >= f_cx]
            b_si_l = [g for g in b["side"] if group_midpoint(g, back["edges"])[0] < b_cx]
            b_si_r = [g for g in b["side"] if group_midpoint(g, back["edges"])[0] >= b_cx]
            for a, bb in _greedy_faces(f_si_r, b_si_l):
                add(_make_stitch("", "front_side_to_back_side",
                                 [(front, [a["group_id"]])], [(back, [bb["group_id"]])],
                                 0.7, "rule_inferred"))
            for a, bb in _greedy_faces(f_si_l, b_si_r):
                add(_make_stitch("", "front_side_to_back_side",
                                 [(front, [a["group_id"]])], [(back, [bb["group_id"]])],
                                 0.7, "rule_inferred"))

    # 2) 袖：袖底缝（同片内）+ 袖山入袖窿
    #    袖山沿对称轴分为左右两半：左半 ↔ 前片左侧袖窿，右半 ↔ 后片右侧袖窿
    #    （同一袖窿圈由前片左侧 + 后片右侧的肩点至腋下线条构成）
    front_armholes: list[tuple[dict[str, Any], dict[str, Any]]] = []
    back_armholes: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for p in panels:
        if p["role"] in FRONT_ROLES:
            for g in classified[p["panel_id"]]["armhole"]:
                front_armholes.append((p, g))
        elif p["role"] in BACK_ROLES:
            for g in classified[p["panel_id"]]["armhole"]:
                back_armholes.append((p, g))
    sleeves = [p for p in panels if p["role"] in SLEEVE_ROLES]
    used_armholes: set[str] = set()
    for sleeve in sleeves:
        cl = classified[sleeve["panel_id"]]
        underarms = cl["underarm"]
        if len(underarms) == 2:
            ratio = min(underarms[0]["length"], underarms[1]["length"]) / max(
                underarms[0]["length"], underarms[1]["length"])
            if ratio >= 0.85:
                # 单片袖：袖片整体近轴对称 且 前袖缝翻转后与后袖缝形状重合时，
                # 建立 front/back 袖缝缝合；否则降级为长度匹配的通用 seam_pair。
                matched, sym, overlap = validate_sleeve_seam_pair(sleeve, underarms)
                if matched:
                    add(_make_stitch("", "front_sleeve_seam_to_back_sleeve_seam",
                                     [(sleeve, [underarms[0]["group_id"]])],
                                     [(sleeve, [underarms[1]["group_id"]])],
                                     0.75, "rule_inferred"))
                    logger.info("sleeve %s: 轴对称(sym=%.2f)且前袖缝翻转重合(overlap=%.2f)，建立前后袖缝缝合",
                                sleeve["panel_id"], sym, overlap)
                else:
                    add(_make_stitch("", "seam_pair",
                                     [(sleeve, [underarms[0]["group_id"]])],
                                     [(sleeve, [underarms[1]["group_id"]])],
                                     0.45, "rule_inferred"))
                    logger.info("sleeve %s: 未通过袖缝对称验证(sym=%.2f, overlap=%.2f)，降级为长度匹配 seam_pair",
                                sleeve["panel_id"], sym, overlap)
        caps = cl["cap"]
        if not caps:
            continue
        sleeve_cx = (sleeve["bbox"]["min_x"] + sleeve["bbox"]["max_x"]) / 2.0
        for cap in caps:
            cap_mid = group_midpoint(cap, sleeve["edges"])
            cap_side = "left" if cap_mid[0] < sleeve_cx else "right"
            # 情形一：袖山边组本身已是半片（长度与单个袖窿相当），整体配对
            # 左半 ↔ 前片左袖窿，右半 ↔ 后片右袖窿
            target = None
            if cap_side == "left":
                target = _pick_armhole(front_armholes, "left", cap["length"], used_armholes)
            else:
                target = _pick_armhole(back_armholes, "right", cap["length"], used_armholes)
            if target is not None:
                bodice_p, armhole_g = target
                add(_cap_half_stitch(sleeve, cap, cap["member_edge_ids"], bodice_p, armhole_g,
                                     "sleeve_cap_front_to_armhole" if cap_side == "left"
                                     else "sleeve_cap_back_to_armhole",
                                     0.6, "rule_inferred"))
                used_armholes.add(armhole_g["group_id"])
                continue
            # 情形二：完整袖山，沿对称轴分为左右两半，分别与前片左袖窿/后片右袖窿配对
            left_ids, right_ids = _cap_halves(cap, sleeve["edges"])
            if len(left_ids) < 2 or len(right_ids) < 2:
                continue
            left_len = _group_length(left_ids, sleeve["edges"])
            right_len = _group_length(right_ids, sleeve["edges"])
            front_left = _pick_armhole(front_armholes, "left", left_len, used_armholes)
            back_right = _pick_armhole(back_armholes, "right", right_len, used_armholes)
            if front_left and back_right:
                (fp, fg), (bp, bg) = front_left, back_right
                fl_ratio = min(left_len, fg["length"]) / max(left_len, fg["length"])
                br_ratio = min(right_len, bg["length"]) / max(right_len, bg["length"])
                if fl_ratio >= 0.75 and br_ratio >= 0.75:
                    add(_cap_half_stitch(sleeve, cap, left_ids, fp, fg,
                                         "sleeve_cap_front_to_armhole",
                                         0.6, "rule_inferred"))
                    add(_cap_half_stitch(sleeve, cap, right_ids, bp, bg,
                                         "sleeve_cap_back_to_armhole",
                                         0.6, "rule_inferred"))
                    used_armholes.add(fg["group_id"])
                    used_armholes.add(bg["group_id"])

    # 2.5) binding strip：矩形裁片的两条长边互缝（长边 ↔ 长边）
    for panel in panels:
        if panel["role"] != "binding_strip":
            continue
        sides = rectangle_long_edges(panel)
        if sides is None:
            continue
        side_a, side_b = sides
        add(_binding_long_stitch(panel, side_a, side_b,
                                 "binding_long_edge_to_long_edge",
                                 0.6, "shape_inferred",
                                 ))

    # 3) 领/滚条 -> 领口
    necklines: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for p in panels:
        if p["role"] in BODICE_ROLES:
            for g in classified[p["panel_id"]]["neckline"]:
                necklines.append((p, g))
    if necklines:
        for collar in [p for p in panels if p["role"] in COLLAR_ROLES]:
            cl = classified[collar["panel_id"]]
            best = None
            best_ratio = 0.0
            for g in cl["long_edge"]:
                combined = sum(n[1]["length"] for n in necklines)
                ratio = min(g["length"], combined) / max(g["length"], combined)
                if ratio > best_ratio:
                    best_ratio = ratio
                    best = g
            if best and best_ratio >= 0.85:
                add(_make_stitch("", "collar_to_neckline",
                                 [(collar, [best["group_id"]])],
                                 [(n[0], [n[1]["group_id"]]) for n in necklines],
                                 0.55, "rule_inferred"))

    # 几何兜底：未匹配边组跨片长度匹配
    # 跨部件过滤：袖片(袖缝)与主体(肩缝/领口/侧缝/下摆)的实际连接仅通过规则阶段建立
    # （袖山↔袖窿、领↔领口），几何兜底若再按长度把袖缝线与主体的肩缝/领口线配对，
    # 会产生实际服装中不存在的错缝。因此兜底阶段禁止 袖/身/领 三大功能组之间的交叉缝合。
    pool: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for p in panels:
        cl = classified[p["panel_id"]]
        for g in p["edge_groups"]:
            if g["group_id"] in used_groups:
                continue
            kind = next((k for k, items in cl.items() if g in items), "other")
            if kind in {"hem", "neckline", "sleeve_hem", "cap", "armhole"}:
                continue
            pool.append((p, g))
    pool_by_len = sorted(pool, key=lambda item: -item[1]["length"])
    for i, (pa, ga) in enumerate(pool_by_len):
        if ga["group_id"] in used_groups:
            continue
        best = None
        best_ratio = 0.0
        for pb, gb in pool_by_len[i + 1:]:
            if gb["group_id"] in used_groups or pb["panel_id"] == pa["panel_id"]:
                continue
            if _geom_cross_family_banned(pa["role"], pb["role"]):
                # 跨 袖/身/领 功能组的兜底缝合一律排除（如 袖缝↔肩缝/领口、领↔侧缝）
                continue
            if not ga["length"] or not gb["length"]:
                continue
            ratio = min(ga["length"], gb["length"]) / max(ga["length"], gb["length"])
            if ratio > best_ratio:
                best_ratio = ratio
                best = (pb, gb)
        if best and best_ratio >= 0.8:
            pb, gb = best
            add(_make_stitch("", "seam_pair",
                             [(pa, [ga["group_id"]])], [(pb, [gb["group_id"]])],
                             0.35, "geometry_inferred"))
    return stitches
