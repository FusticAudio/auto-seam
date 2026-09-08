# -*- coding: utf-8 -*-
import sys, glob, logging
from pathlib import Path
sys.path.insert(0, r'd:\project\0824cloth\0901dxf\auto-annotator')
from app.core.service import annotate_dxf_file
logging.disable(logging.CRITICAL)

print(f"{'样本':<16s} {'unknown识别':<18s} {'被缝合引用':<14s} 关键角色保留")
total_unk = 0
bad_ref = 0
samples = 0
for pth in sorted(glob.glob(r'd:\project\0824cloth\0901dxf\缝合关系文件\*\*.reviewed.dxf')):
    g = annotate_dxf_file(Path(pth))['garment']
    se = annotate_dxf_file(Path(pth))['seam']
    unk = [x['panel_id'] for x in g['panels'] if x['role'] == 'unknown_panel']
    ref = {eid.split('.')[0] for s in se['stitches'] for eid in s.get('a_edges', []) + s.get('b_edges', [])}
    bad = unk and (ref & set(unk))
    samples += 1
    total_unk += len(unk)
    if bad:
        bad_ref += 1
    # 关键角色是否存在（校验未误杀真实裁片）
    roles = {x['role'] for x in g['panels']}
    key = []
    for r in ('front_bodice', 'back_bodice', 'sleeve', 'binding_strip', 'placket', 'facing'):
        if r in roles:
            key.append(r)
    name = Path(pth).name.split('.')[0][:14]
    print(f"{name:16s} {str(unk or '无'):<18s} {str(sorted(bad) if isinstance(bad,set) and bad else ('无' if not bad else len(bad))):<14s} {','.join(key)}")
print(f"\n样本数={samples}  识别unknown总数={total_unk}  含被缝合引用的样本数={bad_ref}")