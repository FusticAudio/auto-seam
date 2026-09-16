"""领片刀口标记（collar notch）。

识别衬衫领片的上领/下领，定义 l = 上领"下边"弧线上中点到左顶点的
**线上（沿弧线路径）距离**（非直线距离），在下领上边中点沿边向左右各量 l，
得到两个刀口位置。结果写入下领面板的 ``panel["notches"]``（含刀口、下领上边
中点 ``panel["notch_midpoint"]``），并在上领面板写入 ``panel["notch_reference"]``
（含上领下边中点 midpoint）作追溯。
    距离语义：l = 沿上领下边折线从中点 m_u 到左顶点 c1 的实际路径弧长。
            因 m_u 位于下边弧长 total_u/2 处，故 l = total_u / 2。

几何策略
    上领：存在一条"长且平直"的边组（长度占比与 sag 上限判定），且轮廓上有
    >= 2 个尖角（group 按平滑角切分，尖角天然落在组边界 / 环顶点）。
    下领：无长平直边组，轮廓平滑无尖角，为带形弧边。
    配对：上领"下边"（最长低 sag 边组）长度 与 下领"上边"（朝向该上领的
    连续轮廓弧段，经有序环提取）长度作长度比匹配（>=0.8）。
"""
from __future__ import annotations

import math
from typing import Any

# ---------------------------------------------------------------------------
# 阈值（用 4条纹衬衫 样本校准）
# ---------------------------------------------------------------------------
_LONG_RATIO_MIN = 0.22       # "长且平直"边组长度占周长比下限
_STRAIGHT_SAG_MAX = 0.05     # 平直边组 sag（最大垂距/弦长）上限
_PAIR_LENGTH_RATIO_MIN = 0.8  # 上-下"下边/上边"长度比下限
_CURVE_SAG_THRESHOLD = 0.10  # 有明显弧度边（下领圆头/弧边）的 sag 阈值
_PROJ_SIDE_EPS = 1e-9        # 投影方向退化判定

_NOTCH_CONFIDENCE = 0.7
_MAX_PERIMETER_FALLBACK = 1e-9
# 刀口路径重采样步长（mm）：沿缝线折线等距加密，保证绿线虚线在每个虚线段间
# 都有充分顶点、贴合缝线；也避免过长弦段导致视觉"横跨"。
_PATH_STEP = 0.5


