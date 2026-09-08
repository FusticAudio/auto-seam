# -*- coding: utf-8 -*-
"""面板检测：候选轮廓（闭合多段线 + 开放曲线重建）、嵌套分类、边检测、边组构建。"""
from __future__ import annotations

import math
from typing import Any

from .geometry import (
    bbox,
    bbox_contains,
    canonical_polygon_key,
    clean_number,
    clean_point,
    distance,
    geometry_hash,
    point_in_polygon,
    polyline_length,
    reconstruct_cycles,
    signed_area,
)

PANEL_TYPES = {"LWPOLYLINE", "POLYLINE", "COMPOSITE"}

# 边组平滑合并参数（与人工标注基准对齐）
AUTO_JOIN_ANGLE_DEGREES = 15.0
AUTO_FRAGMENT_RATIO = 0.12
AUTO_MIN_EDGE_COUNT = 8


def detect_panels(
    records: list[dict[str, Any]],
    join_tolerance: float = 0.1,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """从实体记录中识别物理版片与缝份曲线。

    返回 (panels, diagnostics)。panels 只含主轮廓（含 edges / edge_groups /
    seam_allowances 之后由 build_panel_topology 补齐）。
    """
    # 1) 候选：所有闭合曲线实体（任意图层）+ 开放曲线端点重建的闭合环
    open_curves = [
        record
        for record in records
        if record["entity_type"] in {"LINE", "LWPOLYLINE", "POLYLINE", "ARC", "SPLINE"}
        and not record["is_closed"]
        and len(record["points"]) >= 2
    ]
    reconstructed = reconstruct_cycles(open_curves, tolerance=join_tolerance)
    candidates = [
        record
        for record in records + reconstructed
        if record["entity_type"] in PANEL_TYPES
        and record["is_closed"]
        and len(record["points"]) >= 3
        and abs(signed_area(record["points"])) > 1e-6
    ]
    candidates.sort(key=lambda item: (-abs(signed_area(item["points"])), item["bbox"]["min_x"], item["bbox"]["min_y"]))

    # 2) 去重 + 嵌套分类（内层 35%~99.9% 面积、bbox 包含、点在内部 -> 缝份）
    primary: list[dict[str, Any]] = []
    seam_groups: dict[str, list[dict[str, Any]]] = {}
    seen: set[str] = set()
    diagnostics = {"duplicate_contours_removed": 0, "seam_allowance_contours": 0, "reconstructed_cycles": len(reconstructed)}
    for candidate in candidates:
        key = canonical_polygon_key(candidate["points"])
        if key in seen:
            diagnostics["duplicate_contours_removed"] += 1
            continue
        seen.add(key)
        candidate_area = abs(signed_area(candidate["points"]))
        parent: Any = None
        for outer in primary:
            outer_area = abs(signed_area(outer["points"]))
            ratio = candidate_area / outer_area if outer_area else 0.0
            if (
                0.35 <= ratio < 0.999999
                and bbox_contains(outer["bbox"], candidate["bbox"], join_tolerance)
                and point_in_polygon(candidate["points"][0], outer["points"])
            ):
                parent = outer
                break
        if parent is not None:
            seam_groups.setdefault(parent["geometry_hash"], []).append(candidate)
            diagnostics["seam_allowance_contours"] += 1
        else:
            primary.append(candidate)

    primary.sort(key=lambda item: (item["bbox"]["min_x"], item["bbox"]["min_y"], item["geometry_hash"]))

    # 3) 组装 panel 记录
    panels: list[dict[str, Any]] = []
    for index, record in enumerate(primary, 1):
        points = [clean_point(p) for p in record["points"]]
        if record["entity_type"] == "COMPOSITE":
            source_entity = {
                "handle": record["handle"],
                "handles": [e["handle"] for e in record["source_entities"]],
                "layer": record["layer"],
                "entity_type": "COMPOSITE",
                "source_entities": record["source_entities"],
            }
            confidence = 0.85
        else:
            source_entity = {
                "handle": record["handle"],
                "layer": record["layer"],
                "entity_type": record["entity_type"],
            }
            confidence = 1.0
        center = [
            (record["bbox"]["min_x"] + record["bbox"]["max_x"]) / 2,
            (record["bbox"]["min_y"] + record["bbox"]["max_y"]) / 2,
        ]
        panel: dict[str, Any] = {
            "panel_id": f"panel_{index:03d}",
            "role": "unknown_panel",
            "role_source": None,
            "piece_name": None,
            "cut_mode": "unknown",
            "cut_instruction": {
                "cut_quantity": 1,
                "orientation": "single",
                "side_assignment": [],
                "cut_on_fold": False,
                "quantity_source": "default",
            },
            "source_entity": source_entity,
            "bbox": record["bbox"],
            "centroid": [clean_number(center[0]), clean_number(center[1])],
            "area": clean_number(abs(signed_area(points))),
            "perimeter": clean_number(polyline_length(points, True)),
            "is_closed": True,
            "geometry_hash": record["geometry_hash"],
            "confidence": confidence,
            "review_status": "needs_review",
            "seam_allowances": [],
            "edges": [],
            "edge_groups": [],
            "_points": points,
            "_edge_segments": record.get("segments"),
        }
        panels.append(panel)

    # 4) 缝份附加
    for panel in panels:
        panel["seam_allowances"] = _build_seam_allowances(panel, seam_groups.get(panel["geometry_hash"], []))
    return panels, diagnostics


def _build_seam_allowances(panel: dict[str, Any], records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records = sorted(records, key=lambda item: (-abs(signed_area(item["points"])), item["geometry_hash"]))
    allowances: list[dict[str, Any]] = []
    for index, record in enumerate(records, 1):
        if record["entity_type"] == "COMPOSITE":
            source_entity = {
                "handle": record["handle"],
                "handles": [e["handle"] for e in record["source_entities"]],
                "layer": record["layer"],
                "entity_type": "COMPOSITE",
                "source_entities": record["source_entities"],
            }
        else:
            source_entity = {
                "handle": record["handle"],
                "layer": record["layer"],
                "entity_type": record["entity_type"],
            }
        allowances.append(
            {
                "curve_id": f"{panel['panel_id']}.seam_allowance_{index:02d}",
                "role": "seam_allowance",
                "source_entity": source_entity,
                "bbox": record["bbox"],
                "length": record["length"],
                "geometry_hash": record["geometry_hash"],
                "sampled_points": record["points"],
                "review_status": "needs_review",
            }
        )
    return allowances


def detect_edges(panel: dict[str, Any]) -> list[dict[str, Any]]:
    """把面板轮廓拆成原子边：重建片用原始分段，普通片按相邻顶点成边。"""
    points = panel["_points"]
    segments = panel.get("_edge_segments")
    if segments:
        pairs = [
            (list(segment["points"]), segment["source_entity"], segment["geometry_hash"])
            for segment in segments
        ]
    else:
        pairs = [
            ([list(points[i]), list(points[(i + 1) % len(points)])],
             panel["source_entity"],
             geometry_hash("edge", [points[i], points[(i + 1) % len(points)]]))
            for i in range(len(points))
        ]
    edges: list[dict[str, Any]] = []
    for index, (raw_samples, source_entity, source_hash) in enumerate(pairs, 1):
        samples = [clean_point(point) for point in raw_samples]
        start, end = samples[0], samples[-1]
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        if abs(dx) > abs(dy) * 2:
            direction = "left_to_right" if dx > 0 else "right_to_left"
        elif abs(dy) > abs(dx) * 2:
            direction = "bottom_to_top" if dy > 0 else "top_to_bottom"
        else:
            direction = "diagonal"
        edges.append(
            {
                "edge_id": f"{panel['panel_id']}.edge_{index:03d}",
                "role": "unknown_edge",
                "start_point": samples[0],
                "end_point": samples[-1],
                "sampled_points": samples,
                "length": clean_number(polyline_length(samples)),
                "direction_hint": direction,
                "source_entity": dict(source_entity),
                "source_entity_handle": source_entity["handle"],
                "geometry_hash": geometry_hash("edge", samples),
                "source_geometry_hash": source_hash,
                "confidence": 0.85 if segments else 1.0,
                "review_status": "needs_review",
            }
        )
    return edges


def build_edge_groups(panel: dict[str, Any]) -> list[dict[str, Any]]:
    """把平滑连续的相邻短边合并成边组（肩缝/侧缝/袖窿等一段轮廓）。"""
    edges = panel.get("edges") or []
    if not edges:
        panel["edge_groups"] = []
        return []
    perimeter = max(float(panel.get("perimeter", 0.0)), 1e-9)
    fragment_limit = perimeter * AUTO_FRAGMENT_RATIO
    allow_auto = len(edges) >= AUTO_MIN_EDGE_COUNT
    chains: list[list[dict[str, Any]]] = [[edges[0]]]
    for edge in edges[1:]:
        previous = chains[-1][-1]
        fragments = (
            float(previous.get("length", 0.0)) <= fragment_limit
            and float(edge.get("length", 0.0)) <= fragment_limit
        )
        smooth = _join_angle(previous, edge) <= AUTO_JOIN_ANGLE_DEGREES
        if allow_auto and fragments and smooth:
            chains[-1].append(edge)
        else:
            chains.append([edge])
    groups = [
        _group_record(panel, f"{panel['panel_id']}.edge_group_{index:03d}", members, "auto" if len(members) > 1 else "single")
        for index, members in enumerate(chains, 1)
    ]
    panel["edge_groups"] = groups
    edge_lookup = {edge["edge_id"]: edge for edge in edges}
    for group in groups:
        for edge_id in group["member_edge_ids"]:
            edge_lookup[edge_id]["group_id"] = group["group_id"]
    return groups


def _vector(points: list[list[float]], at_end: bool) -> tuple[float, float] | None:
    pairs = zip(reversed(points[1:]), reversed(points[:-1])) if at_end else zip(points[1:], points[:-1])
    for current, previous in pairs:
        dx = current[0] - previous[0]
        dy = current[1] - previous[1]
        if math.hypot(dx, dy) > 1e-9:
            return dx, dy
    return None


def _join_angle(left: dict[str, Any], right: dict[str, Any]) -> float:
    left_vector = _vector(left.get("sampled_points") or [left["start_point"], left["end_point"]], True)
    right_vector = _vector(right.get("sampled_points") or [right["start_point"], right["end_point"]], False)
    if not left_vector or not right_vector:
        return 180.0
    left_length = math.hypot(*left_vector)
    right_length = math.hypot(*right_vector)
    cosine = (left_vector[0] * right_vector[0] + left_vector[1] * right_vector[1]) / (left_length * right_length)
    return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))


def _group_record(panel: dict[str, Any], group_id: str, members: list[dict[str, Any]], source: str) -> dict[str, Any]:
    length = sum(float(edge.get("length", 0.0)) for edge in members)
    return {
        "group_id": group_id,
        "panel_id": panel["panel_id"],
        "member_edge_ids": [edge["edge_id"] for edge in members],
        "role": "unknown_edge",
        "start_point": members[0]["start_point"],
        "end_point": members[-1]["end_point"],
        "length": clean_number(length),
        "direction_hint": members[0].get("direction_hint", "unknown"),
        "group_source": source,
        "confidence": 0.75 if len(members) > 1 else 1.0,
        "review_status": "needs_review",
    }


def build_panel_topology(panels: list[dict[str, Any]]) -> None:
    """补齐每个面板的 edges 与 edge_groups。"""
    for panel in panels:
        panel["edges"] = detect_edges(panel)
        build_edge_groups(panel)
