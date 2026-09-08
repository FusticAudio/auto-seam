# -*- coding: utf-8 -*-
import sys, glob, logging
from pathlib import Path
sys.path.insert(0, r'd:\project\0824cloth\0901dxf\auto-annotator')
from app.core.service import annotate_dxf_file
from app.core.semantics import classify_panel_groups
logging.disable(logging.CRITICAL)

def kind_of(panel, gid, cl):
    grp = next((x for x in panel['edge_groups'] if x['group_id'] == gid), None)
    if grp is None:
        return '??'
    return next((k for k, items in cl.items() if grp in items), '?')

for pth in sorted(glob.glob(r'd:\project\0824cloth\0901dxf\缝合关系文件\*\*.reviewed.dxf')):
    g = annotate_dxf_file(Path(pth))['garment']
    se = annotate_dxf_file(Path(pth))['seam']
    pmap = {x['panel_id']: x for x in g['panels']}
    caches = {}
    def cl(pid):
        if pid not in caches:
            caches[pid] = classify_panel_groups(pmap[pid])
        return caches[pid]
    for s in se['stitches']:
        if s['confidence_source'] != 'geometry_inferred':
            continue
        ag = s['a_groups'][0]; bg = s['b_groups'][0]
        ap = ag.split('.')[0]; bp = bg.split('.')[0]
        ak = kind_of(pmap[ap], ag, cl(ap)); bk = kind_of(pmap[bp], bg, cl(bp))
        ar = pmap[ap]['role']; br = pmap[bp]['role']
        flag = ''
        slv_body = ((ar in ('sleeve',) and bp != ap) or (br in ('sleeve',)))
        slv_body = (ar == 'sleeve' or br == 'sleeve') and ar != br
        if slv_body:
            flag = '<-- 袖↔主体'
        name = Path(pth).name.split('.')[0][:12]
        print(f"{name:13s} {s['stitch_id']} {ap}[{ar}:{ak}] ↔ {bp}[{br}:{bk}] {flag}")