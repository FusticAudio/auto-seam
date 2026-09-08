# -*- coding: utf-8 -*-
"""几何基础工具：长度、面积、包围盒、质心、点在多边形内、开放曲线闭环重建。"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from typing import Any

EPS = 1e-9


def clean_number(value: float) -> float:
    return round(float(value), 4)


def clean_point(point: list[float]) -> list[float]:
    return [clean_number(point[0]), clean_number(point[1])]


def distance(a: list[float], b: list[float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def bbox(points: list[list[float]]) -> dict[str, float]:
    xs = [float(p[0]) for p in points]
    ys = [float(p[1]) for p in points]
    return {
        "min_x": clean_number(min(xs)),
        "min_y": clean_number(min(ys)),
        "max_x": clean_number(max(xs)),
        "max_y": clean_number(max(ys)),
    }


def centroid(points: list[list[float]]) -> list[float]:
    n = len(points)
    if not n:
        return [0.0, 0.0]
    return [
        clean_number(sum(p[0] for p in points) / n),
        clean_number(sum(p[1] for p in points) / n),
    ]


def polyline_length(points: list[list[float]], closed: bool = False) -> float:
    length = 0.0
    for i in range(len(points) - 1):
        length += distance(points[i], points[i + 1])
    if closed and len(points) > 2 and distance(points[0], points[-1]) > EPS:
        length += distance(points[0], points[-1])
    return length


def signed_area(points: list[list[float]]) -> float:
    area = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return area * 0.5


def point_in_polygon(point: list[float], polygon: list[list[float]]) -> bool:
    x, y = point
    inside = False
    previous = polygon[-1]
    for current in polygon:
        x1, y1 = previous
        x2, y2 = current
        if (y1 > y) != (y2 > y):
            crossing_x = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < crossing_x:
                inside = not inside
        previous = current
    return inside


def bbox_contains(outer: dict[str, float], inner: dict[str, float], tolerance: float) -> bool:
    return (
        outer["min_x"] <= inner["min_x"] + tolerance
        and outer["min_y"] <= inner["min_y"] + tolerance
        and outer["max_x"] >= inner["max_x"] - tolerance
        and outer["max_y"] >= inner["max_y"] - tolerance
    )


def geometry_hash(prefix: str, points: list[list[float]]) -> str:
    import hashlib

    vertices = [tuple(round(float(v), 3) for v in point) for point in points]
    key = json.dumps(vertices, separators=(",", ":"))
    return f"{prefix}_{hashlib.md5(key.encode('utf-8')).hexdigest()[:12]}"


def canonical_polygon_key(points: list[list[float]]) -> str:
    vertices = [tuple(round(float(v), 6) for v in point) for point in points]
    if not vertices:
        return ""
    start = min(range(len(vertices)), key=vertices.__getitem__)
    forward = vertices[start:] + vertices[:start]
    reversed_vertices = list(reversed(vertices))
    reverse_start = min(range(len(reversed_vertices)), key=reversed_vertices.__getitem__)
    reverse = reversed_vertices[reverse_start:] + reversed_vertices[:reverse_start]
    return json.dumps(min(forward, reverse), separators=(",", ":"))


# ---------------------------------------------------------------------------
# 开放曲线端点闭环重建（用于 BOKE 中用多条开放线段画出的零散小片）
# ---------------------------------------------------------------------------

class _UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, value: int) -> int:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, a: int, b: int) -> None:
        a, b = self.find(a), self.find(b)
        if a != b:
            self.parent[b] = a


def reconstruct_cycles(
    records: list[dict[str, Any]],
    tolerance: float = 0.1,
) -> list[dict[str, Any]]:
    """把端点相接的开放曲线连接成闭合环，返回 COMPOSITE 轮廓记录。

    records: 非闭合曲线实体记录（points 至少 2 个点）。
    """
    if tolerance <= 0:
        raise ValueError("join tolerance must be greater than zero")
    if not records:
        return []
    # 去重（正反方向）
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for record in records:
        pts = record["points"]
        if len(pts) < 2:
            continue
        forward = json.dumps([tuple(p) for p in pts], separators=(",", ":"))
        reverse = json.dumps([tuple(p) for p in reversed(pts)], separators=(",", ":"))
        key = min(forward, reverse)
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)

    endpoints = [point for record in unique for point in (record["points"][0], record["points"][-1])]
    groups = _UnionFind(len(endpoints))
    grid: dict[tuple[int, int], list[int]] = defaultdict(list)
    for index, point in enumerate(endpoints):
        cell = (
            math.floor(float(point[0]) / tolerance),
            math.floor(float(point[1]) / tolerance),
        )
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for other in grid[(cell[0] + dx, cell[1] + dy)]:
                    if distance(point, endpoints[other]) <= tolerance:
                        groups.union(index, other)
        grid[cell].append(index)
    node_segments: dict[int, list[int]] = defaultdict(list)
    for segment_index in range(len(unique)):
        node_segments[groups.find(2 * segment_index)].append(segment_index)
        node_segments[groups.find(2 * segment_index + 1)].append(segment_index)

    remaining = set(range(len(unique)))
    contours: list[dict[str, Any]] = []
    while remaining:
        seed = next(iter(remaining))
        component: set[int] = set()
        stack = [seed]
        while stack:
            segment = stack.pop()
            if segment in component:
                continue
            component.add(segment)
            remaining.discard(segment)
            for endpoint in (2 * segment, 2 * segment + 1):
                stack.extend(node_segments[groups.find(endpoint)])
        traced = _trace_cycle(component, unique, groups, node_segments)
        if traced is None:
            continue
        points, segments = traced
        area = abs(signed_area(points))
        if len(points) < 3 or area <= tolerance * tolerance:
            continue
        source_entities = [segment["source_entity"] for segment in segments]
        layer = (
            source_entities[0]["layer"]
            if len({e["layer"] for e in source_entities}) == 1
            else "MULTI"
        )
        contour_hash = geometry_hash("composite", points)
        contours.append(
            {
                "handle": contour_hash,
                "layer": layer,
                "entity_type": "COMPOSITE",
                "points": points,
                "segments": segments,
                "source_entities": source_entities,
                "is_closed": True,
                "bbox": bbox(points),
                "length": clean_number(polyline_length(points, True)),
                "area": clean_number(area),
                "geometry_hash": contour_hash,
            }
        )
    return contours


def _trace_cycle(
    component: set[int],
    records: list[dict[str, Any]],
    groups: _UnionFind,
    node_segments: dict[int, list[int]],
) -> tuple[list[list[float]], list[dict[str, Any]]] | None:
    nodes = {
        groups.find(endpoint)
        for segment in component
        for endpoint in (2 * segment, 2 * segment + 1)
    }
    if not all(len(node_segments[node]) == 2 for node in nodes):
        return None
    first = min(component)
    current_node = groups.find(2 * first)
    start_node = current_node
    used: set[int] = set()
    joined_points: list[list[float]] = []
    oriented_segments: list[dict[str, Any]] = []
    while len(used) < len(component):
        choices = sorted(
            segment
            for segment in node_segments[current_node]
            if segment in component and segment not in used
        )
        if not choices:
            return None
        segment_index = choices[0]
        used.add(segment_index)
        record = records[segment_index]
        start = groups.find(2 * segment_index)
        end = groups.find(2 * segment_index + 1)
        if start == current_node:
            points = [list(point) for point in record["points"]]
            next_node = end
        else:
            points = [list(point) for point in reversed(record["points"])]
            next_node = start
        if joined_points:
            joined_points.extend(points[1:])
        else:
            joined_points.extend(points)
        oriented_segments.append(
            {
                "points": points,
                "source_entity": {
                    "handle": record["handle"],
                    "layer": record["layer"],
                    "entity_type": record["entity_type"],
                },
                "geometry_hash": record["geometry_hash"],
                "length": record["length"],
            }
        )
        current_node = next_node
    if current_node != start_node or len(used) != len(component):
        return None
    if len(joined_points) > 2 and distance(joined_points[0], joined_points[-1]) <= 1e-9:
        joined_points.pop()
    return joined_points, oriented_segments
