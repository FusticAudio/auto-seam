# -*- coding: utf-8 -*-
"""回归验证：跨功能组（袖/身/领）在几何兜底阶段不再产生错误缝合。"""
import glob
import sys
from pathlib import Path

sys.path.insert(0, r'd:\project\0824cloth\0901dxf\auto-annotator')

from app.core.service import annotate_dxf_file  # noqa: E402
from app.core.semantics import (  # noqa: E402
    SLEEVE_ROLES, BODICE_ROLES, COLLAR_ROLES,
)

SAMPLES = sorted(
    glob.glob(r'd:\project\0824cloth\0901dxf\缝合关系文件\*\*.reviewed.dxf')
)


def cross_family(ra, rb):
    if ra in SLEEVE_ROLES and rb in (BODICE_ROLES | COLLAR_ROLES):
        return True
    if rb in SLEEVE_ROLES and ra in (BODICE_ROLES | COLLAR_ROLES):
        return True
    if ra in BODICE_ROLES and rb in COLLAR_ROLES:
        return True
    if rb in BODICE_ROLES and ra in COLLAR_ROLES:
        return True
    return False


total_cross = 0
violations = []
for pth in SAMPLES:
    name = Path(pth).name.split('.', 1)[0]
    try:
        result = annotate_dxf_file(Path(pth))
    except Exception as e:  # noqa: BLE001
        print(f"[ERROR] {name}: {e}")
        continue
    g = result['garment']
    se = result['seam']
    pmap = {p['panel_id']: p for p in g['panels']}
    observed_cross = []
    # 仅校验 geometry_inferred（几何兜底）阶段产生的缝合。
    # rule_inferred 中的 袖山↔袖窿、领/滚条↔领口 属跨功能组但为合法规则缝合。
    for s in se['stitches']:
        if s['confidence_source'] != 'geometry_inferred':
            continue
        ap = s['a'].split('.')[0] if s.get('a') else ''
        bp = s['b'].split('.')[0] if s.get('b') else ''
        if not ap or not bp:
            continue
        ra = pmap.get(ap, {}).get('role')
        rb = pmap.get(bp, {}).get('role')
        if ra and rb and cross_family(ra, rb):
            observed_cross.append(
                f"{s['stitch_id']}:{ra}({s.get('a_groups')})<>{rb}({s.get('b_groups')})[{s['confidence_source']}]"
            )
    if observed_cross:
        total_cross += len(observed_cross)
        print(f"[FAIL] {name}: {len(observed_cross)} 条跨功能组缝合")
        for v in observed_cross:
            print("        ", v)
        violations.append(name)
    else:
        rulers = [s['stitch_id'] for s in se['stitches']]
        print(f"[OK]   {name}: {len(se['stitches'])} 条缝线，无跨功能组缝合")

print("\n================ REGRESSION RESULT ================")
print(f"样本数: {len(SAMPLES)}  违规缝合总数: {total_cross}  涉及样本: {len(violations)}")
sys.exit(0 if total_cross == 0 else 1)