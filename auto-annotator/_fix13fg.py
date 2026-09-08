# -*- coding: utf-8 -*-
"""修复 13FG短袖.seam.reviewed.json：
解除 stitch_008（主体肩缝<->袖片袖底缝 的错误跨部件缝合），
保留正确的 袖山<->袖窿 连接（stitch_005/006）。
"""
import json, shutil, sys

SEAM = r'C:\Users\Lenovo\Downloads\13FG短袖.seam.reviewed.json'

with open(SEAM, encoding='utf-8') as f:
    data = json.load(f)

stitches = data['stitches']

# 定位错误关系：geometry_inferred 且跨 袖/身 且非 袖山<->袖窿
keep = []
removed = []
for s in stitches:
    ag = (s['a_groups'] or [''])[0]
    bg = (s['b_groups'] or [''])[0]
    a_edges = s.get('a') or ''
    set_a = set(s.get('a_edges') or [])
    set_b = set(s.get('b_edges') or [])
    # 识别袖片：panel_001
    is_sleeve_a = a_edges.startswith('panel_001.')
    is_sleeve_b = a_edges.startswith('panel_001.')  # placeholder, refined below
    is_sleeve_a = any(e.startswith('panel_001.') for e in set_a)
    is_sleeve_b = any(e.startswith('panel_001.') for e in set_b)
    cross_sleeve_body = is_sleeve_a != is_sleeve_b  # 一端在袖片
    if s['confidence_source'] == 'geometry_inferred' and cross_sleeve_body:
        removed.append(s)
    else:
        keep.append(s)

if not removed:
    print('未发现需要移除的错误缝合关系。')
    sys.exit(0)

print(f'将移除 {len(removed)} 条错误缝合关系：')
for s in removed:
    print('  -', s['stitch_id'], s['a_groups'], '<->', s['b_groups'], f"({s['confidence_source']})")

# 备份原始文件
bak = SEAM.replace('.seam.reviewed.json', '.seam.reviewed.orig-backup.json')
shutil.copyfile(SEAM, bak)
print('已备份原文件 ->', bak)

# 重新编号并写回
for i, s in enumerate(keep, 1):
    s['stitch_id'] = f'stitch_{i:03d}'
data['stitches'] = keep
with open(SEAM, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f'已写回修正文件：{SEAM}')
print(f'现有缝线数：{len(keep)}（原 {len(stitches)}）')