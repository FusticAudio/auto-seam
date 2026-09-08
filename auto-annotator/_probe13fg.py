# -*- coding: utf-8 -*-
import sys, logging
sys.path.insert(0, r'd:\project\0824cloth\0901dxf\auto-annotator')
logging.disable(logging.CRITICAL)
from pathlib import Path
from app.core.service import annotate_dxf_file
r = annotate_dxf_file(Path(r'd:\project\0824cloth\0901dxf\缝合关系文件\13 FG短袖.review-package\13FG短袖.reviewed.dxf'))
pmap = {p['panel_id']: p for p in r['garment']['panels']}
for s in r['seam']['stitches']:
    ap = s['a'].split('.')[0]; bp = s['b'].split('.')[0]
    print(f"{s['stitch_id']} {s['relation']:34s} {s['confidence_source']:18s} {ap}({pmap[ap]['role']:14s}) <-> {bp}({pmap[bp]['role']})")