def _pt_dist(a: list[float], b: list[float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _vector_angle(ax: float, ay: float, bx: float, by: float) -> float:
    """两个向量的夹角（0~180 度）。"""
    denom = math.hypot(ax, ay) * math.hypot(bx, by)
    if denom < 1e-9:
        return 0.0
    c = (ax * bx + ay * by) / denom
    c = max(-1.0, min(1.0, c))
    return math.degrees(math.acos(c))


def _group_pts(group: dict[str, Any], edges: list[dict[str, Any]]) -> list[list[float]]:
    """边组成员按顺序拼接成折线；必要时反转单边采样方向保持连续性。"""
    lookup = {e["edge_id"]: e for e in edges}
    pts: list[list[float]] = []
    for eid in group.get("member_edge_ids") or []:
        edge = lookup.get(eid)
        if not edge:
            continue
        sp = [list(p) for p in (edge.get("sampled_points") or [edge["start_point"], edge["end_point"]])]
        if not sp:
            continue
        if pts and len(sp) >= 2 and _pt_dist(pts[-1], sp[0]) > _pt_dist(pts[-1], sp[-1]):
            sp = sp[::-1]
        if pts:
            pts.extend(sp[1:])
        else:
            pts.extend(sp)
    return pts


def _ordered_ring(panel: dict[str, Any]) -> list[list[float]]:
    """面板全部原子边按轮廓顺序拼接成有序环（边按闭合参数序给出）。"""
    pts: list[list[float]] = []
    for edge in panel.get("edges") or []:
        sp = [list(p) for p in (edge.get("sampled_points") or [edge["start_point"], edge["end_point"]])]
        if not sp:
            continue
        if pts and len(sp) >= 2 and _pt_dist(pts[-1], sp[0]) > _pt_dist(pts[-1], sp[-1]):
            sp = sp[::-1]
        if pts:
            pts.extend(sp[1:])
        else:
            pts.extend(sp)
    return pts


def _polyline_len(pts: list[list[float]]) -> float:
    total = 0.0
    for i in range(1, len(pts)):
        total += _pt_dist(pts[i - 1], pts[i])
    return total


def _densify_polyline(pts: list[list[float]], step: float) -> list[list[float]]:
    """沿折线以固定弧长 step 等距重采样（保留两端点，仅插入中间点）。

    插入点落在原线段之上，因此不改变折线形状与总长，只提高顶点密度。
    """
    if not pts or step <= 0 or len(pts) < 2:
        return [list(p) for p in pts]
    out: list[list[float]] = [list(pts[0])]
    carry = 0.0  # 累计到当前线段的"上次输出点之后剩余弧长"
    for i in range(1, len(pts)):
        ax, ay = pts[i - 1]
        bx, by = pts[i]
        seg = math.hypot(bx - ax, by - ay)
        if seg <= 1e-12:
            continue
        pos = step - carry
        while pos <= seg - 1e-9:
            t = pos / seg
            out.append([ax + (bx - ax) * t, ay + (by - ay) * t])
            pos += step
        carry = (pos - seg) % step
        if carry < 1e-9:
            carry = 0.0
    if _pt_dist(out[-1], pts[-1]) > 1e-9:
        out.append(list(pts[-1]))
    else:
        out[-1] = list(pts[-1])
    return out


def _points_up_to_arclen(pts: list[list[float]], off: float) -> list[list[float]]:
    """返回从 pts[0] 沿折线到弧长 off 处的顶点序列（终点为 off 处内插点）。

    不越过 off：终点精确落在弧长 off 处，而非下一个折线顶点，避免路径长度膨胀。
    off<=0 -> [pts[0]]；off 超出总长 -> 全部顶点。
    """
    if off <= 0 or not pts:
        return [list(pts[0])] if pts else []
    total = 0.0
    for i in range(len(pts)):
        total += 0 if i == 0 else _pt_dist(pts[i - 1], pts[i])
    if off >= total:
        return [list(p) for p in pts]
    res: list[list[float]] = [list(pts[0])]
    acc = 0.0
    for i in range(1, len(pts)):
        a = pts[i - 1]
        b = pts[i]
        seg = _pt_dist(a, b)
        if acc + seg >= off:
            t = 1.0 if seg < 1e-12 else (off - acc) / seg
            res.append([
                a[0] + (b[0] - a[0]) * t,
                a[1] + (b[1] - a[1]) * t,
            ])
            break
        res.append([b[0], b[1]])
        acc += seg
    return res


def _point_at_arclen(pts: list[list[float]],
                     offset: float) -> (list[float] | None, float | None):
    """在折线上按弧长 offset 取点；返回 (点, 该点在折线累计弧长位置)。"""
    if offset < 0 or not pts:
        return None, None
    acc = 0.0
    for i in range(1, len(pts)):
        seg = _pt_dist(pts[i - 1], pts[i])
        if acc + seg >= offset:
            t = 1.0 if seg < 1e-12 else (offset - acc) / seg
            return ([pts[i - 1][0] + t * (pts[i][0] - pts[i - 1][0]),
                     pts[i - 1][1] + t * (pts[i][1] - pts[i - 1][1])],
                    offset)
        acc += seg
    return None, offset


def _group_sag(pts: list[list[float]]) -> float:
    """组折线最大垂距相对弦长比（单位长度最大偏离）。直线≈0。"""
    if len(pts) < 3:
        return 0.0
    a, b = pts[0], pts[-1]
    dx, dy = b[0] - a[0], b[1] - a[1]
    chord = math.hypot(dx, dy)
    if chord < 1e-9:
        return 0.0
    maxd = 0.0
    for x, y in pts[1:-1]:
        perp = abs(dy * (x - a[0]) - dx * (y - a[1])) / chord
        if perp > maxd:
            maxd = perp
    return maxd / chord


def _count_corners(pts: list[list[float]]) -> int:
    """计数轮廓上的尖角数（相邻边界线段转角 >= 阈值）。

    用于诊断/校验。上领呈直线边构成的尖角领，下领为圆头弧边带（无尖角）。
    """
    n = len(pts)
    if n < 3:
        return 0
    cnt = 0
    for i in range(n):
        a = pts[(i - 1) % n]
        b = pts[i]
        c = pts[(i + 1) % n]
        ang = _vector_angle(b[0] - a[0], b[1] - a[1], c[0] - b[0], c[1] - b[1])
        if ang >= 55.0:
            cnt += 1
    return cnt


def classify_collar_kind(panel: dict[str, Any]) -> str | None:
    """返回 "upper" / "lower" / None（二义或异常）。

    判别核心是各边组的整体弯曲度（sag）：
      上领  由近乎直线的边组成（尖角/平边），无明显弧度边组；
      下领  存在圆头/弧边边组（如领座两端的圆角，sag 明显偏大）。
    样本标定：panel_007(上) 最大边组 sag≈0.026，panel_009(下) 最大 sag≈0.246，
    以 0.10 阈值可清晰分离。
    """
    edges = panel.get("edges") or []
    max_sag = 0.0
    for g in panel.get("edge_groups") or []:
        sag = _group_sag(_group_pts(g, edges))
        if sag > max_sag:
            max_sag = sag
    if max_sag >= _CURVE_SAG_THRESHOLD:
        return "lower"
    # 无弧度边组：须存在一条长平直边作“下边”才判为上领
    if _seam_group(panel) is not None:
        return "upper"
    return None


def _seam_group(panel: dict[str, Any]) -> dict[str, Any] | None:
    """上领"下边"：最长且平直的边组。"""
    edges = panel.get("edges") or []
    perimeter = max(float(panel.get("perimeter", 0.0) or 0.0), _MAX_PERIMETER_FALLBACK)
    best, best_len = None, -1.0
    for g in panel.get("edge_groups") or []:
        glen = float(g.get("length", 0.0) or 0.0)
        if _group_sag(_group_pts(g, edges)) <= _STRAIGHT_SAG_MAX and glen > best_len:
            best_len = glen
            best = g
    if best is None or best_len < _LONG_RATIO_MIN * perimeter:
        return None
    return best


def _bottom_chain(upper: dict[str, Any], lower: dict[str, Any]) -> list[list[float]] | None:
    """上领"下边"：朝向下领的连续轮廓弧段（沿有序环提取，排除上边与两侧领尖）。

    上领的"上边"（外弧，通常为最长平直边）远离下领，"下边"（与下领上边缝合的
    内弧）朝向下领。用"沿 上领→下领 方向的有符号投影 t"标注每个环顶点：t>=0 的
    顶点位于下领一侧，t<0 的顶点位于上领一侧（含上边与领尖）。下边即为环上所有
    t>=0 的顶点构成的、离下领最近的连续弧段。
    """
    c_u = upper.get("centroid") or [0.0, 0.0]
    c_l = lower.get("centroid") or [0.0, 0.0]
    ux, uy = c_l[0] - c_u[0], c_l[1] - c_u[1]
    norm = math.hypot(ux, uy)
    if norm < _PROJ_SIDE_EPS:
        return None
    ux, uy = ux / norm, uy / norm
    ring = _ordered_ring(upper)
    if len(ring) < 3:
        return None
    # 计算每个环顶点沿 "上领→下领" 方向的有符号投影
    proj = [
        (v[0] - c_u[0]) * ux + (v[1] - c_u[1]) * uy
        for v in ring
    ]
    n = len(ring)
    # 划分出所有 t>=0 的连续区间（环向闭合）
    positive = [proj[i] > 0 for i in range(n)]
    runs: list[list[int]] = []
    cur: list[int] = []
    for i in range(2 * n):
        idx = i % n
        if positive[idx]:
            cur.append(idx)
        else:
            if cur:
                runs.append(cur)
                cur = []
    if cur:
        runs.append(cur)
    if not runs:
        return None
    # 选取 "离下领最近" 的运行：以运行内最大投影值 + 顶点数为判据
    def _run_score(run: list[int]) -> tuple[float, int]:
        return (max(proj[i] for i in run), len(run))
    runs = sorted(runs, key=_run_score, reverse=True)
    best_run = runs[0]
    # 去重（环向闭合可能在首尾重复），并按环序排好
    seen_idxs: list[int] = []
    for i in best_run:
        if i not in seen_idxs:
            seen_idxs.append(i)
    chain = [ring[i] for i in seen_idxs]
    if len(chain) < 2:
        return None
    return chain


def _top_boundary(lower: dict[str, Any], upper: dict[str, Any]) -> list[list[float]] | None:
    """下领"上边"：朝向上领的连续轮廓弧段（由朝向上领的边组按切向排序拼接）。
      1) 只取"节点朝向上领一侧"的边组（中点在上领方向投影 > 0）；
      2) 沿与"上领方向"垂直的切向 t 将各边组定向并排序（沿带形从左到右）；
      3) 顺序拼接成一条开放链，即下领上边。
    """
    edges = lower.get("edges") or []
    if len(edges) == 0:
        return None
    c_l = lower.get("centroid") or [0.0, 0.0]
    c_u = upper.get("centroid") or [0.0, 0.0]
    ux, uy = c_u[0] - c_l[0], c_u[1] - c_l[1]
    norm = math.hypot(ux, uy)
    if norm < _PROJ_SIDE_EPS:
        return None
    ux, uy = ux / norm, uy / norm
    tx, ty = -uy, ux  # 垂直于"上领方向"的切向（沿带形）

    cand: list[tuple[float, str, list[list[float]]]] = []
    for g in lower.get("edge_groups") or []:
        pts = _group_pts(g, edges)
        if len(pts) < 2:
            continue
        # 只取"近直"边组作缝合段：圆头/圆角角组（sag 明显偏大）不参与上边链，
        # 否则会把下领两端的圆角计入、使上边链过长而与上领下边长度失真。
        if _group_sag(pts) > _CURVE_SAG_THRESHOLD:
            continue
        # 组中点沿上领方向投影：>0 表示朝向上领一侧
        gm = [sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)]
        if ((gm[0] - c_l[0]) * ux + (gm[1] - c_l[1]) * uy) <= 0:
            continue
        # 沿切向 t 定向（使组内投影随 t 递增，即为带形行进方向）
        t0 = (pts[0][0] - c_l[0]) * tx + (pts[0][1] - c_l[1]) * ty
        t1 = (pts[-1][0] - c_l[0]) * tx + (pts[-1][1] - c_l[1]) * ty
        if t1 < t0:
            pts = pts[::-1]
        tang_mid = ((t0 + t1) / 2.0) if len(pts) >= 2 else t0
        cand.append((tang_mid, g["group_id"], pts))
    if not cand:
        return None
    cand.sort(key=lambda item: item[0])
    chain: list[list[float]] = []
    for _, _, pts in cand:
        if chain:
            chain.extend(pts[1:])
        else:
            chain.extend(pts)
    if len(chain) < 2:
        return None
    return chain


def _group_of_point(panel: dict[str, Any], point: list[float],
                    tol: float = 1.0) -> str | None:
    """刀口点归属的边组（与某成员边折线距离 <= tol 时返回其 group_id）。"""
    edges = panel.get("edges") or []
    best_gid, best_d = None, tol
    for g in panel.get("edge_groups") or []:
        for pt in _group_pts(g, edges):
            d = _pt_dist(pt, point)
            if d < best_d:
                best_d = d
                best_gid = g["group_id"]
    return best_gid


def mark_collar_notches(panels: list[dict[str, Any]], diagnostics: dict[str, Any]) -> None:
    """入口：为衬衫领片生成刀口标记。对 panels 原地写入 notches / notch_reference。"""
    from .semantics import COLLAR_ROLES  # 延迟导入避免循环依赖

    counted = 0
    for p in panels:
        if p.get("role") in COLLAR_ROLES and p.get("is_closed", False):
            counted += 1
    if not counted:
        return

    collars = [p for p in panels if p.get("role") in COLLAR_ROLES]
    uppers: list[dict[str, Any]] = []
    lowers: list[dict[str, Any]] = []
    for p in collars:
        kind = classify_collar_kind(p)
        p["collar_kind"] = kind
        if kind == "upper":
            uppers.append(p)
        elif kind == "lower":
            lowers.append(p)

    rejected: list[str] = []
    notch_total = 0
    for upper in uppers:
        # 与下领配对：候选对的"上领下边"与"下领上边"应长度相近且几何相邻
        # （同一组领的上/下领在版式中通常彼此靠近）。评分 = 长度比 / (1+链中点间距)，
        # 以长度比为主、中点间距为惩罚，避免错配到远侧但长度巧合相近的下领。
        best_lower, best_bottom, best_chain, best_score = None, None, None, 0.0
        for lower in lowers:
            chain = _top_boundary(lower, upper)
            if not chain:
                continue
            total_l = _polyline_len(chain)
            if total_l <= 0:
                continue
            bottom = _bottom_chain(upper, lower)
            if not bottom or len(bottom) < 2:
                continue
            total_u = _polyline_len(bottom)
            if total_u <= 0:
                continue
            ratio = min(total_u, total_l) / max(total_u, total_l)
            if ratio < _PAIR_LENGTH_RATIO_MIN:
                continue
            mu_mid, _ = _point_at_arclen(bottom, total_u / 2)
            ml_mid, _ = _point_at_arclen(chain, total_l / 2)
            if mu_mid is None or ml_mid is None:
                continue
            dist = _pt_dist(mu_mid, ml_mid)
            score = ratio / (1.0 + dist)
            if score > best_score:
                best_lower, best_bottom, best_chain, best_score = lower, bottom, chain, score
        if best_lower is None or best_bottom is None or best_chain is None:
            rejected.append(f"{upper['panel_id']}:未找到匹配下领")
            continue

        seam_pts = best_bottom
        best_chain_pts = best_chain
        total_u = _polyline_len(seam_pts)
        total_l = _polyline_len(best_chain_pts)

        # 上领下边中点（定位基准，应为下边而非上边）
        m_u = _point_at_arclen(seam_pts, total_u / 2)[0]
        if m_u is None:
            rejected.append(f"{upper['panel_id']}:下边中点失败")
            continue
        # l = 沿下边弧线从中点 m_u 到顶点（左顶点）的"线上"路径距离（非直线距离）。
        # 因 m_u 位于下边弧长 total_u/2 处，到任一端顶点的沿路径距离均为 total_u/2。
        l_len = 0.5 * total_u
        if l_len <= 1e-6:
            rejected.append(f"{upper['panel_id']}:长度异常")
            continue

        if total_l <= 0:
            rejected.append(f"{upper['panel_id']}:下领上边长异常")
            continue
        mid_pos = total_l / 2
        m_l, _ = _point_at_arclen(best_chain_pts, mid_pos)
        if m_l is None:
            rejected.append(f"{upper['panel_id']}:下领上边中点失败")
            continue
        # 刀口沿下领**完整有序环**（而非被切断的上边链）从中点 M_l 向左右各量
        # 弧长 l（=上领下边半长，≈225mm）。上边半弧通常不足 2l（上下领缝边存在
        # 正常公差），故允许刀口越过上边与圆头的交界、落在扩展后的缝合弧段内，
        # 而不钳位到上边端点——确保到中点的弧线距离严格等于 l。
        ring = _ordered_ring(best_lower)
        ring_len = _polyline_len(ring)
        if ring_len <= 0 or not ring:
            rejected.append(f"{upper['panel_id']}:下领轮廓异常")
            continue
        best_i = min(range(len(ring)), key=lambda i: _pt_dist(ring[i], m_l))
        # 以最接近 M_l 的环顶点为起点重排成闭合折线（首尾同点）
        reord = ring[best_i:] + ring[: best_i + 1]
        n1, _ = _point_at_arclen(reord, l_len)              # 朝一侧走 l
        n2, _ = _point_at_arclen(reord, ring_len - l_len)   # 朝另一侧走 l
        if n1 is None or n2 is None:
            rejected.append(f"{upper['panel_id']}:刀口定位失败")
            continue
        # 按 x 坐标准一 left/right 语义（x 较小者为 left）
        n_left, n_right = (n1, n2) if n1[0] <= n2[0] else (n2, n1)

        # 为每条刀口预生成"沿下领轮廓"的路径顶点（首=下领上边中点 m_l，尾=刀口点）。
        # 供前端绿线折线使用：顶点均取自有序环 reord，故天然贴合缝线。
        def _notch_path(off_arc: float, target: list[float]) -> list[list[float]]:
            # 从中点 m_l 到弧长 off_arc 处：取较短一侧路径方向，终点精确落在 off_arc，
            # 不再因取下一个折线顶点而越过目标、导致路径长度膨胀。
            fwd = off_arc
            rev = ring_len - off_arc
            if fwd <= rev + 1e-9:
                seq = _points_up_to_arclen(reord, fwd)   # 沿环正向取 fwd
            else:
                rev_walk = [reord[0]] + list(reversed(reord[1:]))  # 反向环，从 m_l 逆向走
                seq = _points_up_to_arclen(rev_walk, rev)
            if not seq:
                seq = [list(target)]
            # 沿缝线折线等距加密，提高顶点密度，保证绿线贴合缝线
            seq = _densify_polyline(seq, _PATH_STEP)
            seq[0] = list(m_l)
            seq[-1] = list(target)
            return seq

        path_n1 = _notch_path(l_len, n1)
        path_n2 = _notch_path(ring_len - l_len, n2)

        notches = []
        for idx, (pt, side) in enumerate(((n_left, "left"), (n_right, "right")), 1):
            # 中点到刀口的线上（沿下领轮廓弧线）距离 = l，不再受上边长度钳位
            midline_len = l_len
            path = path_n1 if _pt_dist(pt, n1) < 0.05 else path_n2
            notches.append({
                "notch_id": f"{best_lower['panel_id']}.notch_{idx:03d}",
                "panel_id": best_lower["panel_id"],
                "notch_type": "collar_point",
                "pair_reference": upper["panel_id"],
                "point": [round(pt[0], 3), round(pt[1], 3)],
                "path_points": [[round(c, 3) for c in v] for v in path],
                "edge_group_id": _group_of_point(best_lower, pt),
                "midpoint": [round(m_l[0], 3), round(m_l[1], 3)],
                "distance_from_mid": round(midline_len, 3),
                "side": side,
                "reference_length": round(l_len, 3),
                "source": "auto_collar_notch",
                "confidence": _NOTCH_CONFIDENCE,
                "status": "proposed",
            })
        best_lower["notches"] = notches
        best_lower["notch_midpoint"] = [round(m_l[0], 3), round(m_l[1], 3)]
        upper["notch_reference"] = {
            "reference_edge": "下边(与下领上边缝合的内弧)",
            "midpoint": [round(m_u[0], 3), round(m_u[1], 3)],
            "length_l": round(l_len, 3),
            "lower_panel_id": best_lower["panel_id"],
            "lower_midpoint": [round(m_l[0], 3), round(m_l[1], 3)],
        }
        notch_total += len(notches)

    diagnostics.setdefault("collar_notches", {})
    diagnostics["collar_notches"]["upper_count"] = len(uppers)
    diagnostics["collar_notches"]["lower_count"] = len(lowers)
    diagnostics["collar_notches"]["notch_count"] = notch_total
    diagnostics["collar_notches"]["rejected"] = rejected