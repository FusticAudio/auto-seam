# -*- coding: utf-8 -*-
import sys, logging
sys.path.insert(0, r'd:\project\0824cloth\0901dxf\auto-annotator')
logging.disable(logging.CRITICAL)
import json
from app.core.semantics import classify_panel_groups

SEAM = r'C:\Users\Lenovo\Downloads\13FG短袖.seam.reviewed.json'
GAR = r'C:\Users\Lenovo\Downloads\13FG短袖.garment.reviewed.json'

g = json.load(open(GAR, encoding='utf-8'))
se = json.load(open(SEAM, encoding='utf-8'))
pmap = {p['panel_id']: p for p in g['panels']}

def kind_of(pid, gid):
    p = pmap[pid]
    cl = classify_panel_groups(p)
    for k, items in cl.items():
        if any(x['group_id'] == gid for x in items):
            return k
    return 'other'

print('=== 全部缝线 ===')
for s in se['stitches']:
    ag = (s['a_groups'] or [''])[0]
    bg = (s['b_groups'] or [''])[0]
    ap = ag.split('.')[0] if ag else (s['a'].split('.')[0] if s.get('a') else '')
    bp = bg.split('.')[0] if bg else (s['b'].split('.')[0] if s.get('b') else '')
    ar = pmap.get(ap, {}).get('role', '?')
    br = pmap.get(bp, {}).get('role', '?')
    ak = kind_of(ap, ag) if ag else '?'
    bk = kind_of(bp, bg) if bg else '?'
    note = ''
    if ag and bg and (('sleeve' in ar) != ('sleeve' in br)):
        if not (('cap' == ak and 'armhole' == bk) or ('armhole' == ak and 'cap' == bk)):
            note = '   <-- 袖↔身 疑点(非袖山↔袖窿)'
    print(f"{s['stitch_id']} {s['relation']:34s} {s['confidence_source']:16s} {ap}[{ar}:{ak}] <-> {bp}[{br}:{bk}]{note}")